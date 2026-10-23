import { useState, useEffect, useRef } from 'react'
import styles from './BoardCover.module.css'

/**
 * BoardCover — cover card for BoardDetailPage (FULL-REPORT-UI-1 WP4,
 * mock `boardDetail`): aspect 4:3, radius-lg, soft border, E5 shadow, bottom
 * scrim, board name (24px bold, white; an inline input in owner edit mode)
 * + meta line (12px, white 72%).
 *
 * Image chain is decided by the caller (persona image -> first building cover);
 * with no image a neutral accent gradient face is rendered so the title still
 * has a surface to sit on.
 *
 * ownerChips (owner only, independent of edit mode): { isPrivate, onToggleVisibility,
 * onDelete, labels: { makePublic, makePrivate, nowPublic, nowPrivate, deleteBoard, deleteConfirm,
 * deleteConfirmAria } } -> glass chips top-right (lock) and top-left (X, 2-step).
 */

const CHIP_STROKE = 'rgba(255,255,255,0.85)'
// 44px transparent hit area around a 28px visual circle.
const hitStyle = {
  position: 'absolute', top: 4, width: 44, height: 44, padding: 0, margin: 0,
  display: 'flex', alignItems: 'center', background: 'transparent', border: 0,
  cursor: 'pointer', touchAction: 'manipulation', zIndex: 2,
  textAlign: 'left', whiteSpace: 'nowrap',
}

