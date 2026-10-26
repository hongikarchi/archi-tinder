import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useImageTelemetry } from '../../hooks/useImageTelemetry.js'
import { getProjectReportImage } from '../../api/projects.js'
import { useTranslation } from '../../i18n/index.js'
import { safeImageMime } from '../../utils/imageMime.js'
import s from './BoardCard.module.css'

/**
 * BoardCard — simple 3:4 tile for the profile boards grid.
 *   cover (persona image -> building cover -> gradient placeholder)
 *   + bottom gradient + name (2-line clamp) + one meta line
 *   "공개 · 건물 N개" / "비공개 · 건물 N개".
 *
 * Tap navigates to /board/<id>. In select mode (P6 bulk edit, owner) a tap
 * toggles selection instead and a selection circle shows top-right.
 *
 * Props: board, isOwner, selectMode, isSelected, onSelectToggle(board_id),
 *   ownerLabel (optional '@handle' -- Liked tab: shown in place of the
 *   public/private word, since every liked board is someone else's public one).
 */
export default function BoardCard({
  board,
  isOwner = false,
  selectMode = false,
  isSelected = false,
  onSelectToggle = () => {},
  ownerLabel = '',
}) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const isPrivate = board.visibility === 'private'
  const count = board.building_count ?? 0
  const countText = t(count === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: count })
  const meta = `${ownerLabel || t(isPrivate ? 'board.private' : 'board.public')} · ${countText}`

  // FRONT-PEOPLE-THUMB-1: the cover is the board's PERSONA REPORT image when it
  // has one; the building cover stays as the fallback. Fetched lazily because
  // the board list only carries a pointer (Project.report_image is base64 TEXT
  // and the list holds up to 50 boards).
  const [personaImage, setPersonaImage] = useState(null)

  useEffect(() => {
    if (!board.has_report_image) {
      setPersonaImage(null)
      return
    }
    let cancelled = false
    getProjectReportImage(board.board_id).then(data => {
      if (cancelled) return
      // null = no image / not visible to this caller -> keep the fallback.
      if (data?.image_data) {
        setPersonaImage(`data:${safeImageMime(data.mime_type)};base64,${data.image_data}`)
      }
    })
    return () => { cancelled = true }
  }, [board.board_id, board.has_report_image])

  const coverSrc = personaImage || board.cover_image_url || ''

  const { onLoad: coverOnLoad, onError: coverOnError } = useImageTelemetry({
    buildingId: board.board_id,
    context: 'user_profile_board_cover',
  })

  function handleClick() {
    if (selectMode) {
      onSelectToggle(board.board_id)
      return
    }
    navigate('/board/' + board.board_id)
  }

  return (
    <div
      className={s.tile}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-pressed={selectMode && isOwner ? isSelected : undefined}
      aria-label={board.name}
      onKeyDown={e => {
        if (e.target !== e.currentTarget) return
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleClick()
        }
      }}
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '3 / 4',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        cursor: 'pointer',
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border-soft)',
        boxShadow: isSelected ? '0 0 0 3px var(--accent-1)' : '0 8px 20px rgba(0,0,0,0.25)',
        userSelect: 'none', WebkitUserSelect: 'none', touchAction: 'manipulation',
      }}
    >
      {coverSrc ? (
        <img
          src={coverSrc}
          alt={board.name}
          loading="lazy"
          onLoad={coverOnLoad}
          onError={coverOnError}
          style={{
            position: 'absolute', inset: 0,
            width: '100%', height: '100%',
            objectFit: 'cover', objectPosition: 'center',
            display: 'block',
          }}
        />
      ) : (
        // Gradient placeholder for boards with no cover.
        <div
          aria-hidden
          style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(135deg, color-mix(in srgb, var(--accent-1) 22%, transparent) 0%, color-mix(in srgb, var(--accent-2) 18%, transparent) 50%, rgba(15,15,15,0.85) 100%)',
          }}
        />
      )}

      {/* Bottom gradient for legibility */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.2) 50%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {/* Select mode: selection circle (owner only), top-right */}
      {selectMode && isOwner && (
        <div
          aria-label={isSelected ? t('board.selected') : t('board.notSelected')}
          style={{
            position: 'absolute', top: 12, right: 12,
            width: 28, height: 28, borderRadius: '50%',
            border: isSelected ? 'none' : '2px solid rgba(255,255,255,0.9)',
            background: isSelected ? 'var(--accent-1)' : 'rgba(0,0,0,0.4)',
            backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s cubic-bezier(0.4,0,0.2,1), border 0.15s cubic-bezier(0.4,0,0.2,1)',
            pointerEvents: 'none',
          }}
        >
          {isSelected && (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="#fff" strokeWidth="2.5"
                 strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>
      )}

      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '16px 18px 18px',
      }}>
        <h2 style={{
          color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1.3,
          margin: '0 0 4px',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {board.name}
        </h2>
        <p style={{
          color: 'rgba(255,255,255,0.7)', fontSize: 'var(--fs-caption)',
          margin: 0,
        }}>
          {meta}
        </p>
      </div>
    </div>
  )
}
