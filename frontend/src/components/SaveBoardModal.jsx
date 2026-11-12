import { useEffect, useRef, useState } from 'react'
import { updateProject, VerifyRequiredError } from '../api/projects.js'
import styles from './SaveBoardModal.module.css'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
import Modal from './Modal.jsx'
import { MONO, INK, LS_CAPS, LS_TIGHT } from './cardLanguage.js'
import { describeSaveError } from '../utils/apiError.js'

/**
 * SaveBoardModal — shown after report completion (or from re-entry banner).
 *
 * Props:
 *   projectId   — backend project ID (string)
 *   finalReport — report object; persona_type used to pre-fill name
 *   onSaved     — called with { name, visibility } after successful PATCH
 *   onClose     — called when user dismisses without saving
 *
 * API: PATCH /api/v1/projects/{projectId}/ { is_temp: false, name, visibility }
 * Built on the shared Modal component (DESIGN.md §8.10).
 */
export default function SaveBoardModal({ projectId, finalReport, onSaved, onClose }) {
  const { t, language } = useTranslation()
  const defaultName = localizeReport(finalReport, language)?.persona_type || t('board.defaultName')

  const [name, setName] = useState(defaultName)
  // FRONT-PEOPLE-FEED-1 (2026-09-03): defaults to public.
  //
  // The /people discovery feed only surfaces a user whose taste report lives on
  // a PUBLIC project (report_image sits on Project, next to private reports, so
  // the feed cannot serve private ones without leaking them). With the old
  // 'private' default, generating a persona image did nothing visible — the
  // board saved as private and the card never appeared, which is exactly the
  // "이미지를 만들었는데 발견 탭에 안 뜬다" report this changes.
  //
  // The toggle is unchanged and right here in the same dialog, so this only
  // moves which option is pre-selected — it never publishes silently.
  const [visibility, setVisibility] = useState('public')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const nameInputRef = useRef(null)

  // Autofocus the name input — after Modal's own panel-focus effect (this
  // effect belongs to the parent SaveBoardModal, so it runs after Modal's
  // child effect), otherwise Modal's panelRef.focus() steals it back.
  useEffect(() => { nameInputRef.current?.focus() }, [])

  async function handleSave() {
    const trimmed = name.trim()
    if (!trimmed || saving) return
    setSaving(true)
    setError(null)
    try {
      await updateProject(projectId, { is_temp: false, name: trimmed, visibility })
      onSaved({ name: trimmed, visibility })
    } catch (err) {
      if (err instanceof VerifyRequiredError) {
        // Global VerifyGateModal is already mounted via the
        // 'archithon:verify-required' event dispatched by updateProject.
        // Leave this sheet open (not onClose()) so the user can retry the
        // save after verifying — keeps their name/visibility choices intact.
        setSaving(false)
        return
      }
      const { reason, code } = describeSaveError(err)
      // Raw failure for debugging - status / detail / name only, never tokens.
      console.warn('[SaveBoardModal] save failed', { status: err?.status, detail: err?.data?.detail, name: err?.name })
      const base = reason === 'unknown' ? t('board.saveError') : t(`board.saveError_${reason}`)
      setError(`${base} (${code})`)
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      ariaLabel={t('board.saveTitle')}
      closeLabel={t('modalB3.close')}
      zIndex={1000}
      closeOnEscape={false}
    >
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 18 }}>
        <span style={{
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: LS_CAPS,
          color: INK.mid,
        }}>
          {t('board.saveStamp')}
        </span>
      </div>

      <h2 style={{
        margin: '0 0 10px',
        textAlign: 'center',
        fontSize: 18,
        fontWeight: 700,
        letterSpacing: LS_TIGHT,
        lineHeight: 1.35,
        color: 'var(--color-text)',
      }}>
        {t('board.saveTitle')}
      </h2>

      <p style={{
        margin: 0,
        textAlign: 'center',
        fontSize: 13,
        lineHeight: 1.55,
        color: 'var(--color-text-muted)',
        wordBreak: 'keep-all',
        textWrap: 'balance',
      }}>
        {t('board.saveSubtitle')}
      </p>

      <div style={{ marginTop: 22 }}>
        {/* Board name input */}
        <label className={styles.label} htmlFor="save-board-name">
          {t('board.nameLabel')}
        </label>
        <input
          id="save-board-name"
          ref={nameInputRef}
          className={styles.input}
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          maxLength={200}
          placeholder={t('board.namePlaceholder')}
        />

        {/* Visibility toggle */}
        <span className={styles.label}>{t('board.visibilityLabel')}</span>
        <div className={styles.toggleRow}>
          {[
            { value: 'private', labelKey: 'board.private' },
            { value: 'public',  labelKey: 'board.public' },
          ].map(opt => (
            <button
              key={opt.value}
              type="button"
              className={[
                styles.toggleBtn,
                visibility === opt.value ? styles.toggleBtnActive : '',
              ].join(' ')}
              onClick={() => setVisibility(opt.value)}
            >
              {t(opt.labelKey)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className={styles.error} role="alert">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" fill="currentColor" />
            <path d="M8.5 8.5l7 7M15.5 8.5l-7 7" stroke="var(--color-surface)" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          <span>{error}</span>
        </p>
      )}

      <div className={styles.choices}>
        <div className={styles.moons} aria-hidden="true">
          <div className={`${styles.moon} ${styles.moonLeft}`}><div className={styles.blob} /></div>
          <div className={`${styles.moon} ${styles.moonRight}`}><div className={styles.blob} /></div>
        </div>
        <div className={styles.row}>
          <button
            type="button"
            className={styles.pill}
            onClick={handleSave}
            disabled={saving || !name.trim()}
          >
            {saving ? (
              <>
                <span className={styles.spinner} aria-hidden="true" />
                {t('board.saving')}
              </>
            ) : t('board.save')}
          </button>
        </div>
      </div>
    </Modal>
  )
}
