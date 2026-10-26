import { useCallback, useEffect, useRef, useState } from 'react'
import { useReportImageJob, reportImageJobs } from '../hooks/useReportImageJob.js'
import { useTranslation } from '../i18n/index.js'
import { localizeReport } from '../utils/reportText.js'
import { isLegacyAxisScores } from '../utils/axisScores.js'
import { safeImageMime, imageExtension } from '../utils/imageMime.js'
import TasteSpectrum from './TasteSpectrum.jsx'
import EmptyState from './EmptyState.jsx'
import PageLogoHeader from './PageLogoHeader.jsx'
import PageTopControls from './PageTopControls.jsx'
import PageBackButton from './PageBackButton.jsx'
import { atHandle } from '../utils/userIdentity.js'
import s from './PersonaReportPage.module.css'

/**
 * PersonaReportPage — the ONE shared persona report page (FULL-REPORT-UI-1, #445).
 *
 * Used by /board/:boardId/report (BoardReportPage), which is also the post-save
 * landing (ResultCards hands off to it). Look, copy and behaviour follow the approved mock
 * (archi-tinder-mock/persona-report-all.html); off-scale values are DESIGN.md
 * §11 E1-E10 and live in PersonaReportPage.module.css.
 *
 * Exports
 *   default  PersonaReportPage  — page shell (logo header, top controls, scroll
 *            column) + the state screens (loading skeleton, generation failure,
 *            no report, board unavailable) + the report body when state='ready'.
 *   named    PersonaReportBody  — the report sections only (no page chrome).
 */

/* ── Constants ──────────────────────────────────────────────────────────── */
const REVEAL_THRESHOLD = 0.15          // DESIGN.md §3.5a rule 1
const TAG_STAGGER_S = 0.06             // E8
const TAG_STAGGER_MAX_S = 0.66         // §3.5a rule 3: total stagger ≤ 700 ms
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)'

function prefersReducedMotion() {
  return typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(REDUCED_MOTION_QUERY).matches
}

function cardId(card) {
  return card?.image_id || card?.canonical_bld_id || card?.building_id || ''
}

/* ── Reveal on scroll (DESIGN.md §3.5a) ─────────────────────────────────── */
/**
 * One IntersectionObserver per page. Every `[data-rv]` element inside the
 * container is revealed once (class `in`) when ≥15 % of it is visible, then
 * unobserved. Reduced motion / no IntersectionObserver → revealed immediately.
 * `onReveal(node)` fires for each revealed node (used to start the spectrum).
 * Re-scans after every render so late-mounting blocks (recommendations that
 * arrive after the fetch) are picked up.
 */
function useReveal(containerRef, onReveal) {
  const ioRef = useRef(null)
  const onRevealRef = useRef(onReveal)
  useEffect(() => { onRevealRef.current = onReveal })

  // Tear the observer down on unmount (and for StrictMode's mount→cleanup→mount).
  useEffect(() => () => {
    ioRef.current?.disconnect()
    ioRef.current = null
  }, [])

  useEffect(() => {
    const root = containerRef.current
    if (!root) return
    const nodes = [...root.querySelectorAll('[data-rv]')].filter(n => !n.classList.contains(s.in))
    if (nodes.length === 0) return
    const reveal = node => {
      node.classList.add(s.in)
      onRevealRef.current?.(node)
    }
    if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
      nodes.forEach(reveal)
      return
    }
    if (!ioRef.current) {
      ioRef.current = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return
          reveal(entry.target)
          ioRef.current?.unobserve(entry.target)
        })
      }, { threshold: REVEAL_THRESHOLD })
    }
    nodes.forEach(n => ioRef.current.observe(n))   // observing twice is a no-op
  })
}

/* ── Small pieces ───────────────────────────────────────────────────────── */
const ICON_PROPS = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }

function IconRefresh({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...ICON_PROPS} aria-hidden="true">
      <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  )
}
function IconDoc() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...ICON_PROPS} aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
    </svg>
  )
}
function IconLock() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" {...ICON_PROPS} aria-hidden="true">
      <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}
