import { useState, useRef, useEffect, useMemo } from 'react'
import { recognizeTaste, findTasteCards } from '../api/taste.js'
import { submitCardReport, cancelCardReport, submitQueryReport, cancelQueryReport } from '../api/feedback.js'
import { useImageTelemetry } from '../hooks/useImageTelemetry.js'
import Modal from '../components/Modal.jsx'
import TasteCardDetail from '../components/TasteCardDetail.jsx'
import TasteCardGallery from '../components/TasteCardGallery.jsx'
import TasteCardReport, { ReportIcon } from '../components/TasteCardReport.jsx'
import fb from '../components/TasteFeedback.module.css'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import { stepIndex, buildChips, isTypingTarget, tagKey, keptCards, cardZIndex, buildStartDeck } from '../utils/tasteStart.js'
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

function TagChip({ tag, matched, language, t }) {
  const dim = !matched
  return (
    <span
      title={matched ? t('search.tasteTagMatched') : t('search.tasteTagMissed')}
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
      <span aria-hidden="true">{matched ? '✓' : '✕'}</span>
      {tagLabel(tag, language)}
    </span>
  )
}

function CardImage({ card, priority }) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  const showImg = card.image_url && !failed
  const { onLoad, onError } = useImageTelemetry({ buildingId: card.image_id, context: 'taste_start_card' })
  return (
    <>
      {!loaded && <div className="skeleton-shimmer" style={{ position: 'absolute', inset: 0 }} />}
      {showImg ? (
        <img
          src={card.image_url} srcSet={card.image_srcset || undefined}
          alt={card.image_title || ''} draggable={false}
          loading="eager" fetchpriority={priority ? 'high' : 'auto'}
          onLoad={e => { setLoaded(true); onLoad(e) }}
          onError={e => { setFailed(true); setLoaded(true); onError(e) }}
          style={{
            width: '100%', height: '100%', objectFit: 'cover', display: 'block',
            opacity: loaded ? 1 : 0, transition: 'opacity 0.3s',
          }}
        />
      ) : null}
    </>
  )
}

const blankUi = id => ({ id, exp: false, gal: false, galSeen: false, panel: false })

