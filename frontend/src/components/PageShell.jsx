/**
 * PageShell — shared viewport-locked scroll container + centered content
 * column.
 *
 * DESIGN.md §3.3 `--page-height` + this PR's width-variant decision:
 * 'narrow' 600 / 'medium' 680 / 'wide' 1100, side padding 20.
 *
 * UI-CONSISTENCY-B Phase 2b: replaces the `.page { height: var(--page-height);
 * overflow-y: auto; background: var(--color-bg); }` CSS Module rule that was
 * copy-pasted verbatim into 5 settings screens' modules (SettingsPage,
 * AccountScreen, AppearanceScreen, NotificationsScreen,
 * NotificationInboxScreen) plus a cross-import into EditProfileScreen, and
 * the manual `<div style={{ maxWidth:600, margin:'0 auto', padding:'24px
 * 16px' }}>` content wrapper each of those screens also hand-rolled.
 *
 * `chrome` renders full-bleed ABOVE the width-constrained column — for the
 * page furniture that must not be squeezed into the narrow column:
 * `PageBackButton` / `PageTopControls` are `position:fixed` (unaffected by
 * ancestor width either way) and `PageLogoHeader` is an in-flow, full-width,
 * text-align:center block whose own padding (`20px 16px 6px`) already
 * supplies its vertical spacing — nesting it inside the padded inner column
 * would double up its top offset. `children` render inside the centered,
 * side-padded column (the `PageTitle` + page content that used to live in
 * the hand-rolled wrapper div).
 *
 * `contentStyle` lets a caller override/extend the inner column's padding —
 * used where a page's own top/bottom padding differs from the previous
 * 16px-side default (all adopters bump 16 -> 20 per this PR's side-padding
 * decision; NotificationInboxScreen keeps its distinct 12px-aligned-with-rows
 * padding verbatim via this prop, since that spacing is its own deliberate
 * mock-parity choice, not a generic default).
 */
const WIDTHS = {
  narrow: 600,
  medium: 680,
  wide: 1100,
}

export default function PageShell({
  width = 'medium',
  chrome,
  children,
  contentStyle,
  style,
  className,
}) {
  const maxWidth = WIDTHS[width] ?? WIDTHS.medium
  return (
    <div
      className={className}
      style={{
        height: 'var(--page-height)',
        overflowY: 'auto',
        background: 'var(--color-bg)',
        ...style,
      }}
    >
      {chrome}
      <div
        style={{
          maxWidth,
          margin: '0 auto',
          padding: '0 20px',
          ...contentStyle,
        }}
      >
        {children}
      </div>
    </div>
  )
}
