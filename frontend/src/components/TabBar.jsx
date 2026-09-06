import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from '../i18n/index.js'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'

const TAB_ICONS = {
  discovery: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </svg>
  ),
  swipe: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="6" width="16" height="13" rx="2" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    </svg>
  ),
  social: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  profile: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
}

function getActiveTab(pathname) {
  if (pathname === '/swipe' || pathname.startsWith('/search') || pathname.startsWith('/result')) return 'swipe'
  if (pathname.startsWith('/people') || pathname.startsWith('/assessment')) return 'social'
  if (pathname.startsWith('/user') || pathname.startsWith('/board') || pathname.startsWith('/settings')) return 'profile'
  return 'discovery'
}

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const activeTab = getActiveTab(location.pathname)

  const tabs = [
    { id: 'discovery', labelKey: 'tabbar.discovery', path: '/discovery' },
    { id: 'swipe',     labelKey: 'tabbar.taste',     path: '/search' },
    { id: 'social',    labelKey: 'tabbar.social',    path: '/people' },
    { id: 'profile',   labelKey: 'tabbar.profile',   path: '/user/me' },
  ]

  function handleSelect(tab) {
    // Already on this tab — tapping the active tab is a no-op; do not invoke
    // the guard or navigate (prevents false-alarm modal when the user taps the
    // active Discovery tab while a draft is in progress).
    if (tab.path === location.pathname) return

    // If the guard is active (Discovery mounted with draft likes >= 1), show the
    // leave-warning modal and defer navigation to the user's choice.
    if (discoveryNavigationGuard.check) {
      discoveryNavigationGuard.check(tab.path, () => navigate(tab.path))
    } else {
      navigate(tab.path)
    }
  }

  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      display: 'flex', zIndex: 100, height: 64,
      paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      boxSizing: 'content-box',
      background: 'var(--color-nav-bg)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid var(--color-border)',
    }}>
      {tabs.map(tab => {
        const active = activeTab === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => handleSelect(tab)}
            style={{
              flex: 1, border: 'none', background: 'none',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
              cursor: 'pointer', fontFamily: 'inherit',
              color: active ? 'var(--accent-1)' : 'var(--color-nav-inactive)',
              transition: 'color 0.18s',
              paddingBottom: 4,
            }}
          >
            <div style={{
              width: 40, height: 28, borderRadius: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: active ? 'color-mix(in srgb, var(--accent-1) 12%, transparent)' : 'transparent',
              transition: 'background 0.18s',
            }}>
              {TAB_ICONS[tab.id]}
            </div>
            <span style={{ fontSize: 10, fontWeight: active ? 600 : 400, letterSpacing: '0.02em' }}>
              {t(tab.labelKey)}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
