/**
 * api.js
 * 실제 백엔드 API를 호출하고, 백엔드 미연결 시 localSession으로 fallback합니다.
 * Base URL: /api/v1
 */
import * as local from './localSession.js'

const BASE = 'http://localhost:3001/api/v1'

const isLocalSession = id => id?.startsWith('sess_local_')

async function callApi(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw Object.assign(new Error(err.message || 'API error'), { status: res.status, data: err })
  }
  return res.json()
}

// ── Auth ────────────────────────────────────────────────────────────────────

export async function login(user_id, password) {
  return callApi('POST', '/auth/login', { user_id, password })
}

// ── Projects ────────────────────────────────────────────────────────────────

export async function createProject(user_id, project_name, filters) {
  return callApi('POST', '/projects', { user_id, project_name, filters })
}

export async function updateProject(project_id, user_id, filters) {
  return callApi('PATCH', `/projects/${project_id}`, {
    user_id,
    filter_mode: 'modify',
    filters,
  })
}

// ── Analysis Sessions ────────────────────────────────────────────────────────

/**
 * 분석 세션 시작
 * preloaded_images가 있으면 로컬 세션을 직접 사용
 * 백엔드 미연결 시 localSession으로 fallback
 */
export async function startSession(params) {
  if (params.preloaded_images?.length > 0) {
    return local.startSession(params)
  }
  try {
    return await callApi('POST', '/analysis/sessions', {
      user_id: params.user_id,
      project_id: params.project_id,
      is_new_project: params.is_new_project,
      filter_mode: params.filter_mode || 'keep',
      analysis_options: params.analysis_options,
    })
  } catch {
    return local.startSession(params)
  }
}

/**
 * 스와이프 피드백 전송 → next_image 수신
 * 로컬 세션이면 localSession 사용
 */
export async function recordSwipe({ session_id, user_id, project_id, image_id, action, swiped_image_ids }) {
  if (isLocalSession(session_id)) {
    return local.recordSwipe({ session_id, image_id, action })
  }
  try {
    return await callApi('POST', `/analysis/sessions/${session_id}/swipes`, {
      user_id,
      project_id,
      image_id,
      action,
      swiped_image_ids,
      timestamp: new Date().toISOString(),
      idempotency_key: `swp_${Date.now()}`,
    })
  } catch {
    return local.recordSwipe({ session_id, image_id, action })
  }
}

/**
 * 분석 완료 후 최종 결과 조회
 */
export async function getResult({ session_id, user_id, project_id }) {
  if (isLocalSession(session_id)) {
    return local.getResult({ session_id })
  }
  try {
    const params = new URLSearchParams({ user_id, project_id })
    return await callApi('GET', `/analysis/sessions/${session_id}/result?${params}`)
  } catch {
    return local.getResult({ session_id })
  }
}
