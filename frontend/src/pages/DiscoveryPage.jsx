import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDiscoveryFeed, getImageSource } from '../api/client.js'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import SurpriseBoardModal from '../components/SurpriseBoardModal.jsx'

const PAGE_LIMIT = 12
const SURPRISE_THRESHOLD = 5

function getCardId(card) {
  return card?.canonical_bld_id || card?.image_id || card?.building_id || null
}

function DiscoveryCard({ card, onOpen, onSave }) {
  const id = getCardId(card)
  const architect = card?.metadata?.axis_architects
  const source = getImageSource(card?.image_url)

  return (
    <article
      onClick={() => {
        if (!id) return
        onOpen(card)
      }}
      style={{
        position: 'relative',
        borderRadius: 16,
        overflow: 'hidden',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        aspectRatio: '4 / 5',
        cursor: id ? 'pointer' : 'default',
      }}
    >
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.image_title || 'Discovery card'}
          loading="lazy"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            opacity: source === 'unknown' ? 0.95 : 1,
          }}
        />
      ) : (
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(135deg, rgba(236,72,153,0.18), rgba(15,15,15,0.85))',
        }} />
      )}

      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.5) 44%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          if (!id) return
          onSave(card)
        }}
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          width: 44,
          height: 44,
          borderRadius: '50%',
          background: 'rgba(0,0,0,0.45)',
          border: '1px solid rgba(255,255,255,0.18)',
          color: '#fff',
          fontSize: 20,
          cursor: id ? 'pointer' : 'default',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
          pointerEvents: id ? 'auto' : 'none',
          opacity: id ? 1 : 0.55,
        }}
        aria-label="Save to board"
      >
        ☆
      </button>

      <div style={{
        position: 'absolute',
        left: 12,
        right: 12,
        bottom: 12,
      }}>
        <h3 style={{
          color: '#fff',
          fontSize: 17,
          fontWeight: 700,
          margin: '0 0 6px',
          lineHeight: 1.2,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {card.image_title || 'Untitled building'}
        </h3>
        {architect && (
          <p style={{
            color: 'rgba(255,255,255,0.72)',
            margin: 0,
            fontSize: 12,
            fontStyle: 'italic',
          }}>
            {architect}
          </p>
        )}
      </div>
    </article>
  )
}

function LoadingSkeleton({ count }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
      gap: 12,
    }}>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="skeleton-shimmer"
          style={{ height: 280, borderRadius: 16 }}
        />
      ))}
    </div>
  )
}

