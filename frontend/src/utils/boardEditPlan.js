import { isNameDirty } from './boardCoverTitle.js'

/**
 * What a "save" action in board edit mode has to send.
 *  - name: trimmed new name, or null when the draft is clean/blank
 *  - deleteIds: building ids to remove ([] unless `deleting`)
 *  - noop: nothing to send (caller just exits edit mode, or ignores a blank draft)
 *  - blank: draft is empty/whitespace (invalid; caller keeps edit mode open)
 * `baseline` is the currently saved title (saved name, or the shown fallback).
 */
export function planEditSave({ draft, baseline, selectedIds, deleting }) {
  const blank = typeof draft !== 'string' || draft.trim() === ''
  const name = isNameDirty(draft, baseline) ? draft.trim() : null
  const deleteIds = deleting ? [...(selectedIds || [])] : []
  return { name, deleteIds, noop: name === null && deleteIds.length === 0, blank }
}
