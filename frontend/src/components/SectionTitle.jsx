/**
 * SectionTitle — shared section-level heading (h2 by default).
 *
 * DESIGN.md §2.2: section / modal title = `--fs-heading` (20px) / `--fw-bold`
 * (700). Optional `right` slot (e.g. an "Edit" button) and an optional
 * `count` badge next to the title (dim, `--fs-caption`) — mirrors the
 * "Curated Boards  12" / "N projects" pattern already used ad hoc in a few
 * places (UserProfilePage's board/liked/created tab headers).
 *
 * Built in UI-CONSISTENCY-B Phase 2b; no adoption site was in-scope for this
 * PR (see PR description "Deferred"). `as` lets a caller render `h3` etc.
 * when heading order requires it — the visual style stays the same.
 */
export default function SectionTitle({ as, children, count, right, style, className }) {
  const Tag = as || 'h2'
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <Tag
          className={className}
          style={{
            fontSize: 'var(--fs-heading)',
            fontWeight: 'var(--fw-bold)',
            margin: 0,
            color: 'var(--color-text)',
            letterSpacing: '-0.01em',
            ...style,
          }}
        >
          {children}
        </Tag>
        {count != null && (
          <span
            style={{
              fontSize: 'var(--fs-caption)',
              fontWeight: 'var(--fw-semibold)',
              color: 'var(--color-text-dimmer)',
            }}
          >
            {count}
          </span>
        )}
      </div>
      {right && <div style={{ display: 'flex', alignItems: 'center' }}>{right}</div>}
    </div>
  )
}
