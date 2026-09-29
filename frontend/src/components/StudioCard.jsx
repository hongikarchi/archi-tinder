import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from '../i18n/index.js'
import FloatingIconButton from './FloatingIconButton.jsx'
import styles from './StudioCard.module.css'

/**
 * StudioCard — architect/studio row + building carousel, shown on
 * UserProfilePage's Studios tab.
 *
 * Extracted from the (now-deleted) LikedOfficesPage — that page's own route
 * was dead (App.jsx redirected `my/liked-offices` straight past it), but its
 * `OfficeCard`/`BuildingCarousel` were the only live consumers of this UI,
 * reached via direct import from UserProfilePage. UI-CONSISTENCY-B Phase 3.
 */

/* ── Placeholder SVG icons ──────────────────────────────────────────────── */

export function BuildingPlaceholderSmall() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.5 }}>
      <rect x="3" y="9" width="13" height="13" rx="1" />
      <path d="M16 9V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5" />
      <line x1="9" y1="21" x2="9" y2="15" />
      <line x1="13" y1="21" x2="13" y2="15" />
    </svg>
  )
}

export function BuildingPlaceholderLarge() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.4 }}>
      <rect x="3" y="9" width="13" height="13" rx="1" />
      <path d="M16 9V4a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v5" />
      <line x1="9" y1="21" x2="9" y2="15" />
      <line x1="13" y1="21" x2="13" y2="15" />
      <rect x="16" y="13" width="5" height="9" rx="1" />
      <line x1="18.5" y1="11" x2="18.5" y2="13" />
    </svg>
  )
}

export function BuildingIconEmpty() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--color-text-muted)', opacity: 0.45 }}>
      <rect x="2" y="7" width="14" height="15" rx="1" />
      <path d="M16 7V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1v4" />
      <line x1="6" y1="22" x2="6" y2="17" />
      <line x1="10" y1="22" x2="10" y2="17" />
      <rect x="16" y="11" width="6" height="11" rx="1" />
      <line x1="19" y1="9" x2="19" y2="11" />
      <line x1="17" y1="14" x2="22" y2="14" />
      <line x1="17" y1="17" x2="22" y2="17" />
    </svg>
  )
}

/* ── BuildingCarousel ───────────────────────────────────────────────────── */

/**
 * `onNavigateOffice` — fallback tap target used only while buildings are
 * still loading (`null`) or the architect turned out to have none with a
 * usable image (`[]`); both cases show a single placeholder slide that
 * opens the architect page. Once real buildings with images are available,
 * each slide instead opens that specific building (`onNavigateBuilding`).
 */
function BuildingCarousel({ buildings, fallbackUrl, altText, onNavigateOffice, onNavigateBuilding }) {
  const { t } = useTranslation()
  const scrollRef = useRef(null)
  const [canPrev, setCanPrev] = useState(false)
  const [canNext, setCanNext] = useState(false)

  const updateArrows = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setCanPrev(el.scrollLeft > 1)
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
  }, [])

  // Only buildings with a real photo get a slide — no placeholder slides
  // mixed into an otherwise-real carousel.
  const withImages = (buildings || []).filter(b => b.image_url)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    updateArrows()
    const ro = new ResizeObserver(updateArrows)
    ro.observe(el)
    return () => ro.disconnect()
  }, [withImages.length, updateArrows])

  function scrollByStep(direction) {
    const el = scrollRef.current
    if (!el) return
    const step = (el.firstElementChild?.offsetWidth || el.clientWidth) + 8 // + gap
    el.scrollBy({ left: direction * step, behavior: 'smooth' })
  }

  // Loading (null/undefined) or loaded-but-none-with-images → single
  // fallback slide that opens the architect page.
  if (buildings === null || buildings === undefined || withImages.length === 0) {
    return (
      <div
        onClick={e => { e.stopPropagation(); onNavigateOffice?.() }}
        className={styles.fallbackSlide}
      >
        {fallbackUrl ? (
          <img
            src={fallbackUrl}
            alt={altText}
            loading="lazy"
            className={styles.fallbackImage}
          />
        ) : (
          <BuildingPlaceholderLarge />
        )}
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <div
        ref={scrollRef}
        className={`${styles.carousel} hide-scrollbar`}
        onClick={e => e.stopPropagation()}
        onScroll={updateArrows}
      >
        {withImages.map((bld, i) => (
          <div
            key={bld.canonical_bld_id || i}
            onClick={e => { e.stopPropagation(); onNavigateBuilding?.(bld.canonical_bld_id) }}
            className={styles.slide}
          >
            <img
              src={bld.image_url}
              alt={bld.name_en || altText}
              loading="lazy"
              className={styles.slideImage}
            />
          </div>
        ))}
      </div>

      {/* Mouse-only prev/next affordance (DESIGN.md §4 gesture-friendly —
          touch devices keep plain swipe, see .module.css hover/pointer query). */}
      {canPrev && (
        <FloatingIconButton
          onClick={e => { e.stopPropagation(); scrollByStep(-1) }}
          ariaLabel={t('profile.prevImage')}
          className={`${styles.arrow} ${styles.arrowPrev}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </FloatingIconButton>
      )}
      {canNext && (
        <FloatingIconButton
          onClick={e => { e.stopPropagation(); scrollByStep(1) }}
          ariaLabel={t('profile.nextImage')}
          className={`${styles.arrow} ${styles.arrowNext}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </FloatingIconButton>
      )}
    </div>
  )
}

/* ── StudioCard ─────────────────────────────────────────────────────────── */

/**
 * `office`     — { architect_id, name, logo_url, cover_image_url }
 * `buildings`  — null (loading) | [] (loaded, none) | [{ canonical_bld_id,
 *                image_url, name_en }] from getArchitectProfile().
 * `onClick`    — opens the architect page; used by the header row AND as the
 *                carousel's fallback target while there is no per-building
 *                image to click into yet.
 */
export function StudioCard({ office, buildings, onClick }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <div className={styles.card}>
      {/* Header row: logo + name + subtitle — opens the architect page */}
      <div onClick={onClick} className={styles.header}>
        <div className={styles.logo}>
          {office.logo_url ? (
            <img
              src={office.logo_url}
              alt={office.name}
              className={styles.logoImage}
            />
          ) : (
            <BuildingPlaceholderSmall />
          )}
        </div>

        <div className={styles.textBlock}>
          <p className={styles.name}>{office.name}</p>
          <p className={styles.subtitle}>{t('profile.savedStudio')}</p>
        </div>
      </div>

      {/* Building carousel — each image opens that specific building */}
      <BuildingCarousel
        buildings={buildings}
        fallbackUrl={office.cover_image_url}
        altText={office.name}
        onNavigateOffice={onClick}
        onNavigateBuilding={bldId => navigate('/buildings/' + bldId)}
      />
    </div>
  )
}

/* ── Skeleton card ──────────────────────────────────────────────────────── */

export function SkeletonCard() {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <div className={`${styles.logo} ${styles.skeletonBlock}`} />
        <div className={styles.textBlock} style={{ gap: 6 }}>
          <div className={`${styles.skeletonBlock} ${styles.skeletonLineWide}`} />
          <div className={`${styles.skeletonBlock} ${styles.skeletonLineNarrow}`} />
        </div>
      </div>
      <div className={`${styles.skeletonBlock} ${styles.skeletonCarousel}`} />
    </div>
  )
}
