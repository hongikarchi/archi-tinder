/**
 * EditCardForm.jsx
 * Profile-edit form.
 * Edits our writable fields: display_name, onboarding_role (dropdown, replaces
 * the old free-text role input — SETTINGS-POLISH-1 §A), affiliation, bio,
 * external_links. Legacy free-text `role` is preserved (not editable here) —
 * see the commit() SAVE RULE below for the exact clear/preserve semantics.
 *
 * external_links shape (from backend model + serializer):
 *   dict { instagram?: string, email?: string, website?: string }
 * Internally we work with a flat array of { id, key, value } rows
 * and reduce to { instagram, email, website } on output.
 *
 * Props:
 *   user     — UserProfile object (display_name, role, onboarding_role, affiliation, bio, external_links)
 *   onChange — called with { display_name, [onboarding_role, role], affiliation, bio, external_links } on
 *              every change. onboarding_role/role are only present together (a
 *              selection clears legacy role) — see commit() for details.
 */

import { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { getRoles } from '../../api/meta.js'
import { useLanguage } from '../../hooks/useLanguage.js'
import { useTranslation } from '../../i18n/index.js'
import styles from './EditCardForm.module.css'

// Bio textarea auto-grow cap (SETTINGS-POLISH-1 §B). Floor (90px) comes from
// the .textarea min-height in EditCardForm.module.css.
const BIO_MAX_HEIGHT = 240

// Supported link keys — must match backend external_links dict keys.
// website is stored but not yet rendered in ProfileHero (noted in PR description).
const LINK_TYPES = {
  instagram: { label: 'Instagram', placeholder: '@handle' },
  email:     { label: 'Email',     placeholder: 'you@email.com' },
  website:   { label: 'Website',   placeholder: 'https://yoursite.com' },
}

/** Convert external_links dict → array of row objects */
function dictToRows(dict) {
  if (!dict || typeof dict !== 'object') return []
  return Object.entries(dict)
    .filter(([key]) => key in LINK_TYPES && typeof dict[key] === 'string' && dict[key] !== '')
    .map(([key, value], i) => ({ id: i + 1, key, value }))
}

/** Convert row array → external_links dict (omits blank values) */
function rowsToDict(rows) {
  const out = {}
  for (const row of rows) {
    if (row.key in LINK_TYPES && row.value.trim() !== '') {
      out[row.key] = row.value.trim()
    }
  }
  return out
}

/** Label style — §4 hybrid: uppercase caps label, one-off letter-spacing */
const labelStyle = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: '0.06em',
  color: 'var(--color-text-muted)',
  textTransform: 'uppercase',
  display: 'block',
  marginBottom: 6,
}

/** Section header style */
const sectionLabelStyle = {
  ...labelStyle,
  marginTop: 20,
  marginBottom: 10,
}

