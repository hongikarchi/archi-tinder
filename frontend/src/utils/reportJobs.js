/**
 * utils/reportJobs.js
 * Shared in-flight store for report REGENERATIONS (sibling of reportImageJobs.js).
 *
 * Several independent triggers can regenerate the same board's persona report
 * (swipe-end in App, the manual button). The server
 * keeps report_stale=true until the first one commits, so without coordination a
 * second trigger sends a second paid LLM call. regenerate(id) joins the running
 * promise instead. `afterSuccess` (leader only) runs once when the new report has
 * landed; it runs even if the caller unmounted. It must NOT be used to regenerate
 * the persona image: the image is regenerated only by the owner's refresh button.
 * First generations are not routed here (they are not regenerate:true).
 */
export function createReportJobs(generate) {
  const inflight = new Map()   // projectId -> Promise<data>

  return {
    /** Resolves with the response; rejects like `generate` (all joiners see the same outcome). */
    regenerate(id, { afterSuccess } = {}) {
      if (!id) return Promise.reject(new Error('missing project id'))
      if (inflight.has(id)) return inflight.get(id)
      const p = Promise.resolve()
        .then(() => generate(id, { regenerate: true }))
        .then(data => {
          if (data?.final_report && afterSuccess) {
            try { afterSuccess(data) } catch (e) { console.error('[reportJobs] afterSuccess failed:', e) }
          }
          return data
        })
        .finally(() => inflight.delete(id))
      inflight.set(id, p)
      return p
    },
    isRegenerating(id) { return inflight.has(id) },
    reset() { inflight.clear() },
  }
}
