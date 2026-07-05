/**
 * EditProfileScreen — /settings/edit-profile
 *
 * Full-screen settings child layout (same pattern as AccountScreen).
 * Edits: display_name, role, affiliation, bio, external_links.
 * Saves via PATCH /api/v1/users/me/ (updateMyProfile).
 *
 * Uses EditCardForm for all fields.
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe } from '../../api/client.js'
import { updateMyProfile } from '../../api/profiles.js'
import { IconBack } from '../../components/icons.jsx'
import EditCardForm from '../../components/profile/EditCardForm.jsx'
import btnStyles from '../../components/Button.module.css'
import styles from './AccountScreen.module.css'

export default function EditProfileScreen() {
  const navigate = useNavigate()

  const [me, setMe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  const [patch, setPatch] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const hasPatch = patch !== null

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setFetchError(null)
    getMe()
      .then(data => {
        if (cancelled) return
        setMe(data)
      })
      .catch(err => {
        if (cancelled) return
        setFetchError(err.message || '프로필을 불러올 수 없습니다.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  async function handleSave() {
    if (!hasPatch || saving) return
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      // SETTINGS-POLISH-1 §A.4 SAVE RULE: EditCardForm.onChange only includes
      // onboarding_role/role in the patch when a dropdown selection was made
      // (clearing legacy role text). An empty selection omits both keys so
      // the legacy free-text role is preserved untouched server-side — do
      // NOT hardcode `role: patch.role` here, that would always send an
      // (often blank) role and defeat the preservation rule.
      const payload = {
        display_name: patch.display_name,
        affiliation: patch.affiliation,
        bio: patch.bio,
        external_links: patch.external_links,
      }
      if ('onboarding_role' in patch) payload.onboarding_role = patch.onboarding_role
      if ('role' in patch) payload.role = patch.role
      await updateMyProfile(payload)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
      // Optionally navigate back to profile after save
      // navigate(-1)
    } catch (err) {
      setSaveError(err?.message || '저장에 실패했습니다. 다시 시도해주세요.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} />
        <div style={{
          display: 'flex', justifyContent: 'center',
          padding: 48, color: 'var(--color-text-dim)', fontSize: 14,
        }}>
          불러오는 중...
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} />
        <div style={{
          display: 'flex', justifyContent: 'center',
          padding: 48, color: 'var(--color-destructive)', fontSize: 14,
        }}>
          {fetchError}
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <ScreenHeader navigate={navigate} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>

        <EditCardForm
          user={me}
          onChange={setPatch}
        />

        {/* Error */}
        {saveError && (
          <div style={{
            marginTop: 16,
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(215,58,73,0.08)',
            border: '1px solid rgba(215,58,73,0.28)',
            color: 'var(--color-destructive)',
            fontSize: 13,
            lineHeight: 1.45,
          }}>
            {saveError}
          </div>
        )}

        {/* Success */}
        {saveSuccess && (
          <div style={{
            marginTop: 16,
            padding: '10px 14px',
            background: 'color-mix(in srgb, var(--accent-1) 10%, transparent)',
            border: '1px solid var(--accent-1)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 13,
            color: 'var(--accent-1)',
            fontWeight: 500,
          }}>
            프로필이 저장되었습니다.
          </div>
        )}

        {/* Save CTA */}
        <div style={{ marginTop: 24 }}>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !hasPatch}
            className={btnStyles.cta}
            style={{ width: '100%' }}
          >
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>

      </div>
      <div style={{ height: 24 }} />
    </div>
  )
}

/* ── Internal helpers ────────────────────────────────────────────────── */

function ScreenHeader({ navigate }) {
  return (
    <div className={styles.header}>
      <button
        type="button"
        onClick={() => navigate(-1)}
        aria-label="Back"
        className={styles.iconBtn}
      >
        <IconBack width={20} height={20} />
      </button>
      <h2 className={styles.headerTitle}>프로필 편집</h2>
      <div style={{ width: 44 }} />
    </div>
  )
}
