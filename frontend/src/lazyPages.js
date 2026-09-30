/**
 * lazyPages — route-level code splitting (PERF-FE-1).
 *
 * Every page/modal that is NOT part of the first screen is loaded on demand.
 * The `load*` functions double as idle-time prefetchers (see
 * `prefetchLikelyNextPages`) so navigation to the likely next page stays
 * instant. Eager on purpose (not in this file): app shell, MainLayout/TabBar,
 * ProtectedRoute, contexts, and DiscoveryPage (the landing route of every
 * returning logged-in user; `/` redirects there, so lazy-loading it would add a
 * visible flash on the most common first paint).
 */
import { lazy } from 'react'

const RELOAD_KEY = 'archithon_chunk_reload_at'

// After a deploy, an already-open tab still points at old hashed chunk URLs that
// no longer exist -> the dynamic import rejects. Hard-reload once (guarded so a
// genuinely broken chunk cannot loop) so the tab picks up the fresh build.
// Only chunk-fetch failures reload; a bug inside the page module rethrows to
// ErrorBoundary so in-memory state (e.g. a swipe session) is not dropped.
const CHUNK_LOAD_ERROR = /dynamically imported module|Importing a module script failed|Failed to fetch|error loading dynamically/i

function lazyPage(loader) {
  return lazy(() =>
    loader().catch(err => {
      if (!CHUNK_LOAD_ERROR.test(String(err && err.message))) throw err
      let last = 0
      try { last = Number(sessionStorage.getItem(RELOAD_KEY) || 0) } catch { /* storage blocked */ }
      if (Date.now() - last > 15000) {
        try { sessionStorage.setItem(RELOAD_KEY, String(Date.now())) } catch { /* storage blocked */ }
        window.location.reload()
        return new Promise(() => {}) // page is unloading; never settle
      }
      throw err
    })
  )
}

// ── Loaders (also used for prefetch) ──────────────────────────────────────
export const loadSwipePage = () => import('./pages/SwipePage.jsx')
export const loadLLMSearchPage = () => import('./pages/LLMSearchPage.jsx')
export const loadUserProfilePage = () => import('./pages/UserProfilePage.jsx')
export const loadPeopleDiscoveryPage = () => import('./pages/PeopleDiscoveryPage.jsx')
export const loadResultsPage = () => import('./pages/ResultsPage.jsx')

// ── Lazy components ───────────────────────────────────────────────────────
export const SwipePage = lazyPage(loadSwipePage)
export const LoginPage = lazyPage(() => import('./pages/LoginPage.jsx'))
export const LLMSearchPage = lazyPage(loadLLMSearchPage)
export const LLMSearchUpdateWrapper = lazyPage(() => import('./components/LLMSearchUpdateWrapper.jsx'))
export const UserProfilePage = lazyPage(loadUserProfilePage)
export const ResultsPage = lazyPage(loadResultsPage)
export const BuildingDetailPage = lazyPage(() => import('./pages/BuildingDetailPage.jsx'))
export const BoardDetailPage = lazyPage(() => import('./pages/BoardDetailPage.jsx'))
export const BoardReportPage = lazyPage(() => import('./pages/BoardReportPage.jsx'))
export const LikedProjectsPage = lazyPage(() => import('./pages/LikedProjectsPage.jsx'))
export const UploadWorkPage = lazyPage(() => import('./pages/UploadWorkPage.jsx'))
export const ArchitectProfilePage = lazyPage(() => import('./pages/ArchitectProfilePage.jsx'))
export const AssessmentPage = lazyPage(() => import('./pages/AssessmentPage.jsx'))
export const PeopleDiscoveryPage = lazyPage(loadPeopleDiscoveryPage)
export const CompetitionListPage = lazyPage(() => import('./pages/CompetitionListPage.jsx'))
export const CompetitionDetailPage = lazyPage(() => import('./pages/CompetitionDetailPage.jsx'))
export const SettingsPage = lazyPage(() => import('./pages/settings/SettingsPage.jsx'))
export const AccountScreen = lazyPage(() => import('./pages/settings/AccountScreen.jsx'))
export const NotificationsScreen = lazyPage(() => import('./pages/settings/NotificationsScreen.jsx'))
export const NotificationInboxScreen = lazyPage(() => import('./pages/settings/NotificationInboxScreen.jsx'))
export const AppearanceScreen = lazyPage(() => import('./pages/settings/AppearanceScreen.jsx'))
export const EditProfileScreen = lazyPage(() => import('./pages/settings/EditProfileScreen.jsx'))
// Modals mounted on demand from App.jsx.
export const SaveBoardModal = lazyPage(() => import('./components/SaveBoardModal.jsx'))
export const VerifyGateModal = lazyPage(() => import('./components/VerifyGateModal.jsx'))

/**
 * Warm the chunks of the pages a user is most likely to open next (TabBar
 * destinations + the swipe page that follows search) once the browser is idle
 * after first render. Failures are ignored — the real navigation retries.
 */
export function prefetchLikelyNextPages() {
  const run = () => {
    ;[loadSwipePage, loadLLMSearchPage, loadUserProfilePage, loadPeopleDiscoveryPage, loadResultsPage]
      .forEach(load => { load().catch(() => {}) })
  }
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(run, { timeout: 5000 })
  } else {
    setTimeout(run, 2500)
  }
}
