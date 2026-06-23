import { useState } from 'react'
import { updateProject } from '../api/projects.js'
import styles from './SaveBoardModal.module.css'

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
  const defaultName = finalReport?.persona_type || '내 건축 취향 보드'

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
      setError(err?.message || '저장에 실패했어요. 다시 시도해주세요.')
      setSaving(false)
    }
  }

  // Close on backdrop click
  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className={styles.backdrop} onClick={handleBackdropClick}>
      <div className={styles.sheet} role="dialog" aria-modal="true" aria-label="보드 저장하기">
        {/* Swipe handle — mobile only */}
        <div className={styles.handle} />

        <h2 className={styles.title}>보드 저장하기</h2>
        <p className={styles.subtitle}>
          이 취향 분석 결과를 보드로 저장해두세요
        </p>

        {/* Board name input */}
        <label className={styles.label} htmlFor="save-board-name">
          보드 이름
        </label>
        <input
          id="save-board-name"
          className={styles.input}
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          maxLength={200}
          placeholder="보드 이름을 입력하세요"
          autoFocus
        />

        {/* Visibility toggle */}
        <span className={styles.label}>공개 설정</span>
        <div className={styles.toggleRow}>
          {[
            { value: 'private', label: '비공개' },
            { value: 'public',  label: '공개' },
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
              {opt.label}
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
            {saving ? '저장 중...' : '저장하기'}
          </button>
          <button className={styles.skipBtn} onClick={onClose}>
            나중에
          </button>
        </div>
      </div>
    </div>
  )
}
