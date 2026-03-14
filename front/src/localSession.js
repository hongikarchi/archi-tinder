/**
 * localSession.js
 * 백엔드 분석 세션 API를 로컬에서 시뮬레이션합니다.
 * 백엔드 연결 시 api.js에서 이 모듈 대신 실제 API를 호출합니다.
 */
import buildingsData from './buildings_master.json'

// 세션 상태 저장 (메모리, 페이지 새로고침 시 초기화)
const sessions = new Map()

function parseArea(raw) {
  if (raw == null) return null
  const n = parseFloat(String(raw).replace(/[^\d.]/g, ''))
  return isNaN(n) ? null : n
}

function applyFilters(buildings, filters = {}) {
  const { typologies = [], min_area = 0, max_area = Infinity } = filters
  return buildings.filter(b => {
    const passType = typologies.length === 0 || typologies.includes(b.typology)
    const area = parseArea(b.area_m2)
    const passArea = area === null || (area >= min_area && area <= max_area)
    return passType && passArea
  })
}

// building 객체 → ImageCard 스키마 변환
export function toImageCard(b) {
  return {
    image_id: b.building_id,
    image_title: b.building_name,
    image_url: b.imageUrl || `https://picsum.photos/seed/${b.building_id}/600/800`,
    source_url: b.url || null,
    metadata: {
      axis_typology: b.typology || null,
      axis_architects: b.architects || null,
      axis_country: b.country || null,
      axis_area_m2: b.area_m2 || null,
      axis_capacity: b.capacity || null,
      axis_tags: b.tags || [],
    },
  }
}

/**
 * POST /api/v1/analysis/sessions (로컬 구현)
 * preloaded_images: ImageCard[] — LLM 검색 결과를 직접 덱으로 사용할 때
 */
export function startSession({ project_id, is_new_project, filter_mode, filters = {}, swiped_image_ids = [], preloaded_images = null }) {
  const swipedSet = new Set(swiped_image_ids)
  let remaining
  if (preloaded_images && preloaded_images.length > 0) {
    remaining = preloaded_images.filter(img => !swipedSet.has(img.image_id))
  } else {
    const filtered = applyFilters(buildingsData.Buildings, filters)
    remaining = filtered.filter(b => !swipedSet.has(b.building_id)).map(toImageCard)
  }

  const session_id = `sess_local_${Date.now()}`
  const all_images = preloaded_images && preloaded_images.length > 0
    ? [...preloaded_images]
    : (remaining.length > 0 ? remaining : [])
  sessions.set(session_id, {
    project_id,
    all_images,
    remaining: [...remaining],
    liked: [],
    current_round: 0,
    total_rounds: remaining.length,
    like_count: 0,
    dislike_count: 0,
  })

  return {
    session_id,
    session_status: 'active',
    total_rounds: remaining.length,
    next_image: remaining[0] || null,
    progress: {
      current_round: 0,
      total_rounds: remaining.length,
      like_count: 0,
      dislike_count: 0,
    },
  }
}

/**
 * POST /api/v1/analysis/sessions/{session_id}/swipes (로컬 구현)
 */
export function recordSwipe({ session_id, image_id, action }) {
  const s = sessions.get(session_id)
  if (!s) return { error_code: 'NOT_FOUND', message: 'Session not found' }

  s.remaining = s.remaining.filter(img => img.image_id !== image_id)
  s.current_round++

  if (action === 'like') {
    const card = s.all_images.find(img => img.image_id === image_id)
    if (card) s.liked.push(card)
    s.like_count++
  } else {
    s.dislike_count++
  }

  const is_analysis_completed = s.remaining.length === 0
  return {
    accepted: true,
    session_status: is_analysis_completed ? 'report_ready' : 'active',
    progress: {
      current_round: s.current_round,
      total_rounds: s.total_rounds,
      like_count: s.like_count,
      dislike_count: s.dislike_count,
    },
    next_image: is_analysis_completed ? null : s.remaining[0],
    is_analysis_completed,
  }
}

/**
 * GET /api/v1/analysis/sessions/{session_id}/result (로컬 구현)
 * predicted_like_images: 아직 스와이프하지 않은 이미지 최대 20개
 */
export function getResult({ session_id }) {
  const s = sessions.get(session_id)
  if (!s) return { error_code: 'NOT_FOUND', message: 'Session not found' }

  const likedIds = new Set(s.liked.map(img => img.image_id))
  const predicted = s.remaining.filter(img => !likedIds.has(img.image_id)).slice(0, 20)

  return {
    session_id,
    session_status: 'completed',
    liked_images: s.liked,
    predicted_like_images: predicted,
    predicted_like_count: predicted.length,
    analysis_report: {
      dominant_axes: [],
      keywords: [],
      keyword_count: 0,
      summary_text: '(로컬 모드 — 백엔드 연결 후 실제 분석 결과가 표시됩니다)',
    },
    generated_at: new Date().toISOString(),
  }
}
