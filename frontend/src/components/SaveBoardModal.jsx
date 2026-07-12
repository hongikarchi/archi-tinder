import { useState } from 'react'
import { updateProject } from '../api/projects.js'
import styles from './SaveBoardModal.module.css'
import { useTranslation } from '../i18n/index.js'

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
 * DESIGN.md §8.10 — Bottom Sheet (mobile ≤768px) / Centered Modal (desktop ≥769px)
 */
export default function SaveBoardModal({ projectId, finalReport, onSaved, onClose }) {
  const { t } = useTranslation()
  const defaultName = finalReport?.persona_type || t('board.defaultName')

  const [name, setName] = useState(defaultName)
  const [visibility, setVisibility] = useState('private')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSave() {
    const trimmed = name.trim()
    if (!trimmed || saving) return
    setSaving(true)
    setError(null)
    try {
      await updateProject(projectId, { is_temp: false, name: trimmed, visibility })
      onSaved({ name: trimmed, visibility })
    } catch (err) {
      setError(err?.message || t('board.saveError'))
      setSaving(false)
    }
  }

  // Close on backdrop click
  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.sheet} role="dialog" aria-modal="true" aria-label={t('board.saveTitle')}>
        {/* Swipe handle — mobile only */}
        <div className={styles.handle} />

        <h2 className={styles.title}>{t('board.saveTitle')}</h2>
        <p className={styles.subtitle}>
          {t('board.saveSubtitle')}
        </p>

        {/* Board name input */}
        <label className={styles.label} htmlFor="save-board-name">
          {t('board.nameLabel')}
        </label>
        <input
          id="save-board-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          maxLength={200}
          placeholder={t('board.namePlaceholder')}
          autoFocus
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

        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.actions}>
          <button
            className={styles.saveBtn}
            onClick={handleSave}
            disabled={saving || !name.trim()}
          >
            {saving ? t('board.saving') : t('board.save')}
          </button>
          <button className={styles.skipBtn} onClick={onClose}>
            {t('board.later')}
          </button>
        </div>
      </div>
    </div>
  )
}
