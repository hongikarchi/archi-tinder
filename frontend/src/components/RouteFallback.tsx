/**
 * RouteFallback — Suspense fallback for lazy route chunks (PERF-FE-1).
 *
 * Deliberately just the viewport-locked page background (same box the
 * "no active project" screen in MainLayout uses) so a chunk load never flashes
 * a different colour or shifts layout; the page paints in over it.
 */
export default function RouteFallback() {
  return (
    <div
      aria-busy="true"
      style={{ height: 'var(--page-height)', background: 'var(--color-bg)' }}
    />
  )
}
