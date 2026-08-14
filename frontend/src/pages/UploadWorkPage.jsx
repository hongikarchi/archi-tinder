/**
 * UploadWorkPage — /upload
 *
 * Portfolio work upload flow:
 *   1. Select images → convert to WebP via canvas (with EXIF orientation fix)
 *   2. Fill metadata form (title, program, location, year)
 *   3. Confirm copyright
 *   4. Presign → upload to R2 → finalize with backend
 *
 * FRONT-UX-13: image editing (crop + rotate), cover image, per-file validation.
 */

import { useCallback, useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactCrop from 'react-image-crop'
import 'react-image-crop/dist/ReactCrop.css'
import { presignFiles, uploadToR2, finalizeWork } from '../api/works.js'
import { useTranslation } from '../i18n/index.js'
import s from './UploadWorkPage.module.css'

// Matches backend MAX_WORK_IMAGES — presign/finalize reject >10 images with a 400.
const MAX_WORK_IMAGES = 10

// Individual file size limit: 10 MB (matches backend presign limit)
const MAX_FILE_BYTES = 10 * 1024 * 1024

// convertToWebP() always emits image/webp — this single constant is sent as
// content_type in the presign request AND set as the Content-Type header on
// the R2 PUT. Both MUST match exactly (R2 signs Content-Type into the URL and
// rejects a mismatched PUT), so it's declared once here rather than
// hardcoded in two places.
const UPLOAD_CONTENT_TYPE = 'image/webp'

// Backend PROGRAM_CHOICES keys (value sent to API) — display labels are
// resolved via t(`uploadWork.programs.${value}`), see locales.js. Ordered to
// match canonical_v2_buildings vocabulary; 'Other' is omitted — no backend
// key exists for it.
const PROGRAM_VALUES = [
  'residential',
  'office',
  'cultural',
  'educational',
  'religious',
  'sports',
  'hospitality',
  'healthcare',
  'public',
  'mixed_use',
  'landscape',
  'infrastructure',
  'commercial',
  'industrial',
]

/* ── EXIF orientation reader ────────────────────────────────────────────── */

/**
 * Reads EXIF orientation from a JPEG blob using DataView.
 * Returns orientation 1-8, or 1 (no rotation) if not found / not JPEG.
 */
async function readExifOrientation(blob) {
  try {
    // Only attempt EXIF on JPEG (starts with 0xFFD8)
    const header = await blob.slice(0, 2).arrayBuffer()
    const dv = new DataView(header)
    if (dv.getUint16(0, false) !== 0xFFD8) return 1

    // Read up to 64 KB to find EXIF APP1 marker
    const buf = await blob.slice(0, 65536).arrayBuffer()
    const view = new DataView(buf)
    let offset = 2
    while (offset < view.byteLength - 4) {
      const marker = view.getUint16(offset, false)
      const segLen = view.getUint16(offset + 2, false)
      if (marker === 0xFFE1) {
        // APP1 — check for "Exif\0\0" header
        if (view.getUint32(offset + 4, false) === 0x45786966 &&
            view.getUint16(offset + 8, false) === 0x0000) {
          // TIFF header starts at offset + 10
          const tiffStart = offset + 10
          const littleEndian = view.getUint16(tiffStart, false) === 0x4949
          const ifdOffset = view.getUint32(tiffStart + 4, littleEndian)
          const ifdStart = tiffStart + ifdOffset
          const numEntries = view.getUint16(ifdStart, littleEndian)
          for (let i = 0; i < numEntries; i++) {
            const tag = view.getUint16(ifdStart + 2 + i * 12, littleEndian)
            if (tag === 0x0112) {
              return view.getUint16(ifdStart + 2 + i * 12 + 8, littleEndian)
            }
          }
        }
        break
      }
      offset += 2 + segLen
    }
  } catch {
    // Ignore parse errors — fall back to no rotation
  }
  return 1
}

/* ── WebP converter ─────────────────────────────────────────────────────── */

/**
 * Converts a file to WebP blob, applying EXIF orientation correction.
 * Returns the WebP blob.
 */
async function convertToWebP(file, t) {
  const orientation = await readExifOrientation(file)

  const img = new Image()
  const srcUrl = URL.createObjectURL(file)
  img.src = srcUrl
  try {
    await new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = () => reject(new Error(t('uploadWork.error.imageLoadFailed')))
    })

    const MAX = 2400
    let w = img.naturalWidth
    let h = img.naturalHeight
    if (w > MAX || h > MAX) {
      const ratio = Math.min(MAX / w, MAX / h)
      w = Math.round(w * ratio)
      h = Math.round(h * ratio)
    }

    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')

    // Apply EXIF orientation correction
    // orientations 5-8 require width/height swap
    const swapDims = orientation >= 5 && orientation <= 8
    canvas.width = swapDims ? h : w
    canvas.height = swapDims ? w : h

    switch (orientation) {
      case 2: ctx.transform(-1, 0, 0, 1, w, 0); break
      case 3: ctx.transform(-1, 0, 0, -1, w, h); break
      case 4: ctx.transform(1, 0, 0, -1, 0, h); break
      case 5: ctx.transform(0, 1, 1, 0, 0, 0); break
      case 6: ctx.transform(0, 1, -1, 0, h, 0); break
      case 7: ctx.transform(0, -1, -1, 0, h, w); break
      case 8: ctx.transform(0, -1, 1, 0, 0, w); break
      default: break // orientation 1 — no transform
    }

    ctx.drawImage(img, 0, 0, w, h)

    return new Promise(resolve => canvas.toBlob(resolve, 'image/webp', 0.85))
  } finally {
    URL.revokeObjectURL(srcUrl)
  }
}

