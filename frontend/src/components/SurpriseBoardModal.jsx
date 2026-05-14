import { useEffect, useState } from 'react'
import { fetchBoardSurprise } from '../api/discovery.js'
import { bookmarkBuilding } from '../api/client.js'
import { callApi } from '../api/core.js'

/**
 * SurpriseBoardModal
 * Shown once per Discovery visit after SURPRISE_THRESHOLD saves.
 * Loads 10 curated cards, offers "Save this board" → creates Project + bulk-bookmarks.
 *
 * Props:
 *   onClose  () => void
 *   onSaved  () => void
 */
export default function SurpriseBoardModal({ onClose, onSaved }) {
  const [phase, setPhase] = useState('loading') // 'loading' | 'ready' | 'naming' | 'saving' | 'error'
  const [cards, setCards] = useState([])
  const [title, setTitle] = useState('Curated for you')
  const [rationale, setRationale] = useState('')
  const [boardName, setBoardName] = useState('')
  const [nameError, setNameError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetchBoardSurprise()
      .then(result => {
        if (cancelled) return
        setCards(result.cards)
        setTitle(result.title)
        setRationale(result.rationale)
        setPhase('ready')
      })
      .catch(() => {
        if (cancelled) return
        setPhase('error')
      })

    return () => { cancelled = true }
  }, [])

  async function handleSaveBoard(event) {
    event.preventDefault()
    const trimmedName = boardName.trim()
    if (!trimmedName) {
      setNameError('Board name is required.')
      return
    }

    setNameError('')
    setPhase('saving')

    try {
      const created = await callApi('POST', '/projects/', { name: trimmedName, visibility: 'private' })
      const projectId = created?.project_id || created?.id
      if (!projectId) throw new Error('No project_id in response')

      // Bulk-bookmark all cards into the new board (sequential for v1)
      for (let i = 0; i < cards.length; i++) {
        const card = cards[i]
        const buildingId = card?.building_id || card?.image_id
        if (!buildingId) continue
        await bookmarkBuilding(projectId, buildingId, 'save', i + 1, null)
      }

      onSaved()
      onClose()
    } catch {
      setPhase('error')
    }
  }

  function handleRetry() {
    setPhase('loading')
    fetchBoardSurprise()
      .then(result => {
        setCards(result.cards)
        setTitle(result.title)
        setRationale(result.rationale)
        setPhase('ready')
      })
      .catch(() => {
        setPhase('error')
      })
  }

  return (
    <div
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: 'rgba(0,0,0,0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 'min(94vw, 460px)',
          maxHeight: '88vh',
          background: 'var(--color-surface-2)',
          borderRadius: 20,
          border: '1px solid var(--color-border-soft)',
          color: 'var(--color-text)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '16px 16px 12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          borderBottom: '1px solid var(--color-border)',
          flexShrink: 0,
        }}>
          <div style={{ flex: 1, paddingRight: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 18 }}>✨</span>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>{title}</h3>
            </div>
            {rationale ? (
              <p style={{ margin: '0 0 4px', fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
                {rationale}
              </p>
            ) : null}
            <p style={{ margin: 0, fontSize: 13, color: 'var(--color-text-2)', fontWeight: 600 }}>
              Your saves shaped this — save it as a board?
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              border: '1px solid var(--color-border-soft)',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--color-text-muted)',
              fontSize: 18,
              lineHeight: 1,
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
          {phase === 'loading' && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
              gap: 6,
            }}>
              {Array.from({ length: 10 }).map((_, i) => (
                <div
                  key={i}
                  className="skeleton-shimmer"
                  style={{ aspectRatio: '4/5', borderRadius: 8 }}
                />
              ))}
            </div>
          )}

          {phase === 'error' && (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              padding: '24px 0',
              textAlign: 'center',
            }}>
              <p style={{ margin: 0, fontSize: 14, color: 'var(--color-text-muted)' }}>
                Couldn&apos;t load. Try again.
              </p>
              <button
                type="button"
                onClick={handleRetry}
                style={{
                  minHeight: 40,
                  padding: '0 16px',
                  borderRadius: 10,
                  border: '1px solid var(--color-border-soft)',
                  background: 'rgba(255,255,255,0.05)',
                  color: 'var(--color-text)',
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                Retry
              </button>
            </div>
          )}

          {(phase === 'ready' || phase === 'naming' || phase === 'saving') && cards.length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
              gap: 6,
            }}>
              {cards.map((card, i) => {
                const imgUrl = card?.image_url
                return (
                  <div
                    key={card?.image_id || card?.building_id || i}
                    style={{
                      aspectRatio: '4/5',
                      borderRadius: 8,
                      overflow: 'hidden',
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    {imgUrl ? (
                      <img
                        src={imgUrl}
                        alt={card?.image_title || ''}
                        loading="lazy"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <div style={{
                        width: '100%',
                        height: '100%',
                        background: 'linear-gradient(135deg,rgba(236,72,153,0.18),rgba(15,15,15,0.85))',
                      }} />
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Inline name form */}
          {phase === 'naming' && (
            <form onSubmit={handleSaveBoard} style={{ marginTop: 12 }}>
              <input
                type="text"
                value={boardName}
                onChange={(event) => setBoardName(event.target.value)}
                placeholder="Name this board"
                maxLength={60}
                autoFocus
                style={{
                  width: '100%',
                  minHeight: 40,
                  borderRadius: 10,
                  border: nameError
                    ? '1px solid #fca5a5'
                    : '1px solid var(--color-border-soft)',
                  background: 'var(--color-bg)',
                  color: 'var(--color-text)',
                  padding: '0 10px',
                  fontSize: 14,
                  outline: 'none',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
              />
              {nameError && (
                <p style={{ margin: '4px 0 0', color: '#fca5a5', fontSize: 12 }}>
                  {nameError}
                </p>
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={() => { setPhase('ready'); setNameError('') }}
                  style={{
                    flex: 1,
                    minHeight: 40,
                    borderRadius: 10,
                    border: '1px solid var(--color-border-soft)',
                    background: 'rgba(255,255,255,0.04)',
                    color: 'var(--color-text)',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  Back
                </button>
                <button
                  type="submit"
                  style={{
                    flex: 2,
                    minHeight: 40,
                    borderRadius: 10,
                    border: 'none',
                    background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
                    color: '#fff',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  Create board
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Action bar — shown only in 'ready' or 'saving' phase */}
        {(phase === 'ready' || phase === 'saving') && (
          <div style={{
            padding: '12px 16px',
            borderTop: '1px solid var(--color-border)',
            display: 'flex',
            gap: 8,
            flexShrink: 0,
          }}>
            <button
              type="button"
              onClick={onClose}
              disabled={phase === 'saving'}
              style={{
                flex: 1,
                minHeight: 44,
                borderRadius: 12,
                border: '1px solid var(--color-border-soft)',
                background: 'rgba(255,255,255,0.04)',
                color: 'var(--color-text)',
                fontSize: 14,
                fontWeight: 700,
                cursor: phase === 'saving' ? 'default' : 'pointer',
                opacity: phase === 'saving' ? 0.5 : 1,
                fontFamily: 'inherit',
              }}
            >
              Not now
            </button>
            <button
              type="button"
              onClick={() => { setPhase('naming'); setNameError('') }}
              disabled={phase === 'saving'}
              style={{
                flex: 2,
                minHeight: 44,
                borderRadius: 12,
                border: 'none',
                background: phase === 'saving'
                  ? 'rgba(236,72,153,0.5)'
                  : 'linear-gradient(135deg,#ec4899,#f43f5e)',
                color: '#fff',
                fontSize: 14,
                fontWeight: 700,
                cursor: phase === 'saving' ? 'default' : 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {phase === 'saving' ? 'Saving…' : 'Save this board'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
