/**
 * PersonCard.jsx
 * Discovery card for a single user in the people feed (/people).
 *
 * FRONT-PEOPLE-CARD-1 (2026-08-25): image-front / flip-to-detail.
 *   Front — the user's taste-report architecture image, full-bleed. Nothing else.
 *   Back  — personality graph overlaid with the viewer's own, plus the name.
 *
 * The flip reuses the app's established rule, identical to
 * profile/BioPersonaFlipCard.jsx, profile/DescriptionAboutFlipCard.jsx and
 * SwipeCard's gallery face: perspective on the wrapper, preserve-3d on the
 * rotating layer, backface-visibility hidden on both faces, rotateY(180deg).
 * The duration/easing come from the tokens those files' literals match —
 * --motion-flip (500ms) and --motion-ease (cubic-bezier(0.4,0,0.2,1)).
 *
 * The image is fetched lazily per card: Project.report_image is base64 TEXT,
 * so the feed endpoint returns a pointer and this component resolves it.
 *
 * Props:
 *   person      {object}    { user_id, display_name, handle, avatar_url, type_code, vector, highlight_axis, reason }
 *   myVector    {number[]|null}  caller's own 5-axis vector for overlay comparison
 *   onClick     {Function}  optional override for name/profile navigation
 *   onInterest  {Function}  called when "관심 있어요" button is clicked (toast only)
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import PentagonChart from './PentagonChart.jsx'
import { getPersonReportImage } from '../api/people.js'
import { TYPE_LABELS } from '../constants/personalityTypes.js'
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
    // The name and the interest button own their own clicks.
    if (e.target.closest('[data-no-flip]')) return
    if (flippingRef.current) return
    flippingRef.current = true
    setIsFlipped(f => !f)
    flipTimerRef.current = setTimeout(() => {
      flippingRef.current = false
    }, flipDurationMs())
  }

  function goToProfile(e) {
    e.stopPropagation()
    if (onClick) onClick(person)
    else navigate(`/user/${person.user_id}`)
  }

  function handleInterestClick(e) {
    e.stopPropagation()
    onInterest?.(person)
  }

  const typeLabel = person.type_code ? (TYPE_LABELS[person.type_code] || person.type_code) : null

  const faceBase = {
    position: 'absolute', inset: 0,
    backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
    borderRadius: 'var(--radius-lg)',
    overflow: 'hidden',
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
  }

  return (
    <article
      className={styles.flipWrap}
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
        {/* ── FRONT — report image only ── */}
        <div style={faceBase} aria-hidden={isFlipped}>
          {image ? (
            <img
              src={image}
              alt={`${person.display_name}의 취향 리포트 이미지`}
              className={styles.reportImage}
              draggable={false}
            />
          ) : (
            <div className={`${styles.imagePlaceholder} ${imageFailed ? '' : 'skeleton-shimmer'}`}>
              {imageFailed && (
                <span className={styles.imagePlaceholderText}>이미지를 불러오지 못했어요</span>
              )}
            </div>
          )}
          <span className={styles.flipHint}>tap to compare</span>
        </div>

        {/* ── BACK — overlaid graph + name ── */}
        <div
          style={{ ...faceBase, transform: 'rotateY(180deg)' }}
          className={styles.back}
          aria-hidden={!isFlipped}
        >
          <button
            type="button"
            data-no-flip="true"
            className={styles.nameBtn}
            onClick={goToProfile}
            aria-label={`${person.display_name} 프로필 보기`}
          >
            {person.display_name}
            {person.handle && <span className={styles.handle}>@{person.handle}</span>}
          </button>

          {person.type_code && (
            <span className={styles.typeBadge} title={typeLabel || undefined}>
              {person.type_code}
            </span>
          )}

          <div className={styles.chartWrap}>
            <PentagonChart
              myVector={myVector ?? null}
              theirVector={person.vector ?? null}
              highlightAxis={person.highlight_axis ?? null}
              size={168}
              legend
              legendTheirsLabel={person.display_name}
            />
          </div>

          {person.reason && <p className={styles.reason}>{person.reason}</p>}

          <button
            type="button"
            data-no-flip="true"
            className={styles.interestBtn}
            onClick={handleInterestClick}
            aria-label={`${person.display_name}에게 관심 있어요`}
          >
            관심 있어요
          </button>
        </div>
      </div>
    </article>
  )
}
