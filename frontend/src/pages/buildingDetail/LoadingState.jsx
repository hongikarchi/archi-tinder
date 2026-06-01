import Header from './Header.jsx'

export default function LoadingState({ onBack }) {
  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
    }}>
      <Header onBack={onBack} />
      <div className="skeleton-shimmer" style={{ height: '50vh', width: '100%' }} />
      <div style={{ padding: '22px 20px' }}>
        <div className="skeleton-shimmer" style={{ width: '72%', height: 28, borderRadius: 8, marginBottom: 14 }} />
        <div className="skeleton-shimmer" style={{ width: '46%', height: 16, borderRadius: 8, marginBottom: 24 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} className="skeleton-shimmer" style={{ height: 58, borderRadius: 12 }} />
          ))}
        </div>
      </div>
    </div>
  )
}
