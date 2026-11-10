/**
 * utils/swipeSettle.js
 * Pure waiter registry for "all in-flight swipe POSTs have committed".
 * Report generation must not start before the last like is stored server-side,
 * otherwise the report is built from a liked set that misses it (stale at birth).
 *
 * `wait()` never rejects and never hangs: it resolves immediately at 0, when the
 * counter returns to 0, or after `timeoutMs` (resolves anyway). Timers/waiters are
 * cleaned up on every resolution path.
 */
export const SWIPE_SETTLE_TIMEOUT_MS = 8000

export function createSwipeSettler({ timeoutMs = SWIPE_SETTLE_TIMEOUT_MS } = {}) {
  let pending = 0
  const waiters = new Set()

  function release(w) {
    if (!waiters.has(w)) return
    waiters.delete(w)
    clearTimeout(w.timer)
    w.resolve()
  }

  return {
    increment() { pending += 1; return pending },
    decrement() {
      pending = Math.max(0, pending - 1)
      if (pending === 0) [...waiters].forEach(release)
      return pending
    },
    get pending() { return pending },
    get waiterCount() { return waiters.size },
    wait() {
      if (pending === 0) return Promise.resolve()
      return new Promise(resolve => {
        const w = { resolve, timer: null }
        w.timer = setTimeout(() => release(w), timeoutMs)
        waiters.add(w)
      })
    },
  }
}
