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
import EditCardForm from '../../components/profile/EditCardForm.jsx'
import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import PageTopControls from '../../components/PageTopControls.jsx'
import PageBackButton from '../../components/PageBackButton.jsx'
import btnStyles from '../../components/Button.module.css'
import styles from './AccountScreen.module.css'

export default function EditProfileScreen({ onLogout }) {
  const navigate = useNavigate()
  const { t } = useTranslation()

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
        setFetchError(err.message || t('profileEdit.profileLoadError'))
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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
      setSaveError(err?.message || t('profileEdit.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} t={t} onLogout={onLogout} />
        <div style={{
          display: 'flex', justifyContent: 'center',
          padding: 48, color: 'var(--color-text-dim)', fontSize: 14,
        }}>
          {t('profileEdit.loading')}
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className={styles.page}>
        <ScreenHeader navigate={navigate} t={t} onLogout={onLogout} />
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
      <ScreenHeader navigate={navigate} t={t} onLogout={onLogout} />

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '0 16px 24px' }}>

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
            background: 'color-mix(in srgb, var(--color-destructive) 8%, transparent)',
            border: '1px solid var(--color-destructive)',
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
            {t('profileEdit.saved')}
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
            {saving ? t('profileEdit.saving') : t('profileEdit.save')}
          </button>
        </div>

      </div>
      <div style={{ height: 24 }} />
    </div>
  )
}

/* ── Internal helpers ────────────────────────────────────────────────── */

function ScreenHeader({ navigate, t, onLogout }) {
  return (
    <>
      <PageBackButton onClick={() => navigate(-1)} />
      <PageLogoHeader />
      <PageTopControls onLogout={onLogout} />
      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px 0' }}>
        <h2 className={styles.headerTitle}>{t('profileEdit.title')}</h2>
      </div>
    </>
  )
}
