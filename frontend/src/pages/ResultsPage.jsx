import { Fragment, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { useResults } from '../hooks/useResults.js'
import { resolveProjectBackendId } from '../utils/resolveProjectBackendId.js'

function cardId(card) {
  return card?.image_id || card?.canonical_bld_id || card?.building_id || ''
}

function personaFields(result, project) {
  const report = result?.analysis_report || project?.finalReport || {}
  return {
    type: report.persona_type || report.title || 'Your Architecture Persona',
    line: report.one_liner || report.summary || 'A compact read of the forms, programs, and atmospheres you kept choosing.',
    styles: report.styles || report.style_tags || [],
    programs: report.programs || report.program_tags || [],
  }
}

function ResultCard({ card, rank, saved, pending, onOpen, onToggle }) {
  const title = card.image_title || card.name_en || `Recommendation ${rank}`
  const architects = card.metadata?.axis_architects || card.architect
  const country = card.metadata?.axis_country || card.location_country
  const year = card.metadata?.axis_year || card.year

  return (
    <article
      onClick={() => onOpen(card, rank)}
      style={{
      position: 'relative',
      flex: '0 0 min(82vw, 320px)',
      height: 'min(58vh, 520px)',
      minHeight: 420,
      borderRadius: 20,
      overflow: 'hidden',
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border-soft)',
      boxShadow: '0 18px 42px rgba(0,0,0,0.35)',
      scrollSnapAlign: 'start',
      cursor: 'pointer',
    }}>
      <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />
      {card.image_url && (
        <img
          src={card.image_url}
          alt={title}
          loading={rank === 1 ? 'eager' : 'lazy'}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      )}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.94) 0%, rgba(0,0,0,0.52) 48%, rgba(0,0,0,0.08) 100%)',
      }} />
      <div style={{
        position: 'absolute',
        top: 14,
        left: 14,
        padding: '7px 10px',
        borderRadius: 999,
        background: 'rgba(0,0,0,0.48)',
        border: '1px solid rgba(255,255,255,0.12)',
        color: '#fff',
        fontSize: 12,
        fontWeight: 800,
      }}>
        #{rank}
      </div>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          onToggle(card, rank)
        }}
        disabled={pending}
        aria-label={saved ? 'Remove bookmark' : 'Save bookmark'}
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          width: 44,
          height: 44,
          borderRadius: '50%',
          border: saved ? '1px solid rgba(251,191,36,0.65)' : '1px solid rgba(255,255,255,0.16)',
          background: saved ? 'rgba(251,191,36,0.18)' : 'rgba(0,0,0,0.45)',
          color: saved ? '#fbbf24' : '#fff',
          fontSize: 20,
          cursor: pending ? 'default' : 'pointer',
          opacity: pending ? 0.65 : 1,
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        {saved ? '★' : '☆'}
      </button>
      <div style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        padding: '22px 18px 20px',
      }}>
        <h2 style={{
          color: '#fff',
          fontSize: 21,
          fontWeight: 800,
          lineHeight: 1.2,
          margin: '0 0 8px',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {title}
        </h2>
        {architects && (
          <p style={{ color: 'rgba(255,255,255,0.68)', fontSize: 13, fontStyle: 'italic', margin: '0 0 14px' }}>
            {architects}
          </p>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {[country, year].filter(Boolean).map(value => (
            <span key={value} style={{
              color: 'rgba(255,255,255,0.72)',
              fontSize: 11,
              fontWeight: 700,
              padding: '5px 8px',
              borderRadius: 999,
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.10)',
            }}>
              {value}
            </span>
          ))}
        </div>
      </div>
    </article>
  )
}

export default function ResultsPage({ projects, setProjects }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { sessionId } = useParams()
  const { cards, error, loading, pendingIds, project, result, toggleBookmark } = useResults(sessionId, projects, setProjects)
  const [loadedRank, setLoadedRank] = useState(10)
  const observerRef = useRef(null)
  const persona = personaFields(result, project)
  const cappedTotal = Math.min(cards.length, 50)
  const visibleCount = Math.min(loadedRank, cappedTotal)
  const topCards = cards.slice(0, visibleCount)
  const savedIds = project?.savedIds || []

  // Reconcile bookmark state when navigating back from BuildingDetailPage
  useEffect(() => {
    const changed = location.state?.bookmarkChanged
    if (!changed || !project) return
    const { buildingId, action } = changed
    if (!buildingId || !action) return
    setProjects(prev => prev.map(p => {
      if (p.sessionId !== sessionId) return p
      const current = p.savedIds || []
      const next = action === 'save'
        ? [...new Set([...current, buildingId])]
        : current.filter(id => id !== buildingId)
      return { ...p, savedIds: next }
    }))
    // Clear signal so a further navigate(-1)/forward doesn't re-apply it
    navigate(location.pathname, { replace: true, state: null })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setLoadedRank(10)
  }, [sessionId])

  useEffect(() => {
    const node = observerRef.current
    if (!node || loadedRank >= cappedTotal) return
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        setLoadedRank(prev => Math.min(prev + 10, cappedTotal))
      }
    }, { root: null, rootMargin: '160px' })
    observer.observe(node)
    return () => observer.disconnect()
  }, [loadedRank, cappedTotal])

  function handleOpenBuilding(card, rank) {
    const id = cardId(card)
    const fromProjectId = resolveProjectBackendId(project)
    if (!id) return
    navigate(`/buildings/${id}`, {
      state: {
        fromProjectId,
        fromSessionId: sessionId,
        rank,
        savedIds,
        referrer: location.pathname,
      },
    })
  }

  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'calc(88px + env(safe-area-inset-bottom, 0px))',
    }}>
      <section style={{
        minHeight: '34vh',
        maxHeight: '40vh',
        padding: '18px 18px 16px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--color-border-soft)',
        background: 'radial-gradient(circle at 20% 0%, rgba(236,72,153,0.14), transparent 45%), var(--color-bg)',
      }}>
        <button
          type="button"
          onClick={() => navigate('/')}
          style={{
            alignSelf: 'flex-start',
            minHeight: 44,
            border: 'none',
            background: 'transparent',
            color: 'var(--color-text-dim)',
            fontSize: 13,
            fontWeight: 700,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          ← Home
        </button>
        <div>
          <p style={{
            color: 'var(--color-text-muted)',
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            margin: '0 0 10px',
          }}>
            Persona report
          </p>
          <h1 style={{
            color: 'var(--color-text)',
            fontSize: 'clamp(26px, 8vw, 38px)',
            fontWeight: 800,
            lineHeight: 1.05,
            margin: '0 0 10px',
          }}>
            {persona.type}
          </h1>
          <p style={{
            color: 'var(--color-text-dim)',
            fontSize: 14,
            lineHeight: 1.5,
            margin: 0,
            maxWidth: 620,
          }}>
            {persona.line}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div className="skeleton-shimmer" style={{ width: 72, height: 44, borderRadius: 12 }} />
          <div style={{ color: 'var(--color-text-dimmer)', fontSize: 12, fontWeight: 600 }}>
            Imagen persona preview queued for Phase 2
          </div>
        </div>
      </section>

      <section style={{
        minHeight: '60vh',
        padding: '18px 0 24px',
      }}>
        <div style={{ padding: '0 18px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', margin: '0 0 5px' }}>
              Top-K recommendations
            </p>
            <h2 style={{ color: 'var(--color-text)', fontSize: 20, fontWeight: 800, margin: 0 }}>
              Rank 1-{Math.max(visibleCount, 10)}
            </h2>
          </div>
          <span style={{ color: 'var(--color-text-dimmer)', fontSize: 12, fontWeight: 700 }}>
            {topCards.length}/{Math.max(cappedTotal, 10)}
          </span>
        </div>

        {loading && topCards.length === 0 ? (
          <div style={{ display: 'flex', gap: 14, overflow: 'hidden', padding: '0 18px' }}>
            {[0, 1].map(i => (
              <div key={i} className="skeleton-shimmer" style={{
                flex: '0 0 min(82vw, 320px)',
                height: 'min(58vh, 520px)',
                minHeight: 420,
                borderRadius: 20,
              }} />
            ))}
          </div>
        ) : error ? (
          <p style={{ color: 'var(--color-text-dim)', fontSize: 14, padding: '20px 18px', margin: 0 }}>
            {error}
          </p>
        ) : (
          <>
            <div className="hide-scrollbar" style={{
              display: 'flex',
              gap: 14,
              overflowX: 'auto',
              scrollSnapType: 'x mandatory',
              padding: '0 18px 18px',
            }}>
              {topCards.map((card, index) => {
                const id = cardId(card)
                return (
                  <Fragment key={id || index}>
                    {index === 10 && (
                      <div style={{
                        flex: '0 0 120px',
                        minHeight: 420,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--color-text-dim)',
                        fontSize: 12,
                        fontWeight: 700,
                        textAlign: 'center',
                        borderLeft: '1px solid var(--color-border-soft)',
                        borderRight: '1px solid var(--color-border-soft)',
                        margin: '24px 10px',
                      }}>
                        더 많은 추천
                      </div>
                    )}
                    <ResultCard
                      card={card}
                      rank={index + 1}
                      saved={savedIds.includes(id)}
                      pending={pendingIds.has(id)}
                      onOpen={handleOpenBuilding}
                      onToggle={toggleBookmark}
                    />
                  </Fragment>
                )
              })}
              {loadedRank < cappedTotal && (
                <div ref={observerRef} style={{ flex: '0 0 1px', minHeight: 420 }} />
              )}
            </div>
            {loadedRank >= cards.length && cards.length > 0 && cards.length < 50 && (
              <div style={{
                margin: '10px 18px 0',
                padding: '16px 0 0',
                borderTop: '1px solid var(--color-border-soft)',
                color: 'var(--color-text-dimmer)',
                fontSize: 13,
                fontWeight: 700,
                textAlign: 'center',
              }}>
                더 볼 게 없어요
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
