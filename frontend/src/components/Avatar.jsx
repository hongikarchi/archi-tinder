/**
 * Avatar — small reusable avatar circle: image if avatar_url present, else an
 * initial-letter fallback (first character of name, uppercased).
 *
 * Purely presentational, no :hover/:focus/:active state -> inline styles only
 * per DESIGN.md §4/§10.4 (extracted here because NOTIF-INAPP-1 needs it in
 * NotificationInboxScreen rows; ProfileHero.jsx keeps its own inline
 * AvatarCircle unchanged — not touched by this change).
 */
export default function Avatar({ src, name, size = 40 }) {
  const initial = (name || '?').trim().charAt(0).toUpperCase() || '?'

  if (src) {
    return (
      <img
        src={src}
        alt=""
        aria-hidden="true"
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          objectFit: 'cover',
          background: 'var(--color-surface-2)',
          border: '1px solid var(--color-border-soft)',
          flexShrink: 0,
          display: 'block',
        }}
      />
    )
  }

  return (
    <div
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border-soft)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        color: 'var(--color-text-muted)',
        fontSize: Math.round(size * 0.42),
        fontWeight: 600,
      }}
    >
      {initial}
    </div>
  )
}
