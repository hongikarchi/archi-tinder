import { useCallback, useEffect, useRef, useState } from 'react'
import { useReportImageJob, reportImageJobs } from '../hooks/useReportImageJob.js'
import { useRegeneration } from '../hooks/useRegeneration.jsx'
import { useCardSize } from '../hooks/useCardSize.js'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
import { isLegacyAxisScores } from '../utils/axisScores.js'
import { safeImageMime } from '../utils/imageMime.js'
import TasteSpectrum from './TasteSpectrum.jsx'
import EmptyState from './EmptyState.jsx'
import PageLogoHeader from './PageLogoHeader.jsx'
import PageTopControls from './PageTopControls.jsx'
import PageBackButton from './PageBackButton.jsx'
import { ImageSlot } from './PersonaReportPage.jsx'
import rp from './PersonaReportPage.module.css'
import s from './ResultCards.module.css'

/**
 * ResultCards — the 3-card swipeable result view of /result/:sessionId
 * (FULL-REPORT-UI-1 WP3, #445). Look/copy/behaviour follow the approved mock
 * (archi-tinder-mock/persona-report-all.html: vCards / vPost); off-scale values
 * (DESIGN.md §11 E1/E5/E7/E8) live in ResultCards.module.css.
 *
 * Exports
 *   default  ResultCards      - the 3 cards (persona / pattern + taste / closing)
 *   named    ResultsStage     - page chrome (logo, top controls, centred card slot)
 *   named    ResultStateCard  - loading / failure / zero-likes card in the SAME box
 *
 * Card box = the Swipe card area: width/height from useCardSize() (the store
 * SwipeDeck/SwipePage use), centred, with a 16px side margin and an 8px peek of
 * the next card.
 */

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'
const ACTIVE_THRESHOLD = 0.6      // card counts as "active" once 60 % visible
const SIDE_PAD = 16               // carousel left padding (= scroll-padding-left in the CSS)
const DRAG_START_PX = 6
const CARD_COUNT = 3
const TAG_STAGGER_S = 0.06        // E8
const TAG_STAGGER_MAX_S = 0.66

function prefersReducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(REDUCED_MOTION_QUERY).matches
}

const ICON_PROPS = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
function IconRefresh() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...ICON_PROPS} aria-hidden="true">
      <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  )
}
function IconSearch() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...ICON_PROPS} aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

/* ── Page chrome ────────────────────────────────────────────────────────── */
export function ResultsStage({ onLogout, onBack, children }) {
  const { width, height } = useCardSize()
  return (
    <div className={s.page}>
      <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={onBack} />} />
      <PageLogoHeader padding="0 0 6px" marginBottom={8} />
      <div className={s.stage} style={{ '--cw': `${width}px`, '--ch': `${height}px` }}>
        {children}
      </div>
    </div>
  )
}

/* ── State card ─────────────────────────────────────────────────────────── */
function Bar({ w, h, mb }) {
  return <div className={rp.bar} style={{ width: w, height: h, marginBottom: mb }} />
}

/**
 * kind 'loading'  - "리포트를 만드는 중이에요" skeleton
 *      'fail'     - report generation failed (title/body/retry)
 *      'empty'    - zero likes (persona fallback + hint + start exploring)
 * Neutral tone, no red (DESIGN.md §8.9).
 */
export function ResultStateCard({ kind, onAction, actionLabel, title, body, hint }) {
  const { t } = useTranslation()
  if (kind === 'loading') {
    return (
      <div className={`${s.stateBox} ${s.skel}`} role="status" aria-live="polite">
        <p className={rp.skelLabel} style={{ marginBottom: 22 }}>{t('persona.loadingMake')}</p>
        <Bar w="34%" h={10} mb={16} /><Bar w="62%" h={26} mb={16} /><Bar w="96%" h={13} mb={8} />
        <Bar w="90%" h={13} mb={8} /><Bar w="58%" h={13} mb={24} />
        <div className={s.skelTags}><Bar w="64px" h={22} /><Bar w="64px" h={22} /><Bar w="64px" h={22} /></div>
        <Bar w="100%" h={150} />
      </div>
    )
  }
  return (
    <div className={s.stateBox}>
      <EmptyState
        neutral
        icon={kind === 'fail' ? <IconRefresh /> : <IconSearch />}
        title={title}
        body={body}
        hint={hint}
        actionLabel={actionLabel}
        onAction={onAction}
      />
    </div>
  )
}

