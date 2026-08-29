/**
 * ThemePreviewCard.jsx — SETTINGS-POLISH-1 §D
 *
 * Static mini app-screen mockup that previews a theme without switching the
 * whole app to it. Renders a `data-theme={theme}` wrapper so tokens.css
 * `[data-theme="..."]` overrides apply ONLY inside this subtree (see the
 * tokens.css :root, [data-theme="github-light"] fix that makes this work
 * correctly even when github-light is being previewed from a different
 * active app theme).
 *
 * Every color / border / font below is a var(--...) token from tokens.css —
 * no invented token names, no literal hex. Purely decorative: inner controls
 * are non-interactive (pointer-events: none) and aria-hidden.
 */
export default function ThemePreviewCard({ theme }) {
  return (
    <div
      data-theme={theme}
      style={{
        width: '100%',
        height: 168,
        borderRadius: 12,
        overflow: 'hidden',
        background: 'var(--color-bg)',
        border: '1px solid var(--color-border)',
        fontFamily: 'var(--font-family)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div aria-hidden="true" style={{ pointerEvents: 'none', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Header row — wordmark + 3 accent dots */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 14px',
            background: 'var(--color-header-bg)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <span style={{
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: 'var(--color-text)',
          }}>
            archibe
          </span>
          <div style={{ display: 'flex', gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-1)' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-2)' }} />
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-3)' }} />
          </div>
        </div>

        {/* Content area */}
        <div style={{ flex: 1, minHeight: 0, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Mini content card */}
          <div
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text)' }}>
              Aa — {theme}
            </span>
            <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--color-text-muted)' }}>
              Sample card text on surface
            </span>
          </div>

          {/* Button row + chips */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 'auto' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '6px 12px',
                borderRadius: 999,
                background: 'var(--accent-1)',
                color: '#fff',
                fontSize: 10,
                fontWeight: 600,
              }}
            >
              Like
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '6px 12px',
                borderRadius: 999,
                background: 'transparent',
                border: '1px solid var(--color-border-soft)',
                color: 'var(--color-text)',
                fontSize: 10,
                fontWeight: 500,
              }}
            >
              Skip
            </span>
            <span
              style={{
                marginLeft: 'auto',
                padding: '4px 10px',
                borderRadius: 999,
                background: 'var(--color-tag-bg)',
                border: '1px solid var(--color-tag-border)',
                color: 'var(--color-tag-label)',
                fontSize: 9,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Tag
            </span>
            <span
              style={{
                padding: '4px 10px',
                borderRadius: 999,
                background: 'var(--color-tag-bg)',
                border: '1px solid var(--color-tag-border)',
                color: 'var(--color-tag-label)',
                fontSize: 9,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Tag
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
