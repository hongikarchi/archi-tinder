/**
 * throttleRetry.js
 * Pure helper for the one-shot retry after an HTTP 429.
 */

export const DEFAULT_RETRY_MS = 8000
export const MAX_RETRY_MS = 30000

/**
 * Delay (ms) before the single retry. Uses Retry-After seconds when valid,
 * else ~8s; adds 0-1s jitter (`rand` in [0,1)) so a page of cards that were
 * all throttled together doesn't retry in lockstep. Capped at MAX_RETRY_MS.
 */
export function throttleRetryDelayMs(retryAfterSec, rand = Math.random()) {
  const base = Number.isFinite(retryAfterSec) && retryAfterSec > 0
    ? retryAfterSec * 1000
    : DEFAULT_RETRY_MS
  return Math.min(MAX_RETRY_MS, Math.round(base + rand * 1000))
}
