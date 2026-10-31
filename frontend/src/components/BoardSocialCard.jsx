/**
 * BoardSocialCard.jsx
 * One public board in the /people feed (mock: social-board-like.html).
 *
 * Collapsed — a non-interactive <article>; a stretched sibling <button> opens the
 *   card and the heart is a separate sibling button above it (no nested controls).
 *   The app's 2:3 photo tile (photoCardShell.js): the board's report
 *   image, bottom scrim + caption = board name only, a 28px glass heart top-right
 *   (hidden on the viewer's own board). The heart toggles the like and never
 *   expands the card.
 * Expanded — the SAME element grows to span the full grid row: BoardCover-style
 *   4:3 cover (radius-lg, soft border, E5 shadow), X top-left, 24px title with a
 *   32px glass heart on its right, owner/type/date meta line, and the board's
 *   buildings in a 2-col grid that scrolls INSIDE the fixed-height card.
 *
 * The page owns expand state, FLIP animation and like state; this component is
 * controlled (`board` carries is_reacted / reaction_count so the collapsed and
 * expanded hearts can never disagree).
 *
 * Props:
 *   board       {object}   feed item (see api/people.js)
 *   expanded    {boolean}
 *   onToggle    {(boardId) => void}   open / close
 *   onLike      {(board) => void}     like / unlike
 *   registerRef {(boardId, el|null) => void}  page-level element registry (FLIP)
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { getBoardReportImage } from '../api/people.js'
import { getProject, getBoardBuildings } from '../api/projects.js'
import { collectBoardBuildingIds } from '../hooks/useBoard.js'
import { useNearViewport } from '../hooks/useNearViewport.js'
import BuildingTile from '../pages/boardDetail/BuildingTile.jsx'
import { useTranslation } from '../i18n/index.js'
import { safeImageMime } from '../utils/imageMime.js'
import { throttleRetryDelayMs } from '../utils/throttleRetry.js'
import { atHandle } from '../utils/userIdentity.js'
import {
  photoCardShellStyle,
  photoCardImageStyle,
  photoCardScrimStyle,
  photoCardCaptionStyle,
  photoCardTitleStyle,
} from './photoCardShell.js'
import styles from './BoardSocialCard.module.css'

function HeartIcon({ size }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21.2l7.8-7.7 1-1.1a5.5 5.5 0 0 0 0-7.8z" />
    </svg>
  )
}

function formatDate(iso, language) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString(language === 'ko' ? 'ko-KR' : 'en-US', { month: 'numeric', day: 'numeric' })
}

export default function BoardSocialCard({ board, expanded, onToggle, onLike, registerRef }) {
  const { t, language } = useTranslation()
  const id = board.board_id
  const rootRef = useRef(null)
  const closeRef = useRef(null)
  const openRef = useRef(null)
  const wasExpandedRef = useRef(false)

  // Report image (lazy, per board). null from the api = terminal "no image".
  const [image, setImage] = useState(null)
  const [imageFailed, setImageFailed] = useState(false)
  // Fetched only once the card nears the viewport; kept afterwards.
  const near = useNearViewport(rootRef)
  useEffect(() => {
    if (!near) return undefined
    let cancelled = false
    let timer = null
    // On 429 keep the shimmer, wait, retry exactly once; a second failure
    // (including another 429) falls through to the normal placeholder.
    const attempt = isRetry => {
      getBoardReportImage(id).then(data => {
        if (cancelled) return
        if (data?.image_data) {
          setImage(`data:${safeImageMime(data.mime_type)};base64,${data.image_data}`)
        } else if (data?.throttled && !isRetry) {
          timer = setTimeout(() => { timer = null; if (!cancelled) attempt(true) },
            throttleRetryDelayMs(data.retryAfter))
        } else {
          setImageFailed(true)
        }
      })
    }
    attempt(false)
    return () => { cancelled = true; if (timer) clearTimeout(timer) }
  }, [id, near])

  // Buildings: loaded the first time the card is expanded.
  const [bState, setBState] = useState({ status: 'idle', items: [] })
  const loadTokenRef = useRef(0)
  const loadBuildings = useCallback(() => {
    const token = ++loadTokenRef.current
    setBState({ status: 'loading', items: [] })
    getProject(id, { throwOnError: true })
      .then(project => {
        if (!project) throw new Error('not found')
        return getBoardBuildings(collectBoardBuildingIds(project))
      })
      .then(items => {
        if (token === loadTokenRef.current) setBState({ status: 'ready', items })
      })
      .catch(() => {
        if (token === loadTokenRef.current) setBState({ status: 'error', items: [] })
      })
  }, [id])
  useEffect(() => {
    if (expanded && bState.status === 'idle') loadBuildings()
  }, [expanded, bState.status, loadBuildings])
  useEffect(() => () => { loadTokenRef.current++ }, [])

  // Focus: into the card on open, back to the tile on close.
  useEffect(() => {
    if (expanded) {
      closeRef.current?.focus({ preventScroll: true })
    } else if (wasExpandedRef.current) {
      const active = document.activeElement
      if (!active || active === document.body || rootRef.current?.contains(active)) {
        openRef.current?.focus({ preventScroll: true })
      }
    }
    wasExpandedRef.current = expanded
  }, [expanded])

  const setRoot = useCallback(el => {
    rootRef.current = el
    registerRef?.(id, el)
  }, [id, registerRef])

  const title = board.board_name || ''
  const isMe = !!board.is_me
  const liked = !!board.is_reacted

  function handleHeart(e) {
    e.stopPropagation()
    if (isMe) return
    onLike?.(board)
  }

  const heartLabel = isMe ? t('socialBoard.likeOwn') : t(liked ? 'socialBoard.unlike' : 'socialBoard.like')
  const ownerLabel = atHandle(board)
  const date = formatDate(board.updated_at, language)

  return (
    <article
      ref={setRoot}
      data-board-id={id}
      className={`${styles.tile} ${expanded ? styles.exp : ''}`}
      style={expanded ? undefined : photoCardShellStyle}
      role={expanded ? 'group' : undefined}
      tabIndex={expanded ? -1 : undefined}
      aria-label={expanded ? title : undefined}
    >
      <div className={styles.frame}>
        {image ? (
          <img
            src={image}
            alt={t('socialBoard.reportImageAlt', { title })}
            loading="lazy"
            style={photoCardImageStyle}
            draggable={false}
          />
        ) : (
          <div className={`${styles.placeholder} ${imageFailed ? '' : 'skeleton-shimmer'}`}>
            {imageFailed && !expanded && <span className={styles.placeholderText}>{t('socialBoard.noImage')}</span>}
          </div>
        )}
        <div style={photoCardScrimStyle} className={styles.scrim} />

        {!expanded && (
          <button
            ref={openRef}
            type="button"
            className={styles.open}
            onClick={() => onToggle(id)}
            aria-label={t('socialBoard.openCard', { title })}
            aria-expanded="false"
          />
        )}

        {!expanded && !isMe && (
          <button
            type="button"
            className={`${styles.frontHeart} ${liked ? styles.on : ''}`}
            onClick={handleHeart}
            aria-label={heartLabel}
            aria-pressed={liked}
          >
            <HeartIcon size={13} />
          </button>
        )}

        {expanded && (
          <button
            ref={closeRef}
            type="button"
            className={styles.close}
            onClick={e => { e.stopPropagation(); onToggle(id) }}
            aria-label={t('socialBoard.closeCard')}
            aria-expanded="true"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}

        <div className={styles.cap} style={expanded ? undefined : photoCardCaptionStyle}>
          <div className={styles.titleRow}>
            <div className={styles.titleCol}>
              <h2 className={styles.title} style={expanded ? undefined : photoCardTitleStyle}>{title}</h2>
              {expanded && (
                <div className={styles.owner}>
                  {ownerLabel && <span>{ownerLabel}</span>}
                  {board.type_code && <span className={styles.type}>{board.type_code}</span>}
                  {date && <span>· {date}</span>}
                </div>
              )}
            </div>
            {expanded && (
              <button
                type="button"
                className={`${styles.heartIcon} ${liked ? styles.on : ''}`}
                onClick={handleHeart}
                disabled={isMe}
                title={isMe ? t('socialBoard.likeOwn') : undefined}
                aria-label={heartLabel}
                aria-pressed={liked}
              >
                <HeartIcon size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      {expanded && (
        <div className={styles.detail}>
          {bState.status === 'ready' && bState.items.length > 0 && (
            <p className={styles.label}>{t('socialBoard.buildingsLabel', { n: bState.items.length })}</p>
          )}
          {(bState.status === 'idle' || bState.status === 'loading') && (
            <div className={styles.bgrid} aria-hidden="true">
              {[0, 1, 2, 3].map(i => <div key={i} className={`${styles.bSkeleton} skeleton-shimmer`} />)}
            </div>
          )}
          {bState.status === 'error' && (
            <div className={styles.note}>
              <p>{t('socialBoard.buildingsError')}</p>
              <button type="button" className={styles.retry} onClick={loadBuildings}>{t('socialBoard.retry')}</button>
            </div>
          )}
          {bState.status === 'ready' && bState.items.length === 0 && (
            <div className={styles.note}><p>{t('socialBoard.buildingsEmpty')}</p></div>
          )}
          {bState.status === 'ready' && bState.items.length > 0 && (
            <div className={styles.bgrid}>
              {bState.items.map(b => <BuildingTile key={b.id || b.image_id} building={b} />)}
            </div>
          )}
        </div>
      )}
    </article>
  )
}