export default function DiscoveryPage() {
  const navigate = useNavigate()
  const sentinelRef = useRef(null)
  const requestIdRef = useRef(0)
  const isActiveRef = useRef(true)
  const [cards, setCards] = useState([])
  const [cursor, setCursor] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [tasteState, setTasteState] = useState('cold')
  const [error, setError] = useState('')
  const [saveModalCard, setSaveModalCard] = useState(null)
  const [savesThisVisit, setSavesThisVisit] = useState(0)
  const [surpriseShown, setSurpriseShown] = useState(false)
  const [surpriseOpen, setSurpriseOpen] = useState(false)
  const [isThreeColumns, setIsThreeColumns] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth >= 768
  })

  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)')
    const apply = () => setIsThreeColumns(media.matches)
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    isActiveRef.current = true
    return () => { isActiveRef.current = false }
  }, [])

  // Surprise trigger: fires once per visit after SURPRISE_THRESHOLD saves
  useEffect(() => {
    if (savesThisVisit >= SURPRISE_THRESHOLD && !surpriseShown) {
      setSurpriseShown(true)
      setSurpriseOpen(true)
    }
  }, [savesThisVisit, surpriseShown])

  const fetchPage = useCallback(async (nextCursor, reset = false) => {
    if (loading) return

    if (!isActiveRef.current) return
    const requestId = ++requestIdRef.current
    const normalizedCursor = typeof nextCursor === 'number' ? nextCursor : 0

    setLoading(true)
    setError('')

    try {
      const result = await fetchDiscoveryFeed(normalizedCursor, PAGE_LIMIT)
      if (!isActiveRef.current || requestId !== requestIdRef.current) return

      setCards(prev => (reset ? result.cards : [...prev, ...result.cards]))
      setCursor(result.nextCursor ?? 0)
      setHasMore(Boolean(result.hasMore))
      setTasteState(result.tasteState || 'cold')
    } catch (err) {
      if (!isActiveRef.current || requestId !== requestIdRef.current) return
      setError(err?.message || "Couldn't load Discovery. Tap to retry.")
    } finally {
      if (isActiveRef.current && requestId === requestIdRef.current) {
        setLoading(false)
      }
    }
  }, [loading])

  useEffect(() => {
    fetchPage(0, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const node = sentinelRef.current
    if (!node || !hasMore || cards.length === 0) return
    if (loading) return

    const observer = new IntersectionObserver(entries => {
      const entry = entries[0]
      if (!entry?.isIntersecting) return
      if (!hasMore || loading || !cards.length) return
      fetchPage(cursor)
    }, {
      root: null,
      rootMargin: '140px',
    })

    observer.observe(node)
    return () => observer.disconnect()
  }, [cards.length, cursor, hasMore, loading, fetchPage])

  const memoizedCards = useMemo(() => cards, [cards])

  function handleOpenCard(card) {
    const id = getCardId(card)
    if (!id) return
    navigate(`/buildings/${id}`)
  }

  function handleRetry() {
    setCards([])
    setCursor(0)
    setHasMore(true)
    fetchPage(0, true)
  }

  function handleSaved() {
    setSaveModalCard(null)
    setSavesThisVisit(s => s + 1)
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      position: 'relative',
      padding: 12,
    }}>
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 2,
        height: 46,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div />
        <div style={{
          color: 'var(--color-text-dim)',
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.01em',
        }}>
          Discovery · {tasteState}
        </div>
      </div>

      {error && cards.length === 0 && (
        <div style={{
          height: 'calc(100% - 46px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 12,
          textAlign: 'center',
          color: 'var(--color-text)',
          padding: '0 20px',
        }}>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
            Couldn't load Discovery. Tap to retry.
          </p>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              minHeight: 44,
              padding: '0 16px',
              borderRadius: 12,
              border: '1px solid var(--color-border-soft)',
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
              fontSize: 14,
              fontWeight: 700,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {!error && cards.length === 0 && loading && <LoadingSkeleton count={6} />}

      {cards.length > 0 && (
        <div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: isThreeColumns ? 'repeat(3, minmax(0, 1fr))' : 'repeat(2, minmax(0, 1fr))',
            gap: 12,
          }}>
            {memoizedCards.map((card, index) => (
              <DiscoveryCard
                key={`${card?.image_id || index}`}
                card={card}
                onOpen={handleOpenCard}
                onSave={setSaveModalCard}
              />
            ))}
          </div>
        </div>
      )}

      {cards.length > 0 && (
        <div
          ref={sentinelRef}
          style={{ height: 30, marginTop: 12 }}
          aria-hidden
        />
      )}

      {cards.length > 0 && error === '' && loading && (
        <div style={{ height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            width: 18,
            height: 18,
            borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.2)',
            borderTopColor: '#ec4899',
            animation: 'spin 0.8s linear infinite',
          }} />
        </div>
      )}

      {cards.length === 0 && !loading && !error && (
        <div style={{
          height: 'calc(100% - 46px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          color: 'var(--color-text)',
          padding: '0 20px',
        }}>
          <p style={{ margin: 0, color: 'var(--color-text)', fontSize: 16, fontWeight: 700 }}>
            Nothing to show yet
          </p>
          <button
            type="button"
            onClick={() => navigate('/new')}
            style={{
              marginTop: 12,
              minHeight: 44,
              padding: '0 18px',
              borderRadius: 12,
              border: 'none',
              background: 'linear-gradient(135deg,#ec4899,#f43f5e)',
              color: '#fff',
              fontSize: 14,
              fontWeight: 700,
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            Start Taste Analysis
          </button>
        </div>
      )}

      {saveModalCard && (
        <SaveToBoardModal
          card={saveModalCard}
          onClose={() => setSaveModalCard(null)}
          onSaved={handleSaved}
        />
      )}

      {surpriseOpen && (
        <SurpriseBoardModal
          onClose={() => setSurpriseOpen(false)}
          onSaved={() => setSurpriseOpen(false)}
        />
      )}
    </div>
  )
}
