/**
 * WorkDetailModal.jsx
 * Full-screen overlay modal for viewing a single uploaded work.
 *
 * Props:
 *   uploadId {string}   — work upload_id to fetch
 *   onClose  {Function} — called when the user closes the modal
 *
 * DESIGN.md §8.10: centered modal (desktop), bottom sheet (mobile ≤768px).
 * DESIGN.md §8.8: spinner while loading.
 * DESIGN.md §8.9: inline error state.
 * DESIGN.md §3.5: motion tokens for transitions.
 */

import { useState, useEffect, useCallback } from 'react'
import { getWork } from '../api/works.js'
import { useTranslation } from '../i18n/index.js'
import styles from './WorkDetailModal.module.css'

// Close (×) icon — 14px SVG
function IconClose() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

// Chevron left icon
function IconChevronLeft() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}

// Chevron right icon
function IconChevronRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

export default function WorkDetailModal({ uploadId, onClose }) {
  const { t } = useTranslation()

  const [work, setWork] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [imgIndex, setImgIndex] = useState(0)

  // Fetch on mount
  useEffect(() => {
    if (!uploadId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setWork(null)
    setImgIndex(0)
    getWork(uploadId)
      .then(data => { if (!cancelled) setWork(data) })
      .catch(() => { if (!cancelled) setError(true) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [uploadId])

  // Close on ESC key
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const handlePrev = useCallback(() => {
    setImgIndex(i => Math.max(0, i - 1))
  }, [])

  const handleNext = useCallback((total) => {
    setImgIndex(i => Math.min(total - 1, i + 1))
  }, [])

  // Backdrop click → close
  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  // Status badge classes
  function badgeClass(status) {
    if (status === 'published')  return styles.badgePublished
    if (status === 'processing') return styles.badgeProcessing
    return styles.badgeRejected
  }

  function statusLabel(status) {
    if (status === 'published')  return t('workDetail.status.published')
    if (status === 'processing') return t('workDetail.status.processing')
    return t('workDetail.status.rejected')
  }

  const galleryUrls = work?.gallery_urls || []
  const hasMultiple = galleryUrls.length > 1

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      aria-label={work?.title || 'Work detail'}
      onClick={handleBackdropClick}
    >
      <div className={styles.modal}>
        {/* Loading state */}
        {loading && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '60px 24px',
            gap: 16,
          }}>
            <div className={styles.spinner} />
            <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
              {t('workDetail.loading')}
            </span>
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '60px 24px',
            gap: 16,
            textAlign: 'center',
          }}>
            <p style={{ margin: 0, fontSize: 15, color: 'var(--color-text)', fontWeight: 600 }}>
              {t('workDetail.error')}
            </p>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '10px 24px',
                borderRadius: 'calc(var(--radius-md) * 1px)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {t('workDetail.close')}
            </button>
          </div>
        )}

        {/* Success state */}
        {!loading && !error && work && (
          <>
            {/* Gallery */}
            <div className={styles.galleryWrap}>
              {galleryUrls.length > 0 ? (
                <img
                  key={imgIndex}
                  src={galleryUrls[imgIndex]}
                  alt={`${work.title} — ${imgIndex + 1}`}
                  className={styles.galleryImg}
                />
              ) : work.cover_url ? (
                <img
                  src={work.cover_url}
                  alt={work.title}
                  className={styles.galleryImg}
                />
              ) : (
                <div style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-text-muted)',
                  fontSize: 13,
                }} />
              )}

              {/* Left / right arrows — only when multiple images */}
              {hasMultiple && imgIndex > 0 && (
                <button
                  type="button"
                  className={`${styles.arrowBtn} ${styles.arrowLeft}`}
                  onClick={handlePrev}
                  aria-label="Previous image"
                >
                  <IconChevronLeft />
                </button>
              )}
              {hasMultiple && imgIndex < galleryUrls.length - 1 && (
                <button
                  type="button"
                  className={`${styles.arrowBtn} ${styles.arrowRight}`}
                  onClick={(e) => { e.stopPropagation(); handleNext(galleryUrls.length) }}
                  aria-label="Next image"
                >
                  <IconChevronRight />
                </button>
              )}

              {/* Index badge */}
              {hasMultiple && (
                <span className={styles.indexBadge}>
                  {imgIndex + 1} / {galleryUrls.length}
                </span>
              )}

              {/* Close button (top-right, overlaid on gallery) */}
              <button
                type="button"
                className={styles.closeBtn}
                onClick={onClose}
                aria-label={t('workDetail.close')}
              >
                <IconClose />
              </button>
            </div>

            {/* Meta */}
            <div className={styles.meta}>
              <h2 className={styles.title}>{work.title}</h2>

              <div className={styles.details}>
                {work.program && (
                  <span className={styles.detailItem}>{work.program}</span>
                )}
                {work.location_city && (
                  <span className={styles.detailItem}>{work.location_city}</span>
                )}
                {work.location_country && (
                  <span className={styles.detailItem}>{work.location_country}</span>
                )}
                {work.project_year && (
                  <span className={styles.detailItem}>{work.project_year}</span>
                )}
              </div>

              <span className={`${styles.badge} ${badgeClass(work.status)}`}>
                {statusLabel(work.status)}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
