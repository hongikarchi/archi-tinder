/**
 * UploadWorkPage — /upload
 *
 * Portfolio work upload flow:
 *   1. Select images → convert to WebP via canvas (modern browsers auto-apply
 *      EXIF orientation when decoding <img>, so no manual EXIF handling is
 *      needed — see convertToWebP())
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
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
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

/* ── WebP converter ─────────────────────────────────────────────────────── */

/**
 * Converts a file to WebP blob.
 * Modern browsers (Chrome 81+/Firefox 77+/Safari 13.1+) auto-apply EXIF
 * orientation when decoding <img> — naturalWidth/naturalHeight and
 * drawImage() already return correctly-oriented pixels, so no manual EXIF
 * transform is needed (or wanted — doing it manually here would double-rotate).
 * Returns the WebP blob.
 */
async function convertToWebP(file, t) {
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
    canvas.width = w
    canvas.height = h
    ctx.drawImage(img, 0, 0, w, h)

    return canvasToBlob(canvas)
  } finally {
    URL.revokeObjectURL(srcUrl)
  }
}

/* ── Edit apply ─────────────────────────────────────────────────────────── */

/**
 * Draws `blob` onto a fresh canvas with `rotation` (0/90/180/270) baked in.
 * Dimensions are swapped for 90/270 so the output canvas always matches what
 * the rotated image visually looks like. Shared by the edit-modal preview
 * regenerator and applyEditToBlob so both use identical rotation math.
 */
async function drawRotatedCanvas(blob, rotation) {
  const srcUrl = URL.createObjectURL(blob)
  const img = new Image()
  img.src = srcUrl
  try {
    await new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = reject
    })

    const srcW = img.naturalWidth
    const srcH = img.naturalHeight
    const rad = (rotation * Math.PI) / 180
    const swapDims = rotation === 90 || rotation === 270
    const outW = swapDims ? srcH : srcW
    const outH = swapDims ? srcW : srcH

    const canvas = document.createElement('canvas')
    canvas.width = outW
    canvas.height = outH
    const ctx = canvas.getContext('2d')
    ctx.translate(outW / 2, outH / 2)
    ctx.rotate(rad)
    ctx.drawImage(img, -srcW / 2, -srcH / 2)

    return canvas
  } finally {
    URL.revokeObjectURL(srcUrl)
  }
}

/**
 * Converts a canvas to a blob, preferring WebP and falling back to JPEG.
 * Rejects if both encodings fail (never resolves with a null blob).
 */
function canvasToBlob(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
        return
      }
      // Fallback to JPEG if WebP fails
      canvas.toBlob((jpegBlob) => {
        if (jpegBlob) {
          resolve(jpegBlob)
        } else {
          reject(new Error('Canvas encoding failed'))
        }
      }, 'image/jpeg', 0.85)
    }, 'image/webp', 0.85)
  })
}

/**
 * Applies rotation + percent-crop to originalBlob.
 * `percentCrop` is a react-image-crop PercentCrop ({ unit: '%', x, y, width, height })
 * or undefined/empty for "no crop". Rotation is baked in first (from the
 * original, for quality), then the crop rect is extracted from the rotated
 * canvas — this matches what the user sees in the edit modal, where crop
 * always operates on an already-rotated preview.
 * Returns { blob, previewUrl } for the edited image.
 */
