import { useLocation, useNavigate } from 'react-router-dom'

const TAB_ICONS = {
  home: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="8" x2="12" y2="16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  ),
  swipe: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="6" width="16" height="13" rx="2" />
      <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    </svg>
  ),
  folders: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    </svg>
  ),
}

function getActiveTab(pathname) {
  if (pathname === '/swipe') return 'swipe'
  if (pathname.startsWith('/library')) return 'folders'
  return 'home'
}

export default function TabBar({ swipeEnabled }) {
  const location = useLocation()
  const navigate = useNavigate()
  const activeTab = getActiveTab(location.pathname)

  const tabs = [
    { id: 'home',    label: 'New',     path: '/' },
    { id: 'swipe',   label: 'Swipe',   path: '/swipe' },
    { id: 'folders', label: 'Library', path: '/library' },
  ]

  function handleSelect(tab) {
    navigate(tab.path)
  }

  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      display: 'flex', zIndex: 100, height: 64,
      background: 'var(--color-nav-bg)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid var(--color-border)',
    }}>
      {tabs.map(t => {
        const active   = activeTab === t.id
        const disabled = t.id === 'swipe' && !swipeEnabled
        return (
          <button
            key={t.id}
            onClick={() => !disabled && handleSelect(t)}
            style={{
              flex: 1, border: 'none', background: 'none',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
              cursor: disabled ? 'default' : 'pointer', fontFamily: 'inherit',
              color: disabled ? 'var(--color-nav-disabled)' : active ? '#ec4899' : 'var(--color-nav-inactive)',
              transition: 'color 0.18s',
              paddingBottom: 4,
            }}
          >
            <div style={{
              width: 40, height: 28, borderRadius: 14,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: active ? 'rgba(236,72,153,0.12)' : 'transparent',
              transition: 'background 0.18s',
            }}>
              {TAB_ICONS[t.id]}
            </div>
            <span style={{ fontSize: 10, fontWeight: active ? 600 : 400, letterSpacing: '0.02em' }}>
              {t.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
