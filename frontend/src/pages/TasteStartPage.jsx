import { useState, useRef, useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { getProject } from '../api/projects.js'
import { recognizeTaste, findTasteCards } from '../api/taste.js'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import { stepIndex, buildChips, isTypingTarget } from '../utils/tasteStart.js'
import ps from './TasteStartPage.module.css'

const MAX_EXCLUDE = 100
const CARD_W = 'min(280px, calc(100vw - 110px))'

function tagLabel(tag, language) {
  return (language === 'en' ? tag.label_en || tag.label_ko : tag.label_ko || tag.label_en) || String(tag.value)
}

function loadRounds(key) {
  try {
    const raw = sessionStorage.getItem(key)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
    }
  } catch { /* ignore */ }
  return []
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  )
}

function Composer({ value, onChange, onSubmit, disabled, placeholder, rows, sendLabel }) {
  const canSend = !disabled && value.trim().length > 0
  return (
    <div className={ps.composer}>
      <textarea
        className={ps.textarea}
        value={value}
        rows={rows}
        maxLength={500}
        placeholder={placeholder}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            if (canSend) onSubmit()
          }
        }}
        style={{ maxHeight: 96 }}
      />
      <button type="button" className={ps.sendBtn} disabled={!canSend} onClick={onSubmit} aria-label={sendLabel}>
        <SendIcon />
      </button>
    </div>
  )
}

// matched === undefined -> plain chip (no check mark), used for carried-over board tags.
function TagChip({ tag, matched, language, t }) {
  const showMark = matched !== undefined
  const dim = showMark && !matched
  return (
    <span
      title={showMark ? (matched ? t('search.tasteTagMatched') : t('search.tasteTagMissed')) : undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 11, fontWeight: 500, padding: '4px 10px', borderRadius: 999,
        color: 'var(--accent-1)',
        background: 'color-mix(in srgb, var(--accent-1) 10%, transparent)',
        border: '1px solid color-mix(in srgb, var(--accent-1) 22%, transparent)',
        opacity: dim ? 0.5 : 1,
        textDecoration: dim ? 'line-through' : 'none',
      }}
    >
      {showMark && <span aria-hidden="true">{matched ? '✓' : '✕'}</span>}
      {tagLabel(tag, language)}
    </span>
  )
}

function CardImage({ card, priority }) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const showImg = card.image_url && !failed
  return (
    <>
      {!loaded && <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />}
      {showImg ? (
        <img
          src={card.image_url} srcSet={card.image_srcset || undefined}
          alt={card.image_title || ''} draggable={false}
          loading="eager" fetchpriority={priority ? 'high' : 'auto'}
          onLoad={() => setLoaded(true)}
          onError={() => { setFailed(true); setLoaded(true) }}
          style={{
            width: '100%', height: '100%', objectFit: 'cover', display: 'block',
            opacity: loaded ? 1 : 0, transition: 'opacity 0.3s',
          }}
        />
      ) : null}
    </>
  )
}

