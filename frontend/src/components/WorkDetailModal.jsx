/**
 * WorkDetailModal.jsx
 * Full-screen overlay modal for viewing a single uploaded work.
 *
 * Props:
 *   uploadId {string}   — work upload_id to fetch
 *   onClose  {Function} — called when the user closes the modal
 *
 * Built on the shared `Modal` component (DESIGN.md §8.10): centered modal
 * (desktop), bottom sheet (mobile ≤768px). The gallery image bleeds edge-to-
 * edge by cancelling Modal's own 24px panel padding with a negative margin
 * (see .galleryWrap) — the built-in Modal close button (top-right) overlays
 * directly on the image, same as the previous hand-rolled close button.
 * DESIGN.md §8.8: spinner while loading.
 * DESIGN.md §8.9: inline error state.
 * DESIGN.md §3.5: motion tokens for transitions.
 */

import { useState, useEffect, useCallback } from 'react'
import { getWork } from '../api/works.js'
import { useTranslation } from '../i18n/index.js'
import Modal from './Modal.jsx'
import styles from './WorkDetailModal.module.css'

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

  const handlePrev = useCallback(() => {
    setImgIndex(i => Math.max(0, i - 1))
  }, [])

  const handleNext = useCallback((total) => {
    setImgIndex(i => Math.min(total - 1, i + 1))
  }, [])

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
    <Modal
      open
      onClose={onClose}
      zIndex={300}
      closeLabel={t('workDetail.close')}
      width={560}
    >
      {/* Loading state */}
      {loading && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 24px',
          gap: 16,
        }}>
          <div className={styles.spinner} />
          <span style={{ fontSize: 'var(--fs-body)', color: 'var(--color-text-muted)' }}>
            {t('workDetail.loading')}
          </span>
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 24px',
          gap: 16,
          textAlign: 'center',
        }}>
          <p style={{ margin: 0, fontSize: 'var(--fs-emphasis)', color: 'var(--color-text)', fontWeight: 600 }}>
            {t('workDetail.error')}
          </p>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '10px 24px',
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 'var(--fs-body)',
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
          {/* Gallery — bleeds edge-to-edge (negative margin cancels panel padding) */}
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
                fontSize: 'var(--fs-caption)',
              }} />
            )}

            {/* Left / right arrows — only when multiple images */}
            {hasMultiple && imgIndex > 0 && (
              <button
                type="button"
                className={`${styles.arrowBtn} ${styles.arrowLeft}`}
                onClick={handlePrev}
                aria-label={t('modalB3.workDetail.prevImage')}
              >
                <IconChevronLeft />
              </button>
            )}
            {hasMultiple && imgIndex < galleryUrls.length - 1 && (
              <button
                type="button"
                className={`${styles.arrowBtn} ${styles.arrowRight}`}
                onClick={(e) => { e.stopPropagation(); handleNext(galleryUrls.length) }}
                aria-label={t('modalB3.workDetail.nextImage')}
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
    </Modal>
  )
}