/* ── Small pieces ───────────────────────────────────────────────────────── */
function Thumb({ imageData, imageMime, jobStatus, regenerating }) {
  const src = imageData ? `data:${safeImageMime(imageMime)};base64,${imageData}` : null
  const generating = !src && (jobStatus === 'generating' || regenerating)
  return (
    <div className={`${s.rv} ${s.thumb}`} style={{ '--d': '0s' }} aria-hidden="true">
      {src && <img className={s.thumbImg} src={src} alt="" />}
      {generating && <div className={rp.skeletonPulse} />}
    </div>
  )
}

/* ── Cards ──────────────────────────────────────────────────────────────── */
/**
 * Props
 *   project   the project (finalReport, axisScores, reportImage, reportImageMime)
 *   backendId project UUID (image job + regeneration)
 *   ctaLabel  closing-card CTA text
 *   onCta     () => void
 */
export default function ResultCards({ project, backendId, ctaLabel, onCta }) {
  const { t, language } = useTranslation()
  const carRef = useRef(null)
  const dragRef = useRef({ x0: null, sl0: 0, moved: false })
  const [reduced] = useState(prefersReducedMotion)
  const [seen, setSeen] = useState(() => new Set())
  const [active, setActive] = useState(0)

  const report = localizeReport(project?.finalReport || {}, language)
  const axisScores = project?.axisScores || null
  const legacy = isLegacyAxisScores(axisScores)

  // Image: same source + states as the shared report page. Image refresh is
  // owner-only; a result screen is always the owner's.
  const imageJob = useReportImageJob(backendId)
  const imageData = imageJob.image || project?.reportImage || null
  const imageMime = imageJob.image ? imageJob.mime : project?.reportImageMime
  const regen = useRegeneration({ projectId: backendId, enabled: true, axisScores, withReport: false })

  // Auto-start for legacy / previously failed boards (job must be idle; never after error/done).
  useEffect(() => {
    if (backendId && !imageData && imageJob.status === 'idle') reportImageJobs.start(backendId)
  }, [backendId, imageData, imageJob.status])

  // Per-card reveal + dots: a card becomes "seen" the first time it is ≥60 % visible.
  useEffect(() => {
    const car = carRef.current
    if (!car) return
    const cards = [...car.querySelectorAll('article')]
    const all = () => new Set(cards.map((_, i) => i))
    if (typeof IntersectionObserver === 'undefined') {
      setSeen(all())   // no observer: reveal everything, active dot stays on 1
      return
    }
    // Reduced motion: reveal everything up front but keep observing for the active dot.
    if (reduced) setSeen(all())
    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return
        const i = cards.indexOf(entry.target)
        if (i < 0) return
        setActive(i)
        if (!reduced) setSeen(prev => (prev.has(i) ? prev : new Set(prev).add(i)))
      })
    }, { root: car, threshold: ACTIVE_THRESHOLD })
    cards.forEach(c => io.observe(c))
    return () => io.disconnect()
  }, [reduced])

  const goTo = useCallback(i => {
    const car = carRef.current
    const card = car?.querySelectorAll('article')[i]
    if (!card) return
    car.scrollTo({ left: card.offsetLeft - SIDE_PAD, behavior: reduced ? 'auto' : 'smooth' })
  }, [reduced])

  // Mouse drag (touch scrolls natively). Buttons / links keep their own clicks.
  function onPointerDown(e) {
    if (e.pointerType !== 'mouse' || e.target.closest('button, a')) return
    dragRef.current = { x0: e.clientX, sl0: carRef.current.scrollLeft, moved: false }
  }
  function onPointerMove(e) {
    const d = dragRef.current
    const car = carRef.current
    if (d.x0 === null || !car) return
    const dx = e.clientX - d.x0
    if (!d.moved && Math.abs(dx) > DRAG_START_PX) {
      d.moved = true
      car.style.scrollSnapType = 'none'
      car.style.cursor = 'grabbing'
      car.setPointerCapture(e.pointerId)
    }
    if (d.moved) car.scrollLeft = d.sl0 - dx
  }
  function endDrag() {
    const d = dragRef.current
    const car = carRef.current
    if (d.x0 === null || !car) return
    dragRef.current = { x0: null, sl0: 0, moved: false }
    if (!d.moved) return
    car.style.cursor = ''
    const cards = car.querySelectorAll('article')
    const step = cards[1].offsetLeft - cards[0].offsetLeft
    const i = Math.max(0, Math.min(CARD_COUNT - 1, Math.round(car.scrollLeft / step)))
    car.style.scrollSnapType = ''
    goTo(i)
  }

  const delay = d => ({ '--d': `${d}s` })
  const cardCls = i => `${s.card} ${i === 2 ? s.cardEnd : ''} ${seen.has(i) ? s.seen : ''}`

  const tags = [
    ...(report.dominant_programs || []).map(x => [x, rp.tagP]),
    ...(report.dominant_styles || []).map(x => [x, rp.tagS]),
    ...(report.dominant_materials || []).map(x => [x, rp.tagM]),
  ]

  return (
    <>
      <div className={s.viewport}>
        <div
          ref={carRef}
          className={s.car}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          {/* 1 — persona */}
          <article className={cardCls(0)}>
            <p className={`${s.rv} ${s.eyebrow}`}><span className={s.eyebrowLine} />{t('detailB3.personaReportEyebrow')}</p>
            <h1 className={`${s.rv} ${s.name}`} style={delay(0.1)}>{report.persona_type}</h1>
            <p className={`${s.rv} ${s.oneLiner}`} style={delay(0.3)}>{report.one_liner}</p>
            {report.description && (
              <p className={`${s.rv} ${s.desc}`} style={delay(0.45)}>{report.description}</p>
            )}
            <div className={`${s.rv} ${s.mainSlot}`} style={delay(0.6)}>
              <ImageSlot
                fill
                role="owner"
                boardId={backendId}
                personaName={report.persona_type}
                imageData={imageData}
                imageMime={imageMime}
                jobStatus={imageJob.status}
                {...regen.imageProps}
                t={t}
              />
            </div>
          </article>

          {/* 2 — pattern + taste analysis */}
          <article className={cardCls(1)}>
            <p className={`${s.rv} ${s.eyebrow}`}><span className={s.eyebrowLine} />{t('persona.whyLabel')}</p>
            <h2 className={`${s.rv} ${s.h2}`} style={delay(0.1)}>{t('persona.patternTitle')}</h2>
            {report.pattern_paragraph && (
              <p className={`${s.rv} ${s.pattern}`} style={delay(0.2)}>{report.pattern_paragraph}</p>
            )}
            <div className={s.tags}>
              {tags.map(([tag, cls], i) => (
                <span
                  key={`${cls}-${tag}`}
                  className={`${s.rv} ${s.pop} ${rp.tag} ${cls}`}
                  style={delay(Math.min(0.25 + i * TAG_STAGGER_S, TAG_STAGGER_MAX_S))}
                >
                  {tag}
                </span>
              ))}
            </div>
            <h3 className={`${s.rv} ${s.h3}`} style={delay(0.3)}>{t('persona.tasteSection')}</h3>
            {legacy && <p className={`${s.rv} ${s.legacy}`}>{t('persona.legacySpectrum')}</p>}
            <div className={s.rv} style={delay(0.4)}>
              <TasteSpectrum axisScores={axisScores || {}} rowHeight={48} animate={!reduced} play={seen.has(1)} />
            </div>
          </article>

          {/* 3 — closing */}
          <article className={cardCls(2)}>
            <Thumb imageData={imageData} imageMime={imageMime} jobStatus={imageJob.status} regenerating={regen.imageProps.imageRegenerating} />
            <h2 className={`${s.rv} ${s.doneTitle}`} style={delay(0.1)}>{t('results.doneTitle')}</h2>
            <p className={`${s.rv} ${s.doneName}`} style={delay(0.2)}>{report.persona_type}</p>
            <p className={`${s.rv} ${s.doneBody}`} style={delay(0.3)}>{t('results.doneBody')}</p>
            <button type="button" className={`${s.rv} ${s.cta}`} style={delay(0.4)} onClick={onCta}>
              {ctaLabel}
            </button>
          </article>
        </div>
      </div>

      <div className={s.dots} role="group" aria-label={t('results.cardsAria')}>
        {[0, 1, 2].map(i => (
          <button
            key={i}
            type="button"
            className={`${s.dot} ${i === active ? s.dotActive : ''}`}
            aria-label={t('results.cardDotAria', { n: i + 1 })}
            aria-current={i === active ? 'true' : undefined}
            onClick={() => goTo(i)}
          />
        ))}
      </div>
      {regen.overlay}
    </>
  )
}