function CardStack({ cards, index, onStep, rankLabel }) {
  const [dragX, setDragX] = useState(0)
  const startX = useRef(null)
  const moved = useRef(false)

  function onPointerDown(e) {
    startX.current = e.clientX
    moved.current = false
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }
  function onPointerMove(e) {
    if (startX.current === null) return
    const dx = e.clientX - startX.current
    if (Math.abs(dx) > 8) moved.current = true
    setDragX(Math.max(-120, Math.min(120, dx)))
  }
  function finish(e, cancelled) {
    if (startX.current === null) return
    const dx = e.clientX - startX.current
    startX.current = null
    setDragX(0)
    if (cancelled) return
    if (dx <= -40) onStep(1)
    else if (dx >= 40) onStep(-1)
    else if (!moved.current) onStep(1) // tap = next
  }

  return (
    <div
      className={ps.stack}
      tabIndex={0}
      role="group"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={e => finish(e, false)}
      onPointerCancel={e => finish(e, true)}
      style={{ width: `calc(${CARD_W} + 28px)`, margin: '0 auto' }}
    >
      <div style={{ position: 'relative', width: CARD_W, aspectRatio: '280 / 380', maxHeight: 380 }}>
        {cards.map((item, j) => {
          const rel = j - index
          const c = item.card
          const hidden = rel < 0
          const isFront = rel === 0
          const tx = hidden ? -50 : rel * 14 + (isFront ? dragX : 0)
          const scale = hidden ? 0.95 : 1 - 0.05 * rel
          const country = c.metadata?.axis_country
          const use = c.metadata?.axis_typology
          return (
            <div
              key={c.image_id}
              className={`${ps.card} ${isFront && dragX !== 0 ? ps.cardDragging : ''}`}
              style={{
                width: '100%', height: '100%',
                transform: `translateX(${tx}px) scale(${scale})`,
                opacity: hidden ? 0 : 1,
                zIndex: 10 - j,
                pointerEvents: 'none',
              }}
            >
              <CardImage card={c} priority={isFront} />
              <span style={{
                position: 'absolute', top: 12, left: 12,
                fontSize: 'var(--fs-caption)', fontWeight: 600, color: '#fff',
                background: 'var(--color-scrim)', borderRadius: 999, padding: '3px 10px',
              }}>{rankLabel(j + 1)}</span>
              <div style={{
                position: 'absolute', left: 0, right: 0, bottom: 0, padding: '40px 14px 14px',
                background: 'linear-gradient(to top, var(--color-scrim-strong), transparent)',
                color: '#fff',
              }}>
                <div style={{
                  fontSize: 'var(--fs-emphasis)', fontWeight: 600, lineHeight: 1.3,
                  overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                }}>{c.image_title}</div>
                {(country || use) && (
                  <div style={{ fontSize: 'var(--fs-caption)', opacity: 0.85, marginTop: 4 }}>
                    {[country, use].filter(Boolean).map(String).join(' · ')}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function LoadingBlock({ label }) {
  return (
    <div role="status" aria-label={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: '4px 0' }}>
      <div className={ps.skelBlock} style={{ width: CARD_W, aspectRatio: '280 / 380', maxHeight: 380, borderRadius: 'var(--radius-lg)' }} />
      <span style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)' }}>{label}</span>
    </div>
  )
}

function UserBubble({ text }) {
  return (
    <div style={{ alignSelf: 'flex-end', maxWidth: '85%' }}>
      <div style={{
        padding: '10px 14px', borderRadius: 16, borderBottomRightRadius: 4,
        fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        background: 'var(--color-user-bubble)', color: 'var(--color-user-bubble-text)',
      }}>{text}</div>
    </div>
  )
}

function Round({ round, isLatest, language, t, busy, starting, onStep, onFindAgain, onStart }) {
  const front = round.cards[round.index] || round.cards[0]
  const chips = useMemo(() => buildChips(round.tags, front?.matched_keys), [round.tags, front])
  const n = round.cards.length
  return (
    <div id={`taste-round-${round.id}`} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <UserBubble text={round.text} />

      {chips.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {chips.map(({ tag, matched }) => (
            <TagChip key={`${tag.axis}:${tag.value}`} tag={tag} matched={matched} language={language} t={t} />
          ))}
        </div>
      )}

      {n === 0 ? (
        <div style={{ fontSize: 'var(--fs-body)', color: 'var(--color-text-muted)', textAlign: 'center', padding: '16px 0' }}>
          {t('search.tasteNoCards')}
        </div>
      ) : busy ? (
        <LoadingBlock label={t('search.tasteRoundLoading')} />
      ) : (
        <>
          <CardStack
            cards={round.cards} index={round.index}
            onStep={dir => onStep(round.id, dir)}
            rankLabel={k => t('search.tasteRankLabel', { n: k })}
          />
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            {front && front.total > 0 && (
              <div style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)' }}>
                {t('search.tasteTagsMatch', { n: front.total, m: front.hit })}
              </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fs-caption)', color: 'var(--color-text-dim)' }}>
              <span>{t('search.tasteCardPosition', { k: round.index + 1, n })}</span>
              <span style={{ display: 'flex', gap: 5 }} aria-hidden="true">
                {round.cards.map((_, j) => (
                  <span key={j} style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: j === round.index ? 'var(--color-text)' : 'var(--color-surface-3)',
                  }} />
                ))}
              </span>
            </div>
          </div>
        </>
      )}

      {isLatest && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360, width: '100%', alignSelf: 'center' }}>
          <button type="button" className={ps.ctaPrimary} disabled={n === 0 || busy || starting} onClick={() => onStart(round)}>
            {t('search.tasteStartSwiping')}
          </button>
          <button type="button" className={ps.ctaSecondary} disabled={busy || starting || round.exhausted} onClick={() => onFindAgain(round.id)}>
            {t('search.tasteFindAgain')}
          </button>
          {round.exhausted && (
            <div style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-dim)', textAlign: 'center' }}>
              {t('search.tasteNoMoreCards')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function TasteStartPage({ onStartTaste, onLogout }) {
  const { t, language } = useTranslation()
  const { projectId } = useParams()
  const mode = projectId ? 'update' : 'new'
  const userId = sessionStorage.getItem('archithon_user') || 'anon'
  const storageKey = `archithon_taste_${userId}_${mode}_${projectId || 'new'}`

  const [rounds, setRounds] = useState(() => loadRounds(storageKey))
  const [pending, setPending] = useState(null) // { text } while recognize is in flight
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [busyRoundId, setBusyRoundId] = useState(null)
  const [starting, setStarting] = useState(false)
  const [board, setBoard] = useState(null) // update mode: { name, tags }
  const scrollRef = useRef(null)
  const endRef = useRef(null)
  const roundsRef = useRef(rounds)

  useEffect(() => { roundsRef.current = rounds }, [rounds])

  // Persist rounds (refresh keeps them).
  useEffect(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify(rounds)) } catch { /* quota: ignore */ }
  }, [storageKey, rounds])

  // Update mode: load the board for its name + carried-over taste_tags.
  // projectId from the route is the board's project_id (the same id
  // handleResumeProject / handleUpdateWithImages use as the local project id).
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    getProject(projectId).then(p => {
      if (cancelled || !p) return
      setBoard({ name: p.name || '', tags: Array.isArray(p.taste_tags) ? p.taste_tags : [] })
    })
    return () => { cancelled = true }
  }, [projectId])

  const latest = rounds[rounds.length - 1] || null
  const inRounds = rounds.length > 0 || pending !== null

  // Arrow keys act on the latest round, never while typing.
  useEffect(() => {
    function onKey(e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(document.activeElement)) return
      const last = roundsRef.current[roundsRef.current.length - 1]
      if (!last || last.cards.length === 0) return
      e.preventDefault()
      const dir = e.key === 'ArrowRight' ? 1 : -1
      setRounds(prev => prev.map(r => r.id === last.id ? { ...r, index: stepIndex(r.index, dir, r.cards.length) } : r))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Scroll the new round (or the loading placeholder) into view.
  useEffect(() => {
    if (pending) {
      endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    } else if (latest) {
      const el = scrollRef.current?.querySelector(`#taste-round-${latest.id}`)
      // Stop below the fixed top controls (top 14 + height 34) instead of under them.
      if (el) el.style.scrollMarginTop = '64px'
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [latest?.id, pending]) // eslint-disable-line react-hooks/exhaustive-deps

  function stepRound(id, dir) {
    setRounds(prev => prev.map(r => r.id === id ? { ...r, index: stepIndex(r.index, dir, r.cards.length) } : r))
  }

  function errorMessage(err) {
    return err?.status === 429 ? t('search.tasteRateLimited') : t('search.tasteError')
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || pending) return
    setError('')
    setPending({ text })
    try {
      const res = await recognizeTaste({ text, prevTags: mode === 'update' ? (board?.tags || []) : [] })
      const round = {
        id: `r${Date.now()}`,
        text,
        tags: res.tags,
        cards: res.cards,
        shown: res.cards.map(c => c.card.image_id),
        index: 0,
        exhausted: false,
      }
      setRounds(prev => [...prev, round])
      setInput('')
    } catch (err) {
      setError(errorMessage(err)) // typed text stays in the composer
    } finally {
      setPending(null)
    }
  }

  async function handleFindAgain(id) {
    const round = rounds.find(r => r.id === id)
    if (!round || busyRoundId) return
    setBusyRoundId(id)
    setError('')
    try {
      const cards = await findTasteCards({ tags: round.tags, excludeIds: round.shown })
      setRounds(prev => prev.map(r => {
        if (r.id !== id) return r
        if (cards.length === 0) return { ...r, exhausted: true }
        const shown = [...new Set([...r.shown, ...cards.map(c => c.card.image_id)])]
        return { ...r, cards, shown, index: 0, exhausted: false }
      }))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyRoundId(null)
    }
  }

  async function handleStart(round) {
    if (starting || round.cards.length === 0) return
    setStarting(true)
    const startIds = round.cards.map(c => c.card.image_id)
    const excludeIds = round.shown.filter(id => !startIds.includes(id)).slice(-MAX_EXCLUDE)
    const firstText = rounds[0]?.text || round.text
    try { sessionStorage.removeItem(storageKey) } catch { /* ignore */ }
    try {
      await onStartTaste({
        mode,
        projectId,
        projectName: mode === 'update' ? board?.name : '',
        rawQuery: firstText,
        tags: round.tags,
        startIds,
        excludeIds,
      })
    } catch {
      setError(t('search.tasteStartFailed'))
      try { sessionStorage.setItem(storageKey, JSON.stringify(roundsRef.current)) } catch { /* ignore */ }
    } finally {
      setStarting(false)
    }
  }

  function handleNewConversation() {
    if (rounds.length > 0 && !window.confirm(t('search.newConversationConfirm'))) return
    setRounds([])
    setPending(null)
    setInput('')
    setError('')
    try { sessionStorage.removeItem(storageKey) } catch { /* ignore */ }
  }

  const errorEl = error ? (
    <div role="alert" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-destructive)', marginTop: 8 }}>{error}</div>
  ) : null

  const carriedChips = mode === 'update' && rounds.length === 0
    ? (board?.tags || []).filter(g => g.polarity !== 'exclude')
    : []
  const carried = carriedChips.length > 0 ? (
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-muted)', marginBottom: 6 }}>
        {t('search.tasteCurrentConditions')}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {carriedChips.map(tag => (
          <TagChip key={`${tag.axis}:${tag.value}`} tag={tag} matched={undefined} language={language} t={t} />
        ))}
      </div>
    </div>
  ) : null

  return (
    <div style={{
      height: 'var(--page-height)', overflow: 'hidden', background: 'var(--color-bg)',
      display: 'flex', flexDirection: 'column',
    }}>
      <PageTopControls
        onLogout={onLogout}
        leading={
          <PageBackButton
            inline
            onClick={handleNewConversation}
            label={t('search.newConversation')}
            icon={
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 .49-4.5" />
              </svg>
            }
          />
        }
      />

      {!inRounds ? (
        <div style={{
          flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
          justifyContent: 'center', alignItems: 'center',
          padding: '24px 16px', paddingBottom: 'var(--tabbar-clearance)',
        }}>
          <div style={{ width: '100%', maxWidth: 420 }}>
            <PageLogoHeader padding="0" marginBottom={20} />
            <h2 style={{
              fontSize: 30, fontWeight: 500, lineHeight: 1.25, margin: '0 0 24px',
              textAlign: 'center', letterSpacing: '-0.01em', color: 'var(--color-text)',
            }}>
              {t('search.tasteHeadlineLine1')}<br />
              <span style={{ color: 'var(--accent-1)' }}>{t('search.tasteHeadlineLine2')}</span>
            </h2>
            {carried}
            <Composer
              value={input} onChange={setInput} onSubmit={handleSend}
              disabled={false} rows={3}
              placeholder={t('search.tastePlaceholder')} sendLabel={t('search.tasteSend')}
            />
            {errorEl}
          </div>
        </div>
      ) : (
        <>
          <div ref={scrollRef} style={{
            flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '0 16px',
            paddingBottom: 'calc(var(--tabbar-clearance) + 84px)',
          }}>
            <div style={{ width: '100%', maxWidth: 480, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 36 }}>
              <PageLogoHeader padding="60px 16px 6px" />
              {rounds.map(r => (
                <Round
                  key={r.id} round={r} isLatest={pending === null && r.id === latest?.id} language={language} t={t}
                  busy={busyRoundId === r.id} starting={starting}
                  onStep={stepRound} onFindAgain={handleFindAgain} onStart={handleStart}
                />
              ))}
              {pending && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <UserBubble text={pending.text} />
                  <LoadingBlock label={t('search.tasteRoundLoading')} />
                </div>
              )}
              <div ref={endRef} />
            </div>
          </div>

          <div style={{
            position: 'fixed', bottom: 'var(--tabbar-clearance)', left: 0, right: 0,
            padding: '12px 16px', zIndex: 30,
            background: 'linear-gradient(to top, var(--color-bg) 80%, transparent)',
          }}>
            <div style={{ maxWidth: 480, margin: '0 auto' }}>
              <Composer
                value={input} onChange={setInput} onSubmit={handleSend}
                disabled={pending !== null} rows={1}
                placeholder={t('search.inputPlaceholder')} sendLabel={t('search.tasteSend')}
              />
              {errorEl}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
