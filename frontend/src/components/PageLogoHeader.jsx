/**
 * PageLogoHeader — the "Arch|ibe" two-tone wordmark shown at the top of
 * (almost) every page.
 *
 * Per the Claude Design canvas boards (canvas-design-port.md §6d item 1),
 * 36 of 37 mocked screens render this exact element in the top slot —
 * the user confirmed this is intentional, not template noise. It replaces
 * whatever ad-hoc page-title `<h1>`/`<h2>` each page used to render there
 * (e.g. DiscoveryPage's two-tone `Disc|overy`) so every page shares one
 * title element instead of drifting independently.
 *
 * "Archibe" is a brand wordmark, not user-facing copy — intentionally NOT
 * routed through i18n (mirrors the uppercase ARCHIBE wordmark elsewhere,
 * e.g. LoginPage / SwipePage fallback / CardSkeleton, which is also literal).
 */
export default function PageLogoHeader({ padding = '18px 16px 6px', marginBottom = 0, style }) {
  return (
    <div style={{ textAlign: 'center', width: '100%', padding, boxSizing: 'border-box', ...style }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: `0 0 ${marginBottom}px`, letterSpacing: '-0.01em' }}>
        <span style={{ color: 'var(--color-text)' }}>Arch</span>
        <span style={{ color: 'var(--accent-1)' }}>ibe</span>
      </h1>
    </div>
  )
}
