/**
 * contestDeadline.js — contest deadline math, pinned to KST (UTC+09:00).
 *
 * Decision D9 (docs/decisions/2026-10-09-contest-real-data.md): the countdown
 * tracks the NEAREST REMAINING deadline — the apply deadline while it is still
 * in the future, otherwise the submission deadline.
 *
 * All calendar math uses a fixed +09:00 offset and the UTC getters only, never
 * local-time getters or Intl with the device zone, so results are identical on
 * any machine / CI timezone (see contestDeadline.test.mjs).
 */

const KST_OFFSET_MS = 9 * 60 * 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000
const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/

const WEEKDAYS = {
  ko: ['일', '월', '화', '수', '목', '금', '토'],
  en: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
}
const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function toDate(value) {
  if (value == null || value === '') return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Whole KST calendar-day index of an instant (days since 1970-01-01 KST). */
function kstDayNumber(date) {
  return Math.floor((date.getTime() + KST_OFFSET_MS) / DAY_MS)
}

/** Calendar fields of an instant as seen on a KST wall clock. */
function kstParts(date) {
  const shifted = new Date(date.getTime() + KST_OFFSET_MS)
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
    weekday: shifted.getUTCDay(),
  }
}

const pad2 = n => String(n).padStart(2, '0')

function lang(language) {
  return language === 'en' ? 'en' : 'ko'
}

/**
 * The deadline the countdown should track.
 * @returns {{ kind: 'apply' | 'submission', at: Date } | null}
 */
export function nextDeadline(contest, now = new Date()) {
  const nowMs = toDate(now)?.getTime() ?? Date.now()
  const apply = toDate(contest?.apply_deadline)
  if (apply && apply.getTime() > nowMs) return { kind: 'apply', at: apply }
  const submission = toDate(contest?.submission_deadline)
  if (!submission) return null
  return { kind: 'submission', at: submission }
}

/**
 * D-n as a KST calendar-date difference: (KST date of deadline) - (KST date of
 * now), in days. 0 on the deadline's own KST day, negative afterwards.
 */
export function ddayKst(deadline, now = new Date()) {
  const dl = toDate(deadline)
  const n = toDate(now)
  if (!dl || !n) return null
  return kstDayNumber(dl) - kstDayNumber(n)
}

/** True once the submission deadline instant has passed. */
export function isClosed(contest, now = new Date()) {
  const submission = toDate(contest?.submission_deadline)
  const n = toDate(now)
  if (!submission || !n) return false
  return submission.getTime() <= n.getTime()
}

/** '2026.10.28 (수) 18:00' (ko) / 'Wed, Oct 28, 2026, 18:00 KST' (en), always KST. */
export function formatKstDateTime(iso, language = 'ko') {
  const d = toDate(iso)
  if (!d) return ''
  const p = kstParts(d)
  const l = lang(language)
  const wd = WEEKDAYS[l][p.weekday]
  const time = `${pad2(p.hour)}:${pad2(p.minute)}`
  if (l === 'en') return `${wd}, ${MONTHS_EN[p.month - 1]} ${p.day}, ${p.year}, ${time} KST`
  return `${p.year}.${pad2(p.month)}.${pad2(p.day)} (${wd}) ${time}`
}

/**
 * '2026.10.28 (수)' (ko) / 'Wed, Oct 28, 2026' (en). Accepts an ISO instant
 * (rendered in KST) or a date-only 'YYYY-MM-DD' (already a KST calendar date).
 */
export function formatKstDate(value, language = 'ko') {
  let p
  const m = typeof value === 'string' ? DATE_ONLY_RE.exec(value.trim()) : null
  if (m) {
    const [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])]
    p = { year, month, day, weekday: new Date(Date.UTC(year, month - 1, day)).getUTCDay() }
  } else {
    const d = toDate(value)
    if (!d) return ''
    p = kstParts(d)
  }
  const l = lang(language)
  const wd = WEEKDAYS[l][p.weekday]
  if (l === 'en') return `${wd}, ${MONTHS_EN[p.month - 1]} ${p.day}, ${p.year}`
  return `${p.year}.${pad2(p.month)}.${pad2(p.day)} (${wd})`
}