function IconDownload() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" {...ICON_PROPS} strokeWidth="2.5" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function MetaRow({ role, meta, t }) {
  const count = meta?.buildingCount ?? 0
  const parts = []
  if (meta?.visibility) parts.push(meta.visibility === 'public' ? t('board.public') : t('board.private'))
  parts.push(t(count === 1 ? 'board.buildingCountOne' : 'board.buildingCountMany', { n: count }))
  if (typeof meta?.reactionCount === 'number') parts.push(`♥ ${meta.reactionCount}`)
  const user = meta?.user
  return (
    <p className={s.meta}>
      {role === 'viewer' && user && (
        <>
          <img className={s.metaAvatar} src={user.avatar_url || ''} alt="" />
          <span>{atHandle(user)}</span>
          <span aria-hidden="true">·</span>
        </>
      )}
      <span>{parts.join(' · ')}</span>
    </p>
  )
}

function RefreshButton({ busy, failed, onClick, t }) {
  return (
    <div className={s.refreshWrap}>
      {failed && <span className={s.refreshFail} role="status">{t('persona.regenFail')}</span>}
      <button
        type="button"
        className={`${s.refreshBtn} ${busy ? s.refreshBtnBusy : ''}`}
        aria-label={t('persona.imgRefreshAria')}
        onClick={onClick}
      >
        <IconRefresh />
      </button>
    </div>
  )
}

/** Image slot: generating / failed / none / loaded (DESIGN.md §8.8 skeleton, no shimmer). */
export function ImageSlot({ role, boardId, personaName, imageData, imageMime, jobStatus, onRegenerateImage, imageRegenerating, imageRegenFailed, fill = false, t }) {
  const box = fill ? `${s.imgBox} ${s.imgBoxFill}` : s.imgBox   // fill: flex-grow slot inside a result card
  const owner = role === 'owner'
  const showRefresh = owner && !!onRegenerateImage
  const mime = safeImageMime(imageMime)
  const src = imageData ? `data:${mime};base64,${imageData}` : null

  if (src && !imageRegenerating) {
    return (
      <div className={box}>
        <img className={s.img} src={src} alt={t('persona.imageSection')} />
        {showRefresh && <RefreshButton busy={imageRegenerating} failed={imageRegenFailed} onClick={onRegenerateImage} t={t} />}
        <a className={s.imgSave} href={src} download={`persona-${boardId || 'report'}.${imageExtension(mime)}`}>
          <IconDownload />
          {t('persona.imageSave')}
        </a>
      </div>
    )
  }
  if (jobStatus === 'generating' || imageRegenerating) {
    return (
      <div className={box}>
        <div className={s.imgState} role="status" aria-live="polite">
          <div className={s.skeletonPulse} aria-hidden="true" />
          <span className={s.imgStateLabel}>{t('persona.imgGenerating')}</span>
        </div>
        {showRefresh && <RefreshButton busy failed={imageRegenFailed} onClick={onRegenerateImage} t={t} />}
      </div>
    )
  }
  if (jobStatus === 'error') {
    return (
      <div className={box}>
        <div className={`${s.imgState} ${s.imgFail}`} role="alert">
          <span className={s.imgFailText}>{t('persona.imgError')}</span>
          {owner && boardId && (
            <button type="button" className={s.imgRetry} onClick={() => reportImageJobs.start(boardId)}>
              {t('persona.imgRetry')}
            </button>
          )}
        </div>
      </div>
    )
  }
  return (
    <div className={box}>
      <div className={`${s.imgState} ${s.imgNone}`}>
        <span className={s.imgNoneName}>{personaName}</span>
        <span className={s.imgNoneCap}>{t('persona.imgNone')}</span>
      </div>
    </div>
  )
}

function BuildingCard({ card, rank, big, onOpen }) {
  const title = card.image_title || card.name_en || ''
  const architects = card.metadata?.axis_architects || card.architect
  const year = card.metadata?.axis_year || card.year
  const sub = [architects, year].filter(Boolean).join(' · ')
  const rec = typeof rank === 'number'
  const open = () => onOpen?.(card, rank)
  return (
    <article
      className={`${s.card} ${rec ? (big ? s.recBig : s.recSmall) : ''}`}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open() } }}
    >
      {card.image_url && <img className={s.cardImg} src={card.image_url} alt={title} loading={big ? 'eager' : 'lazy'} />}
      <div className={s.cardScrim} />
      {rec && <span className={s.pill}>#{rank}</span>}
      <div className={s.cardCap}>
        <h3 className={s.cardTitle}>{title}</h3>
        {big && sub && <p className={s.recSub}>{sub}</p>}
      </div>
    </article>
  )
}

