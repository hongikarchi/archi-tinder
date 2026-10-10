/**
 * CompetitionDetailPage.jsx — 공모전 상세
 * Route: /competitions/:competitionId
 *
 * 설계: docs/decisions/2026-10-09-contest-real-data.md §3 (D4 D5 D9 D10 D11), §4-4
 *
 * 위에서 아래: 상단바 -> D-n 배지·제목·주최처 -> 정보 카드(포스터 썸네일 + 주제·마감·
 * 요약, 포스터가 없으면 폴백 카드) -> 출처 줄 -> 관심 등록.
 *
 * 포스터는 hotlink 만 한다(D4): 내려받지도, 프록시·캐시·재호스팅하지도 않는다.
 * API 가 준 모든 href/src 는 렌더 시점에 safeHttpUrl / safeMailto 를 다시 통과한다.
 * 추천(관심 있는 사람)·모집 중인 팀 섹션은 가짜 유저 방지(D10)를 위해 이 화면에서
 * 제거됐다 — 실제 데이터와 함께 후속 PR 에서 돌아온다.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from '../i18n/index.js'
import PageShell from '../components/PageShell.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTitle from '../components/PageTitle.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Skeleton from '../components/Skeleton.jsx'
import DeadlineBadge from '../components/contests/DeadlineBadge.jsx'
import PosterLightbox from '../components/contests/PosterLightbox.jsx'
import {
  getContest,
  addContestInterest,
  removeContestInterest,
  reportContestPoster,
} from '../api/contests.js'
import { VerifyRequiredError } from '../api/projects.js'
import { useNow } from '../hooks/useNow.js'
import { formatKstDateTime, formatKstDate } from '../utils/contestDeadline.js'
import { safeHttpUrl, safeMailto } from '../utils/safeUrl.js'
import styles from './CompetitionDetailPage.module.css'

const TOAST_MS = 3000

export default function CompetitionDetailPage({ onLogout }) {
  const navigate = useNavigate()
  const { t, language } = useTranslation()
  const { competitionId } = useParams()
  const now = useNow()

  const [status, setStatus] = useState('loading')   // 'loading' | 'notfound' | 'error' | 'ready'
  const [contest, setContest] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [posterHidden, setPosterHidden] = useState(false)   // report done / image failed to load
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [pending, setPending] = useState(false)             // interest request in flight
  const [toast, setToast] = useState(null)
  const thumbRef = useRef(null)
  const toastTimer = useRef(null)

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const showToast = useCallback(msg => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), TOAST_MS)
  }, [])

  // Load on id change / retry. The route element is reused across ids, so the
  // effect resets per-contest state first; responses for a superseded id (or
  // after unmount) are dropped via the `cancelled` flag in cleanup.
  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setContest(null)
    setPosterHidden(false)
    setLightboxOpen(false)
    setPending(false)
    setToast(null)
    getContest(competitionId)
      .then(data => {
        if (cancelled) return
        setContest(data)
        setStatus('ready')
      })
      .catch(err => {
        if (cancelled) return
        setStatus(err?.status === 404 ? 'notfound' : 'error')
      })
    return () => { cancelled = true }
  }, [competitionId, reloadKey])

  function retry() {
    setStatus('loading')
    setReloadKey(k => k + 1)
  }

  const chrome = (
    <>
      <PageTopControls
        onLogout={onLogout}
        leading={(
          <PageBackButton
            inline
            label={t('contest.detail.backAria')}
            onClick={() => navigate('/competitions')}
          />
        )}
      />
      <PageLogoHeader />
    </>
  )

  if (status === 'loading') {
    return (
      <PageShell width="medium" contentStyle={{ padding: '20px 20px 0' }} chrome={chrome}>
        <div className={styles.skeletons} aria-hidden="true">
          <Skeleton width={120} height={24} radius="var(--radius-pill)" />
          <Skeleton height={32} />
          <Skeleton height={186} radius="var(--radius-lg)" />
          <Skeleton height={56} radius="var(--radius-md)" />
        </div>
      </PageShell>
    )
  }

  if (status === 'notfound') {
    return (
      <PageShell width="medium" chrome={chrome}>
        <EmptyState
          title={t('contest.detail.notFound')}
          actionLabel={t('contest.detail.backToList')}
          onAction={() => navigate('/competitions')}
        />
      </PageShell>
    )
  }

  if (status === 'error' || !contest) {
    return (
      <PageShell width="medium" chrome={chrome}>
        <div className={styles.inlineError} role="alert">
          <p>{t('contest.detail.loadError')}</p>
          <button type="button" className={styles.retryBtn} onClick={retry}>
            {t('contest.detail.retry')}
          </button>
        </div>
      </PageShell>
    )
  }

  // ── Derived, render-time-safe values ─────────────────────────────────────
  const title = contest.title
  const posterUrl = contest.poster_status === 'allowed' ? safeHttpUrl(contest.poster_url) : null
  const showPoster = Boolean(posterUrl) && !posterHidden
  const sourceUrl = safeHttpUrl(contest.source_url) || safeHttpUrl(contest.listing_url)
  const mailHref = contest.takedown_email
    ? safeMailto(
        contest.takedown_email,
        t('contest.takedown.mailSubject', { title }),
        t('contest.takedown.mailBody', { title, url: window.location.href }),
      )
    : null
  const applyAt = contest.apply_deadline ? new Date(contest.apply_deadline) : null
  const showApplyRow = Boolean(applyAt) && !Number.isNaN(applyAt.getTime()) && applyAt.getTime() > now.getTime()
  const noticeText = contest.notice_date ? formatKstDate(contest.notice_date, language) : ''
  const interestCount = Number(contest.interest_count) || 0
  const interested = Boolean(contest.interested)

  // ── Actions ──────────────────────────────────────────────────────────────
  async function handleToggleInterest() {
    if (pending) return
    const prev = contest
    const next = !prev.interested
    // Optimistic: flip now, roll back (and tell the user) if the call fails.
    setContest({
      ...prev,
      interested: next,
      interest_count: Math.max(0, (Number(prev.interest_count) || 0) + (next ? 1 : -1)),
    })
    setPending(true)
    try {
      const res = next ? await addContestInterest(prev.id) : await removeContestInterest(prev.id)
      if (res && typeof res.interest_count === 'number') {
        setContest(c => (c ? { ...c, interest_count: res.interest_count, interested: next } : c))
      }
    } catch (err) {
      setContest(c => (c ? { ...c, interested: prev.interested, interest_count: prev.interest_count } : c))
      // The global VerifyGateModal already explains a guest 403.
      if (!(err instanceof VerifyRequiredError)) showToast(t('contest.detail.interestError'))
    } finally {
      setPending(false)
    }
  }

  async function handleReport(reason) {
    try {
      await reportContestPoster(contest.id, { reason })
    } catch {
      showToast(t('contest.takedown.error'))
      return
    }
    // 201 received / 200 already_reported: the poster is hidden server-side
    // already — mirror that here immediately, then refetch in the background.
    setPosterHidden(true)
    setLightboxOpen(false)
    showToast(t('contest.takedown.done'))
    getContest(contest.id).then(setContest).catch(() => {})
  }

  function handlePosterError() {
    setLightboxOpen(false)
    setPosterHidden(true)
  }

  // ── Pieces ───────────────────────────────────────────────────────────────
  const deadlineRow = (
    <div className={styles.row}>
      <dt className={styles.label}>{t('contest.detail.submissionDeadline')}</dt>
      <dd className={`${styles.value} ${styles.deadline}`}>
        {formatKstDateTime(contest.submission_deadline, language)}
      </dd>
    </div>
  )
  const applyRow = showApplyRow && (
    <div className={styles.row}>
      <dt className={styles.label}>{t('contest.detail.applyDeadline')}</dt>
      <dd className={styles.value}>{formatKstDateTime(contest.apply_deadline, language)}</dd>
    </div>
  )
  const noticeRow = noticeText && (
    <div className={styles.row}>
      <dt className={styles.label}>{t('contest.detail.noticeDate')}</dt>
      <dd className={styles.value}>{noticeText}</dd>
    </div>
  )

  const sourceText = showPoster
    ? t('contest.detail.sourceLine', { organizer: contest.organizer })
    : t('contest.detail.noPosterSourceLine', { organizer: contest.organizer })

  return (
    <PageShell width="medium" contentStyle={{ padding: '20px 20px 0' }} chrome={chrome}>
      {/* ── 상단: D-n · 제목 · 주최처 ── */}
      <header className={styles.hero}>
        <DeadlineBadge contest={contest} now={now} />
        <PageTitle as="h2" style={{ margin: '10px 0 6px', overflowWrap: 'anywhere' }}>{title}</PageTitle>
        <p className={styles.organizer}>
          {contest.team_size
            ? t('contest.detail.organizerTeam', { organizer: contest.organizer, teamSize: contest.team_size })
            : contest.organizer}
        </p>
      </header>

      {/* ── 정보 카드: 포스터 썸네일 + 요약, 또는 폴백 ── */}
      {showPoster ? (
        <section className={styles.infoCard}>
          <div className={styles.posterCol}>
            <button
              ref={thumbRef}
              type="button"
              className={styles.thumbBtn}
              onClick={() => setLightboxOpen(true)}
              aria-label={t('contest.poster.open')}
              aria-haspopup="dialog"
            >
              <img
                className={styles.thumb}
                src={posterUrl}
                alt={t('contest.poster.alt', { title })}
                loading="lazy"
                decoding="async"
                referrerPolicy="no-referrer"
                onError={() => setPosterHidden(true)}
              />
            </button>
            {contest.poster_credit && (
              <p className={styles.posterCredit}>
                {t('contest.poster.credit', { credit: contest.poster_credit })}
              </p>
            )}
            {mailHref && (
              <a className={styles.takedownLink} href={mailHref}>
                {t('contest.takedown.mailLink')}
              </a>
            )}
          </div>

          <div className={styles.details}>
            <dl className={styles.rows}>
              {contest.theme && (
                <div className={styles.row}>
                  <dt className={styles.label}>{t('contest.detail.theme')}</dt>
                  <dd className={`${styles.value} ${styles.strong}`}>{contest.theme}</dd>
                </div>
              )}
              {deadlineRow}
              {applyRow}
              {noticeRow}
            </dl>
            {contest.summary && <p className={styles.summary}>{contest.summary}</p>}
          </div>
        </section>
      ) : (
        <section className={styles.fallbackCard}>
          <span className={styles.chip}>
            {t('contest.detail.submissionDeadline')} {formatKstDateTime(contest.submission_deadline, language)}
          </span>
          {contest.theme && <p className={styles.fallbackTheme}>{contest.theme}</p>}
          {contest.summary && <p className={styles.fallbackSummary}>{contest.summary}</p>}
          {(applyRow || noticeRow) && (
            <dl className={`${styles.rows} ${styles.fallbackRows}`}>
              {applyRow}
              {noticeRow}
            </dl>
          )}
        </section>
      )}

      {/* ── 출처 줄 ── */}
      <p className={styles.sourceLine}>
        <span>{sourceText}</span>
        {sourceUrl && (
          <a className={styles.sourceLink} href={sourceUrl} target="_blank" rel="noopener noreferrer">
            {t('contest.detail.viewSource')}
          </a>
        )}
      </p>

      {/* ── 관심 등록 ── */}
      <button
        type="button"
        className={`${styles.interestBtn} ${interested ? styles.interestBtnOn : ''}`}
        onClick={handleToggleInterest}
        aria-pressed={interested}
        disabled={pending}
      >
        {t(interested ? 'contest.detail.interestOn' : 'contest.detail.interestOff')}
      </button>
      {interestCount > 0 && (
        <p className={styles.interestCount}>
          {t('contest.detail.interestCount', { count: interestCount })}
        </p>
      )}

      {lightboxOpen && showPoster && (
        <PosterLightbox
          posterUrl={posterUrl}
          title={title}
          credit={contest.poster_credit}
          sourceUrl={sourceUrl}
          mailHref={mailHref}
          returnFocusRef={thumbRef}
          onClose={() => setLightboxOpen(false)}
          onImageError={handlePosterError}
          onReport={handleReport}
        />
      )}

      {toast && <div className={styles.toast} role="status" aria-live="polite">{toast}</div>}
    </PageShell>
  )
}
