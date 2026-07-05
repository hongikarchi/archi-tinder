/**
 * timeAgo.js — small relative time-ago helper (no existing util found in repo).
 *
 * formatTimeAgo(isoString, language) -> localized ko/en string, e.g.
 *   ko: '방금 전' · '5분 전' · '3시간 전' · '2일 전' · '3주 전' · '4개월 전' · '2년 전'
 *   en: 'just now' · '5m ago' · '3h ago' · '2d ago' · '3w ago' · '4mo ago' · '2y ago'
 *
 * Falls back to 'ko' on any unrecognized language code (Korea-first default,
 * consistent with src/i18n/index.js useTranslation() fallback order).
 */
const UNITS_KO = [
  { limit: 60, div: 1, suffix: '초 전', now: '방금 전' },
  { limit: 3600, div: 60, suffix: '분 전' },
  { limit: 86400, div: 3600, suffix: '시간 전' },
  { limit: 604800, div: 86400, suffix: '일 전' },
  { limit: 2629800, div: 604800, suffix: '주 전' },
  { limit: 31557600, div: 2629800, suffix: '개월 전' },
  { limit: Infinity, div: 31557600, suffix: '년 전' },
]

const UNITS_EN = [
  { limit: 60, div: 1, suffix: 's ago', now: 'just now' },
  { limit: 3600, div: 60, suffix: 'm ago' },
  { limit: 86400, div: 3600, suffix: 'h ago' },
  { limit: 604800, div: 86400, suffix: 'd ago' },
  { limit: 2629800, div: 604800, suffix: 'w ago' },
  { limit: 31557600, div: 2629800, suffix: 'mo ago' },
  { limit: Infinity, div: 31557600, suffix: 'y ago' },
]

export function formatTimeAgo(isoString, language) {
  if (!isoString) return ''
  const then = new Date(isoString).getTime()
  if (Number.isNaN(then)) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000))

  const units = language === 'en' ? UNITS_EN : UNITS_KO
  if (diffSec < 60) {
    const unit = units[0]
    return unit.now || `${diffSec}${unit.suffix}`
  }
  const unit = units.find(u => diffSec < u.limit) || units[units.length - 1]
  const value = Math.floor(diffSec / unit.div)
  return `${value}${unit.suffix}`
}