/* ── Edit apply ─────────────────────────────────────────────────────────── */

/**
 * Applies crop + rotation to originalBlob.
 * Returns { blob, previewUrl } for the edited image.
 */
async function applyEditToBlob(originalBlob, crop, rotation) {
  const MAX_OUT = 4096
  const srcUrl = URL.createObjectURL(originalBlob)
  const img = new Image()
  img.src = srcUrl
  try {
    await new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = reject
    })

    const srcW = img.naturalWidth
    const srcH = img.naturalHeight

    // Determine effective source dimensions after downscaling
    let drawW = srcW
    let drawH = srcH
    if (drawW > MAX_OUT || drawH > MAX_OUT) {
      const r = Math.min(MAX_OUT / drawW, MAX_OUT / drawH)
      drawW = Math.round(drawW * r)
      drawH = Math.round(drawH * r)
    }

    // Scale factor from canvas pixel space back to original image pixels
    const scaleX = srcW / drawW
    const scaleY = srcH / drawH

    // Compute crop in original image pixels
    let cropX = 0, cropY = 0, cropW = drawW, cropH = drawH
    if (crop && crop.width > 0 && crop.height > 0) {
      // crop coordinates are in display (drawW/drawH) space — convert to original
      cropX = Math.round(crop.x * scaleX)
      cropY = Math.round(crop.y * scaleY)
      cropW = Math.round(crop.width * scaleX)
      cropH = Math.round(crop.height * scaleY)
    }

    // Build offscreen canvas: draw source then crop
    // Step 1: draw downscaled source
    const srcCanvas = document.createElement('canvas')
    srcCanvas.width = drawW
    srcCanvas.height = drawH
    const srcCtx = srcCanvas.getContext('2d')
    srcCtx.drawImage(img, 0, 0, drawW, drawH)

    // Step 2: extract crop region
    const cropCanvasW = Math.round(cropW / scaleX)
    const cropCanvasH = Math.round(cropH / scaleY)
    const cropedCanvas = document.createElement('canvas')
    cropedCanvas.width = cropCanvasW
    cropedCanvas.height = cropCanvasH
    const cropCtx = cropedCanvas.getContext('2d')
    cropCtx.drawImage(
      srcCanvas,
      Math.round(cropX / scaleX), Math.round(cropY / scaleY),
      cropCanvasW, cropCanvasH,
      0, 0, cropCanvasW, cropCanvasH
    )

    // Step 3: apply rotation
    const rad = (rotation * Math.PI) / 180
    const swapDimsOut = rotation === 90 || rotation === 270
    const outW = swapDimsOut ? cropCanvasH : cropCanvasW
    const outH = swapDimsOut ? cropCanvasW : cropCanvasH

    const outCanvas = document.createElement('canvas')
    outCanvas.width = outW
    outCanvas.height = outH
    const outCtx = outCanvas.getContext('2d')
    outCtx.translate(outW / 2, outH / 2)
    outCtx.rotate(rad)
    outCtx.drawImage(cropedCanvas, -cropCanvasW / 2, -cropCanvasH / 2)

    return new Promise((resolve) => {
      outCanvas.toBlob((blob) => {
        if (blob) {
          resolve({ blob, previewUrl: URL.createObjectURL(blob) })
        } else {
          // Fallback to JPEG if WebP fails
          outCanvas.toBlob((jpegBlob) => {
            resolve({ blob: jpegBlob, previewUrl: URL.createObjectURL(jpegBlob) })
          }, 'image/jpeg', 0.85)
        }
      }, 'image/webp', 0.85)
    })
  } finally {
    URL.revokeObjectURL(srcUrl)
  }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export default function UploadWorkPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const { t } = useTranslation()

  // FRONT-UX-13: enriched file item shape
  // { id, file, originalBlob, currentBlob, preview }
  const [files, setFiles] = useState([])
  const [coverImageId, setCoverImageId] = useState(null)

  const [formData, setFormData] = useState({
    title: '',
    program: '',
    location_city: '',
    location_country: '',
    project_year: '',
  })
  const [copyrightChecked, setCopyrightChecked] = useState(false)
  const [uploadState, setUploadState] = useState('idle')
  const [progress, setProgress] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')

  // Edit modal state
  const [editTarget, setEditTarget] = useState(null) // { id, previewUrl }
  const [crop, setCrop] = useState(undefined)
  const [rotation, setRotation] = useState(0)

  /* ── File selection / drop ────────────────────────────────────────────── */

  async function processFile(file) {
    if (!file.type.startsWith('image/')) return true

    // 20 MB limit per file
    if (file.size > MAX_FILE_BYTES) {
      setErrorMsg(t('uploadWork.error.fileTooLarge', { name: file.name }))
      return false
    }

    setUploadState('converting')
    try {
      const blob = await convertToWebP(file, t)
      const preview = URL.createObjectURL(blob)
      const id = crypto.randomUUID()
      setFiles(prev => {
        const next = [...prev, { id, file, originalBlob: blob, currentBlob: blob, preview }]
        // Auto-set cover to first image added
        if (prev.length === 0) {
          setCoverImageId(id)
        }
        return next
      })
    } catch (err) {
      setErrorMsg(t('uploadWork.error.conversionFailed', { detail: err.message }))
      setUploadState('error')
      return false
    }
    setUploadState('idle')
    return true
  }

  // Enforce MAX_WORK_IMAGES — dedup by name+size, 20MB filter, partial-add if overflow
  async function addFiles(selected) {
    setErrorMsg('')
    const imageFiles = selected.filter(f => f.type.startsWith('image/'))

    // Dedup by name+size against already-added files
    const existingKeys = new Set(files.map(fi => fi.file.name + '_' + fi.file.size))
    const uniqueFiles = imageFiles.filter(f => {
      const k = f.name + '_' + f.size
      if (existingKeys.has(k)) return false
      existingKeys.add(k)
      return true
    })

    // Filter 20MB oversized files — report error but continue with valid ones
    const oversized = uniqueFiles.filter(f => f.size > MAX_FILE_BYTES)
    const validFiles = uniqueFiles.filter(f => f.size <= MAX_FILE_BYTES)

    if (oversized.length > 0) {
      setErrorMsg(t('uploadWork.error.fileTooLarge', { name: oversized.map(f => f.name).join(', ') }))
    }

    const room = MAX_WORK_IMAGES - files.length
    const toAdd = room > 0 ? validFiles.slice(0, room) : []
    const rejectedCount = validFiles.length - toAdd.length

    let conversionFailed = false
    for (const f of toAdd) {
      const ok = await processFile(f)
      if (!ok) { conversionFailed = true; break }
    }

    if (rejectedCount > 0 && !conversionFailed && oversized.length === 0) {
      setErrorMsg(t('uploadWork.error.maxImages', { max: MAX_WORK_IMAGES }))
    } else if (rejectedCount > 0 && !conversionFailed && oversized.length > 0) {
      // already reported oversized; also mention max limit
      setErrorMsg(
        t('uploadWork.error.fileTooLarge', { name: oversized.map(f => f.name).join(', ') }) +
        ' ' + t('uploadWork.error.maxImages', { max: MAX_WORK_IMAGES })
      )
    }
  }

  async function handleFileInput(e) {
    const selected = Array.from(e.target.files || [])
    e.target.value = ''
    await addFiles(selected)
  }

  async function handleDrop(e) {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer.files || [])
    await addFiles(dropped)
  }

  function handleDragOver(e) {
    e.preventDefault()
  }

  function removeFile(id) {
    setFiles(prev => {
      const idx = prev.findIndex(fi => fi.id === id)
      if (idx === -1) return prev
      URL.revokeObjectURL(prev[idx].preview)
      const next = prev.filter(fi => fi.id !== id)
      // If the removed file was the cover, auto-pick next first image
      if (coverImageId === id) {
        setCoverImageId(next.length > 0 ? next[0].id : null)
      }
      return next
    })
  }

  /* ── Edit modal ──────────────────────────────────────────────────────── */

  function openEdit(fileItem) {
    const previewUrl = URL.createObjectURL(fileItem.originalBlob)
    setEditTarget({ id: fileItem.id, previewUrl })
    setCrop(undefined)
    setRotation(0)
  }

  function closeEdit() {
    if (editTarget?.previewUrl) {
      URL.revokeObjectURL(editTarget.previewUrl)
    }
    setEditTarget(null)
    setCrop(undefined)
    setRotation(0)
  }

  async function applyEdit() {
    if (!editTarget) return
    const fileItem = files.find(fi => fi.id === editTarget.id)
    if (!fileItem) { closeEdit(); return }

    setUploadState('converting')
    try {
      const { blob, previewUrl } = await applyEditToBlob(fileItem.originalBlob, crop, rotation)
      setFiles(prev => prev.map(fi => {
        if (fi.id !== editTarget.id) return fi
        URL.revokeObjectURL(fi.preview)
        return { ...fi, currentBlob: blob, preview: previewUrl }
      }))
      setUploadState('idle')
    } catch {
      setUploadState('idle')
    }
    // Close modal — revoke the edit preview url (was from originalBlob)
    URL.revokeObjectURL(editTarget.previewUrl)
    setEditTarget(null)
    setCrop(undefined)
    setRotation(0)
  }

  /* ── Form field change ───────────────────────────────────────────────── */

  function handleFieldChange(e) {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  /* ── Submit ──────────────────────────────────────────────────────────── */

  async function handleSubmit(e) {
    e.preventDefault()
    setErrorMsg('')

    if (files.length === 0) {
      setErrorMsg(t('uploadWork.error.selectImage'))
      return
    }
    if (!formData.title.trim()) {
      setErrorMsg(t('uploadWork.error.titleRequired'))
      return
    }
    if (!formData.program) {
      setErrorMsg(t('uploadWork.error.programRequired'))
      return
    }
    if (!copyrightChecked) {
      setErrorMsg(t('uploadWork.error.copyrightRequired'))
      return
    }

    // Reorder: cover image first, then rest in original order
    const coverFirst = coverImageId
      ? [
          ...files.filter(fi => fi.id === coverImageId),
          ...files.filter(fi => fi.id !== coverImageId),
        ]
      : files

    setUploadState('uploading')
    setProgress(0)

    try {
      // Step 1: presign (use currentBlob — reflects any edits)
      const presignResults = await presignFiles(
        coverFirst.map(fi => ({
          filename: fi.file.name,
          content_type: UPLOAD_CONTENT_TYPE,
          file_size: fi.currentBlob.size,
        }))
      )

      // Step 2: sequential R2 upload with per-file progress
      for (let i = 0; i < coverFirst.length; i++) {
        await uploadToR2(
          presignResults[i],
          coverFirst[i].currentBlob,
          UPLOAD_CONTENT_TYPE,
          (p) => setProgress(Math.round((i * 100 + p) / coverFirst.length))
        )
      }

      // Step 3: finalize
      const payload = {
        title: formData.title.trim(),
        program: formData.program,
        location_city: formData.location_city.trim() || undefined,
        location_country: formData.location_country.trim() || undefined,
        project_year: formData.project_year ? parseInt(formData.project_year, 10) : undefined,
        r2_keys: presignResults.map(r => r.key),
        is_copyright_confirmed: true,
      }
      await finalizeWork(payload)

      setUploadState('processing')
    } catch (err) {
      setUploadState('error')
      setErrorMsg(err.message || t('uploadWork.error.uploadFailed'))
    }
  }

  /* ── Submit button label per state ──────────────────────────────────── */

  function submitLabel() {
    switch (uploadState) {
      case 'converting': return t('uploadWork.submit.converting')
      case 'uploading':  return t('uploadWork.submit.uploading', { progress })
      case 'processing': return t('uploadWork.submit.processing')
      default:           return t('uploadWork.submit.default')
    }
  }

  const isBusy = uploadState === 'converting' || uploadState === 'uploading' || uploadState === 'processing'

  /* ── Success modal dismiss ───────────────────────────────────────────── */
  // The underlying form is hidden while uploadState === 'processing', so all
  // dismiss paths (confirm click, backdrop click, Escape) perform the same
  // navigation — there is nothing on this page to "return" to.
  const goToCreatedWorks = useCallback(() => {
    navigate('/user/me?tab=created')
  }, [navigate])

  // Escape key closes the success modal (matches PhotoLightbox.jsx precedent).
  useEffect(() => {
    if (uploadState !== 'processing') return
    function onKey(e) {
      if (e.key === 'Escape') goToCreatedWorks()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [uploadState, goToCreatedWorks])

  /* ── Render ──────────────────────────────────────────────────────────── */

  return (
    <div className={s.page}>
      {/* Header */}
      <div className={s.header}>
        <button
          type="button"
          className={s.backBtn}
          onClick={() => navigate(-1)}
          aria-label={t('uploadWork.header.backAria')}
        >
          ←
        </button>
        <h1 className={s.headerTitle}>{t('uploadWork.header.title')}</h1>
        {/* spacer to balance the back button */}
        <div style={{ width: 44 }} />
      </div>

      {/* ── Success modal overlay ──────────────────────────────────────── */}
      {uploadState === 'processing' && (
        <div
          onClick={(e) => {
            if (e.target === e.currentTarget) goToCreatedWorks()
          }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(0,0,0,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 20,
              padding: 24,
              maxWidth: 480,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--color-text)' }}>
              {t('uploadWork.success.title')}
            </p>
            <p style={{ margin: 0, fontSize: 14, color: 'var(--color-text)' }}>
              {t('uploadWork.success.body')}
            </p>
            <button
              type="button"
              onClick={goToCreatedWorks}
              style={{
                marginTop: 8,
                padding: '12px 16px',
                borderRadius: 12,
                border: 0,
                background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
                color: '#fff',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                minHeight: 44,
                alignSelf: 'stretch',
              }}
            >
              {t('uploadWork.success.confirm')}
            </button>
          </div>
        </div>
      )}

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px 48px' }}>
        {uploadState !== 'processing' && (
          <form onSubmit={handleSubmit} noValidate>
            {/* ── Drop zone ── */}
            {files.length < MAX_WORK_IMAGES && (
              <div
                className={s.dropzone}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click()
                }}
                aria-label={t('uploadWork.dropzone.aria')}
              >
                {files.length === 0
                  ? (
                    <>
                      <div style={{ fontSize: 32, marginBottom: 8 }}>+</div>
                      <div>{t('uploadWork.dropzone.prompt')}</div>
                      <div style={{ fontSize: 12, marginTop: 4, color: 'var(--color-text-dim)' }}>
                        {t('uploadWork.dropzone.hint')}
                      </div>
                    </>
                  )
                  : (
                    <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                      {t('uploadWork.dropzone.addMore')}
                    </div>
                  )
                }
              </div>
            )}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={handleFileInput}
            />

            {/* Preview thumbnails */}
            {files.length > 0 && (
              <div className={s.previewGrid}>
                {files.map((fi, i) => (
                  <div key={fi.id} className={s.previewThumb}>
                    <img src={fi.preview} alt={t('uploadWork.preview.alt', { n: i + 1 })} />

                    {/* COVER badge — top left */}
                    {coverImageId === fi.id && (
                      <span className={s.coverBadge}>
                        {t('uploadWork.preview.coverBadge')}
                      </span>
                    )}

                    {/* Delete — top right */}
                    <button
                      type="button"
                      className={s.removeThumb}
                      onClick={() => removeFile(fi.id)}
                      aria-label={t('uploadWork.preview.removeAria', { n: i + 1 })}
                    >
                      ×
                    </button>

                    {/* Edit — bottom left */}
                    <button
                      type="button"
                      className={s.editBtn}
                      onClick={() => openEdit(fi)}
                      aria-label={t('uploadWork.preview.editAria', { n: i + 1 })}
                    >
                      ✏
                    </button>

                    {/* Cover toggle — bottom right */}
                    <button
                      type="button"
                      className={s.coverBtn}
                      onClick={() => setCoverImageId(fi.id)}
                      aria-label={t('uploadWork.preview.coverAria', { n: i + 1 })}
                    >
                      {coverImageId === fi.id ? '★' : '☆'}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* ── Upload progress bar ────────────────────────────────────── */}
            {uploadState === 'uploading' && (
              <div className={s.progressBarWrap} style={{ marginTop: 16 }}>
                <div className={s.progressBar} style={{ width: `${progress}%` }} />
              </div>
            )}

            {/* ── Form fields ───────────────────────────────────────────── */}
            <div className={s.form} style={{ marginTop: 24 }}>
              {/* Title */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="title">{t('uploadWork.form.titleLabel')}</label>
                <input
                  id="title"
                  name="title"
                  type="text"
                  className={s.input}
                  value={formData.title}
                  onChange={handleFieldChange}
                  placeholder={t('uploadWork.form.titlePlaceholder')}
                  disabled={isBusy}
                />
              </div>

              {/* Program */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="program">{t('uploadWork.form.programLabel')}</label>
                <select
                  id="program"
                  name="program"
                  className={s.select}
                  value={formData.program}
                  onChange={handleFieldChange}
                  disabled={isBusy}
                >
                  <option value="">{t('uploadWork.form.programPlaceholder')}</option>
                  {PROGRAM_VALUES.map(value => (
                    <option key={value} value={value}>{t(`uploadWork.programs.${value}`)}</option>
                  ))}
                </select>
              </div>

              {/* Location city */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="location_city">{t('uploadWork.form.cityLabel')}</label>
                <input
                  id="location_city"
                  name="location_city"
                  type="text"
                  className={s.input}
                  value={formData.location_city}
                  onChange={handleFieldChange}
                  placeholder={t('uploadWork.form.cityPlaceholder')}
                  disabled={isBusy}
                />
              </div>

              {/* Location country */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="location_country">{t('uploadWork.form.countryLabel')}</label>
                <input
                  id="location_country"
                  name="location_country"
                  type="text"
                  className={s.input}
                  value={formData.location_country}
                  onChange={handleFieldChange}
                  placeholder={t('uploadWork.form.countryPlaceholder')}
                  disabled={isBusy}
                />
              </div>

              {/* Project year */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="project_year">{t('uploadWork.form.yearLabel')}</label>
                <input
                  id="project_year"
                  name="project_year"
                  type="number"
                  className={s.input}
                  value={formData.project_year}
                  onChange={handleFieldChange}
                  placeholder={t('uploadWork.form.yearPlaceholder')}
                  min="1800"
                  max="2100"
                  disabled={isBusy}
                />
              </div>

              {/* Copyright */}
              <div className={s.copyrightRow}>
                <input
                  id="copyright"
                  type="checkbox"
                  className={s.checkbox}
                  checked={copyrightChecked}
                  onChange={(e) => setCopyrightChecked(e.target.checked)}
                  disabled={isBusy}
                />
                <label htmlFor="copyright" className={s.copyrightLabel}>
                  {t('uploadWork.form.copyrightLabel')}
                </label>
              </div>

              {/* Error message */}
              {errorMsg && (
                <div className={s.errorMsg} role="alert">
                  {errorMsg}
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                className={s.submitBtn}
                disabled={isBusy}
              >
                {submitLabel()}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* ── Edit modal ────────────────────────────────────────────────────── */}
      {editTarget && (
        <div className={s.editModal} role="dialog" aria-modal="true" aria-label={t('uploadWork.edit.title')}>
          <div className={s.editModalCard}>
            <div className={s.editModalHeader}>
              <span className={s.editModalTitle}>{t('uploadWork.edit.title')}</span>
            </div>

            <div className={s.editCropArea}>
              <ReactCrop
                crop={crop}
                onChange={(c) => setCrop(c)}
                aspect={undefined}
              >
                <img
                  src={editTarget.previewUrl}
                  alt={t('uploadWork.edit.title')}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '55vh',
                    display: 'block',
                    transform: `rotate(${rotation}deg)`,
                    transition: 'transform var(--motion-normal) var(--motion-ease)',
                  }}
                />
              </ReactCrop>
            </div>

            <div className={s.editToolbar}>
              <button
                type="button"
                className={s.editToolBtn}
                onClick={() => setRotation(r => (r - 90 + 360) % 360)}
                aria-label={t('uploadWork.edit.rotateLeft')}
              >
                ↺ {t('uploadWork.edit.rotateLeft')}
              </button>
              <button
                type="button"
                className={s.editToolBtn}
                onClick={() => setRotation(r => (r + 90) % 360)}
                aria-label={t('uploadWork.edit.rotateRight')}
              >
                ↻ {t('uploadWork.edit.rotateRight')}
              </button>
            </div>

            <div className={s.editActions}>
              <button
                type="button"
                className={s.editCancelBtn}
                onClick={closeEdit}
              >
                {t('uploadWork.edit.cancel')}
              </button>
              <button
                type="button"
                className={s.editApplyBtn}
                onClick={applyEdit}
              >
                {t('uploadWork.edit.apply')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
