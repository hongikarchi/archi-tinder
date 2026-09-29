/**
 * competitionInterest.js — 찜 상태 (PROTOTYPE, localStorage).
 *
 * 백엔드에 CompetitionInterest 모델이 없으므로 찜은 브라우저에만 남는다.
 * 데모 도중 새로고침해도 누른 것이 유지되어야 "진짜처럼" 느껴지기 때문에
 * sessionStorage 가 아니라 localStorage 를 쓴다.
 *
 * 키 네이밍은 이 저장소 규칙을 따른다(App.jsx 의 `archithon_*_${userId}`).
 * 다만 프로토타입이므로 유저별로 나누지 않는다 — 데모 기기 하나에서 한 사람이
 * 본다는 전제.
 */

const KEY = 'archithon_competition_interest'

/** 찜한 공모전 id 집합. 저장값을 신뢰하지 않고 깨지면 빈 집합으로 폴백. */
export function loadInterests() {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter(v => typeof v === 'string'))
  } catch {
    return new Set()
  }
}

export function saveInterests(set) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(KEY, JSON.stringify([...set]))
  } catch {
    // quota / private mode — 찜이 안 남을 뿐 데모는 계속되어야 한다
  }
}

/** 토글 후 새 집합을 반환(불변). 호출부가 setState 에 그대로 넘길 수 있다. */
export function toggleInterest(set, competitionId) {
  const next = new Set(set)
  if (next.has(competitionId)) next.delete(competitionId)
  else next.add(competitionId)
  saveInterests(next)
  return next
}
