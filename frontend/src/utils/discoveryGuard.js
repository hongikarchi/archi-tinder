/**
 * discoveryNavigationGuard — module-level guard for Discovery leave-warning modal.
 *
 * When DiscoveryPage is mounted with draftLikeCount >= 1, it sets `check` to a
 * function that either shows the modal (and defers the callback) or calls the
 * callback immediately. TabBar and MainLayout import this object to intercept
 * navigation and logout actions.
 *
 * check(action: string, proceed: () => void):
 *   - action: human-readable destination label (kept for debugging)
 *   - proceed: the original navigation / logout callback to run if user confirms
 *
 * When DiscoveryPage is unmounted (user already navigated away) or draftLikeCount
 * is 0, `check` is null — callers fall through to the original action immediately.
 */
export const discoveryNavigationGuard = { check: null }
