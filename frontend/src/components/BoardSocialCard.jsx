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
 * Expanded — the SAME element grows to span the full grid row as a rounded
 *   panel holding ONLY the read-only viewer persona report (PersonaReportBody)
 *   in an internal scroller, with a glass X pinned top-right. Data comes from
 *   the page (`report` = usePublicBoardReport state).
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
 *   report      {{status, data, retry}|undefined}  public report state (expanded only)
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getBoardReportImage } from '../api/people.js'
import { useNearViewport } from '../hooks/useNearViewport.js'
import { PersonaReportBody, ReportSkeleton } from './PersonaReportPage.jsx'
import EmptyState from './EmptyState.jsx'
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

export default function BoardSocialCard({ board, expanded, onToggle, onLike, registerRef, report }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
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
  const reportData = report?.data
  const ownerId = reportData?.ownerId ?? board.user_id

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
      {!expanded && (
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
              {imageFailed && <span className={styles.placeholderText}>{t('socialBoard.noImage')}</span>}
            </div>
          )}
          <div style={photoCardScrimStyle} />

          <button
            ref={openRef}
            type="button"
            className={styles.open}
            onClick={() => onToggle(id)}
            aria-label={t('socialBoard.openCard', { title })}
            aria-expanded="false"
          />

          {!isMe && (
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

          <div style={photoCardCaptionStyle}>
            <h2 className={styles.title} style={photoCardTitleStyle}>{title}</h2>
          </div>
        </div>
      )}

      {expanded && (
        <>
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

          {/* data-report-content: the page fades this in late during the grow FLIP. */}
          <div className={styles.detail} data-report-content>
            {(!report || report.status === 'idle' || report.status === 'loading') && (
              <ReportSkeleton label={t('persona.loadingFetch')} />
            )}
            {report?.status === 'gone' && (
              <EmptyState
                neutral
                title={t('persona.unavailableTitle')}
                body={t('persona.unavailableBody')}
                actionLabel={t('socialBoard.closeCard')}
                onAction={() => onToggle(id)}
              />
            )}
            {report?.status === 'error' && (
              <div className={styles.note}>
                <p>{t('socialBoard.reportError')}</p>
                <button type="button" className={styles.retry} onClick={report.retry}>{t('socialBoard.retry')}</button>
              </div>
            )}
            {report?.status === 'ready' && reportData && (
              <PersonaReportBody
                finalReport={reportData.finalReport}
                axisScores={reportData.axisScores}
                reportImage={reportData.reportImage}
                reportImageMime={reportData.reportImageMime}
                meta={{
                  visibility: 'public',
                  buildingCount: reportData.likedBuildings.length,
                  reactionCount: board.reaction_count ?? 0,
                  ownerLabel: ownerLabel || undefined,
                  onOwner: ownerId != null ? () => navigate(`/user/${ownerId}`) : undefined,
                }}
                likedBuildings={reportData.likedBuildings}
                recommendations={reportData.recommendations}
                architects={reportData.architects}
                onOpenBuilding={card => {
                  const bid = card?.image_id || card?.canonical_bld_id || card?.building_id
                  if (bid) navigate(`/buildings/${bid}`)
                }}
                onOpenArchitect={aid => navigate(`/architects/${aid}`)}
                actionsSlot={isMe ? null : (
                  <button
                    type="button"
                    className={`${styles.likePill} ${liked ? styles.on : ''}`}
                    onClick={handleHeart}
                    aria-pressed={liked}
                  >
                    <HeartIcon size={14} />
                    {t('socialBoard.likeTaste', { n: board.reaction_count ?? 0 })}
                  </button>
                )}
              />
            )}
          </div>
        </>
      )}
    </article>
  )
}
