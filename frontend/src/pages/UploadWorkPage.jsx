/**
 * UploadWorkPage — /upload
 *
 * Portfolio work upload flow:
 *   1. Select images → convert to WebP via canvas
 *   2. Fill metadata form (title, program, location, year)
 *   3. Confirm copyright
 *   4. Presign → upload to R2 → finalize with backend
 */

import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { presignFiles, uploadToR2, finalizeWork } from '../api/works.js'
import { useTranslation } from '../i18n/index.js'
import s from './UploadWorkPage.module.css'

// Matches backend MAX_WORK_IMAGES — presign/finalize reject >10 images with a 400.
const MAX_WORK_IMAGES = 10

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
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d').drawImage(img, 0, 0, w, h)

    return new Promise(resolve => canvas.toBlob(resolve, 'image/webp', 0.85))
  } finally {
    URL.revokeObjectURL(srcUrl)
  }
}

/* ── Component ──────────────────────────────────────────────────────────── */

export default function UploadWorkPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const { t } = useTranslation()

  const [showSuccessModal, setShowSuccessModal] = useState(false)
  const [files, setFiles] = useState([])
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

  /* ── File selection / drop ────────────────────────────────────────────── */

  // Returns true on success, false on conversion failure (caller uses this to
  // avoid clobbering a conversion error with the max-images error below).
  async function processFile(file) {
    if (!file.type.startsWith('image/')) return true
    setUploadState('converting')
    try {
      const blob = await convertToWebP(file, t)
      const preview = URL.createObjectURL(blob)
      setFiles(prev => [...prev, { file, preview, blob }])
    } catch (err) {
      setErrorMsg(t('uploadWork.error.conversionFailed', { detail: err.message }))
      setUploadState('error')
      return false
    }
    setUploadState('idle')
    return true
  }

  // Enforce MAX_WORK_IMAGES (existing selected + new) — keep what fits, reject the excess.
  async function addFiles(selected) {
    setErrorMsg('')
    const imageFiles = selected.filter(f => f.type.startsWith('image/'))
    const room = MAX_WORK_IMAGES - files.length
    const toAdd = room > 0 ? imageFiles.slice(0, room) : []
    const rejectedCount = imageFiles.length - toAdd.length

    let conversionFailed = false
    for (const f of toAdd) {
      const ok = await processFile(f)
      if (!ok) conversionFailed = true
    }

    if (rejectedCount > 0 && !conversionFailed) {
      setErrorMsg(t('uploadWork.error.maxImages', { max: MAX_WORK_IMAGES }))
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

  function removeFile(index) {
    setFiles(prev => {
      URL.revokeObjectURL(prev[index].preview)
      return prev.filter((_, i) => i !== index)
    })
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

    setUploadState('uploading')
    setProgress(0)

    try {
      // Step 1: presign
      const presignResults = await presignFiles(
        files.map(f => ({
          filename: f.file.name,
          content_type: UPLOAD_CONTENT_TYPE,
          file_size: f.blob.size,
        }))
      )

      // Step 2: sequential R2 upload with per-file progress
      for (let i = 0; i < files.length; i++) {
        await uploadToR2(
          presignResults[i],
          files[i].blob,
          UPLOAD_CONTENT_TYPE,
          (p) => setProgress(Math.round((i * 100 + p) / files.length))
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
      setShowSuccessModal(true)
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
      {showSuccessModal && (
        <div
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
              onClick={() => navigate('/user/me?tab=created')}
              style={{
                marginTop: 8,
                padding: '12px 16px',
                borderRadius: 12,
                border: 0,
                background: '#ec4899',
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
            {/* ── Drop zone (hidden once MAX_WORK_IMAGES is reached — nothing more to add) ── */}
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
                {files.map((f, i) => (
                  <div key={f.preview} className={s.previewThumb}>
                    <img src={f.preview} alt={t('uploadWork.preview.alt', { n: i + 1 })} />
                    <button
                      type="button"
                      className={s.removeThumb}
                      onClick={() => removeFile(i)}
                      aria-label={t('uploadWork.preview.removeAria', { n: i + 1 })}
                    >
                      ×
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

              {/* Error message — shown for both validation errors (idle) and upload errors */}
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
    </div>
  )
}
