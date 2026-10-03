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
 *
 * Backend contract (POST report/generate-image/):
 *   200 { image_data, mime_type }            -> done
 *   202 { status:'in_progress', retry_after } -> another request is generating;
 *       re-POST after retry_after (each POST counts against 5/hour — no tight poll)
 *   400/404/429 -> terminal, no retry (throttle / nothing to render)
 *   other errors -> one silent automatic retry, then 'error'
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
  const jobs = new Map()          // projectId -> { status, image, mime }
  const listeners = new Set()
  const inflight = new Map()      // projectId -> Promise (dedupe)
  const IDLE = Object.freeze({ status: 'idle', image: null, mime: null })

  function set(id, next) {
    jobs.set(id, Object.freeze(next))   // new object identity -> useSyncExternalStore re-renders
    listeners.forEach(l => l())
  }

  async function post(id, budget) {
    while (budget.left > 0) {
      budget.left--
      const res = await generate(id)
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

  async function run(id) {
    set(id, { status: 'generating', image: null, mime: null })
    const budget = { left: MAX_POSTS_PER_JOB }   // shared across retries + 202 re-POSTs
    for (let attempt = 0; attempt < 2 && budget.left > 0; attempt++) {
      try {
        const res = await post(id, budget)
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
    set(id, { status: 'error', image: null, mime: null })
    return null
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
      const p = run(id).finally(() => inflight.delete(id))
      inflight.set(id, p)
      return p
    },
    get(id) { return (id && jobs.get(id)) || IDLE },
    subscribe(l) { listeners.add(l); return () => listeners.delete(l) },
    reset() { jobs.clear(); inflight.clear(); listeners.forEach(l => l()) },
  }
}
