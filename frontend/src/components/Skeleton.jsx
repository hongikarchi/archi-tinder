/**
 * Skeleton — shared static loading placeholder block.
 *
 * DESIGN.md §8.8: "No shimmer animation (performance cost + unrelated to the
 * Vibe keywords)." Static `var(--color-surface-2)` block, `--radius-sm`
 * default (badges / thumbnails / lines) — pass `radius` for a card-shaped
 * skeleton (e.g. `var(--radius-lg)` to match a PhotoTile).
 *
 * Build-only in UI-CONSISTENCY-B Phase 2b — no page adopts this component
 * yet; the existing inline skeleton blocks across UserProfilePage /
 * LikedProjectsPage / etc. are untouched (no adoption site was in-scope).
 */
export default function Skeleton({ width = '100%', height = 16, radius = 'var(--radius-sm)', circle = false, style, className }) {
  return (
    <div
      aria-hidden="true"
      className={className}
      style={{
        width: circle ? height : width,
        height,
        borderRadius: circle ? '50%' : radius,
        background: 'var(--color-surface-2)',
        flexShrink: 0,
        ...style,
      }}
    />
  )
}
