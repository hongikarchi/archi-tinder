import { useState, useRef, useEffect } from 'react'
import projectsDb from './raw_database_v8.json'

const API_BASE_URL = 'http://localhost:8000'

const allProjects = Array.isArray(projectsDb) ? projectsDb : (projectsDb.projects || [])

function toImageCard(p) {
  return {
    image_id: p.url || p.project_name,
    image_title: p.project_name || p.title,
    image_url: p.images?.main_image || `https://picsum.photos/seed/${encodeURIComponent(p.project_name)}/600/800`,
    source_url: p.url || null,
    gallery: p.images?.gallery || [],
    metadata: {
      axis_typology: p.program || null,
      axis_architects: p.architect || null,
      axis_country: p.location?.country || null,
      axis_area_m2: p.area?.total_floor_area_m2 || null,
      axis_capacity: null,
      axis_tags: [],
    },
  }
}

async function parseQuery(query) {
  const res = await fetch(`${API_BASE_URL}/api/parse-query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error('API error')
  return await res.json() // { search_text, structured_filters, suggestions }
}

function searchProjects(filters) {
  return allProjects.filter(p => {
    if (filters.country) {
      const text = (String(p.location?.country || '') + ' ' + String(p.location?.raw || '')).toLowerCase()
      if (!text.includes(filters.country.toLowerCase())) return false
    }
    if (filters.architect) {
      if (!String(p.architect || '').toLowerCase().includes(filters.architect.toLowerCase())) return false
    }
    if (filters.program) {
      if (!String(p.program || '').toLowerCase().includes(filters.program.toLowerCase())) return false
    }
    if (filters.mood) {
      if (!String(p.mood || '').toLowerCase().includes(filters.mood.toLowerCase())) return false
    }
    if (filters.material) {
      if (!String(p.material || '').toLowerCase().includes(filters.material.toLowerCase())) return false
    }
    try {
      const year = parseInt(p.dates?.built_year)
      if (filters.year_range?.min && year < filters.year_range.min) return false
      if (filters.year_range?.max && year > filters.year_range.max) return false
    } catch {}
    try {
      const area = parseFloat(p.area?.total_floor_area_m2)
      if (filters.area_range?.min && area < filters.area_range.min) return false
      if (filters.area_range?.max && area > filters.area_range.max) return false
    } catch {}
    return true
  }).slice(0, 10)
}

export default function LLMSearchPage({ mode, projectId, projectName: initialName, minArea, maxArea, onBack, onStart, onUpdate }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: '안녕하세요! 원하시는 건축물의 특징(국가, 용도, 건축가, 연도 등)을 편하게 말씀해주세요.', results: [] }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [latestResults, setLatestResults] = useState([])
  const [showStart, setShowStart] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function handleSubmit(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return

    setMessages(prev => [...prev, { role: 'user', text, results: [] }])
    setInput('')
    setIsLoading(true)

    try {
      const { structured_filters, suggestions } = await parseQuery(text)

      // 규모 설정값 반영 (사전 설정이 있으면 우선 적용)
      if (minArea > 0) structured_filters.area_range = { ...structured_filters.area_range, min: Math.max(structured_filters.area_range?.min || 0, minArea) }
      if (maxArea < 100000) structured_filters.area_range = { ...structured_filters.area_range, max: Math.min(structured_filters.area_range?.max || 100000, maxArea) }

      const results = searchProjects(structured_filters)

      const paramParts = [
        structured_filters.program && `프로그램: ${structured_filters.program}`,
        structured_filters.country && `국가: ${structured_filters.country}`,
        structured_filters.architect && `건축가: ${structured_filters.architect}`,
        structured_filters.year_range?.min && `${structured_filters.year_range.min}년 이후`,
        structured_filters.mood && `분위기: ${structured_filters.mood}`,
        structured_filters.material && `재료: ${structured_filters.material}`,
      ].filter(Boolean)

      const suggestionText = suggestions?.length > 0
        ? '\n' + suggestions.map(s =>
            s.closest_match
              ? `"${s.original_term}"은(는) DB에 없습니다. 대신 "${s.closest_match}"로 검색했습니다.`
              : `"${s.original_term}"은(는) DB에 없어 해당 조건을 제외했습니다.`
          ).join('\n')
        : ''

      const summary = paramParts.length > 0 ? `[${paramParts.join(' · ')}] — ` : ''
      const replyText = results.length > 0
        ? `${results.length}개의 건물을 찾았습니다.${suggestionText}`
        : `${summary}조건에 맞는 건물을 찾지 못했습니다. 다르게 설명해 보세요.${suggestionText}`

      setMessages(prev => [...prev, { role: 'ai', text: replyText, results: [] }])
      if (results.length > 0) {
        setLatestResults(results)
        setShowStart(true)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'ai', text: 'AI 검색 중 오류가 발생했습니다. 다시 시도해주세요.', results: [] }])
    }
    setIsLoading(false)
  }

  function handleStartSwiping() {
    const name = initialName || 'Untitled Project'
    const images = latestResults.map(toImageCard)
    if (mode === 'update') {
      onUpdate(projectId, images)
    } else {
      onStart(name, images)
    }
  }

  const bottomOffset = showStart ? 64 + 140 : 64 + 20

  return (
    <div style={{
      minHeight: '100vh', background: '#0f0f0f',
      display: 'flex', flexDirection: 'column',
      backgroundImage: 'radial-gradient(circle at 15% 50%, rgba(79,70,229,0.1), transparent 30%), radial-gradient(circle at 85% 30%, rgba(139,92,246,0.1), transparent 30%)',
    }}>

      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15,17,21,0.9)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', gap: 12,
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: '#6b7280',
          fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', padding: '4px 0',
        }}>← 뒤로</button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <span style={{
            fontSize: 16, fontWeight: 700,
            background: 'linear-gradient(90deg, #fff, #a5b4fc)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            {mode === 'update' ? `"${initialName}" 업데이트` : 'ArchiTinder AI'}
          </span>
        </div>
        <div style={{ width: 40 }} />
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '24px 16px',
        display: 'flex', flexDirection: 'column', gap: 20,
        paddingBottom: bottomOffset,
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '92%',
          }}>
            <div style={{
              padding: '12px 16px', borderRadius: 16, fontSize: 14, lineHeight: 1.5,
              ...(msg.role === 'user' ? {
                background: '#2d3139', color: '#fff', borderBottomRightRadius: 4,
              } : {
                background: 'rgba(25,28,33,0.8)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#e2e8f0', borderBottomLeftRadius: 4,
              })
            }}>
              {msg.text}
            </div>

            {msg.results?.length > 0 && (
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 8, marginTop: 12, width: '100%',
              }}>
                {msg.results.map(p => (
                  <div key={p.id} style={{
                    borderRadius: 10, overflow: 'hidden', background: '#1c1c1c',
                    border: '1px solid rgba(255,255,255,0.07)',
                  }}>
                    <div style={{ width: '100%', paddingBottom: '66%', position: 'relative', background: '#111' }}>
                      {p.main_image && (
                        <img src={p.main_image} alt={p.project_name} loading="lazy"
                          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      )}
                    </div>
                    <div style={{ padding: '8px 10px' }}>
                      <p style={{ color: '#fff', fontSize: 11, fontWeight: 600, margin: '0 0 3px', lineHeight: 1.3 }}>
                        {p.project_name}
                      </p>
                      <p style={{ color: '#6b7280', fontSize: 10, margin: 0 }}>
                        {[p.city, p.country].filter(Boolean).join(', ')}
                        {p.built_year ? ` · ${p.built_year}` : ''}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div style={{ alignSelf: 'flex-start' }}>
            <div style={{
              padding: '12px 18px', background: 'rgba(25,28,33,0.8)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 16, borderBottomLeftRadius: 4,
              display: 'flex', gap: 5, alignItems: 'center',
            }}>
              {[0, 0.16, 0.32].map(d => (
                <div key={d} style={{
                  width: 6, height: 6, borderRadius: '50%', background: '#6b7280',
                  animation: `bounce 1.4s ${d}s infinite ease-in-out both`,
                }} />
              ))}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Start swiping panel */}
      {showStart && (
        <div style={{
          position: 'fixed', bottom: 64 + 70, left: 0, right: 0,
          padding: '0 16px', zIndex: 20,
        }}>
          <div style={{
            maxWidth: 480, margin: '0 auto',
            background: 'rgba(20,22,28,0.97)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 16, padding: '14px 16px',
            backdropFilter: 'blur(12px)',
          }}>
            <button onClick={handleStartSwiping} style={{
              width: '100%', padding: '13px', borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              color: '#fff', fontSize: 14, fontWeight: 700,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
              {mode === 'update'
                ? `이 결과로 업데이트 · ${latestResults.length}개`
                : `스와이프 시작 · ${latestResults.length}개`}
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{
        position: 'fixed', bottom: 64, left: 0, right: 0,
        padding: '12px 16px',
        background: 'linear-gradient(to top, #0f0f0f 80%, transparent)',
        zIndex: 30,
      }}>
        <form onSubmit={handleSubmit} style={{
          maxWidth: 480, margin: '0 auto',
          display: 'flex',
          background: 'rgba(25,28,33,0.95)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 24, padding: '6px 8px 6px 16px',
          backdropFilter: 'blur(12px)',
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="일본의 현대적인 미술관을 찾아줘..."
            style={{
              flex: 1, background: 'transparent', border: 'none',
              color: '#e2e8f0', fontSize: 14, outline: 'none',
              fontFamily: 'inherit', padding: '8px 0',
            }}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !input.trim()} style={{
            width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
            background: input.trim() && !isLoading ? '#4f46e5' : 'rgba(255,255,255,0.08)',
            border: 'none', cursor: input.trim() && !isLoading ? 'pointer' : 'default',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.2s',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </form>
      </div>

      <style>{`@keyframes bounce { 0%,80%,100%{transform:scale(0)} 40%{transform:scale(1)} }`}</style>
    </div>
  )
}
