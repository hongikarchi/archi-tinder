/**
 * utils/reportImageJobs.js
 * FULL-REPORT-IMG-1: shared, per-project persona-image generation state.
 *
 * App.jsx fires `start(projectId)` the moment the swipe session completes (in
 * parallel with report generation); PersonaReport (ResultsPage and, later,
 * BoardReportPage) subscribes by project id to render the in-progress / done /
 * error state. A module-level store (not React state) so the status survives
 * route changes and unmounts without prop drilling. Intentionally NOT persisted:
 * an in-flight request cannot outlive a page reload, so a stale 'generating'
 * flag in localStorage would spin forever.
 *
 * Status per project: 'idle' (absent) | 'generating' | 'done' | 'error'.
 * Entry shape: { status, image, mime, regen, regenFailed }.
 *   regen        true while a REGENERATION (owner refresh) is in flight; the previous
 *                image stays in `image`/`mime` meanwhile (when the store holds one).
 *   regenFailed  true after a failed regeneration (previous entry restored, previous
 *                image kept); cleared by the next regenerate()/start().
 *
 * Backend contract (POST report/generate-image/):
 *   200 { image_data, mime_type }            -> done
 *   202 { status:'in_progress', retry_after } -> another request is generating;
 *       re-POST after retry_after (each POST counts against 5/hour — no tight poll)
 *   400/404/429 -> terminal, no retry (throttle / nothing to render)
 *   other errors -> one silent automatic retry, then 'error'
 * regenerate(id) sends {regenerate:true} on EVERY POST, including 202 re-POSTs: a plain
 * POST would return the OLD stored image immediately. First-generation (start) never
 * sends the flag.
 * Total POSTs per job (202 re-POSTs + error retries combined) never exceed
 * MAX_POSTS_PER_JOB; start() on an already 'done' project is a no-op.
 */

// Hard cap on POSTs per job (across 202 re-POSTs AND error retries): the backend
// throttle is 5/hour and every POST counts; each POST may hold ~25s server-side.
const MAX_POSTS_PER_JOB = 3
const DEFAULT_RETRY_AFTER_S = 5
const NO_RETRY_STATUSES = new Set([400, 401, 404, 429])

const sleep = (ms) => new Promise(r => setTimeout(r, ms))

export function createReportImageJobs(generate, { wait = sleep } = {}) {
  const jobs = new Map()          // projectId -> entry (see header)
  const listeners = new Set()
  const inflight = new Map()      // projectId -> Promise (dedupe)
  const IDLE = Object.freeze({ status: 'idle', image: null, mime: null, regen: false, regenFailed: false })

  function set(id, next) {
    jobs.set(id, Object.freeze({ regen: false, regenFailed: false, ...next }))   // new identity -> useSyncExternalStore re-renders
    listeners.forEach(l => l())
  }

  async function post(id, budget, regenerate) {
    while (budget.left > 0) {
      budget.left--
      const res = await generate(id, { regenerate })
      if (res?.image_data) return res
      if (res?.status === 'in_progress') {
        const secs = Number(res.retry_after) > 0 ? Number(res.retry_after) : DEFAULT_RETRY_AFTER_S
        await wait(Math.min(secs, 15) * 1000)
        continue
      }
      return null
    }
    return null
  }

  async function run(id, { regenerate = false } = {}) {
    const prev = jobs.get(id) || null
    if (regenerate) {
      // Previous image stays available while the new one is generated.
      set(id, { status: 'generating', image: prev?.image ?? null, mime: prev?.mime ?? null, regen: true })
    } else {
      set(id, { status: 'generating', image: null, mime: null })
    }
    const budget = { left: MAX_POSTS_PER_JOB }   // shared across retries + 202 re-POSTs
    for (let attempt = 0; attempt < 2 && budget.left > 0; attempt++) {
      try {
        const res = await post(id, budget, regenerate)
        if (res?.image_data) {
          set(id, { status: 'done', image: res.image_data, mime: res.mime_type || null })
          return res
        }
        break  // empty / still-in-progress after max posts: treat as failure, no extra paid retry
      } catch (e) {
        if (NO_RETRY_STATUSES.has(e?.status)) break
        // else: one silent automatic retry
      }
    }
    if (regenerate) {
      // Keep whatever was shown before; just flag the failure.
      set(id, { status: prev?.status ?? 'idle', image: prev?.image ?? null, mime: prev?.mime ?? null, regenFailed: true })
    } else {
      set(id, { status: 'error', image: null, mime: null })
    }
    return null
  }

  function launch(id, opts) {
    const p = run(id, opts).finally(() => inflight.delete(id))
    inflight.set(id, p)
    return p
  }

  return {
    /** Fire-and-forget. Resolves with the response (or null on failure); never rejects. */
    start(id) {
      if (!id) return Promise.resolve(null)
      const cur = jobs.get(id)
      if (cur?.status === 'done') {
        return Promise.resolve({ image_data: cur.image, mime_type: cur.mime })   // no POST
      }
      if (inflight.has(id)) return inflight.get(id)
      return launch(id)
    },
    /**
     * Owner-requested regeneration: previous image kept while generating and on
     * failure (`regenFailed`). Joins an in-flight job instead of starting a second.
     * Resolves with the response (or null on failure); never rejects.
     */
    regenerate(id) {
      if (!id) return Promise.resolve(null)
      if (inflight.has(id)) return inflight.get(id)
      return launch(id, { regenerate: true })
    },
    get(id) { return (id && jobs.get(id)) || IDLE },
    subscribe(l) { listeners.add(l); return () => listeners.delete(l) },
    reset() { jobs.clear(); inflight.clear(); listeners.forEach(l => l()) },
  }
}