export default function EditCardForm({ user, onChange }) {
  const { language } = useLanguage()
  const { t } = useTranslation()

  const [draft, setDraft] = useState(() => ({
    display_name: user?.display_name || '',
    // Legacy free-text role — kept in state for the hint + preservation rule
    // (SETTINGS-POLISH-1 §A.4). Never rendered as an editable input anymore.
    role: user?.role || '',
    onboarding_role: user?.onboarding_role || '',
    affiliation: user?.affiliation || '',
    bio: user?.bio || '',
    linkRows: dictToRows(user?.external_links || {}),
  }))
  const [seq, setSeq] = useState(draft.linkRows.length)
  const [roleOptions, setRoleOptions] = useState([])

  // Fetch the role list once (memoized at module scope in api/meta.js).
  useEffect(() => {
    let cancelled = false
    getRoles().then(list => { if (!cancelled) setRoleOptions(list) })
    return () => { cancelled = true }
  }, [])

  function commit(next) {
    setDraft(next)
    // SAVE RULE (SETTINGS-POLISH-1 §A.4): a chosen onboarding_role clears the
    // legacy free-text role (data migration on save). An empty selection
    // omits BOTH fields entirely so the legacy text is preserved untouched.
    const rolePatch = next.onboarding_role
      ? { onboarding_role: next.onboarding_role, role: '' }
      : {}
    onChange?.({
      display_name: next.display_name,
      ...rolePatch,
      affiliation: next.affiliation,
      bio: next.bio,
      external_links: rowsToDict(next.linkRows),
    })
  }

  const setText = (key) => (e) => commit({ ...draft, [key]: e.target.value })

  function addLink(key) {
    // Only one row per key type allowed
    if (draft.linkRows.some(r => r.key === key)) return
    const id = seq + 1
    setSeq(id)
    commit({ ...draft, linkRows: [...draft.linkRows, { id, key, value: '' }] })
  }

  function setLinkValue(id, value) {
    commit({ ...draft, linkRows: draft.linkRows.map(r => r.id === id ? { ...r, value } : r) })
  }

  function removeLink(id) {
    commit({ ...draft, linkRows: draft.linkRows.filter(r => r.id !== id) })
  }

  // Keys already added (prevents duplicates)
  const addedKeys = new Set(draft.linkRows.map(r => r.key))

  // Bio auto-grow (SETTINGS-POLISH-1 §B) — resize to content on every value
  // change, including the pre-filled value on mount.
  const bioRef = useRef(null)
  useLayoutEffect(() => {
    const el = bioRef.current
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(el.scrollHeight, BIO_MAX_HEIGHT)
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > BIO_MAX_HEIGHT ? 'auto' : 'hidden'
  }, [draft.bio])

  const showLegacyRoleHint = !draft.onboarding_role && draft.role

  return (
    <div style={{ display: 'grid', gap: 16 }}>

      {/* Display name */}
      <div>
        <label htmlFor="edit-display-name" style={labelStyle}>{t('profileEdit.displayNameLabel')}</label>
        <input
          id="edit-display-name"
          type="text"
          value={draft.display_name}
          onChange={setText('display_name')}
          maxLength={30}
          placeholder="Your display name"
          className={styles.field}
        />
        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 4, textAlign: 'right' }}>
          {draft.display_name.length}/30
        </div>
      </div>

      {/* Role — dropdown bound to onboarding_role (SETTINGS-POLISH-1 §A.4) */}
      <div>
        <label htmlFor="edit-role" style={labelStyle}>{t('profileEdit.role.label')}</label>
        <select
          id="edit-role"
          value={draft.onboarding_role}
          onChange={(e) => commit({ ...draft, onboarding_role: e.target.value })}
          className={styles.select}
        >
          <option value="">{t('profileEdit.role.blankOption')}</option>
          {roleOptions.map(opt => (
            <option key={opt.value} value={opt.value}>
              {language === 'ko' ? (opt.label_ko || opt.label_en) : (opt.label_en || opt.label_ko)}
            </option>
          ))}
        </select>
        {showLegacyRoleHint && (
          <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 4 }}>
            {t('profileEdit.role.legacyHint', { role: draft.role })}
          </div>
        )}
      </div>

      {/* Affiliation */}
      <div>
        <label htmlFor="edit-affiliation" style={labelStyle}>{t('profileEdit.affiliationLabel')}</label>
        <input
          id="edit-affiliation"
          type="text"
          value={draft.affiliation}
          onChange={setText('affiliation')}
          maxLength={100}
          placeholder="Korea University"
          className={styles.field}
        />
      </div>

      {/* Bio — auto-grows to content, 90px→240px cap (SETTINGS-POLISH-1 §B) */}
      <div>
        <label htmlFor="edit-bio" style={labelStyle}>Bio</label>
        <textarea
          id="edit-bio"
          ref={bioRef}
          value={draft.bio}
          onChange={setText('bio')}
          maxLength={500}
          placeholder="Short intro about yourself"
          className={styles.textarea}
        />
        <div style={{ fontSize: 11, color: 'var(--color-text-dim)', marginTop: 4, textAlign: 'right' }}>
          {draft.bio.length}/500
        </div>
      </div>

      {/* External links section */}
      <div>
        <span style={sectionLabelStyle}>Links</span>

        {/* Existing link rows */}
        {draft.linkRows.map(row => (
          <div key={row.id} className={styles.itemRow} style={{ marginBottom: 8 }}>
            <span style={{
              fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
              color: 'var(--color-text-muted)', textTransform: 'uppercase',
              minWidth: 72, flexShrink: 0,
            }}>
              {LINK_TYPES[row.key]?.label || row.key}
            </span>
            <input
              type="text"
              value={row.value}
              onChange={(e) => setLinkValue(row.id, e.target.value)}
              placeholder={LINK_TYPES[row.key]?.placeholder || ''}
              maxLength={500}
              className={styles.field}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              onClick={() => removeLink(row.id)}
              className={styles.removeBtn}
              aria-label={`Remove ${LINK_TYPES[row.key]?.label || row.key}`}
            >
              ×
            </button>
          </div>
        ))}

        {/* Add-link type buttons (only show un-added types) */}
        {Object.entries(LINK_TYPES).some(([key]) => !addedKeys.has(key)) && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 8 }}>
            {Object.entries(LINK_TYPES).map(([key, { label }]) => (
              !addedKeys.has(key) && (
                <button
                  key={key}
                  type="button"
                  onClick={() => addLink(key)}
                  className={styles.addBtn}
                >
                  <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
                  {label}
                </button>
              )
            ))}
          </div>
        )}
      </div>

    </div>
  )
}
