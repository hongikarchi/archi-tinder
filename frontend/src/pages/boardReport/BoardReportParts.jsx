import { useEffect, useRef, useState } from 'react'
import { useTranslation } from '../../i18n/index.js'
import { userHandle } from '../../utils/userIdentity.js'
import BuildingTile from '../boardDetail/BuildingTile'
import tileStyles from '../boardDetail/BuildingTile.module.css'
import r from './boardReport.module.css'

/* Presentational pieces of the merged board report page (BoardReportPage).
 * All state lives in the page / hooks; these only render slots handed to
 * PersonaReportBody (topNotice, metaSlot, titleSlot, actionsSlot, likedSlot,
 * footerSlot). */

const ICON = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

export function IconEdit() {
  return (
    <svg {...ICON}>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  )
}
export function IconClose() {
  return <svg {...ICON}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
}
export function IconShare() {
  return (
    <svg {...ICON}>
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" /><polyline points="16 6 12 2 8 6" /><line x1="12" y1="2" x2="12" y2="15" />
    </svg>
  )
}
function IconCheck() {
  return <svg {...ICON}><polyline points="20 6 9 17 4 12" /></svg>
}
function IconHeart({ filled }) {
  return (
    <svg {...ICON} width="16" height="16" fill={filled ? 'currentColor' : 'none'} strokeWidth="2.2">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

/** Soft notice row above the hero: stale / legacy report + manual regenerate. */
export function ReportNotice({ text, busy, failed, onRegenerate }) {
  const { t } = useTranslation()
  return (
    <div className={r.notice} role="status">
      <span className={r.noticeText}>
        {text}
        {failed && <span className={r.noticeFail}>{t('persona.regenFail')}</span>}
      </span>
      <button type="button" className={r.noticeBtn} onClick={onRegenerate} disabled={busy}>
        {busy ? t('persona.reportRegenerating') : t('persona.regenNow')}
      </button>
    </div>
  )
}

/** Owner meta row: lock/unlock icon pill (flashes its state label for 2s on toggle) · building count · ♥ count. */
export function OwnerMeta({ isPublic, buildingCount, reactionCount, onToggleVisibility, disabled }) {
  const { t } = useTranslation()
  const [flash, setFlash] = useState(null) // 'public' | 'private' | null
  const timerRef = useRef(null)
  useEffect(() => () => clearTimeout(timerRef.current), [])
  const countLabel = t(buildingCount === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: buildingCount })
  // Label only while it still matches the (optimistic) state; a failed toggle reverts it.
  const showFlash = !!flash && (flash === 'public') === isPublic
  return (
    <p style={{ margin: '0 0 20px', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, color: 'var(--color-text)', fontSize: 'var(--fs-caption)' }}>
      <button
        type="button"
        className={r.visBtn}
        onClick={() => {
          const next = isPublic ? 'private' : 'public'
          clearTimeout(timerRef.current)
          setFlash(next)
          timerRef.current = setTimeout(() => setFlash(null), 2000)
          onToggleVisibility(next)
        }}
        disabled={disabled}
        aria-label={isPublic ? t('board.makePrivate') : t('board.makePublic')}
      >
        <span className={r.visPill}>
          <svg className={r.visIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
               stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d={isPublic ? 'M7 11V7a5 5 0 0 1 9.9-1' : 'M7 11V7a5 5 0 0 1 10 0v4'} />
          </svg>
          {showFlash && (
            <span key={flash} className={r.visLabel}>
              {isPublic ? t('board.nowPublic') : t('board.nowPrivate')}
            </span>
          )}
        </span>
      </button>
      <span>{countLabel} · ♥ {reactionCount}</span>
    </p>
  )
}

/** Viewer meta row: owner link "@handle ›" · public · building count. */
export function ViewerMeta({ owner, isPublic, buildingCount, onOpenOwner }) {
  const { t } = useTranslation()
  const countLabel = t(buildingCount === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: buildingCount })
  const handle = userHandle(owner)
  return (
    <p style={{ margin: '0 0 20px', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, color: 'var(--color-text)', fontSize: 'var(--fs-caption)' }}>
      {owner?.user_id && handle && (
        <button type="button" className={r.ownerLink} onClick={onOpenOwner} aria-label={handle}>
          <img className={r.avatar} src={owner.avatar_url || ''} alt="" />
          <span className={r.ownerName}>@{handle}</span>
          <span aria-hidden="true">›</span>
        </button>
      )}
      <span>· {isPublic ? t('board.public') : t('board.private')} · {countLabel}</span>
    </p>
  )
}

/** Owner tools row: continue exploring · edit toggle · share. */
export function OwnerTools({ onResume, resumeDisabled, isEditMode, editDisabled, onToggleEdit, onShare }) {
  const { t } = useTranslation()
  return (
    <div className={r.tools}>
      {onResume && (
        <button type="button" className={`${r.tool} ${r.toolDark}`} onClick={onResume} disabled={resumeDisabled}>
          {t('board.continueExploring')}
        </button>
      )}
      <button
        type="button"
        className={`${r.icon} ${isEditMode ? r.iconActive : ''}`}
        onClick={onToggleEdit}
        disabled={editDisabled}
        aria-label={isEditMode ? t('board.cancel') : t('board.editBoard')}
        aria-pressed={isEditMode}
      >
        {isEditMode ? <IconClose /> : <IconEdit />}
      </button>
      <button type="button" className={r.icon} onClick={onShare} aria-label={t('board.share')}>
        <IconShare />
      </button>
    </div>
  )
}

/** Viewer tools row: reaction pill + share. */
export function ViewerTools({ isReacted, reactionCount, pending, error, onToggleReaction, onShare }) {
  const { t } = useTranslation()
  return (
    <>
      <div className={r.tools}>
        <button
          type="button"
          className={`${r.tool} ${isReacted ? r.toolReacted : ''}`}
          onClick={onToggleReaction}
          disabled={pending}
          aria-pressed={isReacted}
        >
          <IconHeart filled={isReacted} />
          <span>{t('socialBoard.likeTaste', { n: reactionCount })}</span>
        </button>
        <button type="button" className={r.icon} onClick={onShare} aria-label={t('board.share')}>
          <IconShare />
        </button>
      </div>
      {error && <div className={r.toolError} role="alert">{error}</div>}
    </>
  )
}

/** Edit-mode title: board-name input; Enter / check saves, Escape cancels. */
export function TitleEdit({ value, onChange, onCommit, onCancel, canSave, busy }) {
  const { t } = useTranslation()
  return (
    <div className={r.titleEdit}>
      <input
        className={r.titleInput}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') { e.preventDefault(); if (canSave) onCommit() }
          else if (e.key === 'Escape') onCancel()
        }}
        maxLength={60}
        disabled={!!busy}
        aria-label={t('board.nameLabel')}
        placeholder={t('board.namePlaceholder')}
      />
      <button type="button" className={r.titleBtn} onClick={onCommit} disabled={!canSave || !!busy} aria-label={t('board.save')}>
        <IconCheck />
      </button>
    </div>
  )
}

