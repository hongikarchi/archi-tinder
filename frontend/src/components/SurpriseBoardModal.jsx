import { useEffect, useState } from 'react'
import { fetchBoardSurprise } from '../api/discovery.js'
import { bookmarkBuilding } from '../api/client.js'
import { createProject, VerifyRequiredError } from '../api/projects.js'
import { useTranslation } from '../i18n/index.js'
import Modal from './Modal.jsx'

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
  const { t } = useTranslation()
  const [phase, setPhase] = useState('loading') // 'loading' | 'ready' | 'naming' | 'saving' | 'error'
  const [cards, setCards] = useState([])
  const [title, setTitle] = useState(t('modalB3.surpriseBoard.defaultTitle'))
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
      setNameError(t('modalB3.surpriseBoard.nameRequired'))
      return
    }

    setNameError('')
    setPhase('saving')

    try {
      const created = await createProject({ name: trimmedName, visibility: 'private' })
      const projectId = created?.project_id || created?.id
      if (!projectId) throw new Error('No project_id in response')

      // Bulk-bookmark all cards into the new board (sequential for v1)
      for (let i = 0; i < cards.length; i++) {
        const card = cards[i]
        const buildingId = card?.canonical_bld_id || card?.image_id || card?.building_id
        if (!buildingId) continue
        await bookmarkBuilding(projectId, buildingId, 'save', i + 1, null)
      }

      onSaved()
      onClose()
    } catch (err) {
      if (err instanceof VerifyRequiredError) {
        // VerifyGateModal is mounted globally via 'archithon:verify-required' event.
        // The board payload (10 cards + bulk bookmark) is too large to stash for
        // automatic retry, so we emit a toast-request event that App.jsx will
        // surface after the user verifies. (Fix 3 Option B for SurpriseBoardModal.)
        window.dispatchEvent(new CustomEvent('archithon:verify-required:surprise-pending'))
        onClose()
        return
      }
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

  const showActionBar = phase === 'ready' || phase === 'saving'

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      zIndex={10000}
      closeLabel={t('modalB3.close')}
      width={460}
      footer={showActionBar ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={onClose}
            disabled={phase === 'saving'}
            style={{
              flex: 1,
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 'var(--fs-body)',
              fontWeight: 600,
              cursor: phase === 'saving' ? 'default' : 'pointer',
              opacity: phase === 'saving' ? 0.5 : 1,
              fontFamily: 'inherit',
            }}
          >
            {t('modalB3.surpriseBoard.notNow')}
          </button>
          <button
            type="button"
            onClick={() => { setPhase('naming'); setNameError('') }}
            disabled={phase === 'saving'}
            style={{
              flex: 2,
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: phase === 'saving'
                ? 'color-mix(in srgb, var(--accent-1) 50%, transparent)'
                : 'var(--accent-1)',
              color: '#fff',
              fontSize: 'var(--fs-body)',
              fontWeight: 600,
              cursor: phase === 'saving' ? 'default' : 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {phase === 'saving' ? t('modalB3.surpriseBoard.saving') : t('modalB3.surpriseBoard.saveThisBoard')}
          </button>
        </div>
      ) : null}
    >
      {rationale ? (
        <p style={{ margin: '0 0 4px', fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)', lineHeight: 1.4 }}>
          {rationale}
        </p>
      ) : null}
      <p style={{ margin: '0 0 16px', fontSize: 'var(--fs-body)', color: 'var(--color-text-2)', fontWeight: 600 }}>
        {t('modalB3.surpriseBoard.prompt')}
      </p>

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
              style={{ aspectRatio: '4/5', borderRadius: 'var(--radius-sm)' }}
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
          <p style={{ margin: 0, fontSize: 'var(--fs-body)', color: 'var(--color-text-muted)' }}>
            {t('modalB3.surpriseBoard.loadError')}
          </p>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              minHeight: 44,
              padding: '0 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 'var(--fs-body)',
              fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            {t('modalB3.surpriseBoard.retry')}
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
                key={card?.image_id || card?.canonical_bld_id || card?.building_id || i}
                style={{
                  aspectRatio: '4/5',
                  borderRadius: 'var(--radius-sm)',
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
                    background: 'linear-gradient(135deg, color-mix(in srgb, var(--accent-1) 18%, transparent), rgba(0,0,0,0.85))',
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
            placeholder={t('modalB3.surpriseBoard.namePlaceholder')}
            maxLength={60}
            autoFocus
            style={{
              width: '100%',
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: nameError
                ? '1px solid var(--color-destructive)'
                : '1px solid var(--color-border-soft)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              padding: '0 10px',
              fontSize: 'var(--fs-body)',
              outline: 'none',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
          />
          {nameError && (
            <p style={{ margin: '4px 0 0', color: 'var(--color-destructive)', fontSize: 'var(--fs-caption)' }}>
              {nameError}
            </p>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button
              type="button"
              onClick={() => { setPhase('ready'); setNameError('') }}
              style={{
                flex: 1,
                minHeight: 44,
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-soft)',
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
                fontSize: 'var(--fs-body)',
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {t('modalB3.surpriseBoard.back')}
            </button>
            <button
              type="submit"
              style={{
                flex: 2,
                minHeight: 44,
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: 'var(--accent-1)',
                color: '#fff',
                fontSize: 'var(--fs-body)',
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              {t('modalB3.surpriseBoard.createBoard')}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
