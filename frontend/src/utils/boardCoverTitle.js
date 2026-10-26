/**
 * Cover title of the board detail page: the board name, then the persona type
 * of the report, then the localized default name. Blank/whitespace skipped.
 */
export function isNameDirty(draft, saved) {
  const d = typeof draft === 'string' ? draft.trim() : ''
  return d !== '' && d !== (typeof saved === 'string' ? saved.trim() : '')
}

export function resolveCoverTitle({ boardName, personaType, defaultName }) {
  for (const v of [boardName, personaType, defaultName]) {
    if (typeof v === 'string' && v.trim()) return v
  }
  return ''
}
