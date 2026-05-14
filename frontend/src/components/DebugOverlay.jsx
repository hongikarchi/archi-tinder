import { useState, useEffect } from 'react'
import { getLastCall } from '../api/client.js'

function decodeJwtExp(token) {
  try {
    const payload = token.split('.')[1]
    const decoded = JSON.parse(atob(payload))
    if (!decoded.exp) return 'unknown'
    const d = new Date(decoded.exp * 1000)
    return d.toLocaleTimeString()
  } catch {
    return 'invalid'
  }
}

function shortId(id) {
  if (!id) return '—'
  return id.slice(-8)
}

function ms(n, warn = 800) {
  if (n == null) return '—'
  const s = n + 'ms'
  return n > warn ? `⚠${s}` : s
}

export default function DebugOverlay({ userId, session, swipeDebug }) {
  const [, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [])

  if (typeof window === 'undefined' || (!window.__debugMode && localStorage.getItem('__debugMode') !== 'true')) return null

  const token = localStorage.getItem('archithon_access')
  const jwtExp = token ? decodeJwtExp(token) : 'none'
  const lastCall = getLastCall()

  const c = { color: '#6ee7b7', fontWeight: 'bold' }
  const dim = { color: '#9ca3af' }
  const warn = { color: '#fbbf24' }
  const err = { color: '#f87171' }

  const containerStyle = {
    position: 'fixed',
    bottom: 80,
    left: 12,
    zIndex: 9999,
    background: 'rgba(0,0,0,0.9)',
    fontFamily: 'monospace',
    fontSize: 10,
    borderRadius: 8,
    padding: '10px 12px',
    maxWidth: 380,
    border: '1px solid rgba(255,255,255,0.15)',
    color: '#d1fae5',
    lineHeight: 1.7,
    pointerEvents: 'none',
  }

  // -- Queue section --
  let queueSection = null
  if (swipeDebug) {
    const { log, swipeLock, imagePreloadCache, currentCard, prefetchCard, prefetchCard2, isSwipeLoading } = swipeDebug
    const cacheSize = imagePreloadCache?.current?.size ?? '?'
    const locked = swipeLock?.current ? <span style={warn}>LOCKED</span> : <span style={dim}>free</span>
    const loading = isSwipeLoading ? <span style={warn}>LOADING</span> : <span style={dim}>idle</span>

    function cardLine(label, card) {
      if (!card) return <div><span style={dim}>{label}:</span> <span style={dim}>null</span></div>
      const cached = imagePreloadCache?.current?.has(card.image_url)
      const isAct = card.image_id === '__action_card__' || card.card_type === 'action'
      return (
        <div>
          <span style={dim}>{label}:</span>{' '}
          <span style={{ color: isAct ? '#a78bfa' : '#d1fae5' }}>{shortId(card.image_id)}</span>
          {isAct ? <span style={{ color: '#a78bfa' }}> [action]</span> : (
            cached
              ? <span style={{ color: '#6ee7b7' }}> ✓</span>
              : <span style={warn}> ✗miss</span>
          )}
        </div>
      )
    }

    // Swipe log
    const entries = (log?.current ?? []).slice().reverse()
    const logRows = entries.map((e, i) => {
      const color = e.err ? err : (e.totalMs > 1500 ? warn : dim)
      const instant = e.instant
        ? <span style={{ color: '#6ee7b7' }}>⚡{e.instantReason}</span>
        : <span style={warn}>⏳{e.instantReason}</span>
      const fallbackTag = e.fallback ? <span style={warn}> ↺fb</span> : null
      const blockedTag = e.nextBlocked ? <span style={{ color: '#a78bfa' }}> 🚫act</span> : null
      const errTag = e.err ? <span style={err}> ERR:{e.err.slice(0, 20)}</span> : null
      const preTag = e.preloadMs != null
        ? <span style={e.preloadMs > 1500 ? warn : dim}> pl:{ms(e.preloadMs, 1500)}</span>
        : null
      return (
        <div key={i} style={color}>
          #{e.n} {e.action === 'like' ? '❤' : '✕'}{' '}
          {instant}{' '}
          <span style={dim}>api:{ms(e.apiMs, 1000)}</span>
          {preTag}
          {' '}<span style={dim}>→{e.nextId ?? 'null'}</span>
          {blockedTag}{fallbackTag}{errTag}
          {' '}<span style={{ color: '#6b7280' }}>[{e.totalMs}ms]</span>
        </div>
      )
    })

    queueSection = (
      <>
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 4, paddingTop: 4 }}>
          <span style={c}>[QUEUE]</span>{' '}
          lock:{locked} load:{loading} cache:{cacheSize}
        </div>
        {cardLine('cur ', currentCard)}
        {cardLine('pf  ', prefetchCard)}
        {cardLine('pf2 ', prefetchCard2)}
        {entries.length > 0 && (
          <>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 4, paddingTop: 4 }}>
              <span style={c}>[SWIPE LOG]</span>
            </div>
            {logRows}
          </>
        )}
      </>
    )
  }

  return (
    <div style={containerStyle}>
      <div><span style={c}>[DEBUG]</span> {userId || 'not logged in'}</div>
      <div><span style={dim}>JWT exp:</span> {jwtExp}</div>
      {session ? (
        <>
          <div>
            <span style={dim}>Session:</span>{' '}
            {session.id ? session.id.slice(0, 8) : '—'}{' '}
            · round {session.round ?? '?'}/{session.total ?? '?'}
          </div>
          <div>
            <span style={dim}>Phase:</span> {session.phase ?? '—'}
            {' · '}<span style={dim}>♥</span> {session.like_count ?? 0}
            {' · '}<span style={dim}>conf</span>{' '}
            {session.confidence != null ? session.confidence.toFixed(3) : 'null'}
            {' · '}<span style={dim}>ext?</span>{' '}
            {session.can_continue == null ? '—' : session.can_continue ? 'yes' : 'no'}
          </div>
        </>
      ) : (
        <div><span style={dim}>Session:</span> none</div>
      )}
      {lastCall ? (
        <div>
          <span style={dim}>Last call:</span>{' '}
          {lastCall.method} {lastCall.url} {lastCall.status} {lastCall.ms}ms
        </div>
      ) : (
        <div><span style={dim}>Last call:</span> none yet</div>
      )}
      {queueSection}
    </div>
  )
}