/** Edit-mode liked buildings: selectable grid (the delete bar is EditActionBar). */
export function EditGrid({ buildings, selectedIds, onToggleSelect }) {
  const { t } = useTranslation()
  return (
    <section className={r.editSection}>
      <h2 className={r.editHead}>{t('detailB3.buildingsYouLiked')}</h2>
      <div className={tileStyles.grid}>
        {buildings.map(building => {
          const bid = building.image_id || building.canonical_bld_id || building.building_id || building.id
          return (
            <BuildingTile
              key={bid}
              building={building}
              isEditMode
              isSelected={selectedIds.has(bid)}
              onToggleSelect={onToggleSelect}
            />
          )
        })}
      </div>
      <div className={r.editPad} />
    </section>
  )
}

/** Quiet "delete board" link with inline confirm. */
export function DeleteFooter({ onDelete }) {
  const { t } = useTranslation()
  const [asking, setAsking] = useState(false)
  return (
    <div className={r.foot}>
      {asking ? (
        <div className={r.confirm} role="alertdialog" aria-label={t('board.deleteBoardAsk')}>
          <span className={r.confirmAsk}>{t('board.deleteBoardAsk')}</span>
          <button type="button" className={`${r.footLink} ${r.footStrong}`} onClick={onDelete}>{t('board.deleteOk')}</button>
          <button type="button" className={r.footLink} onClick={() => setAsking(false)}>{t('board.cancel')}</button>
        </div>
      ) : (
        <button type="button" className={r.footLink} onClick={() => setAsking(true)}>{t('board.deleteBoard')}</button>
      )}
    </div>
  )
}
