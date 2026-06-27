import { useState, useRef, useEffect, memo } from 'react'
import * as api from '../api/client.js'
import { getProject, updateProject } from '../api/projects.js'
import s from '../components/CalibrationChat.module.css'

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
          loading="lazy"
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
  // Derive storage key once per render cycle (props/sessionStorage are stable for the lifecycle of this route mount)
  const userId = sessionStorage.getItem('archithon_user') || 'anon'
  const storageKey = `archithon_chat_${userId}_${mode}_${projectId || 'new'}`

  const [messages, setMessages] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__messages`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return [{ role: 'ai', text: "Hello! Describe the kind of architecture you're looking for -- country, program, architect, style, year, and so on." }]
  })
  const [input, setInput]               = useState('')
  const [isLoading, setIsLoading]       = useState(false)
  const [latestResults, setLatestResults] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestResults`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return []
  })
  const [latestFilters, setLatestFilters] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestFilters`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return {}
  })
  const [latestFilterPriority, setLatestFilterPriority] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestFilterPriority`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return []
  })
  const [latestVisualDescription, setLatestVisualDescription] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestVisualDescription`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return null
  })
  const [latestImageFocus, setLatestImageFocus] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestImageFocus`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return null
  })
  const [latestRawQuery, setLatestRawQuery] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestRawQuery`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return ''
  })
  // Calibration fields from the last parse-query response (forwarded to startSession)
  const [latestConfidenceScore, setLatestConfidenceScore] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestConfidenceScore`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return null
  })
  const [latestSystemAction, setLatestSystemAction] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestSystemAction`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return null
  })
  const [latestLlmMessage, setLatestLlmMessage] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestLlmMessage`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return null
  })
  const [latestQuickReplies, setLatestQuickReplies] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestQuickReplies`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return []
  })
  const [latestPriorityOrdered, setLatestPriorityOrdered] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__latestPriorityOrdered`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return []
  })
  const [showStart, setShowStart] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__showStart`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return false
  })
  const [conversationHistory, setConversationHistory] = useState(() => {
    try {
      const stored = localStorage.getItem(`${storageKey}__conversationHistory`)
      if (stored) return JSON.parse(stored)
    } catch { /* ignore */ }
    return []
  })
  const messagesEndRef = useRef(null)
  // Tracks whether backend hydration has finished (prevents save loop on mount).
  const hydrationDoneRef = useRef(false)
  // Tracks the last blob JSON sent to the backend (skip save if unchanged).
  const lastSentBlobRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Persist chat state to localStorage (write-through cache — always active).
  useEffect(() => {
    localStorage.setItem(`${storageKey}__messages`, JSON.stringify(messages))
  }, [storageKey, messages])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__conversationHistory`, JSON.stringify(conversationHistory))
  }, [storageKey, conversationHistory])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestResults`, JSON.stringify(latestResults))
  }, [storageKey, latestResults])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestFilters`, JSON.stringify(latestFilters))
  }, [storageKey, latestFilters])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestFilterPriority`, JSON.stringify(latestFilterPriority))
  }, [storageKey, latestFilterPriority])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestVisualDescription`, JSON.stringify(latestVisualDescription))
  }, [storageKey, latestVisualDescription])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestImageFocus`, JSON.stringify(latestImageFocus))
  }, [storageKey, latestImageFocus])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestRawQuery`, JSON.stringify(latestRawQuery))
  }, [storageKey, latestRawQuery])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__showStart`, JSON.stringify(showStart))
  }, [storageKey, showStart])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestConfidenceScore`, JSON.stringify(latestConfidenceScore))
  }, [storageKey, latestConfidenceScore])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestSystemAction`, JSON.stringify(latestSystemAction))
  }, [storageKey, latestSystemAction])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestLlmMessage`, JSON.stringify(latestLlmMessage))
  }, [storageKey, latestLlmMessage])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestQuickReplies`, JSON.stringify(latestQuickReplies))
  }, [storageKey, latestQuickReplies])
  useEffect(() => {
    localStorage.setItem(`${storageKey}__latestPriorityOrdered`, JSON.stringify(latestPriorityOrdered))
  }, [storageKey, latestPriorityOrdered])

  // ── Backend hydration (existing project only) ────────────────────────────
  // When there IS a real projectId (not the 'new' pre-project case), try to
  // load conversation_history from the backend so the chat is cross-device.
  // Falls back to the existing localStorage values (already seeded above) if
  // the backend returns nothing.
  // NOTE: 'new' mode (no projectId) stays localStorage-only — there is no
  // Project to persist to yet. Migrating a 'new' chat into a freshly-created
  // project is out of scope.
  useEffect(() => {
    if (!projectId) {
      hydrationDoneRef.current = true
      return
    }
    let cancelled = false
    getProject(projectId).then(project => {
      if (cancelled) return
      // null means the load failed (getProject swallows errors and returns null).
      // Keeping saves disabled (hydrationDoneRef stays false) prevents the local/
      // default state from overwriting a good backend blob on a cross-device load.
      // localStorage write-through is still active; a later successful mount
      // will re-hydrate and resume saves.
      if (project === null) return
      const ch = project?.conversation_history
      if (ch && typeof ch === 'object' && Object.keys(ch).length > 0) {
        // Backend is source of truth — overwrite state from stored blob.
        if (Array.isArray(ch.messages) && ch.messages.length > 0) {
          setMessages(ch.messages)
        }
        if (Array.isArray(ch.history)) {
          setConversationHistory(ch.history)
        }
        if (ch.latestResults != null)            setLatestResults(ch.latestResults)
        if (ch.latestFilters != null)            setLatestFilters(ch.latestFilters)
        if (ch.latestFilterPriority != null)     setLatestFilterPriority(ch.latestFilterPriority)
        if (ch.latestVisualDescription !== undefined) setLatestVisualDescription(ch.latestVisualDescription)
        if (ch.latestImageFocus !== undefined)   setLatestImageFocus(ch.latestImageFocus)
        if (ch.latestRawQuery != null)           setLatestRawQuery(ch.latestRawQuery)
        if (ch.showStart != null)                setShowStart(ch.showStart)
        // Seed lastSentBlobRef so the first post-hydrate save is skipped when
        // nothing has changed.
        lastSentBlobRef.current = JSON.stringify(ch)
      }
      // Non-null project = conclusive load (even empty conversation_history: {}
      // is a real "no prior chat"). Enable saves now.
      hydrationDoneRef.current = true
    }).catch(() => {
      /* load failed — keep saves disabled (hydrationDoneRef stays false) */
    })
    return () => { cancelled = true }
  }, [projectId])

  // ── Debounced backend save (existing project only) ───────────────────────
  // When messages or conversationHistory change after hydration, persist a
  // bounded blob to the backend (800ms debounce). localStorage is always the
  // write-through layer; this save is best-effort (errors are swallowed).
  //
  // Blob shape (bounded, no large base64 payloads):
  //   messages         — UI turns with role/text/filters (results/isFallback stripped)
  //   history          — LLM multi-turn probe history (conversationHistory)
  //   latestResults    — image_id-only lightweight array (no card metadata)
  //   latestFilters    — small structured filters dict
  //   latestFilterPriority — small array of filter key names
  //   latestVisualDescription — string or null
  //   latestImageFocus — string or null
  //   latestRawQuery   — string
  //   showStart        — boolean
  useEffect(() => {
    if (!projectId) return
    if (!hydrationDoneRef.current) return

    // Strip heavy fields from messages before persisting.
    // result-card objects in msg.results can contain URLs+metadata and exceed 64KB.
    const safeMessages = messages.slice(-60).map(m => {
      const { results: _r, isFallback: _f, ...rest } = m
      return {
        ...rest,
        text: typeof rest.text === 'string' ? rest.text.slice(0, 2000) : rest.text,
      }
    })

    // Store latestResults as image_id-only lightweight objects.
    const safeLatestResults = (latestResults || []).map(r => ({ image_id: r.image_id }))

    const blob = {
      messages: safeMessages,
      history: conversationHistory.slice(-10).map(t => ({
        ...t,
        text: typeof t.text === 'string' ? t.text.slice(0, 2000) : t.text,
      })),
      latestResults: safeLatestResults,
      latestFilters: latestFilters || {},
      latestFilterPriority: latestFilterPriority || [],
      latestVisualDescription: latestVisualDescription ?? null,
      latestImageFocus: latestImageFocus ?? null,
      latestRawQuery: typeof latestRawQuery === 'string' ? latestRawQuery.slice(0, 2000) : '',
      showStart: showStart || false,
    }

    // Progressively trim blob to fit within the backend's 64KB limit.
    // JSON.stringify uses UTF-16 internally but the wire payload is UTF-8;
    // Korean/CJK text is 3 bytes per char in UTF-8, so a naive char-count
    // budget would underestimate. Use `new Blob([str]).size` for the real
    // byte count (Web API, always available in browser). Budget = 60000 bytes
    // (headroom under the 65536 backend hard limit).
    let blobJson = JSON.stringify(blob)
    const BYTE_BUDGET = 60000
    while (new Blob([blobJson]).size > BYTE_BUDGET && blob.messages.length > 1) {
      blob.messages.shift()
      blobJson = JSON.stringify(blob)
    }
    while (new Blob([blobJson]).size > BYTE_BUDGET && blob.history.length > 1) {
      blob.history.shift()
      blobJson = JSON.stringify(blob)
    }

    // Skip if nothing changed since last send (e.g. right after hydration).
    if (blobJson === lastSentBlobRef.current) return

    const timer = setTimeout(() => {
      updateProject(projectId, { conversation_history: blob }).then(() => {
        lastSentBlobRef.current = blobJson
      }).catch(err => {
        // Swallow silently — localStorage still holds the state.
        console.warn('[LLMSearchPage] backend chat save failed (non-blocking):', err?.message ?? err)
      })
    }, 800)

    return () => clearTimeout(timer)
  }, [
    projectId,
    messages,
    conversationHistory,
    latestResults,
    latestFilters,
    latestFilterPriority,
    latestVisualDescription,
    latestImageFocus,
    latestRawQuery,
    showStart,
  ])

  function clearChatStorage() {
    [
      '__messages', '__conversationHistory', '__latestResults',
      '__latestFilters', '__latestFilterPriority', '__latestVisualDescription',
      '__latestImageFocus', '__latestRawQuery', '__showStart',
      '__latestConfidenceScore', '__latestSystemAction', '__latestLlmMessage',
      '__latestQuickReplies', '__latestPriorityOrdered',
    ].forEach(suffix => localStorage.removeItem(`${storageKey}${suffix}`))
  }

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
        setMessages(prev => [...prev, {
          role: 'ai',
          text: probeText,
          quickReplies: parsed.suggested_quick_replies || [],
          priorityOrdered: parsed.priority_ordered || [],
          systemAction: parsed.system_action || null,
        }])
        // Do not enable swipe yet -- waiting for user reply to the probe
        setShowStart(false)
      } else {
        // Terminal path: existing flow preserved verbatim
        const results    = parsed.results || []
        const isFallback = parsed.is_fallback || false
        const filters    = parsed.structured_filters || {}
        const filterPriority = parsed.filter_priority || []
        const rawQueryForSession = nextHistory
          .filter(turn => turn.role === 'user')
          .map(turn => turn.text)
          .join(' ')
          .trim()

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
          filters,
        }])

        // Reset history for the next fresh query
        setConversationHistory([])

        if (results.length > 0) {
          setLatestResults(results)
          setLatestFilters(filters)
          setLatestFilterPriority(filterPriority)
          setLatestVisualDescription(parsed.visual_description ?? null)
          setLatestImageFocus(parsed.image_focus || null)
          setLatestRawQuery(rawQueryForSession || parsed.raw_query || text || '')
          // Capture calibration fields so startSession can branch into chat_initializing
          setLatestConfidenceScore(parsed.confidence_score ?? null)
          setLatestSystemAction(parsed.system_action ?? null)
          setLatestLlmMessage(parsed.llm_response_message ?? null)
          setLatestQuickReplies(parsed.suggested_quick_replies ?? [])
          setLatestPriorityOrdered(parsed.priority_ordered ?? [])
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
    clearChatStorage()
    // Clear backend blob so a consumed chat does not resurrect next time this
    // project is opened in update mode (backend was source of truth, now reset).
    if (projectId) {
      updateProject(projectId, { conversation_history: {} }).catch(() => {})
    }
    if (mode === 'update') {
      onUpdate(projectId, latestResults, latestFilters, latestFilterPriority, latestVisualDescription, latestImageFocus)
    } else {
      onStart(
        name,
        latestResults,
        latestFilters,
        latestFilterPriority,
        latestVisualDescription,
        visibility,
        latestRawQuery || '',
        latestImageFocus,
      )
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
            {mode === 'update' ? `Update "${initialName}"` : 'archibe AI'}
          </span>
        </div>
        <div style={{ width: 40 }} />
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '24px 16px',
        display: 'flex', flexDirection: 'column',
        paddingBottom: bottomOffset,
      }}>
        <div style={{
          width: '100%',
          maxWidth: 680,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
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
              {msg.role === 'ai' && msg.priorityOrdered && msg.priorityOrdered.length > 0 && (
                <div className={s.badgesRow} role="list" aria-label="Extracted taste priorities" style={{ marginTop: 6 }}>
                  {msg.priorityOrdered.slice(0, 4).map((label, i) => (
                    <span key={`${label}_${i}`} className={s.priorityBadge} role="listitem">
                      {i === 0 ? '★ ' : ''}{label}
                    </span>
                  ))}
                </div>
              )}
              {msg.role === 'ai' && msg.quickReplies && msg.quickReplies.length > 0 && (
                <div className={s.quickRepliesWrapper} role="group" aria-label="Quick reply options" style={{ marginTop: 8 }}>
                  {msg.quickReplies.map((reply, i) => (
                    <button
                      key={`${reply}_${i}`}
                      className={s.chip}
                      onClick={() => submitQuery(reply)}
                      aria-label={`Quick reply: ${reply}`}
                    >
                      {reply}
                    </button>
                  ))}
                </div>
              )}
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
