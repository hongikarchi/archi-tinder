/**
 * EditProfileModal.jsx
 * Centered modal (DESIGN.md §8.10 desktop) wrapping EditCardForm.
 * Follows VerifyGateModal pattern: role/aria-modal/backdrop-click/ESC.
 *
 * Props:
 *   user     — UserProfile object passed to EditCardForm as initial state
 *   onClose  — close without saving
 *   onSaved  — called with the updated profile after a successful PATCH
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { updateMyProfile } from '../api/profiles.js'
import EditCardForm from './profile/EditCardForm.jsx'

export default function EditProfileModal({ user, onClose, onSaved }) {
  // patch holds the latest value from EditCardForm onChange
  const [patch, setPatch] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  // Track whether the user made any change
  const hasPatch = patch !== null

  // ESC key closes the modal
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  async function handleSave() {
    if (!hasPatch || saving) return
    setSaving(true)
    setError(null)
    try {
      // Only send editable fields; NEVER send persona_summary or read-only fields.
      const payload = {
        display_name: patch.display_name,
        bio: patch.bio,
        mbti: patch.mbti,
        external_links: patch.external_links,
      }
      const updated = await updateMyProfile(payload)
      // Merge server-normalized response into parent state
      onSaved(updated)
      onClose()
    } catch (err) {
      setError(err?.message || 'Failed to save profile. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // Ref for backdrop click distinction
  const backdropRef = useRef(null)

  return (
    <div
      ref={backdropRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-profile-title"
      onClick={(e) => { if (e.target === backdropRef.current) onClose() }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10200,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(94vw, 480px)',
          maxHeight: '85vh',
          overflowY: 'auto',
          background: 'var(--color-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border)',
          color: 'var(--color-text)',
          boxShadow: '0 18px 40px rgba(0,0,0,0.20)',
        }}
      >
        {/* Modal header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 24px 16px',
          borderBottom: '1px solid var(--color-border)',
          position: 'sticky',
          top: 0,
          background: 'var(--color-surface)',
          zIndex: 1,
        }}>
          <h2
            id="edit-profile-title"
            style={{ fontSize: 17, fontWeight: 700, margin: 0, color: 'var(--color-text)' }}
          >
            Edit Profile
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              border: '1px solid var(--color-border-soft)',
              background: 'transparent',
              color: 'var(--color-text-muted)',
              fontSize: 18,
              lineHeight: 1,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: 'inherit',
            }}
          >
            ✕
          </button>
        </div>

        {/* Form body */}
        <div style={{ padding: '20px 24px' }}>
          <EditCardForm
            user={user}
            onChange={setPatch}
          />
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            margin: '0 24px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(215,58,73,0.08)',
            border: '1px solid rgba(215,58,73,0.28)',
            color: 'var(--color-destructive)',
            fontSize: 13,
            lineHeight: 1.45,
          }}>
            {error}
          </div>
        )}

        {/* Footer — Cancel / Save */}
        <div style={{
          display: 'flex',
          gap: 10,
          padding: '16px 24px 20px',
          borderTop: '1px solid var(--color-border)',
          position: 'sticky',
          bottom: 0,
          background: 'var(--color-surface)',
          zIndex: 1,
        }}>
          {/* Cancel — ghost button (DESIGN.md §8.3) */}
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            style={{
              flex: 1,
              minHeight: 44,
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
              background: 'transparent',
              color: 'var(--color-text)',
              fontSize: 14,
              fontWeight: 500,
              cursor: saving ? 'default' : 'pointer',
              opacity: saving ? 0.5 : 1,
              fontFamily: 'inherit',
            }}
          >
            Cancel
          </button>
          {/* Save — primary CTA (DESIGN.md §8.1) */}
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !hasPatch}
            style={{
              flex: 1,
              minHeight: 44,
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: saving || !hasPatch
                ? 'var(--color-surface-2)'
                : 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
              color: saving || !hasPatch ? 'var(--color-text-muted)' : '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: saving || !hasPatch ? 'default' : 'pointer',
              fontFamily: 'inherit',
              transition: 'background var(--motion-normal) var(--motion-ease), color var(--motion-normal) var(--motion-ease)',
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
