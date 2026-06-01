/**
 * EditCardForm.jsx
 * Profile-edit form — adapted from archibe EditCardForm pattern.
 * Edits our writable fields: display_name, bio, mbti, external_links.
 *
 * external_links shape (from backend model + serializer):
 *   dict { instagram?: string, email?: string, website?: string }
 * Internally we work with a flat array of { id, key, value } rows (archibe pattern)
 * and reduce to { instagram, email, website } on output.
 *
 * Props:
 *   user     — UserProfile object (display_name, bio, mbti, external_links)
 *   onChange — called with { display_name, bio, mbti, external_links } on every change
 */

import { useState } from 'react'
import styles from './EditCardForm.module.css'

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
  const [draft, setDraft] = useState(() => ({
    display_name: user?.display_name || '',
    bio: user?.bio || '',
    mbti: user?.mbti || '',
    linkRows: dictToRows(user?.external_links || {}),
  }))
  const [seq, setSeq] = useState(draft.linkRows.length)

  function commit(next) {
    setDraft(next)
    onChange?.({
      display_name: next.display_name,
      bio: next.bio,
      mbti: next.mbti,
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

  return (
    <div style={{ display: 'grid', gap: 16 }}>

      {/* Display name */}
      <div>
        <label htmlFor="edit-display-name" style={labelStyle}>Display Name</label>
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

      {/* Bio */}
      <div>
        <label htmlFor="edit-bio" style={labelStyle}>Bio</label>
        <textarea
          id="edit-bio"
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

      {/* MBTI */}
      <div>
        <label htmlFor="edit-mbti" style={labelStyle}>MBTI</label>
        <input
          id="edit-mbti"
          type="text"
          value={draft.mbti}
          onChange={(e) => {
            const val = e.target.value.replace(/[^a-zA-Z]/g, '').toUpperCase().slice(0, 4)
            commit({ ...draft, mbti: val })
          }}
          maxLength={4}
          placeholder="e.g. INTJ"
          className={styles.field}
          style={{ width: 120 }}
        />
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
