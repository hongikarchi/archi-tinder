/**
 * PageTitle — shared page-level heading (h1).
 *
 * DESIGN.md §2.2: page title = `--fs-title` (24px) / `--fw-bold` (700).
 * UI-CONSISTENCY-B Phase 2b: replaces the `.headerTitle` CSS Module rule that
 * was copy-pasted verbatim into 6 settings/upload page modules (SettingsPage,
 * AccountScreen, AppearanceScreen, NotificationsScreen, NotificationInboxScreen,
 * UploadWorkPage) — all six had the exact same `font-size:20px; font-weight:700;
 * margin:0 0 14px; color:var(--color-text); letter-spacing:-0.01em;` block.
 * The size bump 20 -> 24 is intentional (DESIGN.md §2.2 type-scale decision,
 * 2026-09-26) — every prior `.headerTitle` was an off-scale 20px "page title"
 * that the new 5-step scale reclassifies as 24 (title tier), not 20 (heading
 * tier, reserved for section/modal titles — see SectionTitle.jsx).
 *
 * NOTE: `PageLogoHeader` (the "Arch|ibe" wordmark shown above this on most
 * pages) also renders an `<h1>`, so pages using both end up with two `<h1>`s.
 * That pre-existing structure is out of this component's scope to fix
 * (PageLogoHeader is a separate, unrelated shared component) — flagged for
 * phase 3 / a future a11y pass rather than silently changed here.
 *
 * `as` lets a caller downgrade the tag (e.g. to `h2`) if a page ever nests
 * this under another `<h1>` and heading order matters more than the visual
 * style — the visual style stays identical either way.
 */
export default function PageTitle({ as, children, style, className }) {
  const Tag = as || 'h1'
  return (
    <Tag
      className={className}
      style={{
        fontSize: 'var(--fs-title)',
        fontWeight: 'var(--fw-bold)',
        margin: '0 0 14px',
        color: 'var(--color-text)',
        letterSpacing: '-0.01em',
        ...style,
      }}
    >
      {children}
    </Tag>
  )
}