/* ── Body ───────────────────────────────────────────────────────────────── */
/**
 * Props:
 *   role              'owner' | 'viewer'
 *   boardId           string|null  - project UUID (image job + download name)
 *   finalReport       object       - { persona_type, one_liner, description, pattern_paragraph, dominant_* }
 *   axisScores        object|null  - see TasteSpectrum
 *   reportImage / reportImageMime  - stored base64 image (or null)
 *   meta              { visibility, buildingCount, reactionCount, user }
 *   likedBuildings    ImageCard[]  - liked-buildings row (hidden when empty)
 *   recommendations   ImageCard[]  - recommendation rows (hidden when empty)
 *   onOpenBuilding    (card, rank?) => void
 *   onRegenerateReport  () => void - owner footer link (WP2); link hidden when absent
 *   regenerating      bool         - footer link busy state
 *   regenMessage      string       - small text under the footer link (failure)
 *   onRegenerateImage () => void   - owner image refresh button (WP2); hidden when absent
 *   imageRegenerating / imageRegenFailed  bool
 */
export function PersonaReportBody({
  role = 'viewer', boardId = null, finalReport, axisScores, reportImage, reportImageMime,
  meta, likedBuildings = [], recommendations = [], onOpenBuilding,
  onRegenerateReport, regenerating = false, regenMessage = '',
  onRegenerateImage, imageRegenerating = false, imageRegenFailed = false,
}) {
  const { t, language } = useTranslation()
  const owner = role === 'owner'
  const rootRef = useRef(null)
  const footerRef = useRef(null)
  const linkRef = useRef(null)
  const [specPlay, setSpecPlay] = useState(false)
  const [reduced] = useState(prefersReducedMotion)

  const imageJob = useReportImageJob(boardId)
  const imageData = imageJob.image || reportImage || null
  const imageMime = imageJob.image ? imageJob.mime : reportImageMime

  // Owner-only auto-start for legacy / previously failed boards. Fires only
  // while the job is 'idle' (never after 'error'/'done'); viewers never write.
  useEffect(() => {
    if (owner && boardId && !imageData && imageJob.status === 'idle') {
      reportImageJobs.start(boardId)
    }
  }, [owner, boardId, imageData, imageJob.status])

  const onReveal = useCallback(node => {
    if (node.dataset.spec) setSpecPlay(true)
  }, [])
  useReveal(rootRef, onReveal)

  const report = localizeReport(finalReport || {}, language)
  const scores = axisScores || {}
  const legacy = owner && isLegacyAxisScores(axisScores)
  const canRegenerate = owner && !!onRegenerateReport

  const tags = [
    ...(report.dominant_programs || []).map(x => [x, s.tagP]),
    ...(report.dominant_styles || []).map(x => [x, s.tagS]),
    ...(report.dominant_materials || []).map(x => [x, s.tagM]),
  ]

  function scrollToRegenerate() {
    footerRef.current?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' })
    const btn = linkRef.current
    if (!btn) return
    btn.classList.remove(s.pulse)
    void btn.offsetWidth   // restart the CSS animation
    btn.classList.add(s.pulse)
  }

  const [bigRec, ...restRecs] = recommendations
  const delay = d => ({ '--d': `${d}s` })

  return (
    <div ref={rootRef} className={s.body}>
      {/* Persona */}
      <section className={s.hero}>
        <MetaRow role={role} meta={meta} t={t} />
        <p data-rv className={`${s.rv} ${s.eyebrow} ${s.eyebrowLead}`}>
          <span className={s.eyebrowLine} />{t('detailB3.personaReportEyebrow')}
        </p>
        <h1 data-rv className={`${s.rv} ${s.name} ${s.personaName}`} style={delay(0.1)}>{report.persona_type}</h1>
        <p data-rv className={`${s.rv} ${s.oneLiner}`} style={delay(0.3)}>{report.one_liner}</p>
        <div data-rv className={s.rv} style={delay(0.5)}>
          <ImageSlot
            role={role}
            boardId={boardId}
            personaName={report.persona_type}
            imageData={imageData}
            imageMime={imageMime}
            jobStatus={imageJob.status}
            onRegenerateImage={onRegenerateImage}
            imageRegenerating={imageRegenerating}
            imageRegenFailed={imageRegenFailed}
            t={t}
          />
        </div>
        {report.description && (
          <p data-rv className={`${s.rv} ${s.description}`} style={delay(0.65)}>{report.description}</p>
        )}
      </section>

      {/* Pattern analysis */}
      {(owner || report.pattern_paragraph || tags.length > 0) && (
      <section className={s.section}>
        <p data-rv className={`${s.rv} ${s.eyebrow}`}>{t('persona.whyLabel')}</p>
        <h2 data-rv className={`${s.rv} ${s.h2}`} style={delay(0.05)}>{t('persona.patternTitle')}</h2>
        {(report.pattern_paragraph || owner) && (
          <p data-rv className={`${s.rv} ${s.pattern}`} style={delay(0.1)}>
            {report.pattern_paragraph || t('persona.patternEmpty')}
          </p>
        )}
        <div className={s.tags}>
          {tags.map(([tag, cls], i) => (
            <span
              key={`${cls}-${tag}`}
              data-rv
              className={`${s.rv} ${s.pop} ${s.tag} ${cls}`}
              style={delay(Math.min(i * TAG_STAGGER_S, TAG_STAGGER_MAX_S))}
            >
              {tag}
            </span>
          ))}
        </div>
      </section>
      )}

      {/* Taste analysis */}
      <section className={s.section}>
        <h2 data-rv className={`${s.rv} ${s.h2} ${s.h2Taste}`}>{t('persona.tasteSection')}</h2>
        {legacy && (
          <p data-rv className={`${s.rv} ${s.legacy}`}>
            {t('persona.legacySpectrum')}
            {canRegenerate && (
              <>
                {' '}
                <button type="button" className={s.legacyLink} onClick={scrollToRegenerate}>{t('persona.legacyGo')}</button>
              </>
            )}
          </p>
        )}
        <div data-rv data-spec="1" className={s.rv} style={delay(0.1)}>
          <TasteSpectrum axisScores={scores} animate={!reduced} play={specPlay} />
        </div>
      </section>

      {/* Liked buildings */}
      {likedBuildings.length > 0 && (
        <section className={s.rowSection}>
          <div data-rv className={`${s.rv} ${s.rowHead}`}>
            <p className={s.eyebrow}>{t('detailB3.myLikesEyebrow')}</p>
            <p className={s.rowTitle}>{t('detailB3.buildingsYouLiked', { n: likedBuildings.length })}</p>
          </div>
          <div data-rv className={`${s.rv} ${s.row}`} style={delay(0.1)}>
            {likedBuildings.map((card, i) => (
              <BuildingCard key={cardId(card) || i} card={card} onOpen={onOpenBuilding} />
            ))}
          </div>
        </section>
      )}

      {/* Recommendations */}
      {bigRec && (
        <section className={s.rowSection} style={{ paddingBottom: 8 }}>
          <div data-rv className={`${s.rv} ${s.rowHead}`}>
            <p className={s.eyebrow}>{t('detailB3.topKEyebrow')}</p>
            <p className={s.rowTitle}>{t('results.rankRange', { n: recommendations.length })}</p>
          </div>
          <div data-rv className={`${s.rv} ${s.recBigWrap}`}>
            <BuildingCard card={bigRec} rank={1} big onOpen={onOpenBuilding} />
          </div>
          {restRecs.length > 0 && (
            <div data-rv className={`${s.rv} ${s.row}`} style={delay(0.1)}>
              {restRecs.map((card, i) => (
                <BuildingCard
                  key={cardId(card) || i}
                  card={card}
                  rank={i + 2}
                  onOpen={onOpenBuilding}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Footer — owner: "리포트 재생성" text link (WP2 wires it); viewer: end marker */}
      {owner ? (
        canRegenerate && (
          <div ref={footerRef} className={s.footerOwner}>
            {legacy && <p className={s.footerLegacy}>{t('persona.legacySpectrum')}</p>}
            <button
              ref={linkRef}
              type="button"
              className={`${s.regenLink} ${legacy ? s.regenLinkAccent : ''}`}
              onClick={onRegenerateReport}
              disabled={regenerating}
            >
              {regenerating ? t('persona.reportRegenerating') : t('persona.reportRegenerate')}
            </button>
            <p className={s.regenMsg} role="status">{regenMessage}</p>
          </div>
        )
      ) : (
        <div className={s.footerViewer}>{t('results.allLoaded')}</div>
      )}
    </div>
  )
}

/* ── Loading skeleton ───────────────────────────────────────────────────── */
function Bar({ w, h, mb }) {
  return <div className={s.bar} style={{ width: w, height: h, marginBottom: mb }} />
}

function ReportSkeleton({ label }) {
  return (
    <div className={s.skel} role="status" aria-live="polite">
      <p className={s.skelLabel}>{label}</p>
      <Bar w="30%" h={10} mb={14} /><Bar w="58%" h={28} mb={14} /><Bar w="92%" h={14} mb={8} /><Bar w="70%" h={14} mb={22} />
      <div className={s.skelImg} />
      <Bar w="100%" h={12} mb={8} /><Bar w="96%" h={12} mb={8} /><Bar w="64%" h={12} mb={32} />
      <Bar w="40%" h={16} mb={16} /><Bar w="100%" h={12} mb={8} /><Bar w="88%" h={12} mb={0} />
    </div>
  )
}

/* ── Page ───────────────────────────────────────────────────────────────── */
/**
 * Props (plus every PersonaReportBody prop, used when state === 'ready'):
 *   state     'fetching' | 'making' | 'genFail' | 'loadFail' | 'noReport' | 'unavailable' | 'ready'
 *             (loadFail = board fetch failed for a non-403/404 reason; onRetry re-fetches)
 *   onLogout  () => void
 *   onBack    () => void   - top-left back button + "뒤로가기" in the state screens
 *   backLabel string|undefined - label for the back button on the ready page
 *   onRetry   () => void   - generation-failure "다시 시도"
 *   onProfile () => void   - unavailable-board "프로필로 가기"
 *   makingLabelKey string  - i18n key for the 'making' status line (default persona.loadingMake)
 */
export default function PersonaReportPage({ state = 'ready', onLogout, onBack, backLabel, onRetry, onProfile, makingLabelKey, ...bodyProps }) {
  const { t } = useTranslation()

  let content
  if (state === 'fetching' || state === 'making') {
    content = <ReportSkeleton label={t(state === 'making' ? (makingLabelKey || 'persona.loadingMake') : 'persona.loadingFetch')} />
  } else if (state === 'genFail' || state === 'loadFail') {
    content = (
      <div className={s.stateSlot}>
        <EmptyState
          neutral
          icon={<IconRefresh size={22} />}
          title={t(state === 'loadFail' ? 'persona.loadFailTitle' : 'persona.genFailTitle')}
          body={t('persona.genFailBody')}
          actionLabel={t('board.retry')}
          onAction={onRetry}
          secondaryLabel={t('board.back')}
          onSecondary={onBack}
        />
      </div>
    )
  } else if (state === 'noReport') {
    content = (
      <div className={s.stateSlot}>
        <EmptyState
          neutral
          icon={<IconDoc />}
          title={t('persona.noReportTitle')}
          body={t(bodyProps.role === 'owner' ? 'persona.noReportOwner' : 'persona.noReportViewer')}
          actionLabel={t('board.back')}
          onAction={onBack}
        />
      </div>
    )
  } else if (state === 'unavailable') {
    content = (
      <div className={s.stateSlot}>
        <EmptyState
          neutral
          icon={<IconLock />}
          title={t('persona.unavailableTitle')}
          body={t('persona.unavailableBody')}
          actionLabel={t('persona.toProfile')}
          onAction={onProfile}
          secondaryLabel={t('board.back')}
          onSecondary={onBack}
        />
      </div>
    )
  } else {
    content = <PersonaReportBody {...bodyProps} />
  }

  return (
    <div className={s.page}>
      <PageLogoHeader />
      <PageTopControls
        onLogout={onLogout}
        leading={<PageBackButton inline onClick={onBack} label={state === 'ready' ? backLabel : undefined} />}
      />
      <div className={s.column}>{content}</div>
    </div>
  )
}
