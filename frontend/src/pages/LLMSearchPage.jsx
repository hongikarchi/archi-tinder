import { useState, useRef, useEffect } from 'react'
import buildingsData from '../data/sample_buildings.json'
import { toImageCard } from '../api/localSession.js'

const GEMINI_API_KEY = import.meta.env.VITE_GEMINI_API_KEY
const GEMINI_MODEL = 'gemini-2.5-flash'
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`

const SYSTEM_INSTRUCTION = `You are an architecture search assistant for ArchiTinder.
Users describe the kind of buildings they want to find — by country, typology/program, architect, style, mood, material, year, or area.
Always respond in English. Be helpful and concise.

Respond with ONLY a JSON object (no markdown, no extra text) with exactly these fields:
{
  "reply": "Your conversational response to the user",
  "filters": {
    "country": "country name or null",
    "architect": "architect name or null",
    "program": "building typology or program (e.g. museum, library, housing) or null",
    "mood": "mood or style descriptor or null",
    "material": "primary material or null",
    "area_range": { "min": null_or_number, "max": null_or_number },
    "year_range": { "min": null_or_number, "max": null_or_number }
  }
}

Only fill in fields that the user actually mentioned. Use null for everything else.`

const PRESETS = [
  { label: '🏛️ Japanese modern museum',    query: 'Modern museum in Japan' },
  { label: '🏟️ Stadium under 5,000 seats', query: 'Stadium with capacity less than 5000 seats' },
  { label: '📚 Scandinavian library',       query: 'Library in Scandinavia' },
  { label: '🏠 Minimalist housing',         query: 'Minimalist residential housing' },
  { label: '🌿 Sustainable pavilion',       query: 'Eco-friendly or sustainable pavilion' },
  { label: '🏢 Brutalist office',           query: 'Brutalist office or civic building' },
]

const allBuildings = buildingsData.Buildings || []

function searchBuildings(filters) {
  return allBuildings.filter(b => {
    if (filters.country) {
      if (!String(b.country || '').toLowerCase().includes(filters.country.toLowerCase())) return false
    }
    if (filters.architect) {
      if (!String(b.architects || '').toLowerCase().includes(filters.architect.toLowerCase())) return false
    }
    if (filters.program) {
      if (!String(b.typology || '').toLowerCase().includes(filters.program.toLowerCase())) return false
    }
    const area = parseFloat(b.area_m2)
    if (!isNaN(area)) {
      if (filters.area_range?.min != null && area < filters.area_range.min) return false
      if (filters.area_range?.max != null && area > filters.area_range.max) return false
    }
    return true
  }).slice(0, 10).map(toImageCard)
}

async function callGemini(userMessage, history) {
  const contents = [
    ...history,
    { role: 'user', parts: [{ text: userMessage }] },
  ]

  const res = await fetch(GEMINI_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      system_instruction: { parts: [{ text: SYSTEM_INSTRUCTION }] },
      contents,
      generationConfig: {
        responseMimeType: 'application/json',
        temperature: 0.3,
      },
    }),
  })

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}))
    throw new Error(errBody.error?.message || `Gemini error ${res.status}`)
  }

  const data = await res.json()
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text
  if (!text) throw new Error('Empty response from Gemini')
  return JSON.parse(text)
}

export default function LLMSearchPage({ mode, projectId, projectName: initialName, minArea, maxArea, onBack, onStart, onUpdate }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: "Hello! Describe the kind of architecture you're looking for — country, program, architect, style, year, and so on." }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [latestResults, setLatestResults] = useState([])
  const [showStart, setShowStart] = useState(false)
  const messagesEndRef = useRef(null)
  // Gemini multi-turn conversation history (not the same as displayed messages)
  const geminiHistory = useRef([])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function handleSubmit(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return
    setInput('')
    await submitQuery(text)
  }

  function handlePreset(query) {
    if (isLoading) return
    setInput('')
    const savedInput = input
    setInput(query)
    // Use a ref-based approach: set input then immediately submit
    setTimeout(() => {
      setInput(savedInput)
    }, 0)
    submitQuery(query)
  }

  async function submitQuery(text) {
    setMessages(prev => [...prev, { role: 'user', text }])
    setIsLoading(true)

    try {
      const parsed = await callGemini(text, geminiHistory.current)

      geminiHistory.current = [
        ...geminiHistory.current,
        { role: 'user', parts: [{ text }] },
        { role: 'model', parts: [{ text: JSON.stringify(parsed) }] },
      ]

      const filters = parsed.filters || {}

      if (minArea > 0) filters.area_range = { ...filters.area_range, min: Math.max(filters.area_range?.min ?? 0, minArea) }
      if (maxArea < 100000) filters.area_range = { ...filters.area_range, max: Math.min(filters.area_range?.max ?? 100000, maxArea) }

      const results = searchBuildings(filters)

      const replyText = results.length > 0
        ? `${parsed.reply}\n\nFound ${results.length} building${results.length !== 1 ? 's' : ''} matching your criteria.`
        : `${parsed.reply}\n\nNo buildings matched those criteria in the local database. Try describing it differently.`

      setMessages(prev => [...prev, { role: 'ai', text: replyText }])

      if (results.length > 0) {
        setLatestResults(results)
        setShowStart(true)
      }
    } catch (err) {
      console.error('[LLMSearchPage] Gemini call failed:', err)
      setMessages(prev => [...prev, { role: 'ai', text: `Something went wrong: ${err.message}. Please try again.` }])
    }

    setIsLoading(false)
  }

  function handleStartSwiping() {
    const name = initialName || 'Untitled Project'
    if (mode === 'update') {
      onUpdate(projectId, latestResults)
    } else {
      onStart(name, latestResults)
    }
  }

  const bottomOffset = showStart ? 64 + 140 : 64 + 20

  return (
    <div style={{
      height: 'calc(100vh - 64px)', overflow: 'hidden', background: 'var(--color-bg)',
      display: 'flex', flexDirection: 'column',
      backgroundImage: 'radial-gradient(circle at 15% 50%, rgba(236,72,153,0.07), transparent 30%), radial-gradient(circle at 85% 30%, rgba(244,63,94,0.07), transparent 30%)',
    }}>

      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-header-bg)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', gap: 12,
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', color: 'var(--color-text-dim)',
          fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', padding: '4px 0',
        }}>← Back</button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <span style={{
            fontSize: 16, fontWeight: 700,
            background: 'linear-gradient(90deg, var(--color-text), #f9a8d4)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            {mode === 'update' ? `Update "${initialName}"` : 'ArchiTinder AI'}
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
              padding: '12px 16px', borderRadius: 16, fontSize: 14, lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              ...(msg.role === 'user' ? {
                background: 'var(--color-user-bubble)',
                color: 'var(--color-user-bubble-text)',
                borderBottomRightRadius: 4,
              } : {
                background: 'var(--color-ai-bubble)',
                border: '1px solid var(--color-ai-bubble-border)',
                color: 'var(--color-text-2)', borderBottomLeftRadius: 4,
              })
            }}>
              {msg.text}
            </div>
          </div>
        ))}

        {/* Preset chips — shown only before first user message */}
        {messages.length === 1 && !isLoading && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingLeft: 2 }}>
            {PRESETS.map(p => (
              <button
                key={p.label}
                onClick={() => handlePreset(p.query)}
                style={{
                  padding: '8px 14px', borderRadius: 999, fontSize: 12, fontWeight: 500,
                  background: 'rgba(236,72,153,0.12)',
                  border: '1px solid rgba(236,72,153,0.35)',
                  color: '#f9a8d4', cursor: 'pointer', fontFamily: 'inherit',
                  transition: 'background 0.15s, border-color 0.15s',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'rgba(236,72,153,0.25)'
                  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.6)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'rgba(236,72,153,0.12)'
                  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.35)'
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {isLoading && (
          <div style={{ alignSelf: 'flex-start' }}>
            <div style={{
              padding: '12px 18px', background: 'var(--color-ai-bubble)',
              border: '1px solid var(--color-ai-bubble-border)',
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
            background: 'var(--color-panel-bg)',
            border: '1px solid var(--color-border-soft)',
            borderRadius: 16, padding: '14px 16px',
            backdropFilter: 'blur(12px)',
          }}>
            <button onClick={handleStartSwiping} style={{
              width: '100%', padding: '13px', borderRadius: 12, border: 'none',
              background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
              color: '#fff', fontSize: 14, fontWeight: 700,
              cursor: 'pointer', fontFamily: 'inherit',
            }}>
              {mode === 'update'
                ? `Update with these results · ${latestResults.length}`
                : `Start swiping · ${latestResults.length}`}
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{
        position: 'fixed', bottom: 64, left: 0, right: 0,
        padding: '12px 16px',
        background: 'linear-gradient(to top, var(--color-bg) 80%, transparent)',
        zIndex: 30,
      }}>
        <form onSubmit={handleSubmit} style={{
          maxWidth: 480, margin: '0 auto',
          display: 'flex',
          background: 'var(--color-input-bg)',
          border: '1px solid var(--color-border-soft)',
          borderRadius: 24, padding: '6px 8px 6px 16px',
          backdropFilter: 'blur(12px)',
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Find a modern museum in Japan..."
            style={{
              flex: 1, background: 'transparent', border: 'none',
              color: 'var(--color-text-2)', fontSize: 14, outline: 'none',
              fontFamily: 'inherit', padding: '8px 0',
            }}
            disabled={isLoading}
          />
          <button type="submit" disabled={isLoading || !input.trim()} style={{
            width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
            background: input.trim() && !isLoading ? '#ec4899' : 'var(--color-border-soft)',
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

    </div>
  )
}
