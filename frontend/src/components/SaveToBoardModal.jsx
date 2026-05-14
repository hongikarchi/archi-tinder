import { useEffect, useState } from 'react'
import { bookmarkBuilding, listProjects } from '../api/client.js'
import { callApi } from '../api/core.js'

function getCardId(card) {
  return card?.building_id || card?.image_id || null
}

function ProjectRow({ project, disabled, onClick }) {
  const projectId = project?.project_id || project?.id
  const count = project?.building_count || 0

  return (
    <button
      type="button"
      onClick={() => onClick(projectId)}
      disabled={disabled}
      style={{
        width: '100%',
        minHeight: 48,
        borderRadius: 12,
        border: '1px solid var(--color-border-soft)',
        background: 'rgba(255,255,255,0.02)',
        color: 'var(--color-text)',
        textAlign: 'left',
        padding: '10px 12px',
        cursor: disabled ? 'default' : 'pointer',
        fontFamily: 'inherit',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
        opacity: disabled ? 0.65 : 1,
      }}
    >
      <span style={{ color: 'var(--color-text)' }}>{project?.name || 'Untitled board'}</span>
      <span style={{ color: 'var(--color-text-dimmer)', fontSize: 12 }}>
        {count} building{count === 1 ? '' : 's'}
      </span>
    </button>
  )
}

export default function SaveToBoardModal({ card, onClose, onSaved }) {
  const [boards, setBoards] = useState([])
  const [loading, setLoading] = useState(false)
  const [busyProjectId, setBusyProjectId] = useState('')
  const [error, setError] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newBoardName, setNewBoardName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const buildingId = getCardId(card)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')

    listProjects()
      .then(resp => {
        if (cancelled) return
        const results = Array.isArray(resp?.results) ? resp.results : []
        setBoards(results)
      })
      .catch(err => {
        if (cancelled) return
        setError(err?.message || 'Failed to load boards.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function handleCreateBoard(event) {
    event.preventDefault()
    const trimmedName = newBoardName.trim()
    if (!trimmedName) {
      setCreateError('Board name is required.')
      return
    }
    setCreating(true)
    setCreateError('')

    try {
      const created = await callApi('POST', '/projects/', {
        name: trimmedName,
        visibility: 'private',
      })
      setBoards(prev => [created, ...prev])
      setNewBoardName('')
      setShowCreateForm(false)
    } catch (err) {
      setCreateError(err?.message || 'Failed to create board.')
    } finally {
      setCreating(false)
    }
  }

  async function handleSelect(projectId) {
    if (!projectId || !buildingId || creating || busyProjectId) return
    setBusyProjectId(projectId)
    setError('')
    try {
      await bookmarkBuilding(projectId, buildingId, 'save', 1, null)
      onSaved()
      onClose()
    } catch (err) {
      setError(err?.message || 'Failed to save to board.')
      setBusyProjectId('')
    } finally {
      setBusyProjectId('')
    }
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
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: 'min(92vw, 420px)',
          background: 'var(--color-surface-2)',
          borderRadius: 16,
          border: '1px solid var(--color-border-soft)',
          color: 'var(--color-text)',
          padding: 16,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: 17, margin: 0, fontWeight: 800 }}>Save to board</h3>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              border: '1px solid var(--color-border-soft)',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--color-text-dimmer)',
              fontSize: 18,
              lineHeight: 1,
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <p style={{ color: '#fca5a5', margin: '0 0 8px', fontSize: 13, lineHeight: 1.35 }}>
            {error}
          </p>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 10 }}>
          <button
            type="button"
            onClick={() => {
              setShowCreateForm(prev => !prev)
              setCreateError('')
            }}
            style={{
              minHeight: 40,
              padding: '0 12px',
              borderRadius: 10,
              border: '1px solid var(--color-border-soft)',
              background: 'rgba(236,72,153,0.14)',
              color: '#fff',
              fontSize: 13,
              fontWeight: 700,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            New board
          </button>
        </div>

        {showCreateForm && (
          <form
            onSubmit={handleCreateBoard}
            style={{
              display: 'grid',
              gap: 8,
              marginBottom: 12,
              paddingBottom: 12,
              borderBottom: '1px solid var(--color-border-soft)',
            }}
          >
            <input
              type="text"
              value={newBoardName}
              onChange={(event) => setNewBoardName(event.target.value)}
              placeholder="Board name"
              maxLength={60}
              style={{
                width: '100%',
                minHeight: 40,
                borderRadius: 10,
                border: '1px solid var(--color-border-soft)',
                background: 'var(--color-bg)',
                color: 'var(--color-text)',
                padding: '0 10px',
                fontSize: 14,
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
            <button
              type="submit"
              disabled={creating}
              style={{
                minHeight: 40,
                borderRadius: 10,
                border: '1px solid rgba(236,72,153,0.45)',
                background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
                color: '#fff',
                cursor: creating ? 'default' : 'pointer',
                opacity: creating ? 0.7 : 1,
                fontSize: 13,
                fontWeight: 700,
                fontFamily: 'inherit',
              }}
            >
              {creating ? 'Creating…' : 'Create'}
            </button>
            {createError && (
              <p style={{ margin: 0, color: '#fca5a5', fontSize: 12, lineHeight: 1.35 }}>
                {createError}
              </p>
            )}
          </form>
        )}

        {loading ? (
          <div className="skeleton-shimmer" style={{ height: 90, borderRadius: 12 }} />
        ) : (
          <div style={{ display: 'grid', gap: 8, maxHeight: '40vh', overflowY: 'auto' }}>
            {boards.length === 0 ? (
              <p style={{ margin: 0, color: 'var(--color-text-dimmer)', fontSize: 13 }}>
                No boards yet
              </p>
            ) : boards.map((project) => {
              const projectId = project?.project_id || project?.id
              if (!projectId) return null
              return (
                <ProjectRow
                  key={projectId}
                  project={project}
                  disabled={busyProjectId === projectId}
                  onClick={handleSelect}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
