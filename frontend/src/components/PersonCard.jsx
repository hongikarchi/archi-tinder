/**
 * PersonCard.jsx
 * Discovery tile for a single user in the people feed (/people).
 *
 * FRONT-PEOPLE-CARD-1 (2026-08-25): image-front / flip-to-detail.
 * FRONT-PEOPLE-CARD-3 (2026-08-29): re-sized to the app's photo tile — the
 *   same surface the post-report recommendation grid uses. Measurements come
 *   from photoCardShell.js, which was extracted out of ResultsPage's
 *   `ResultCard` (a local, non-exported function) precisely so these two
 *   surfaces share one definition instead of drifting as look-alikes.
 *
 *   Front — the user's taste-report architecture image, full-bleed, with the
 *           recommendation tile's bottom scrim + caption (name / @handle), a
 *           type-code chip top-left where the tile puts its #rank, and the
 *           interest control top-right where it puts its bookmark star.
 *   Back  — personality chart overlaid with the viewer's own, plus the name.
 *           The reason copy is dropped: at tile width it wraps to four or
 *           five lines and squeezes the chart out.
 *
 * The flip itself is the app's existing rule, identical to
 * profile/BioPersonaFlipCard.jsx and SwipeCard's gallery face: perspective on
 * the wrapper, preserve-3d on the rotating layer, backface-visibility hidden,
 * rotateY(180deg) — timed by --motion-flip / --motion-ease.
 *
 * Props:
 *   person      {object}    { user_id, display_name, handle, avatar_url, type_code, vector, highlight_axis, reason }
 *   myVector    {number[]|null}  caller's own 5-axis vector for overlay comparison
 *   onClick     {Function}  optional override for name/profile navigation
 *   onInterest  {Function}  called when the interest button is pressed
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import PentagonChart from './PentagonChart.jsx'
import { getPersonReportImage } from '../api/people.js'
import {
  photoCardShellStyle,
  photoCardImageStyle,
  photoCardScrimStyle,
  photoCardCaptionStyle,
  photoCardTitleStyle,
  photoCardSubtitleStyle,
} from './photoCardShell.js'
import styles from './PersonCard.module.css'

export default function PersonCard({ person, myVector, onClick, onInterest }) {
  const navigate = useNavigate()

  const [isFlipped, setIsFlipped] = useState(false)
  // Blocks a second tap while the card is mid-rotation, so rapid taps cannot
  // desync the face from the state.
  const flippingRef = useRef(false)
  const flipTimerRef = useRef(null)

  const [image, setImage] = useState(null)
  const [imageFailed, setImageFailed] = useState(false)

  // Lazy image fetch. getPersonReportImage() resolves null on 404 (no public
  // report image) — that is a terminal state, not an error to retry.
  useEffect(() => {
    let cancelled = false
    setImage(null)
    setImageFailed(false)
    getPersonReportImage(person.user_id).then(data => {
      if (cancelled) return
      if (data?.image_data) {
        setImage(`data:${data.mime_type || 'image/png'};base64,${data.image_data}`)
      } else {
        setImageFailed(true)
      }
    })
    return () => { cancelled = true }
  }, [person.user_id])

  useEffect(() => () => {
    if (flipTimerRef.current) clearTimeout(flipTimerRef.current)
  }, [])

  function flipDurationMs() {
    if (typeof window === 'undefined') return 500
    const raw = getComputedStyle(document.documentElement)
      .getPropertyValue('--motion-flip').trim()
    const parsed = parseFloat(raw)
    return Number.isFinite(parsed) ? parsed : 500
  }

  function handleFlip(e) {
    // The name owns its own click (navigates to the profile).
    if (e.target.closest('[data-no-flip]')) return
    if (flippingRef.current) return
    flippingRef.current = true
    setIsFlipped(f => !f)
    flipTimerRef.current = setTimeout(() => {
      flippingRef.current = false
    }, flipDurationMs())
  }

  function handleInterestClick(e) {
    e.stopPropagation()
    onInterest?.(person)
  }

  // The feed marks the requester's own card (views_people.py). Undefined on
  // any older payload -> falsy -> existing overlay behaviour, unchanged.
  const isMe = !!person.is_me

  function goToProfile(e) {
    e.stopPropagation()
    if (onClick) onClick(person)
    else navigate(`/user/${person.user_id}`)
  }

  // Both faces sit on the shared tile surface; the shell already carries
  // position/aspect/radius/border/shadow, so each face only adds the 3-D bits.
  const faceBase = {
    position: 'absolute',
    inset: 0,
    backfaceVisibility: 'hidden',
    WebkitBackfaceVisibility: 'hidden',
    borderRadius: photoCardShellStyle.borderRadius,
    overflow: 'hidden',
    background: 'var(--color-surface)',
  }

  return (
    <article
      className={styles.flipWrap}
      style={photoCardShellStyle}
      onClick={handleFlip}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleFlip(e) }
      }}
      aria-label={`${person.display_name} 카드 뒤집기`}
      aria-pressed={isFlipped}
    >
      <div
        className={styles.flipInner}
        style={{ transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)' }}
      >
        {/* ── FRONT — report image + recommendation-tile caption ── */}
        <div style={faceBase} aria-hidden={isFlipped}>
          {image ? (
            <img
              src={image}
              alt={`${person.display_name}의 취향 리포트 이미지`}
              loading="lazy"
              style={photoCardImageStyle}
              draggable={false}
            />
          ) : (
            <div className={`${styles.imagePlaceholder} ${imageFailed ? '' : 'skeleton-shimmer'}`}>
              {imageFailed && <span className={styles.imagePlaceholderText}>이미지 없음</span>}
            </div>
          )}
          <div style={photoCardScrimStyle} />
          {person.type_code && (
            <div className={styles.typeBadge}>{person.type_code}</div>
          )}
          {/* Top-right circular control — same placement and treatment as the
              recommendation tile's bookmark star (ResultsPage ResultCard). */}
          <button
            type="button"
            data-no-flip="true"
            className={styles.interestBtn}
            onClick={handleInterestClick}
            aria-label={`${person.display_name}에게 관심 있어요`}
            title="관심 있어요"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21.2l7.8-7.7 1-1.1a5.5 5.5 0 0 0 0-7.8z" />
            </svg>
          </button>
          <div style={photoCardCaptionStyle}>
            <h2 style={photoCardTitleStyle}>{person.display_name}</h2>
            {person.handle && (
              <p style={photoCardSubtitleStyle}>@{person.handle}</p>
            )}
          </div>
        </div>

        {/* ── BACK — chart + name ──
            Other people's cards overlay the viewer's vector on theirs so the
            two shapes can be compared. The viewer's OWN card (is_me, set by
            the feed once it stopped excluding the requester) draws a single
            polygon: comparing someone to themselves would render two identical
            shapes on top of each other, and the legend would label both "나". */}
        <div
          style={{ ...faceBase, transform: 'rotateY(180deg)' }}
          className={styles.back}
          aria-hidden={!isFlipped}
        >
          <div className={styles.chartWrap}>
            <PentagonChart
              // Fallback to person.vector: is_me implies the feed returned a
              // my_vector, but a missing one must not blank the chart.
              myVector={myVector ?? person.vector ?? null}
              theirVector={isMe ? null : (person.vector ?? null)}
              highlightAxis={isMe ? null : (person.highlight_axis ?? null)}
              mini
              legend={!isMe}
              legendTheirsLabel={person.display_name}
            />
          </div>

          <div className={styles.nameRow}>
            <button
              type="button"
              data-no-flip="true"
              className={styles.nameBtn}
              onClick={goToProfile}
              aria-label={`${person.display_name} 프로필 보기`}
            >
              {person.display_name}
            </button>
            {/* Without this the single-polygon chart above reads as a bug
                ("why does this one card have no comparison?"). */}
            {isMe && <span className={styles.meBadge}>나</span>}
          </div>
        </div>
      </div>
    </article>
  )
}
