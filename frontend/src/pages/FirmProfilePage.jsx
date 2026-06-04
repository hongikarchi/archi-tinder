import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getOffice } from '../api/client.js'
import FirmProfileHeader from './firmProfile/FirmProfileHeader'
import FirmProfileHero from './firmProfile/FirmProfileHero'
import FirmProjectsSection from './firmProfile/FirmProjectsSection'
import FirmArticlesSection from './firmProfile/FirmArticlesSection'


export default function FirmProfilePage() {
  const rawOfficeId = useParams().officeId
  // Defense-in-depth: only allow alphanumeric office IDs (with optional `_`/`-`).
  // Backend route is the authoritative gate, but reject path-traversal-shaped values
  // early to avoid them reaching fetch().
  const officeId = /^[A-Za-z0-9_-]{1,64}$/.test(String(rawOfficeId || '')) ? rawOfficeId : null

  const [office, setOffice] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [followerCount, setFollowerCount] = useState(0)

  useEffect(() => {
    if (!officeId) {
      setLoading(false)
      setError('Invalid office ID.')
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getOffice(officeId)
      .then(data => {
        if (cancelled) return
        // articles[] absent (Phase 18 External territory) — default to []
        setOffice({ ...data, articles: data.articles || [] })
        setFollowerCount(data.follower_count ?? 0)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message || 'Failed to load office profile.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [officeId])

  function handleMessage() {
    // TODO(claude): wire DM endpoint — POST /api/v1/messages/ or similar
  }

  if (loading) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        Loading office profile...
      </div>
    )
  }

  if (error || !office) {
    return (
      <div style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        background: 'var(--color-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-text-dim)', fontSize: 14,
      }}>
        {error || 'Office not found.'}
      </div>
    )
  }

  return (
    <div
      style={{
        height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
        overflowY: 'auto',
        background: 'var(--color-bg)',
        paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
        position: 'relative',
      }}
    >
      {/* Ambient glow — single brand-pink, no purple */}
      <div
        style={{
          position: 'absolute',
          top: '-10%',
          left: '-10%',
          width: '120%',
          height: '50%',
          background: 'radial-gradient(circle at 50% 0%, rgba(236,72,153,0.10) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      <FirmProfileHeader />

      {/* Unified responsive container (max-width 1100) — mirrors UserProfile */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          maxWidth: 1100,
          margin: '0 auto',
          padding: '32px 20px 40px',
        }}
      >
        <FirmProfileHero
          office={office}
          followerCount={followerCount}
          onMessage={handleMessage}
        />

        <FirmProjectsSection projects={office.projects} />

        <FirmArticlesSection articles={office.articles} />
      </div>
    </div>
  )
}