async function applyEditToBlob(originalBlob, percentCrop, rotation) {
  // Step 1: rotate the original at full quality
  const rotatedCanvas = await drawRotatedCanvas(originalBlob, rotation)

  // Step 2: no crop (or a degenerate crop) → use the rotated canvas as-is
  if (!percentCrop || !percentCrop.width || !percentCrop.height) {
    const blob = await canvasToBlob(rotatedCanvas)
    return { blob, previewUrl: URL.createObjectURL(blob) }
  }

  const rw = rotatedCanvas.width
  const rh = rotatedCanvas.height
  const cropX = Math.max(0, Math.round((percentCrop.x / 100) * rw))
  const cropY = Math.max(0, Math.round((percentCrop.y / 100) * rh))
  let cropW = Math.round((percentCrop.width / 100) * rw)
  let cropH = Math.round((percentCrop.height / 100) * rh)
  // Clamp so the rect never overflows the canvas and is never zero-sized
  // (percent rounding can otherwise produce a degenerate drawImage/toBlob call)
  cropW = Math.max(1, Math.min(cropW, rw - cropX))
  cropH = Math.max(1, Math.min(cropH, rh - cropY))

  const outCanvas = document.createElement('canvas')
  outCanvas.width = cropW
  outCanvas.height = cropH
  const outCtx = outCanvas.getContext('2d')
  outCtx.drawImage(
    rotatedCanvas,
    cropX, cropY, cropW, cropH,
    0, 0, cropW, cropH
  )

  const blob = await canvasToBlob(outCanvas)
  return { blob, previewUrl: URL.createObjectURL(blob) }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export default function UploadWorkPage({ onLogout }) {
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

    // 10 MB limit per file
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

  // Enforce MAX_WORK_IMAGES — dedup by name+size, 10MB filter, partial-add if overflow
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

    // Filter 10MB oversized files — report error but continue with valid ones
    const oversized = uniqueFiles.filter(f => f.size > MAX_FILE_BYTES)
    const validFiles = uniqueFiles.filter(f => f.size <= MAX_FILE_BYTES)

    const room = MAX_WORK_IMAGES - files.length
    const toAdd = room > 0 ? validFiles.slice(0, room) : []
    const rejectedCount = validFiles.length - toAdd.length

    let conversionFailed = false
    for (const f of toAdd) {
      const ok = await processFile(f)
      if (!ok) { conversionFailed = true; break }
    }

    // conversionFailed already set its own error message via processFile —
    // don't clobber it with the oversized/maxImages messages below.
    if (!conversionFailed) {
      const msgs = []
      if (oversized.length > 0) {
        msgs.push(t('uploadWork.error.fileTooLarge', { name: oversized.map(f => f.name).join(', ') }))
      }
      if (rejectedCount > 0) {
        msgs.push(t('uploadWork.error.maxImages', { max: MAX_WORK_IMAGES }))
      }
      if (msgs.length > 0) {
        setErrorMsg(msgs.join(' '))
      }
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
  // Crop always operates on an already-rotated preview (see applyEditToBlob
  // doc comment) — rotate regenerates editTarget.previewUrl from the
  // untouched originalBlob (never from a previously-rotated blob, so repeated
  // rotations don't degrade quality) and resets crop, since the old crop rect
  // no longer lines up with the newly-rotated image.
  const rotateSeqRef = useRef(0)
  // Tracks the rotation actually reflected in editTarget.previewUrl right
  // now — NOT necessarily the latest `rotation` state, since a rotate can be
  // in flight or can fail. rotateBy's catch reverts to this (not to the
  // rotation-before-this-call) so it can never revert to a value the preview
  // never actually showed (e.g. a discarded stale request followed by a
  // failing one).
  const displayedRotationRef = useRef(0)

  function openEdit(fileItem) {
    // Invalidate any in-flight rotate regeneration from a previous modal session
    rotateSeqRef.current++
    const previewUrl = URL.createObjectURL(fileItem.originalBlob)
    setEditTarget({ id: fileItem.id, previewUrl })
    setCrop(undefined)
    setRotation(0)
    displayedRotationRef.current = 0
  }

  function closeEdit() {
    // Invalidate any in-flight rotate regeneration so it can't land on a
    // reopened modal for a different file
    rotateSeqRef.current++
    setEditTarget(prev => {
      if (prev?.previewUrl) {
        URL.revokeObjectURL(prev.previewUrl)
      }
      return null
    })
    setCrop(undefined)
    setRotation(0)
  }

  async function rotateBy(delta) {
    if (!editTarget) return
    const fileItem = files.find(fi => fi.id === editTarget.id)
    if (!fileItem) return

    const nextRotation = (rotation + delta + 360) % 360
    setRotation(nextRotation)
    setCrop(undefined)

    const mySeq = ++rotateSeqRef.current
    try {
      // rotation 0 needs no re-encode — just point back at the original
      const nextPreviewUrl = nextRotation === 0
        ? URL.createObjectURL(fileItem.originalBlob)
        : URL.createObjectURL(await canvasToBlob(await drawRotatedCanvas(fileItem.originalBlob, nextRotation)))

      // Discard stale results if the user rotated again (or closed/reopened
      // the modal) before this resolved
      if (rotateSeqRef.current !== mySeq) {
        URL.revokeObjectURL(nextPreviewUrl)
        return
      }
      setEditTarget(prev => {
        if (!prev) {
          URL.revokeObjectURL(nextPreviewUrl)
          return prev
        }
        URL.revokeObjectURL(prev.previewUrl)
        return { ...prev, previewUrl: nextPreviewUrl }
      })
      displayedRotationRef.current = nextRotation
    } catch (err) {
      if (rotateSeqRef.current !== mySeq) return
      // Regeneration failed — revert to whatever rotation the preview is
      // actually still showing (not necessarily the rotation right before
      // this call, which may itself have been a discarded stale request)
      setRotation(displayedRotationRef.current)
      setErrorMsg(t('uploadWork.error.conversionFailed', { detail: err.message }))
    }
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
    } catch (err) {
      setUploadState('idle')
      setErrorMsg(t('uploadWork.error.conversionFailed', { detail: err.message }))
    }
    closeEdit()
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
      <PageBackButton onClick={() => navigate(-1)} label={t('uploadWork.header.backAria')} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />

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
                background: 'var(--accent-1)',
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
        <h1 className={s.headerTitle}>{t('uploadWork.header.title')}</h1>
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

              {/* Error message — hidden while the edit modal covers the form (rendered there instead) */}
              {errorMsg && !editTarget && (
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
                onChange={(_pixelCrop, percentCrop) => setCrop(percentCrop)}
                aspect={undefined}
              >
                <img
                  src={editTarget.previewUrl}
                  alt={t('uploadWork.edit.title')}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '55vh',
                    display: 'block',
                  }}
                />
              </ReactCrop>
            </div>

            <div className={s.editToolbar}>
              <button
                type="button"
                className={s.editToolBtn}
                onClick={() => rotateBy(-90)}
                aria-label={t('uploadWork.edit.rotateLeft')}
                disabled={uploadState === 'converting'}
              >
                ↺ {t('uploadWork.edit.rotateLeft')}
              </button>
              <button
                type="button"
                className={s.editToolBtn}
                onClick={() => rotateBy(90)}
                aria-label={t('uploadWork.edit.rotateRight')}
                disabled={uploadState === 'converting'}
              >
                ↻ {t('uploadWork.edit.rotateRight')}
              </button>
            </div>

            {/* Error message — the form-level one is covered by this modal (z-index 100) */}
            {errorMsg && (
              <div className={s.errorMsg} role="alert">
                {errorMsg}
              </div>
            )}

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
                disabled={uploadState === 'converting'}
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
