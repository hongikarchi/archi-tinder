import s from './ArticleCard.module.css'

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
      className={s.card}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        padding: '18px 20px 18px 22px',
        background: 'var(--color-surface)',
        borderRadius: 14,
        textDecoration: 'none',
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
            background: 'color-mix(in srgb, var(--accent-1) 12%, transparent)',
            color: 'var(--accent-1)',
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
