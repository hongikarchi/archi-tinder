/**
 * utils/swipeSettle.js
 * Pure waiter registry for "all in-flight swipe POSTs have committed".
 * Report generation must not start before the last like is stored server-side,
 * otherwise the report is built from a liked set that misses it (stale at birth).
 *
 * `wait({ excluding })` never rejects and never hangs. It resolves `true` when the
 * pending counter is (or drops to) `<= excluding`, or `false` after `timeoutMs`
 * (resolves anyway). `excluding` = number of pending units the caller itself owns
 * (e.g. 1 for the swipe whose response is being handled), so it waits only for
 * OTHER in-flight swipes. Callers may ignore the boolean. Timers/waiters are
 * cleaned up on every resolution path.
 */
export const SWIPE_SETTLE_TIMEOUT_MS = 8000

export function createSwipeSettler({ timeoutMs = SWIPE_SETTLE_TIMEOUT_MS } = {}) {
  let pending = 0
  const waiters = new Set()

  function release(w, settled) {
    if (!waiters.has(w)) return
    waiters.delete(w)
    clearTimeout(w.timer)
    w.resolve(settled)
  }

  return {
    increment() { pending += 1; return pending },
    decrement() {
      pending = Math.max(0, pending - 1)
      ;[...waiters].forEach(w => { if (pending <= w.threshold) release(w, true) })
      return pending
    },
    get pending() { return pending },
    get waiterCount() { return waiters.size },
    wait({ excluding = 0 } = {}) {
      if (pending <= excluding) return Promise.resolve(true)
      return new Promise(resolve => {
        const w = { resolve, timer: null, threshold: excluding }
        w.timer = setTimeout(() => release(w, false), timeoutMs)
        waiters.add(w)
      })
    },
  }
}