function CardStack({ round, index, onStep, rankLabel, t, language, onSubmitReport, onCancelReport, sheetOpen }) {
  const cards = round.cards
  const reports = round.reports || {}
  const [dragX, setDragX] = useState(0)
  const [uiState, setUiState] = useState(() => blankUi(null))
  const startX = useRef(null)
  const startT = useRef(0)
  const moved = useRef(false)

  // Detail / gallery / report-panel state belongs to the front card; moving to
  // another card (or a new deck) implicitly resets it.
  const frontItem = cards[index]
  const frontId = frontItem?.card.image_id ?? null
  // Reset when the front card changes (A->B->A must not resurrect A's state)
  // or while the round-report sheet is open (one Escape closes one thing).
  if (uiState.id !== frontId || (sheetOpen && (uiState.exp || uiState.gal || uiState.galSeen || uiState.panel))) {
    setUiState(blankUi(frontId))
  }
  const ui = uiState.id === frontId ? uiState : blankUi(frontId)
  function patch(p) {
    setUiState(prev => ({ ...(prev.id === frontId ? prev : blankUi(frontId)), ...p }))
  }
  const chips = useMemo(
    () => buildChips(round.tags, frontItem?.matched_keys),
    [round.tags, frontItem],
  )

  function onPointerDown(e) {
    // Buttons, the report panel and the gallery close button never start a drag/tap.
    if (e.target.closest?.('[data-nodrag]')) return
    startX.current = e.clientX
    startT.current = Date.now()
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
    else if (!moved.current && Date.now() - startT.current < 300) {
      // tap: close the gallery, else toggle the detail (ignored while reporting)
      if (ui.gal) patch({ gal: false })
      else if (!ui.panel) patch({ exp: !ui.exp })
    }
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
          const reported = !!reports[c.image_id]
          const galOpen = isFront && ui.gal
          return (
            <div
              key={c.image_id}
              className={`${ps.card} ${isFront && dragX !== 0 ? ps.cardDragging : ''}`}
              style={{
                width: '100%', height: '100%',
                transform: `translateX(${tx}px) scale(${scale})`,
                opacity: hidden ? 0 : 1,
                zIndex: cardZIndex(rel),
                pointerEvents: isFront ? 'auto' : 'none',
              }}
            >
              <div style={{
                position: 'absolute', inset: 0, transformStyle: 'preserve-3d',
                transform: galOpen ? 'rotateY(180deg)' : 'none',
                transition: 'transform var(--motion-flip) var(--motion-ease)',
              }}>
                <div style={{
                  position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 'var(--radius-lg)',
                  backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
                  pointerEvents: isFront && !galOpen ? 'auto' : 'none',
                }}>
                  <CardImage card={c} priority={isFront} />
                  <span style={{
                    position: 'absolute', top: 12, left: 12, zIndex: 4,
                    fontSize: 'var(--fs-caption)', fontWeight: 600, color: '#fff',
                    background: 'var(--color-scrim)', borderRadius: 999, padding: '3px 10px',
                  }}>{rankLabel(j + 1)}</span>
                  <TasteCardDetail
                    card={c} t={t}
                    expanded={isFront && ui.exp}
                    captionHidden={isFront && ui.panel}
                    interactive={isFront}
                    onOpenGallery={() => patch({ gal: true, galSeen: true, exp: true })}
                  />
                  {isFront && (
                    <>
                      <div className={`${fb.veil} ${ui.panel ? fb.veilOn : ''}`}>
                        {ui.panel && (
                          <TasteCardReport
                            key={c.image_id}
                            chips={chips}
                            prev={reports[c.image_id] || null}
                            t={t}
                            tagLabel={tag => tagLabel(tag, language)}
                            onClose={() => patch({ panel: false })}
                            onSubmit={async form => {
                              const ok = await onSubmitReport(j, form)
                              if (ok) patch({ panel: false })
                            }}
                            onCancelReport={async () => {
                              const ok = await onCancelReport(j)
                              if (ok) patch({ panel: false })
                            }}
                          />
                        )}
                      </div>
                      <button
                        type="button" data-nodrag=""
                        className={`${fb.reportBtn} ${reported ? fb.reportBtnOn : ''}`}
                        aria-label={t('search.tasteReportAria')} title={t('search.tasteReportAria')}
                        aria-pressed={reported}
                        onClick={() => patch({ panel: !ui.panel, exp: false })}
                      ><ReportIcon /></button>
                    </>
                  )}
                </div>
                {isFront && ui.galSeen && (
                  <div style={{
                    position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 'var(--radius-lg)',
                    backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
                    transform: 'rotateY(180deg)', background: '#000',
                    pointerEvents: ui.gal ? 'auto' : 'none',
                  }}>
                    <TasteCardGallery
                      card={c} active={ui.gal}
                      closeLabel={t('search.tasteReportClose')}
                      onClose={() => patch({ gal: false })}
                    />
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

function QueryReportSheet({ round, language, t, onClose, onSubmit, onCancel }) {
  const prev = round.queryReport || null
  const [picked, setPicked] = useState(() => (prev?.tags || []).map(tagKey))
  const [text, setText] = useState(prev?.text || '')
  const [sending, setSending] = useState(false)
  const allTags = round.tags
  const canSend = (picked.length > 0 || text.trim().length > 0) && !sending

  async function run(fn) {
    setSending(true)
    try { await fn() } finally { setSending(false) }
  }
  function send() {
    return run(() => onSubmit({
      tags: allTags.filter(tg => picked.includes(tagKey(tg))).map(tg => ({ axis: tg.axis, value: tg.value })),
      text: text.trim(),
    }))
  }

  return (
    <Modal open onClose={onClose} title={t('search.tasteQueryLink')} closeLabel={t('search.tasteReportClose')} zIndex={400} portal>
      <p className={fb.sheetSub}>{prev ? t('search.tasteQuerySubPrev') : t('search.tasteQuerySub')}</p>
      <div className={fb.sheetLabel}>{t('search.tasteQueryWrongTags')}</div>
      <div className={fb.pick}>
        {allTags.map(tg => {
          const k = tagKey(tg)
          const on = picked.includes(k)
          return (
            <button
              key={k} type="button" aria-pressed={on}
              className={`${fb.spk} ${on ? fb.spkSel : ''}`}
              onClick={() => setPicked(on ? picked.filter(x => x !== k) : [...picked, k])}
            >{tg.polarity === 'exclude' ? '− ' : ''}{tagLabel(tg, language)}</button>
          )
        })}
      </div>
      <div className={fb.sheetLabel}>{t('search.tasteQueryMissing')}</div>
      <textarea
        className={fb.sheetTextarea} value={text} maxLength={500}
        placeholder={t('search.tasteQueryPlaceholder')}
        onChange={e => setText(e.target.value)}
      />
      <div className={fb.sheetRow}>
        {prev ? (
          <button type="button" className={ps.ctaSecondary} disabled={sending} onClick={() => run(onCancel)}>
            {t('search.tasteReportCancel')}
          </button>
        ) : (
          <button type="button" className={ps.ctaSecondary} onClick={onClose}>
            {t('search.tasteReportClose')}
          </button>
        )}
        <button type="button" className={ps.ctaPrimary} disabled={!canSend} onClick={send}>
          {prev ? t('search.tasteReportEdit') : t('search.tasteQuerySend')}
        </button>
      </div>
    </Modal>
  )
}

function Round({ round, isLatest, language, t, busy, starting, onStep, onFindAgain, onStart, onCardReport, onCardCancel, onQuerySheet, sheetOpen }) {
  const front = round.cards[round.index] || round.cards[0]
  const chips = useMemo(() => buildChips(round.tags, front?.matched_keys), [round.tags, front])
  const n = round.cards.length
  const reports = round.reports || {}
  const kept = keptCards(round.cards, reports).length
  return (
    <div id={`taste-round-${round.id}`} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <UserBubble text={round.text} />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
        {chips.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {chips.map(({ tag, matched }) => (
              <TagChip key={tagKey(tag)} tag={tag} matched={matched} language={language} t={t} />
            ))}
          </div>
        )}
        {round.tags.length > 0 && (
          <button type="button" className={fb.queryLink} onClick={() => onQuerySheet(round.id)}>
            {round.queryReport ? t('search.tasteQueryLinkSent') : t('search.tasteQueryLink')}
          </button>
        )}
      </div>

      {n === 0 ? (
        <div style={{ fontSize: 'var(--fs-body)', color: 'var(--color-text-muted)', textAlign: 'center', padding: '16px 0' }}>
          {t('search.tasteNoCards')}
        </div>
      ) : busy ? (
        <LoadingBlock label={t('search.tasteRoundLoading')} />
      ) : (
        <>
          <CardStack
            round={round} index={round.index}
            onStep={dir => onStep(round.id, dir)}
            rankLabel={k => t('search.tasteRankLabel', { n: k })}
            t={t} language={language} sheetOpen={sheetOpen}
            onSubmitReport={(j, form) => onCardReport(round.id, j, form)}
            onCancelReport={j => onCardCancel(round.id, j)}
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
                    boxShadow: reports[round.cards[j].card.image_id] ? '0 0 0 2px var(--color-destructive)' : 'none',
                  }} />
                ))}
              </span>
            </div>
          </div>
        </>
      )}

      {isLatest && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 360, width: '100%', alignSelf: 'center' }}>
          <button type="button" className={ps.ctaPrimary} disabled={kept === 0 || busy || starting} onClick={() => onStart(round)}>
            {kept === n ? t('search.tasteStartSwiping') : t('search.tasteStartSwipingN', { n: kept })}
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

