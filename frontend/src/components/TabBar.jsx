import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from '../i18n/index.js'
import { discoveryNavigationGuard } from '../utils/discoveryGuard.js'
import SegmentedControl from './SegmentedControl.jsx'
import { useUnreadMessages } from '../hooks/useUnreadMessages.js'

/*
 * TAB_ICONS — { outline, active } SVG pair per tab.
 *
 * UI-CONSISTENCY-B Phase 2a decision log #5 (2026-09-26): Instagram-style
 * icon-only bar — inactive = outline (stroke 2), active = filled variant.
 * Icon size 24 (DESIGN.md §7.1).
 *
 * Superseded in part by decision log #5b (Phase 2c, same date): the bar is
 * now a floating glass capsule, and the active tab gets a rounded pill
 * highlight (`--tabbar-active-bg`) behind the filled icon — see the `<nav>` /
 * pill-`<span>` markup below. The "no color pill / no underline" clause above
 * described the flat Phase 2a bar and no longer applies.
 *
 * `active` variants reuse the exact same path geometry as `outline`
 * wherever a shape is already closed (rects, circles) or trivially
 * closeable (the single-person `profile` body arc, closed with a straight
 * bottom edge: the outline path already ends in `v2`, the active path just
 * appends `z`). This deliberately avoids hand-authoring new bezier/arc
 * geometry that can't be visually verified in this environment (no running
 * browser for this change) — see the front-maker report for `social`'s
 * compromise: its two secondary/background-person arcs stay thin strokes
 * even in the active state rather than force-filling an open arc, which
 * would render as a stray wedge instead of a body shape.
 */
const TAB_ICONS = {
  discovery: {
    outline: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    ),
    active: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="none">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  // "Taste" tab — replaced the old briefcase/bag icon with a magnifying
  // glass (search) per user decision (plan §Decisions log #5). Active state
  // is the same glyph at a heavier stroke (Instagram's own active-search
  // treatment), not a fill — a magnifying glass has no sensible closed
  // fill area.
  swipe: {
    outline: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
    active: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="7" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
  },
  social: {
    outline: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
    active: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2z" fill="currentColor" stroke="none" />
        <circle cx="9" cy="7" r="4" fill="currentColor" stroke="none" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  profile: {
    outline: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
    active: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="none">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2z" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
}

/*
 * getActiveTab — route -> tab mapping.
 * UI-CONSISTENCY-B Phase 2a fix (2026-09-26): `/upload`, `/notifications`,
 * `/liked-projects` previously fell through to the `discovery` default even
 * though they are profile-cluster screens (see App.jsx routes). Added here.
 * `/architects/:id`, `/buildings/:id`, `/library*`, `/my/liked-offices`
 * (dead redirect), `/admin*` intentionally still fall through
 * to `discovery` — "stay on the tab the user came from" is not tracked by
 * this pure-function mapping, and discovery is the simplest acceptable
 * default per the task spec.
 */
function getActiveTab(pathname) {
  if (pathname === '/swipe' || pathname.startsWith('/search') || pathname.startsWith('/result')) return 'swipe'
  if (pathname.startsWith('/people') || pathname.startsWith('/assessment') || pathname.startsWith('/competitions')) return 'social'
  if (
    pathname.startsWith('/user') ||
    pathname.startsWith('/board') ||
    pathname.startsWith('/settings') ||
    pathname.startsWith('/upload') ||
    pathname.startsWith('/notifications') ||
    pathname.startsWith('/liked-projects')
  ) return 'profile'
  return 'discovery'
}

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const activeTab = getActiveTab(location.pathname)
  // FULL-MESSAGING-1 (D6): unread dot on the profile tab — the message pill
  // only lives on /user/me, so other screens learn about new messages here.
  // Flag OFF -> count is always 0 and no request is made.
  const { count: unreadMessages } = useUnreadMessages()

  const tabs = [
    { id: 'discovery', labelKey: 'tabbar.discovery', path: '/discovery' },
    { id: 'swipe',     labelKey: 'tabbar.taste',     path: '/search' },
    { id: 'social',    labelKey: 'tabbar.social',    path: '/people' },
    { id: 'profile',   labelKey: 'tabbar.profile',   path: '/user/me' },
  ]

  function handleSelect(tabId) {
    const tab = tabs.find(t => t.id === tabId)
    if (!tab || tab.path === location.pathname) return

    // If the guard is active (Discovery mounted with draft likes >= 1), show the
    // leave-warning modal and defer navigation to the user's choice.
    if (discoveryNavigationGuard.check) {
      discoveryNavigationGuard.check(tab.path, () => navigate(tab.path))
    } else {
      navigate(tab.path)
    }
  }

  const options = tabs.map(tab => ({
    value: tab.id,
    label: t(tab.labelKey),
    ariaLabel: tab.id === 'profile' && unreadMessages > 0
      ? t('tabbar.profileUnread', { n: unreadMessages })
      : t(tab.labelKey),
  }))

  return (
    <nav
      aria-label={t('tabbar.nav')}
      style={{
        position: 'fixed',
        left: 16, right: 16,
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 10px)',
        maxWidth: 420, margin: '0 auto',
        display: 'flex', zIndex: 100, height: 'var(--tabbar-height)',
        borderRadius: 'var(--radius-pill)',
        background: 'var(--tabbar-glass-bg)',
        border: '1px solid var(--tabbar-glass-border)',
        boxShadow: 'var(--tabbar-glass-shadow)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
      }}
    >
      {/* variant="pill" / size="lg" / as="nav" — the 4 tabs are real route
          navigation (not in-page panels), so this deliberately skips the
          tablist/tab or radiogroup/radio ARIA pattern; see SegmentedControl's
          docblock. `aria-label` stays on THIS <nav> (unchanged); the group
          itself renders no role/aria-label of its own in "nav" mode. */}
      <SegmentedControl
        as="nav"
        variant="pill"
        size="lg"
        fullWidth
        pillHeight={52}
        measureContent
        options={options}
        value={activeTab}
        onChange={handleSelect}
        style={{ width: '100%', height: '100%' }}
        optionStyle={(opt, isActive) => ({
          height: '100%',
          color: isActive ? 'var(--color-text)' : 'var(--color-nav-inactive)',
          transition: 'color var(--motion-fast) var(--motion-ease)',
        })}
        optionContentStyle={{ width: 68, height: 52, flexDirection: 'column', gap: 3 }}
        highlightStyle={{ background: 'var(--tabbar-active-bg)' }}
        renderOption={(opt, isActive) => {
          const baseIcon = isActive ? TAB_ICONS[opt.value].active : TAB_ICONS[opt.value].outline
          const icon = (opt.value !== 'profile' || unreadMessages <= 0) ? baseIcon : (
            <span style={{ position: 'relative', display: 'inline-flex' }}>
              {baseIcon}
              <span
                aria-hidden="true"
                style={{
                  position: 'absolute', top: -1, right: -3,
                  width: 9, height: 9, borderRadius: '50%',
                  background: 'var(--accent-1)',
                  boxShadow: '0 0 0 2px var(--color-bg)',
                }}
              />
            </span>
          )
          return (
            <>
              {icon}
              <span
                aria-hidden="true"
                style={{
                  fontSize: 11, lineHeight: 1, fontWeight: 500,
                  whiteSpace: 'nowrap', maxWidth: '100%',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}
              >
                {opt.label}
              </span>
            </>
          )
        }}
      />
    </nav>
  )
}
