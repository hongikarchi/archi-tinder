/**
 * BoardCover — persona cover card for BoardDetailPage (FULL-REPORT-UI-1 WP4,
 * mock `boardDetail`): aspect 4:3, radius-lg, soft border, E5 shadow, bottom
 * scrim, persona name (24px bold, white) + meta line (12px, white 72%).
 *
 * Image chain is decided by the caller (persona image -> first building cover);
 * with no image a neutral accent gradient face is rendered so the title still
 * has a surface to sit on.
 */
export default function BoardCover({ imageUrl, alt, title, meta }) {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '4 / 3',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        border: '1px solid var(--color-border-soft)',
        boxShadow: '0 8px 24px rgba(0,0,0,.12)',
        background: [
          'radial-gradient(120% 120% at 15% 10%, color-mix(in srgb, var(--accent-1) 18%, var(--color-surface)) 0%, transparent 60%)',
          'radial-gradient(120% 120% at 90% 95%, color-mix(in srgb, var(--accent-2) 16%, var(--color-surface)) 0%, transparent 60%)',
          'var(--color-surface-2)',
        ].join(', '),
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={alt || ''}
          fetchpriority="high"
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            display: 'block',
          }}
        />
      )}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: imageUrl
            ? 'linear-gradient(to top, rgba(0,0,0,.78) 0%, rgba(0,0,0,.2) 50%, rgba(0,0,0,0) 75%)'
            : 'linear-gradient(to top, rgba(0,0,0,.55) 0%, rgba(0,0,0,0) 65%)',
        }}
      />
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '18px 18px 16px' }}>
        <h1 style={{
          margin: '0 0 4px',
          color: '#fff',
          fontSize: 'var(--fs-title)',
          fontWeight: 'var(--fw-bold)',
          lineHeight: 1.2,
          wordBreak: 'keep-all',
        }}>
          {title}
        </h1>
        {meta && (
          <p style={{ margin: 0, color: 'rgba(255,255,255,.72)', fontSize: 'var(--fs-caption)' }}>
            {meta}
          </p>
        )}
      </div>
    </div>
  )
}
