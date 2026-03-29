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

export default function DebugOverlay({ userId, session }) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000)
    return () => clearInterval(id)
  }, [])

  if (typeof window === 'undefined' || !window.__debugMode) return null

  const token = localStorage.getItem('archithon_access')
  const jwtExp = token ? decodeJwtExp(token) : 'none'
  const lastCall = getLastCall()

  const containerStyle = {
    position: 'fixed',
    bottom: 80,
    left: 12,
    zIndex: 9999,
    background: 'rgba(0,0,0,0.85)',
    fontFamily: 'monospace',
    fontSize: 10,
    borderRadius: 8,
    padding: '10px 12px',
    maxWidth: 320,
    border: '1px solid rgba(255,255,255,0.15)',
    color: '#d1fae5',
    lineHeight: 1.6,
    pointerEvents: 'none',
  }

  const labelStyle = { color: '#6ee7b7', fontWeight: 'bold' }
  const dimStyle = { color: '#9ca3af' }

  return (
    <div style={containerStyle}>
      <div><span style={labelStyle}>[DEBUG]</span> {userId || 'not logged in'}</div>
      <div><span style={dimStyle}>JWT exp:</span> {jwtExp}</div>
      {session ? (
        <div>
          <span style={dimStyle}>Session:</span>{' '}
          {session.id ? session.id.slice(0, 8) : '—'}{' '}
          · round {session.round ?? '?'}/{session.total ?? '?'}
        </div>
      ) : (
        <div><span style={dimStyle}>Session:</span> none</div>
      )}
      {lastCall ? (
        <div>
          <span style={dimStyle}>Last call:</span>{' '}
          {lastCall.method} {lastCall.url} {lastCall.status} {lastCall.ms}ms
        </div>
      ) : (
        <div><span style={dimStyle}>Last call:</span> none yet</div>
      )}
    </div>
  )
}