export default function TasteStartPage({ onStartTaste, onLogout, showToast }) {
  const { t, language } = useTranslation()
  const userId = sessionStorage.getItem('archithon_user') || 'anon'
  const storageKey = `archithon_taste_${userId}_new`

  const [rounds, setRounds] = useState(() => loadRounds(storageKey))
  const [pending, setPending] = useState(null) // { text } while recognize is in flight
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [busyRoundId, setBusyRoundId] = useState(null)
  const [starting, setStarting] = useState(false)
  const scrollRef = useRef(null)
  const endRef = useRef(null)
  const roundsRef = useRef(rounds)
  const [sheetRoundId, setSheetRoundId] = useState(null) // round whose query-report sheet is open
  const sheetOpenRef = useRef(false)

  useEffect(() => { roundsRef.current = rounds }, [rounds])
  useEffect(() => { sheetOpenRef.current = sheetRoundId !== null }, [sheetRoundId])

  // Persist rounds (refresh keeps them).
  useEffect(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify(rounds)) } catch { /* quota: ignore */ }
  }, [storageKey, rounds])

  const latest = rounds[rounds.length - 1] || null
  const sheetRound = rounds.find(r => r.id === sheetRoundId) || null
  const inRounds = rounds.length > 0 || pending !== null

  // Arrow keys act on the latest round, never while typing.
  useEffect(() => {
    function onKey(e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(document.activeElement) || sheetOpenRef.current) return
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
      const res = await recognizeTaste({ text })
      const round = {
        id: `r${Date.now()}`,
        text,
        source: res.source,
        tags: res.tags,
        cards: res.cards,
        reports: {},
        queryReport: null,
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
    const { startIds, excludeIds } = buildStartDeck({
      cards: round.cards, shown: round.shown, reports: round.reports, max: MAX_EXCLUDE,
    })
    if (startIds.length === 0) return
    setStarting(true)
    try { sessionStorage.removeItem(storageKey) } catch { /* ignore */ }
    try {
      await onStartTaste({
        projectName: '',
        rawQuery: round.text,
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

  function notify(message, type = 'info') { showToast?.({ message, type }) }
  function patchRound(id, fn) { setRounds(prev => prev.map(r => (r.id === id ? fn(r) : r))) }

  async function handleCardReport(roundId, j, form) {
    const round = roundsRef.current.find(r => r.id === roundId)
    const item = round?.cards[j]
    if (!item) return false
    const id = item.card.image_id
    const again = !!round.reports?.[id]
    try {
      await submitCardReport({
        round_key: round.id,
        query_text: round.text,
        tags: round.tags,
        source: round.source || 'dictionary',
        language: language === 'en' ? 'en' : 'ko',
        canonical_bld_id: id,
        card_rank: j + 1,
        hit: item.hit,
        total: item.total,
        reason: form.reason || null,
        sub_reasons: form.sub,
        wrong_tags: form.reason === 'tag' ? form.tags : [],
        comment: form.text,
      })
    } catch {
      notify(t('search.tasteReportFailed'), 'error')
      return false
    }
    patchRound(roundId, r => ({ ...r, reports: { ...(r.reports || {}), [id]: form } }))
    notify(again ? t('search.tasteToastEdited') : t('search.tasteToastReported'), 'success')
    return true
  }

  async function handleCardCancel(roundId, j) {
    const round = roundsRef.current.find(r => r.id === roundId)
    const id = round?.cards[j]?.card.image_id
    if (!id) return false
    try {
      await cancelCardReport({ round_key: round.id, canonical_bld_id: id })
    } catch {
      notify(t('search.tasteReportFailed'), 'error')
      return false
    }
    patchRound(roundId, r => {
      const reports = { ...(r.reports || {}) }
      delete reports[id]
      return { ...r, reports }
    })
    notify(t('search.tasteToastCanceled'), 'info')
    return true
  }

  async function handleQuerySubmit(roundId, form) {
    const round = roundsRef.current.find(r => r.id === roundId)
    if (!round) return
    const again = !!round.queryReport
    try {
      await submitQueryReport({
        round_key: round.id,
        query_text: round.text,
        tags: round.tags,
        source: round.source || 'dictionary',
        language: language === 'en' ? 'en' : 'ko',
        wrong_tags: form.tags,
        comment: form.text,
      })
    } catch {
      notify(t('search.tasteReportFailed'), 'error')
      return
    }
    patchRound(roundId, r => ({ ...r, queryReport: form }))
    setSheetRoundId(null)
    notify(again ? t('search.tasteToastEdited') : t('search.tasteToastQuerySent'), 'success')
  }

  async function handleQueryCancel(roundId) {
    try {
      await cancelQueryReport({ round_key: roundId })
    } catch {
      notify(t('search.tasteReportFailed'), 'error')
      return
    }
    patchRound(roundId, r => ({ ...r, queryReport: null }))
    setSheetRoundId(null)
    notify(t('search.tasteToastCanceled'), 'info')
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
                  onCardReport={handleCardReport} onCardCancel={handleCardCancel} onQuerySheet={setSheetRoundId} sheetOpen={sheetRoundId !== null}
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

      {sheetRound && (
        <QueryReportSheet
          key={sheetRound.id} round={sheetRound} language={language} t={t}
          onClose={() => setSheetRoundId(null)}
          onSubmit={form => handleQuerySubmit(sheetRound.id, form)}
          onCancel={() => handleQueryCancel(sheetRound.id)}
        />
      )}
    </div>
  )
}
