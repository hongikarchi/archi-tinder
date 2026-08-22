/**
 * PersonCard.jsx
 * Discovery card for a single user in the people feed.
 *
 * Props:
 *   person      {object}    { user_id, display_name, handle, avatar_url, type_code, vector, highlight_axis, reason }
 *   myVector    {number[]|null}  caller's own 5-axis vector for overlay comparison
 *   onClick     {Function}  called when card body is clicked (navigates to user profile)
 *   onInterest  {Function}  called when "관심 있어요" button is clicked (toast only)
 */

import { useNavigate } from 'react-router-dom'
import PentagonChart from './PentagonChart.jsx'
import { TYPE_LABELS } from '../constants/personalityTypes.js'
import styles from './PersonCard.module.css'

export default function PersonCard({ person, myVector, onClick, onInterest }) {
  const navigate = useNavigate()

  function handleCardClick(e) {
    // Don't navigate when clicking the interest button
    if (e.target.closest('[data-interest-btn]')) return
    if (onClick) {
      onClick(person)
    } else {
      navigate(`/user/${person.user_id}`)
    }
  }

  function handleInterestClick(e) {
    e.stopPropagation()
    onInterest?.(person)
  }

  const typeLabel = person.type_code ? (TYPE_LABELS[person.type_code] || person.type_code) : null

  return (
    <article
      className={styles.card}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(e) }}
      aria-label={`${person.display_name} 프로필 보기`}
    >
      {/* Top: avatar + name + handle + type badge */}
      <header className={styles.cardHeader}>
        <div className={styles.avatarWrap}>
          {person.avatar_url ? (
            <img
              src={person.avatar_url}
              alt={`${person.display_name} 아바타`}
              className={styles.avatar}
            />
          ) : (
            <div className={styles.avatarPlaceholder} aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
              </svg>
            </div>
          )}
        </div>

        <div className={styles.identity}>
          <span className={styles.displayName}>{person.display_name}</span>
          {person.handle && (
            <span className={styles.handle}>@{person.handle}</span>
          )}
        </div>

        {person.type_code && (
          <span className={styles.typeBadge} title={typeLabel || undefined}>
            {person.type_code}
          </span>
        )}
      </header>

      {/* Center: pentagon chart */}
      <div className={styles.chartWrap}>
        <PentagonChart
          myVector={myVector ?? null}
          theirVector={person.vector ?? null}
          highlightAxis={person.highlight_axis ?? null}
          mini={true}
          size={140}
        />
      </div>

      {/* Bottom: reason copy + interest button */}
      <footer className={styles.cardFooter}>
        {person.reason && (
          <p className={styles.reason}>{person.reason}</p>
        )}

        <button
          type="button"
          className={styles.interestBtn}
          data-interest-btn="true"
          onClick={handleInterestClick}
          aria-label={`${person.display_name}에게 관심 있어요`}
        >
          관심 있어요
        </button>
      </footer>
    </article>
  )
}
