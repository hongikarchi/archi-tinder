/**
 * ArticleCard — list-style card with §3.5.1 hover behavior (no default border, hover lift)
 *   Content-specific differentiator: left accent border + source pill (preserved from prior redesign).
 */
export default function ArticleCard({ article }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noreferrer"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '18px 20px 18px 22px',
        background: 'var(--color-surface)',
        border: '1px solid transparent',   // §3.5.1: NO default border
        borderLeft: '3px solid #ec4899',    // content-specific accent (articles only)
        borderRadius: 14,
        textDecoration: 'none',
        transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)'
        e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
        e.currentTarget.style.borderLeftColor = '#f43f5e'
        e.currentTarget.style.boxShadow = '0 10px 25px rgba(0,0,0,0.3)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.borderColor = 'transparent'
        e.currentTarget.style.borderLeftColor = '#ec4899'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <p
        style={{
          color: 'var(--color-text)',
          fontSize: 15,
          fontWeight: 600,
          margin: 0,
          lineHeight: 1.4,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {article.title}
      </p>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            background: 'rgba(236,72,153,0.12)',
            color: '#ec4899',
            fontSize: 11,
            fontWeight: 600,
            padding: '4px 10px',
            borderRadius: 999,
            letterSpacing: '0.02em',
            textTransform: 'uppercase',
          }}
        >
          {article.source}
        </span>
        <span
          style={{
            color: 'var(--color-text-dimmer)',
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {article.date}
        </span>
      </div>
    </a>
  )
}
