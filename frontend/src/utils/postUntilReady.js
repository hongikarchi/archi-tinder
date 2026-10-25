/**
 * utils/postUntilReady.js
 * report/generate/ may answer 202 { status:'in_progress', retry_after } when a
 * duplicate request waited on an in-flight generation. Re-POST (same body) after
 * retry_after seconds, at most MAX_RETRIES times, then throw a normal Error so
 * callers' existing failure paths run. Any other body is returned as-is.
 */
const MAX_RETRIES = 4
const DEFAULT_RETRY_AFTER_S = 5
const sleep = ms => new Promise(r => setTimeout(r, ms))

export async function postUntilReady(post, { wait = sleep, maxRetries = MAX_RETRIES } = {}) {
  for (let attempt = 0; ; attempt++) {
    const res = await post()
    if (!(res?.status === 'in_progress' && !res?.final_report)) return res
    if (attempt >= maxRetries) throw new Error('Report generation still in progress')
    const secs = Number(res.retry_after) > 0 ? Number(res.retry_after) : DEFAULT_RETRY_AFTER_S
    await wait(Math.min(secs, 15) * 1000)
  }
}
