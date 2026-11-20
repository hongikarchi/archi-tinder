// Serializes Discovery feedback while no draft id is known, so rapid swipes
// before the first response don't each create their own draft board.
// Once an id is known, calls go out immediately (no serialization).
export function createDraftFeedbackQueue(initialId = null) {
  let draftId = initialId || null
  let creating = null

  return {
    getDraftId: () => draftId,
    setDraftId(id) {
      draftId = id || null
      if (!draftId) creating = null
    },
    // call(draftId) -> Promise<{ draftId?: string }>
    async send(call) {
      while (!draftId && creating) {
        try { await creating } catch { /* creator failed: proceed ourselves */ }
      }
      const id = draftId
      const p = Promise.resolve().then(() => call(id))
      if (id) {
        return p.then(res => {
          if (res?.draftId) draftId = res.draftId
          return res
        })
      }
      const tracked = p
        .then(res => {
          if (res?.draftId) draftId = res.draftId
          return res
        })
        .finally(() => { if (creating === tracked) creating = null })
      creating = tracked
      return tracked
    },
  }
}
