import ArticleCard from '../../components/profile/ArticleCard'

export default function FirmArticlesSection({ articles }) {
  if (!articles?.length) return null

  return (
    /* Articles */
    <section>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 12,
        marginBottom: 20, padding: '0 4px',
      }}>
        <h3 style={{
          color: 'var(--color-text)', fontSize: 20, fontWeight: 700,
          margin: 0, letterSpacing: '-0.01em',
        }}>
          Featured Articles
        </h3>
        <span style={{
          color: 'var(--color-text-dimmer)', fontSize: 13, fontWeight: 600,
        }}>
          {articles.length}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {articles.map((article, idx) => (
          <ArticleCard key={`${article.url}-${idx}`} article={article} />
        ))}
      </div>
    </section>
  )
}
