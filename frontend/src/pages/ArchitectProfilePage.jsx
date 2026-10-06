import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getArchitectProfile, followArchitect, unfollowArchitect } from '../api/architects.js'
import { listProjects } from '../api/client.js'
import SaveToBoardModal from '../components/SaveToBoardModal.jsx'
import styles from './ArchitectProfilePage.module.css'
import { useTranslation } from '../i18n/index.js'
import PageLogoHeader from '../components/PageLogoHeader.jsx'
import PageTopControls from '../components/PageTopControls.jsx'
import PageBackButton from '../components/PageBackButton.jsx'
import FloatingIconButton from '../components/FloatingIconButton.jsx'
import Tabs from '../components/Tabs.jsx'
import EmptyState from '../components/EmptyState.jsx'
import PhotoTile from '../components/PhotoTile.jsx'
import SectionTitle from '../components/SectionTitle.jsx'
import Skeleton from '../components/Skeleton.jsx'

/**
 * ArchitectProfilePage — UI-CONSISTENCY-B3b-2.
 *
 * Rebuilt onto the same shared-component system as UserProfilePage /
 * ProfileHero (DESIGN.md §2.2/§3.1/§3.3a, .claude/plans/archive/ui-consistency-b.md
 * phase 3 item 3): the full-bleed accent-gradient hero band is retired for a
 * centered 1100-wide column with a 480-wide hero (avatar halo, title, meta,
 * stats) that mirrors ProfileHero's structure and sizes; Built/Unbuilt dark
 * pills are replaced with the shared underline `Tabs`; the building grid
 * moves onto `PhotoTile` (same 4:5 / radius-lg / auto-fill(260px) grid as the
 * profile Liked tab); loading/empty/error states move onto `Skeleton` /
 * `EmptyState`. The local `BuildingCard` + bespoke skeleton helpers are
 * deleted — no other page imported them (grep-verified, 2b build-only note
 * did not include this page).
 */
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
  const [saveCard, setSaveCard] = useState(null)
  const [savedIds, setSavedIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('built')

  useEffect(() => {
    listProjects().then(resp => {
      const ids = new Set()
      for (const p of (resp?.results || [])) {
        for (const id of (p.liked_ids || [])) ids.add(id)
        for (const id of (p.saved_ids || [])) ids.add(id)
      }
      setSavedIds(ids)
    }).catch(() => {})
  }, [])

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

  return (
    <div style={{
      height: 'var(--page-height)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      paddingBottom: 'var(--tabbar-clearance)',
    }}>
      <PageTopControls onLogout={onLogout} leading={<PageBackButton inline onClick={() => navigate(-1)} label={t('architect.back')} />} />

      {/* Share — stacked under the back button (kept per existing working
       * control; the mock drops the sticky header with no relocation shown).
       * zIndex 299 (one below PageBackButton's 300) so the two 44px hit
       * areas' overlap sliver resolves toward "back". */}
      <FloatingIconButton
        onClick={handleShare}
        ariaLabel={t('architect.share')}
        style={{ position: 'fixed', top: 50, left: 12, zIndex: 299 }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
          <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
        </svg>
      </FloatingIconButton>

      <PageLogoHeader padding="20px 16px 0" />

      {/* Unified responsive container (max-width 1100) — same shell as UserProfilePage */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: '32px 20px 40px' }}>

        {/* Loading state */}
        {isLoading && (
          <>
            <div style={{ maxWidth: 480, margin: '0 auto 36px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
              <Skeleton circle height={108} />
              <Skeleton width={180} height={24} style={{ marginTop: 10 }} />
              <Skeleton width={100} height={14} />
              <div style={{ display: 'flex', gap: 24, marginTop: 14 }}>
                <Skeleton width={56} height={36} />
                <Skeleton width={56} height={36} />
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 14, width: '100%' }}>
                {[1, 2, 3].map(i => (
                  <Skeleton key={i} height={44} radius="var(--radius-md)" style={{ flex: 1 }} />
                ))}
              </div>
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 20,
            }}>
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} radius="var(--radius-lg)" style={{ height: 'auto', aspectRatio: '4 / 5' }} />
              ))}
            </div>
          </>
        )}

        {/* Error state */}
        {error && (
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
        )}

        {/* Not found state */}
        {!isLoading && !error && profile === null && (
          <EmptyState
            icon={(
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4, color: 'var(--color-text-muted)' }}>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M9 9h6M9 12h6M9 15h6" />
              </svg>
            )}
            title={t('architect.notFound')}
          />
        )}

        {/* Loaded state */}
        {!isLoading && !error && profile && (
          <>
            {/* Hero — same structure/sizes as ProfileHero (narrower nested column, max-width 480) */}
            <div style={{ maxWidth: 480, margin: '0 auto 36px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>

                {/* Avatar / logo — halo treatment matches ProfileHero.AvatarCircle */}
                <div style={{ marginBottom: 18 }}>
                  {profile.logo_url ? (
                    <div style={{ position: 'relative' }}>
                      <div
                        style={{
                          position: 'absolute', inset: -6, borderRadius: '50%',
                          background: 'linear-gradient(135deg, var(--accent-1), var(--accent-2))',
                          opacity: 0.55, filter: 'blur(12px)',
                        }}
                        aria-hidden="true"
                      />
                      <img
                        src={profile.logo_url}
                        alt={profile.name}
                        style={{
                          position: 'relative', zIndex: 2,
                          width: 108, height: 108, borderRadius: '50%',
                          border: '2px solid var(--color-border-soft)',
                          objectFit: 'cover',
                          background: 'var(--color-surface)',
                          display: 'block',
                        }}
                      />
                    </div>
                  ) : (
                    <div style={{
                      width: 108, height: 108, borderRadius: '50%',
                      background: 'var(--color-surface)',
                      border: '2px solid var(--color-border-soft)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-dim)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M9 9h6M9 12h6M9 15h6" />
                      </svg>
                    </div>
                  )}
                </div>

                {/* Name — same title style as ProfileHero */}
                <h1 style={{
                  color: 'var(--color-text)', fontSize: 'var(--fs-title)', fontWeight: 'var(--fw-bold)',
                  margin: '0 0 4px', lineHeight: 1.2, letterSpacing: '-0.01em',
                }}>
                  {profile.name}
                </h1>

                {/* Country / meta line */}
                {profile.primary_country && (
                  <p style={{
                    margin: '0 0 4px',
                    color: 'var(--color-text-muted)',
                    fontSize: 'var(--fs-body)',
                    fontWeight: 400,
                    lineHeight: 1.3,
                  }}>
                    {profile.primary_country}
                  </p>
                )}

                {/* Stats row — same number/divider style as ProfileHero */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  gap: 0, marginTop: 14, marginBottom: 4,
                }}>
                  <div className={styles.statBtn}>
                    <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 'var(--fw-bold)', lineHeight: 1 }}>
                      {profile.building_count != null ? profile.building_count.toLocaleString() : '—'}
                    </span>
                    <span className={styles.statLabel}>{t('architectB3.buildings')}</span>
                  </div>
                  <div style={{ width: 1, height: 28, background: 'var(--color-border)' }} />
                  <div className={styles.statBtn}>
                    <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 'var(--fw-bold)', lineHeight: 1 }}>
                      {followerCount.toLocaleString()}
                    </span>
                    <span className={styles.statLabel}>{t('architectB3.followers')}</span>
                  </div>
                </div>

                {/* Actions — Follow (primary/secondary toggle) · Website · Contact, one row, max-width 480 */}
                <div style={{ display: 'flex', gap: 8, marginTop: 14, width: '100%' }}>
                  <button
                    type="button"
                    className={`${styles.actionBtn} ${isFollowing ? styles.secondaryBtn : styles.primaryBtn}`}
                    onClick={handleFollow}
                    disabled={followPending}
                    aria-label={isFollowing ? t('architect.unfollow') : t('architect.follow')}
                    style={{ opacity: followPending ? 0.7 : 1, cursor: followPending ? 'default' : 'pointer' }}
                  >
                    {isFollowing ? t('architectB3.following') : t('architectB3.follow')}
                  </button>

                  {profile.website && (
                    <button
                      type="button"
                      className={`${styles.actionBtn} ${styles.secondaryBtn}`}
                      onClick={handleWebsite}
                      aria-label={t('architect.website')}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="2" y1="12" x2="22" y2="12" />
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                      </svg>
                      {t('architectB3.website')}
                    </button>
                  )}

                  {profile.email && (
                    <button
                      type="button"
                      className={`${styles.actionBtn} ${styles.secondaryBtn}`}
                      onClick={handleContact}
                      aria-label={t('architect.email')}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                        <polyline points="22,6 12,13 2,6" />
                      </svg>
                      {t('architectB3.contact')}
                    </button>
                  )}
                </div>

                {/* Description card — surface panel radius md */}
                {profile.description && (
                  <div style={{
                    marginTop: 20,
                    width: '100%',
                    padding: 16,
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border-soft)',
                    textAlign: 'left',
                  }}>
                    <p style={{
                      margin: 0,
                      fontSize: 'var(--fs-body)',
                      color: 'var(--color-text)',
                      lineHeight: 1.6,
                    }}>
                      {profile.description}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Buildings section */}
            {Array.isArray(profile.buildings) && profile.buildings.length > 0 && (() => {
              const builtBuildings = profile.buildings.filter(b => b.year_kind === 'completed')
              const unbuiltBuildings = profile.buildings.filter(b => b.year_kind !== 'completed')
              const displayedBuildings = activeTab === 'built' ? builtBuildings : unbuiltBuildings
              return (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <SectionTitle as="h2" count={profile.building_count != null ? profile.building_count.toLocaleString() : profile.buildings.length}>
                      {t('architectB3.buildingsSection')}
                    </SectionTitle>
                  </div>

                  {/* Built / Unbuilt — shared underline Tabs, counts in labels */}
                  <Tabs
                    style={{ marginBottom: 20 }}
                    tabs={[
                      { id: 'built', label: `${t('architectB3.builtTab')} · ${builtBuildings.length}` },
                      { id: 'unbuilt', label: `${t('architectB3.unbuiltTab')} · ${unbuiltBuildings.length}` },
                    ]}
                    value={activeTab}
                    onChange={setActiveTab}
                  />

                  {/* Grid or per-tab empty state */}
                  {displayedBuildings.length === 0 ? (
                    <EmptyState title={t('architectB3.noProjectsYet')} />
                  ) : (
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                      gap: 20,
                    }}>
                      {displayedBuildings.map(building => {
                        const title = building.name_en || building.name || ''
                        const subtitle = [building.year, building.program].filter(Boolean).join(' · ')
                        const isSaved = savedIds.has(building.canonical_bld_id)
                        return (
                          <PhotoTile
                            key={building.canonical_bld_id}
                            imageUrl={building.image_url}
                            title={title}
                            subtitle={subtitle}
                            onClick={() => navigate('/buildings/' + building.canonical_bld_id, { state: { fromRecommended: true } })}
                            topRight={(
                              <FloatingIconButton
                                onClick={(e) => { e.stopPropagation(); setSaveCard(building) }}
                                ariaLabel="Save to board"
                                variant="onPhoto"
                                className={isSaved ? styles.saveBtnActive : ''}
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill={isSaved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                                </svg>
                              </FloatingIconButton>
                            )}
                          />
                        )
                      })}
                    </div>
                  )}
                </>
              )
            })()}

            {(!Array.isArray(profile.buildings) || profile.buildings.length === 0) && (
              <EmptyState title={t('architect.noBuildings')} />
            )}
          </>
        )}

      </div>

      {saveCard && (
        <SaveToBoardModal
          card={saveCard}
          onClose={() => setSaveCard(null)}
          onSaved={() => {
            if (saveCard?.canonical_bld_id) {
              setSavedIds(prev => { const s = new Set(prev); s.add(saveCard.canonical_bld_id); return s })
            }
            setSaveCard(null)
          }}
        />
      )}
    </div>
  )
}
