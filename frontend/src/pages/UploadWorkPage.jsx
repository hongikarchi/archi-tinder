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

// Each entry maps the backend PROGRAM_CHOICES key (value sent to API) to a
// human-readable label shown in the UI.  Ordered to match canonical_v2_buildings
// vocabulary; 'Other' is omitted — no backend key exists for it.
const PROGRAMS = [
  { value: 'residential',    label: 'Housing' },
  { value: 'office',         label: 'Office' },
  { value: 'cultural',       label: 'Museum / Cultural' },
  { value: 'educational',    label: 'Education' },
  { value: 'religious',      label: 'Religion' },
  { value: 'sports',         label: 'Sports' },
  { value: 'hospitality',    label: 'Hospitality' },
  { value: 'healthcare',     label: 'Healthcare' },
  { value: 'public',         label: 'Public' },
  { value: 'mixed_use',      label: 'Mixed Use' },
  { value: 'landscape',      label: 'Landscape' },
  { value: 'infrastructure', label: 'Infrastructure' },
  { value: 'commercial',     label: 'Commercial' },
  { value: 'industrial',     label: 'Industrial' },
]

/* ── WebP converter ─────────────────────────────────────────────────────── */

async function convertToWebP(file) {
  const img = new Image()
  const srcUrl = URL.createObjectURL(file)
  img.src = srcUrl
  try {
    await new Promise((resolve, reject) => {
      img.onload = resolve
      img.onerror = () => reject(new Error('이미지를 불러올 수 없습니다'))
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
      const blob = await convertToWebP(file)
      const preview = URL.createObjectURL(blob)
      setFiles(prev => [...prev, { file, preview, blob }])
    } catch (err) {
      setErrorMsg('이미지 변환 중 오류가 발생했습니다: ' + err.message)
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
      setErrorMsg('최소 1개의 이미지를 선택해주세요.')
      return
    }
    if (!formData.title.trim()) {
      setErrorMsg('작품 제목을 입력해주세요.')
      return
    }
    if (!formData.program) {
      setErrorMsg('프로그램 유형을 선택해주세요.')
      return
    }
    if (!copyrightChecked) {
      setErrorMsg('저작권 확인에 동의해주세요.')
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
    } catch (err) {
      setUploadState('error')
      setErrorMsg(err.message || '업로드 중 오류가 발생했습니다.')
    }
  }

  /* ── Submit button label per state ──────────────────────────────────── */

  function submitLabel() {
    switch (uploadState) {
      case 'converting': return '변환 중...'
      case 'uploading':  return `업로드 중 ${progress}%`
      case 'processing': return '검토 중...'
      default:           return '업로드'
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
          aria-label="뒤로가기"
        >
          ←
        </button>
        <h1 className={s.headerTitle}>작품 업로드</h1>
        {/* spacer to balance the back button */}
        <div style={{ width: 44 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px 48px' }}>
        {/* ── Processing success state ─────────────────────────────────── */}
        {uploadState === 'processing' && (
          <div className={s.processingMsg}>
            <p style={{ margin: '0 0 6px', fontSize: 16, fontWeight: 700 }}>업로드 완료</p>
            <p style={{ margin: 0 }}>
              검토 중입니다. 잠시 후 프로필 Created 탭에서 확인하세요.
            </p>
          </div>
        )}

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
                aria-label="이미지를 여기에 드래그하거나 클릭해 선택하세요"
              >
                {files.length === 0
                  ? (
                    <>
                      <div style={{ fontSize: 32, marginBottom: 8 }}>+</div>
                      <div>이미지를 드래그하거나 클릭해 선택하세요</div>
                      <div style={{ fontSize: 12, marginTop: 4, color: 'var(--color-text-dim)' }}>
                        JPG, PNG, WebP — 최대 2400px로 자동 변환됩니다
                      </div>
                    </>
                  )
                  : (
                    <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
                      + 이미지 추가
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
                    <img src={f.preview} alt={`미리보기 ${i + 1}`} />
                    <button
                      type="button"
                      className={s.removeThumb}
                      onClick={() => removeFile(i)}
                      aria-label={`이미지 ${i + 1} 삭제`}
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
                <label className={s.label} htmlFor="title">제목 *</label>
                <input
                  id="title"
                  name="title"
                  type="text"
                  className={s.input}
                  value={formData.title}
                  onChange={handleFieldChange}
                  placeholder="작품 제목을 입력하세요"
                  disabled={isBusy}
                />
              </div>

              {/* Program */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="program">프로그램 *</label>
                <select
                  id="program"
                  name="program"
                  className={s.select}
                  value={formData.program}
                  onChange={handleFieldChange}
                  disabled={isBusy}
                >
                  <option value="">선택하세요</option>
                  {PROGRAMS.map(p => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>

              {/* Location city */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="location_city">도시</label>
                <input
                  id="location_city"
                  name="location_city"
                  type="text"
                  className={s.input}
                  value={formData.location_city}
                  onChange={handleFieldChange}
                  placeholder="예: Seoul"
                  disabled={isBusy}
                />
              </div>

              {/* Location country */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="location_country">국가</label>
                <input
                  id="location_country"
                  name="location_country"
                  type="text"
                  className={s.input}
                  value={formData.location_country}
                  onChange={handleFieldChange}
                  placeholder="예: South Korea"
                  disabled={isBusy}
                />
              </div>

              {/* Project year */}
              <div className={s.formGroup}>
                <label className={s.label} htmlFor="project_year">완공 연도</label>
                <input
                  id="project_year"
                  name="project_year"
                  type="number"
                  className={s.input}
                  value={formData.project_year}
                  onChange={handleFieldChange}
                  placeholder="예: 2023"
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
                  이 작품은 본인의 저작물임을 확인합니다
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
