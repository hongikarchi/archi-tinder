import { useEffect, useState } from 'react'
import { bookmarkBuilding, listProjects } from '../api/client.js'
import { createProject, VerifyRequiredError } from '../api/projects.js'
import { useTranslation } from '../i18n/index.js'
import Modal from './Modal.jsx'

function getCardId(card) {
  return card?.canonical_bld_id || card?.image_id || card?.building_id || null
}

function ProjectRow({ project, disabled, onClick, t }) {
  const projectId = project?.project_id || project?.id
  const count = (project?.liked_ids?.length || 0) + (project?.saved_ids?.length || 0)

  return (
    <button
      type="button"
      onClick={() => onClick(projectId)}
      disabled={disabled}
      style={{
        width: '100%',
        minHeight: 48,
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--color-border-soft)',
        background: 'var(--color-tag-bg)',
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
      <span style={{ color: 'var(--color-text)', fontSize: 'var(--fs-body)' }}>
        {project?.name || t('modalB3.saveToBoard.untitledBoard')}
      </span>
      <span style={{ color: 'var(--color-text-dimmer)', fontSize: 'var(--fs-caption)' }}>
        {t(count === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: count })}
      </span>
    </button>
  )
}

export default function SaveToBoardModal({ card, onClose, onSaved }) {
  const { t } = useTranslation()
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
        setError(err?.message || t('modalB3.saveToBoard.loadError'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // Mount-only fetch. t() is recreated every render (no useCallback in
    // useTranslation), so including it here would re-run listProjects() on
    // every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleCreateBoard(event) {
    event.preventDefault()
    const trimmedName = newBoardName.trim()
    if (!trimmedName) {
      setCreateError(t('modalB3.saveToBoard.nameRequired'))
      return
    }
    setCreating(true)
    setCreateError('')

    try {
      const created = await createProject({
        name: trimmedName,
        visibility: 'private',
      })
      setBoards(prev => [created, ...prev])
      setNewBoardName('')
      setShowCreateForm(false)
    } catch (err) {
      if (err instanceof VerifyRequiredError) {
        // Stash the pending board-create payload so App.jsx can retry it after
        // the user verifies. archithon:verify-required is already dispatched by
        // createProject; we dispatch a companion event with the payload here.
        window.dispatchEvent(new CustomEvent('archithon:pending-board-create', {
          detail: { name: trimmedName, visibility: 'private' },
        }))
        onClose()
        return
      }
      setCreateError(err?.message || t('modalB3.saveToBoard.createError'))
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
      setError(err?.message || t('modalB3.saveToBoard.saveError'))
      setBusyProjectId('')
    } finally {
      setBusyProjectId('')
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t('board.saveToBoard')}
      zIndex={10000}
      closeLabel={t('modalB3.close')}
      width={420}
    >
      {error && (
        <p style={{ color: 'var(--color-destructive)', margin: '0 0 8px', fontSize: 'var(--fs-body)', lineHeight: 1.35 }}>
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
            minHeight: 44,
            padding: '0 14px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            fontSize: 'var(--fs-body)',
            fontWeight: 600,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {t('modalB3.saveToBoard.newBoard')}
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
            placeholder={t('modalB3.saveToBoard.namePlaceholder')}
            maxLength={60}
            style={{
              width: '100%',
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              padding: '0 10px',
              fontSize: 'var(--fs-body)',
              outline: 'none',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
          />
          <button
            type="submit"
            disabled={creating}
            style={{
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--accent-1)',
              color: '#fff',
              cursor: creating ? 'default' : 'pointer',
              opacity: creating ? 0.7 : 1,
              fontSize: 'var(--fs-body)',
              fontWeight: 600,
              fontFamily: 'inherit',
            }}
          >
            {creating ? t('modalB3.saveToBoard.creating') : t('modalB3.saveToBoard.create')}
          </button>
          {createError && (
            <p style={{ margin: 0, color: 'var(--color-destructive)', fontSize: 'var(--fs-caption)', lineHeight: 1.35 }}>
              {createError}
            </p>
          )}
        </form>
      )}

      {loading ? (
        <div className="skeleton-shimmer" style={{ height: 90, borderRadius: 'var(--radius-md)' }} />
      ) : (
        <>
          <p style={{
            margin: '0 0 8px',
            fontSize: 'var(--fs-caption)', fontWeight: 700,
            letterSpacing: '0.08em', textTransform: 'uppercase',
            color: 'var(--color-text-muted)',
          }}>
            {t('modalB3.saveToBoard.likedProjects')}
          </p>
          <div style={{ display: 'grid', gap: 8, maxHeight: '40vh', overflowY: 'auto', marginRight: -16, paddingRight: 16 }}>
            {boards.length === 0 ? (
              <p style={{ margin: 0, color: 'var(--color-text-dimmer)', fontSize: 'var(--fs-body)' }}>
                {t('board.noBoards')}
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
                  t={t}
                />
              )
            })}
          </div>
        </>
      )}
    </Modal>
  )
}
