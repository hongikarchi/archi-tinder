import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getArchitectProfile, followArchitect, unfollowArchitect } from '../api/architects.js'
import styles from './ArchitectProfilePage.module.css'
import r from './boardReport/boardReport.module.css'
import { useTranslation } from '../i18n/index.js'
import PageShell from '../components/PageShell.jsx'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import EmptyState from '../components/EmptyState.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { ReportScope, ReportSection, ReportHero, ReportHeading } from '../components/PersonaReportPage.jsx'

/**
 * ArchitectProfilePage — studio profile on the persona-report / board-detail
 * shell: 680 column, 28px gutter (ReportScope), left-aligned hero with a 72px
 * rounded-square logo, a board-style tools row (Follow pill + website / email /
 * share icon buttons), plain description text, and a hairline "Buildings"
 * heading with a Built / Unbuilt pill switch above a report-style card grid.
 */
const ICON_PROPS = {
  width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true,
}

export default function ArchitectProfilePage({ onLogout }) {
  const { architectId } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  // undefined = loading, null = not found, object = loaded
  const [profile, setProfile] = useState(undefined)
  const [error, setError] = useState(null)
  const [retryKey, setRetryKey] = useState(0)
  const [isFollowing, setIsFollowing] = useState(false)
  const [followerCount, setFollowerCount] = useState(0)
  const [followPending, setFollowPending] = useState(false)
  const [activeTab, setActiveTab] = useState('built')

  useEffect(() => {
    if (!architectId) {
      setProfile(null)
      return
    }
    setProfile(undefined)
    setError(null)
    getArchitectProfile(architectId)
      .then(data => {
        setProfile(data)
        setIsFollowing(data?.is_following ?? false)
        setFollowerCount(data?.follower_count ?? 0)
      })
      .catch(() => setError(true))
  }, [architectId, retryKey])

  const isLoading = profile === undefined && !error

  const handleFollow = async () => {
    if (followPending) return
    setFollowPending(true)
    const wasFollowing = isFollowing
    setIsFollowing(!wasFollowing)
    setFollowerCount(c => c + (wasFollowing ? -1 : 1))
    try {
      const fn = wasFollowing ? unfollowArchitect : followArchitect
      const res = await fn(architectId)
      if (res?.follower_count != null) setFollowerCount(res.follower_count)
    } catch {
      setIsFollowing(wasFollowing)
      setFollowerCount(c => c + (wasFollowing ? 1 : -1))
    } finally {
      setFollowPending(false)
    }
  }

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({ title: profile?.name || 'archibe', url: window.location.href }).catch(() => {})
    }
  }

  const handleWebsite = () => {
    const url = profile?.website
    if (url && /^https?:\/\//i.test(url)) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  const handleContact = () => {
    const email = profile?.email
    if (email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      window.open('mailto:' + email)
    }
  }

  const hasBuildings = !!profile && Array.isArray(profile.buildings) && profile.buildings.length > 0
  const builtBuildings = hasBuildings ? profile.buildings.filter(b => b.year_kind === 'completed') : []
  const unbuiltBuildings = hasBuildings ? profile.buildings.filter(b => b.year_kind !== 'completed') : []
  const displayedBuildings = activeTab === 'built' ? builtBuildings : unbuiltBuildings

  return (
    <PageShell
      width="medium"
      className={styles.scroll}
      // The report column owns its gutter (28px) via --rp-gutter inside ReportScope.
      contentStyle={{ padding: 0 }}
      chrome={
        <>
          <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} label={t('architect.back')} />} />
          <PageLogoHeader padding="20px 16px 0" />
        </>
      }
    >
      <ReportScope>
        {/* Loading state — mirrors the hero silhouette + grid */}
        {isLoading && (
          <div className={styles.state}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
              <Skeleton width={72} height={72} radius={20} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Skeleton width={60} height={12} />
                <Skeleton width={180} height={24} />
                <Skeleton width={100} height={14} />
              </div>
            </div>
            <Skeleton width={140} height={12} style={{ marginBottom: 18 }} />
            <Skeleton height={44} radius="var(--radius-pill)" style={{ marginBottom: 26 }} />
            <div className={styles.skelGrid}>
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} radius={14} style={{ height: 'auto', aspectRatio: '4 / 5' }} />
              ))}
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className={styles.state}>
            <EmptyState
              icon={(
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4, color: 'var(--color-text-muted)' }}>
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              )}
              title={t('architect.loadError')}
              actionLabel={t('architect.retry')}
              onAction={() => { setError(null); setProfile(undefined); setRetryKey(k => k + 1) }}
            />
          </div>
        )}

        {/* Not found state */}
        {!isLoading && !error && profile === null && (
          <div className={styles.state}>
            <EmptyState
              icon={(
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4, color: 'var(--color-text-muted)' }}>
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M9 9h6M9 12h6M9 15h6" />
                </svg>
              )}
              title={t('architect.notFound')}
            />
          </div>
        )}

        {/* Loaded state */}
        {!isLoading && !error && profile && (
          <>
            <ReportHero>
              <div className={styles.id}>
                <div className={styles.avatar}>
                  {profile.logo_url ? (
                    <img className={styles.avatarImg} src={profile.logo_url} alt={profile.name} />
                  ) : (
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <path d="M9 9h6M9 12h6M9 15h6" />
                    </svg>
                  )}
                </div>
                <div className={styles.idText}>
                  <p className={styles.eyebrow}>{t('architect.eyebrow')}</p>
                  <h1 className={styles.name}>{profile.name}</h1>
                  {profile.primary_country && <p className={styles.sub}>{profile.primary_country}</p>}
                </div>
              </div>

              <p className={styles.metaRow}>
                <span>{t('architectB3.buildings')} <b>{profile.building_count != null ? profile.building_count.toLocaleString() : '—'}</b></span>
                <span aria-hidden="true">·</span>
                <span>{t('architectB3.followers')} <b>{followerCount.toLocaleString()}</b></span>
              </p>

              <div className={r.tools}>
                <button
                  type="button"
                  className={`${r.tool} ${isFollowing ? '' : r.toolDark}`}
                  onClick={handleFollow}
                  disabled={followPending}
                  aria-label={isFollowing ? t('architect.unfollow') : t('architect.follow')}
                >
                  {isFollowing ? t('architectB3.following') : t('architectB3.follow')}
                </button>
                {profile.website && (
                  <button type="button" className={r.icon} onClick={handleWebsite} aria-label={t('architect.website')}>
                    <svg {...ICON_PROPS}>
                      <circle cx="12" cy="12" r="10" />
                      <line x1="2" y1="12" x2="22" y2="12" />
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                    </svg>
                  </button>
                )}
                {profile.email && (
                  <button type="button" className={r.icon} onClick={handleContact} aria-label={t('architect.email')}>
                    <svg {...ICON_PROPS}>
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                      <polyline points="22,6 12,13 2,6" />
                    </svg>
                  </button>
                )}
                <button type="button" className={r.icon} onClick={handleShare} aria-label={t('architect.share')}>
                  <svg {...ICON_PROPS}>
                    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
                    <polyline points="16 6 12 2 8 6" />
                    <line x1="12" y1="2" x2="12" y2="15" />
                  </svg>
                </button>
              </div>

              {profile.description && <p className={styles.desc}>{profile.description}</p>}
            </ReportHero>

            {hasBuildings ? (
              <ReportSection>
                <ReportHeading
                  count={profile.building_count != null ? profile.building_count.toLocaleString() : profile.buildings.length}
                  right={(
                    <span className={styles.vs} role="group">
                      {[
                        { id: 'built', label: t('architectB3.builtTab'), n: builtBuildings.length },
                        { id: 'unbuilt', label: t('architectB3.unbuiltTab'), n: unbuiltBuildings.length },
                      ].map(tab => (
                        <button
                          key={tab.id}
                          type="button"
                          className={`${styles.vsBtn} ${activeTab === tab.id ? styles.vsOn : ''}`}
                          aria-pressed={activeTab === tab.id}
                          onClick={() => setActiveTab(tab.id)}
                        >
                          {`${tab.label} · ${tab.n}`}
                        </button>
                      ))}
                    </span>
                  )}
                >
                  {t('architectB3.buildingsSection')}
                </ReportHeading>

                <div className={styles.wrap}>
                  {displayedBuildings.length === 0 ? (
                    <EmptyState title={t('architectB3.noProjectsYet')} />
                  ) : (
                    <div className={styles.grid}>
                      {displayedBuildings.map(building => {
                        const title = building.name_en || building.name || ''
                        const subtitle = [building.year, building.program].filter(Boolean).join(' · ')
                        return (
                          <button
                            key={building.canonical_bld_id}
                            type="button"
                            className={styles.card}
                            onClick={() => navigate('/buildings/' + building.canonical_bld_id)}
                          >
                            {building.image_url && (
                              <img className={styles.cardImg} src={building.image_url} alt="" loading="lazy" />
                            )}
                            <span className={styles.cardScrim} aria-hidden="true" />
                            <span className={styles.cardCap}>
                              <span className={styles.cardTitle} style={{ display: '-webkit-box' }}>{title}</span>
                              {subtitle && <span className={styles.cardSub} style={{ display: 'block' }}>{subtitle}</span>}
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              </ReportSection>
            ) : (
              <ReportSection>
                <EmptyState title={t('architect.noBuildings')} />
              </ReportSection>
            )}
          </>
        )}
      </ReportScope>
    </PageShell>
  )
}
