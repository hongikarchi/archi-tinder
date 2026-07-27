/**
 * DbCheckTile.jsx — ADMIN-DBCHECK-1 grid tile.
 *
 * LQIP blur-up + main image fade-in, same pattern as SwipeCard.jsx (B1).
 * Broken/missing images render a visible placeholder with the building id —
 * this QA page must EXPOSE missing-image rows, never hide them.
 */

import { useState } from 'react'
import { rightSizeImageUrl, buildLqipUrl } from '../../api/rightSizeImageUrl.js'
import styles from './DbCheck.module.css'

export default function DbCheckTile({ card, onClick }) {
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)

  const rawUrl = card.image_url || ''
  const mainSrc = rightSizeImageUrl(rawUrl, 420)
  const lqipSrc = buildLqipUrl(rawUrl)
  const id = card.image_id || card.canonical_bld_id || '(no id)'
  const name = card.image_title || card.name || card.name_en || '(untitled)'

  const showPlaceholder = !rawUrl || imgFailed

  return (
    <button
      type="button"
      className={styles.tile}
      onClick={() => onClick(id)}
      aria-label={`${name} — ${id}`}
    >
      {showPlaceholder ? (
        <div className={styles.tilePlaceholder}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          <span>missing image</span>
          <span className={styles.tilePlaceholderId}>{id}</span>
        </div>
      ) : (
        <>
          {lqipSrc && (
            <img
              src={lqipSrc}
              alt=""
              aria-hidden="true"
              loading="lazy"
              className={styles.tileImg}
              style={{ filter: 'blur(14px)', opacity: imgLoaded ? 0 : 1, transition: 'opacity 0.2s ease' }}
            />
          )}
          <img
            src={mainSrc}
            alt={name}
            loading="lazy"
            className={styles.tileImg}
            style={{ opacity: imgLoaded ? 1 : 0, transition: 'opacity 0.2s ease' }}
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgFailed(true)}
          />
        </>
      )}
      <div className={styles.tileGradient} />
      <div className={styles.tileLabel}>
        <p className={styles.tileName}>{name}</p>
        <p className={styles.tileId}>{id}</p>
      </div>
    </button>
  )
}
