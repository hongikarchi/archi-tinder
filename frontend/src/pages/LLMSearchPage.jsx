import { useState, useRef, useEffect, memo } from 'react'
import * as api from '../api/client.js'

const PRESETS = [
  { label: 'Japanese modern museum',  query: 'Modern museum in Japan' },
  { label: 'Minimalist housing',       query: 'Minimalist residential housing' },
  { label: 'Landscape architecture',   query: 'Landscape or park architecture' },
  { label: 'Brutalist office',         query: 'Brutalist office or civic building' },
  { label: 'Religious architecture',   query: 'Religious or spiritual architecture' },
  { label: 'Boutique hospitality',     query: 'Small hotel or boutique hospitality' },
]

const FILTER_LABELS = {
  program: 'Program',
  location_country: 'Location',
  material: 'Material',
  style: 'Style',
  year_min: 'Year',
  year_max: 'Year',
  min_area: 'Area',
  max_area: 'Area',
}

function FilterChips({ filters }) {
  if (!filters) return null
  const chips = []
  if (filters.program)          chips.push(`${FILTER_LABELS.program}: ${filters.program}`)
  if (filters.location_country) chips.push(`${FILTER_LABELS.location_country}: ${filters.location_country}`)
  if (filters.material)         chips.push(`${FILTER_LABELS.material}: ${filters.material}`)
  if (filters.style)            chips.push(`${FILTER_LABELS.style}: ${filters.style}`)
  if (filters.year_min || filters.year_max) {
    const from = filters.year_min || '...'
    const to   = filters.year_max || '...'
    chips.push(`Year: ${from}-${to}`)
  }
  if (!chips.length) return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
      {chips.map(c => (
        <span key={c} style={{
          padding: '3px 10px', borderRadius: 999, fontSize: 11, fontWeight: 500,
          background: 'rgba(236,72,153,0.12)',
          border: '1px solid rgba(236,72,153,0.25)',
          color: '#f9a8d4',
        }}>{c}</span>
      ))}
    </div>
  )
}

