/**
 * api/localSession.js
 * Simulates the backend analysis session API locally.
 * When backend is connected, api/client.js calls the real API instead.
 */
import buildingsData from '../data/sample_buildings.json'

// Session state (in-memory, resets on page refresh)
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

// building object → ImageCard schema
export function toImageCard(b) {
  return {
    image_id: b.building_id,
    image_title: b.building_name,
    image_url: b.imageUrl || `https://picsum.photos/seed/${b.building_id}/600/800`,
    source_url: b.url || null,
    gallery: [],
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
 * POST /api/v1/analysis/sessions (local implementation)
 * preloaded_images: ImageCard[] — use LLM search results directly as the deck
 */
export function startSession({ project_id, filters = {}, swiped_image_ids = [], preloaded_images = null }) {
  const swipedSet = new Set(swiped_image_ids)
  let remaining, all_images, total_rounds, current_round

  if (preloaded_images && preloaded_images.length > 0) {
    remaining   = preloaded_images.filter(img => !swipedSet.has(img.image_id))
    all_images  = [...preloaded_images]
    total_rounds  = preloaded_images.length
    current_round = preloaded_images.length - remaining.length
  } else {
    const filtered = applyFilters(buildingsData.Buildings, filters)
    remaining     = filtered.filter(b => !swipedSet.has(b.building_id)).map(toImageCard)
    all_images    = remaining.length > 0 ? remaining : []
    total_rounds  = filtered.length
    current_round = filtered.length - remaining.length
  }

  const session_id = `sess_local_${Date.now()}`
  sessions.set(session_id, {
    project_id,
    all_images,
    remaining: [...remaining],
    liked: [],
    current_round,
    total_rounds,
    like_count: 0,
    dislike_count: 0,
  })

  return {
    session_id,
    session_status: 'active',
    total_rounds,
    next_image: remaining[0] || null,
    progress: {
      current_round,
      total_rounds,
      like_count: 0,
      dislike_count: 0,
    },
  }
}

/**
 * POST /api/v1/analysis/sessions/{session_id}/swipes (local implementation)
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
 * GET /api/v1/analysis/sessions/{session_id}/result (local implementation)
 * predicted_like_images: up to 20 images not yet swiped
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
      summary_text: '(Local mode — connect to the backend to see real analysis results)',
    },
    generated_at: new Date().toISOString(),
  }
}

/**
 * Clear all sessions for the current user (call on logout, spec F7)
 */
export function clearSessions() {
  sessions.clear()
}
