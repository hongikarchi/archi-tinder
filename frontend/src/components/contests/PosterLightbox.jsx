import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import FloatingIconButton from '../FloatingIconButton.jsx'
import { useTranslation } from '../../i18n/index.js'
import styles from './PosterLightbox.module.css'

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * PosterLightbox — enlarged contest poster (decision D4 / D11,
 * docs/decisions/2026-10-09-contest-real-data.md).
 *
 * Hotlink only: `posterUrl` is the SAME url as the thumbnail, already passed
 * through safeHttpUrl by the caller; never downloaded or re-hosted here.
 *
 * Rendered via createPortal to document.body. Closes via the X button, a
 * backdrop click, or Esc. On open: body scroll is locked, focus moves to the
 * close button and Tab is trapped inside the dialog; on close focus returns to
 * `returnFocusRef` (the thumbnail button). If the image fails to load,
 * `onImageError` fires (the caller closes the lightbox and shows the fallback).
 *
 * `sourceUrl` renders only when the caller found it usable.
 */
export default function PosterLightbox({
  posterUrl,
  title,
  credit,
  sourceUrl,
  returnFocusRef,
  onClose,
  onImageError,
}) {
  const { t } = useTranslation()
  const overlayRef = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  // Body scroll lock + focus in / restore focus out.
  useEffect(() => {
    const prevOverflow = document.body.style.overflow
    const prevFocus = document.activeElement
    document.body.style.overflow = 'hidden'
    overlayRef.current?.querySelector('[data-lightbox-close]')?.focus()
    const returnEl = returnFocusRef?.current
    return () => {
      document.body.style.overflow = prevOverflow
      const target = returnEl && returnEl.isConnected ? returnEl : prevFocus
      if (target && target.isConnected && typeof target.focus === 'function') target.focus()
    }
  }, [returnFocusRef])

  // Esc to close + Tab trap.
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab') return
      const nodes = overlayRef.current?.querySelectorAll(FOCUSABLE)
      if (!nodes || nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const active = document.activeElement
      if (!overlayRef.current.contains(active)) {
        e.preventDefault()
        first.focus()
      } else if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const node = (
    <div
      ref={overlayRef}
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label={t('contest.poster.lightboxAria', { title })}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <FloatingIconButton
        variant="onPhoto"
        style={{ position: 'fixed', top: 12, right: 12, zIndex: 1 }}
        onClick={onClose}
        ariaLabel={t('contest.poster.close')}
        data-lightbox-close=""
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </FloatingIconButton>

      {/* Clicks on the empty area around the content also reach the overlay. */}
      <div className={styles.content} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
        <img
          className={styles.poster}
          src={posterUrl}
          alt={t('contest.poster.alt', { title })}
          referrerPolicy="no-referrer"
          decoding="async"
          onError={onImageError}
        />
        {credit && <p className={styles.credit}>{t('contest.poster.credit', { credit })}</p>}

        <div className={styles.actions}>
          {sourceUrl && (
            <a className={styles.action} href={sourceUrl} target="_blank" rel="noopener noreferrer">
              {t('contest.detail.viewSource')}
            </a>
          )}
        </div>
      </div>
    </div>
  )

  return createPortal(node, document.body)
}