const Thumbnail = memo(function Thumbnail({ r }) {
  const [imgLoading, setImgLoading] = useState(true)
  return (
    <div style={{ width: '100%', height: 72, position: 'relative', background: 'rgba(255,255,255,0.04)' }}>
      {imgLoading && <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />}
      {r.image_url ? (
        <img
          src={r.image_url}
          alt={r.image_title || ''}
          style={{
            width: '100%', height: 72, objectFit: 'cover', display: 'block',
            opacity: imgLoading ? 0 : 1, transition: 'opacity 0.3s',
          }}
          onLoad={() => setImgLoading(false)}
          onError={e => { setImgLoading(false); e.target.style.display = 'none' }}
        />
      ) : (
        <div style={{
          width: '100%', height: 72,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>Building</div>
      )}
    </div>
  )
})

function ResultStrip({ results, isFallback }) {
  if (!results || !results.length) return null
  return (
    <div style={{ marginTop: 12 }}>
      {isFallback && (
        <div style={{
          fontSize: 11, color: '#9ca3af', marginBottom: 6,
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <span style={{
            padding: '1px 7px', borderRadius: 999, fontSize: 10,
            background: 'rgba(251,191,36,0.12)',
            border: '1px solid rgba(251,191,36,0.25)',
            color: '#fbbf24',
          }}>similar</span>
          <span>showing related results</span>
        </div>
      )}
      <div style={{
        display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 6,
        scrollbarWidth: 'none',
      }}>
        {results.slice(0, 12).map(r => (
          <div key={r.image_id} style={{
            flexShrink: 0, width: 100, borderRadius: 10, overflow: 'hidden',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <Thumbnail r={r} />
            <div style={{ padding: '5px 7px' }}>
              <div style={{
                fontSize: 10, fontWeight: 600, color: 'var(--color-text-2)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{r.image_title || r.image_id}</div>
              {r.metadata?.axis_country && (
                <div style={{ fontSize: 9, color: 'var(--color-text-dim)', marginTop: 1 }}>
                  {r.metadata.axis_country}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function LLMSearchPage({ mode, projectId, projectName: initialName, visibility = 'private', onBack, onStart, onUpdate }) {
  const [messages, setMessages] = useState([
    { role: 'ai', text: "Hello! Describe the kind of architecture you're looking for -- country, program, architect, style, year, and so on." }
  ])
  const [input, setInput]               = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [latestResults, setLatestResults] = useState([])
  const [latestFilters, setLatestFilters] = useState({})
  const [latestFilterPriority, setLatestFilterPriority] = useState([])
  const [latestVisualDescription, setLatestVisualDescription] = useState(null)
  const [showStart, setShowStart]       = useState(false)
  const [conversationHistory, setConversationHistory] = useState([])
  const messagesEndRef = useRef(null)

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
    submitQuery(query)
  }

  async function submitQuery(text) {
    // Build the next conversation_history with the new user turn appended
    const userTurn = { role: 'user', text }
    const nextHistory = [...conversationHistory, userTurn]

    setMessages(prev => [...prev, { role: 'user', text }])
    setIsLoading(true)

    try {
      // Call parse_query with the full history (not just the new turn)
      const parsed = await api.parseQuery(nextHistory)

      if (parsed.probe_needed) {
        // Probe path: show probe_question as AI message, accumulate history
        const probeText = parsed.probe_question || parsed.reply || ''
        const modelTurn = { role: 'model', text: probeText }
        setConversationHistory([...nextHistory, modelTurn])
        setMessages(prev => [...prev, { role: 'ai', text: probeText }])
        // Do not enable swipe yet -- waiting for user reply to the probe
        setShowStart(false)
      } else {
        // Terminal path: existing flow preserved verbatim
        const results    = parsed.results || []
        const isFallback = parsed.is_fallback || false
        const filters    = parsed.structured_filters || {}
        const filterPriority = parsed.filter_priority || []

        let replyText
        if (results.length > 0 && !isFallback) {
          replyText = `${parsed.reply}\n\nFound ${results.length} building${results.length !== 1 ? 's' : ''} matching your criteria.`
        } else if (results.length > 0 && isFallback) {
          replyText = `${parsed.reply}\n\n${parsed.fallback_note || 'No exact matches -- here are some similar buildings you might like.'}`
        } else {
          replyText = `${parsed.reply}\n\nNo buildings found. Try describing it differently.`
        }

        setMessages(prev => [...prev, {
          role: 'ai', text: replyText,
          results, isFallback,
          filters: isFallback ? {} : filters,
        }])

        // Reset history for the next fresh query
        setConversationHistory([])

        if (results.length > 0) {
          setLatestResults(results)
          setLatestFilters(isFallback ? {} : filters)
          setLatestFilterPriority(isFallback ? [] : filterPriority)
          setLatestVisualDescription(parsed.visual_description ?? null)
          setShowStart(true)
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', text: `Something went wrong: ${err.message}. Please try again.` }])
    }

    setIsLoading(false)
  }

  function handleStartSwiping() {
    const name = initialName || 'Untitled Project'
    if (mode === 'update') {
      onUpdate(projectId, latestResults, latestFilters, latestFilterPriority, latestVisualDescription)
    } else {
      onStart(name, latestResults, latestFilters, latestFilterPriority, latestVisualDescription, visibility)
    }
  }

  const bottomOffset = showStart ? 64 + 140 : 64 + 20

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))', overflow: 'hidden', background: 'var(--color-bg)',
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
          fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', padding: '4px 0', minHeight: 44,
        }}>Back</button>
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
        flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '24px 16px',
        display: 'flex', flexDirection: 'column', gap: 20,
        paddingBottom: bottomOffset,
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: 'flex', flexDirection: 'column',
            alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '100%',
          }}>
            <div style={{
              padding: '12px 16px', borderRadius: 16, fontSize: 14, lineHeight: 1.6,
              whiteSpace: 'pre-wrap', maxWidth: '100%', overflowX: 'hidden',
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
              {msg.role === 'ai' && <FilterChips filters={msg.filters} />}
              {msg.role === 'ai' && <ResultStrip results={msg.results} isFallback={msg.isFallback} />}
            </div>
          </div>
        ))}

        {/* Preset chips -- shown only before first user message */}
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
          position: 'fixed', bottom: 'calc(134px + env(safe-area-inset-bottom, 0px))', left: 0, right: 0,
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
                ? `Update with these results - ${latestResults.length}`
                : `Start swiping - ${latestResults.length}`}
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <div style={{
        position: 'fixed', bottom: 'calc(64px + env(safe-area-inset-bottom, 0px))', left: 0, right: 0,
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