function OwnerChips({ chips }) {
  const [confirming, setConfirming] = useState(false)
  const timerRef = useRef(null)
  const delRef = useRef(null)
  const flashTimerRef = useRef(null)
  const [flash, setFlash] = useState(null) // 'public' | 'private' | null
  const { isPrivate, onToggleVisibility, onDelete, labels } = chips

  useEffect(() => () => { clearTimeout(timerRef.current); clearTimeout(flashTimerRef.current) }, [])
  // Click-outside cancels the pending confirm.
  useEffect(() => {
    if (!confirming) return
    function onDoc(e) {
      if (delRef.current && !delRef.current.contains(e.target)) {
        clearTimeout(timerRef.current)
        setConfirming(false)
      }
    }
    document.addEventListener('pointerdown', onDoc)
    return () => document.removeEventListener('pointerdown', onDoc)
  }, [confirming])

  // Label only while it still matches the (optimistic) state; a failed toggle reverts it.
  const showFlash = !!flash && (flash === 'private') === isPrivate

  const glass = {
    background: 'var(--color-scrim-soft)',
    backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
    height: 28, minWidth: 28, boxSizing: 'border-box',
    transition: 'padding var(--motion-normal, .18s) var(--motion-ease, cubic-bezier(0.4,0,0.2,1))',
  }

  return (
    <>
      <button
        ref={delRef}
        type="button"
        aria-label={confirming ? labels.deleteConfirmAria : labels.deleteBoard}
        onClick={e => {
          e.stopPropagation()
          if (!confirming) {
            clearTimeout(timerRef.current)
            setConfirming(true)
            timerRef.current = setTimeout(() => setConfirming(false), 3000)
          } else {
            clearTimeout(timerRef.current)
            setConfirming(false)
            onDelete?.()
          }
        }}
        style={{ ...hitStyle, left: 4, width: 'auto', minWidth: 44, justifyContent: 'flex-start', paddingLeft: 8, paddingRight: confirming ? 4 : 0 }}
      >
        <span style={{
          ...glass,
          justifyContent: 'flex-start', gap: 0,
          width: confirming ? 'auto' : 28, flexShrink: 0,
          padding: 0,
          borderRadius: 999,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
               style={{ flex: '0 0 14px', margin: '0 7px' }}
               stroke={confirming ? 'var(--color-destructive)' : CHIP_STROKE}
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          {confirming && (
            <span className={styles.chipLabel} style={{
              fontSize: 'var(--fs-caption)', color: 'var(--color-destructive)',
              fontWeight: 600, whiteSpace: 'nowrap', textAlign: 'left', lineHeight: 1,
              paddingRight: 12,
            }}>
              {labels.deleteConfirm}
            </span>
          )}
        </span>
      </button>
      <button
        type="button"
        aria-label={isPrivate ? labels.makePublic : labels.makePrivate}
        onClick={e => {
          e.stopPropagation()
          const next = isPrivate ? 'public' : 'private'
          clearTimeout(flashTimerRef.current)
          setFlash(next)
          flashTimerRef.current = setTimeout(() => setFlash(null), 2000)
          onToggleVisibility?.(next)
        }}
        style={{ ...hitStyle, right: 4, width: 'auto', minWidth: 44, justifyContent: 'flex-end', paddingRight: 8 }}
      >
        <span style={{
          ...glass,
          justifyContent: 'flex-start', gap: 0,
          width: showFlash ? 'auto' : 28, flexShrink: 0,
          padding: 0,
          borderRadius: 999,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
               style={{ flex: '0 0 14px', margin: '0 7px' }}
               stroke={CHIP_STROKE} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d={isPrivate ? 'M7 11V7a5 5 0 0 1 10 0v4' : 'M7 11V7a5 5 0 0 1 9.9-1'} />
          </svg>
          {showFlash && (
            <span key={flash} className={styles.chipLabel} style={{
              fontSize: 'var(--fs-caption)', color: CHIP_STROKE,
              fontWeight: 600, whiteSpace: 'nowrap', textAlign: 'left', lineHeight: 1,
              paddingRight: 12,
            }}>
              {isPrivate ? labels.nowPrivate : labels.nowPublic}
            </span>
          )}
        </span>
      </button>
    </>
  )
}

export default function BoardCover({
  imageUrl, alt, title, meta, rightSlot,
  titleEditable = false, titleDraft = '', onTitleDraftChange, onTitleCommit, onTitleCancel,
  titleSaving = false, titleLabel,
  ownerChips = null,
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '4 / 3',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        border: '1px solid var(--color-border-soft)',
        boxShadow: '0 8px 24px rgba(0,0,0,.12)',
        background: [
          'radial-gradient(120% 120% at 15% 10%, color-mix(in srgb, var(--accent-1) 18%, var(--color-surface)) 0%, transparent 60%)',
          'radial-gradient(120% 120% at 90% 95%, color-mix(in srgb, var(--accent-2) 16%, var(--color-surface)) 0%, transparent 60%)',
          'var(--color-surface-2)',
        ].join(', '),
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={alt || ''}
          fetchpriority="high"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
          }}
        />
      )}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: imageUrl
            ? 'linear-gradient(to top, rgba(0,0,0,.78) 0%, rgba(0,0,0,.2) 50%, rgba(0,0,0,0) 75%)'
            : 'linear-gradient(to top, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 65%)',
        }}
      />
      {ownerChips && <OwnerChips chips={ownerChips} />}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 0, padding: '18px 18px 16px',
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12,
      }}>
        <div style={{ minWidth: 0, flex: titleEditable ? 1 : undefined }}>
        {titleEditable ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '0 0 4px' }}>
            <input
              value={titleDraft}
              onChange={e => onTitleDraftChange?.(e.target.value)}
              onKeyDown={e => {
                // IME guard: Enter/Escape while composing (Korean) must not commit/cancel.
                if (e.nativeEvent?.isComposing || e.keyCode === 229) return
                if (e.key === 'Enter') { e.preventDefault(); onTitleCommit?.() }
                else if (e.key === 'Escape') onTitleCancel?.()
              }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              readOnly={titleSaving}
              maxLength={100}
              aria-label={titleLabel}
              style={{
                flex: 1,
                minWidth: 0,
                boxSizing: 'border-box',
                padding: '0 0 2px',
                margin: 0,
                color: '#fff',
                fontFamily: 'inherit',
                fontSize: 'var(--fs-title)',
                fontWeight: 'var(--fw-bold)',
                lineHeight: 1.2,
                background: 'transparent',
                border: 0,
                borderRadius: 0,
                borderBottom: `1px solid ${focused ? 'var(--accent-1)' : 'rgba(255,255,255,.6)'}`,
                outline: 'none',
              }}
            />
          </div>
        ) : (
          <h1 style={{
            margin: '0 0 4px',
            color: '#fff',
            fontSize: 'var(--fs-title)',
            fontWeight: 'var(--fw-bold)',
            lineHeight: 1.2,
            wordBreak: 'keep-all',
          }}>
            {title}
          </h1>
        )}
        {meta && (
          <p style={{ margin: 0, color: 'rgba(255,255,255,.72)', fontSize: 'var(--fs-caption)' }}>
            {meta}
          </p>
        )}
        </div>
        {rightSlot && <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>{rightSlot}</div>}
      </div>
    </div>
  )
}
