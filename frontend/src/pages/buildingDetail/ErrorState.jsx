import Header from './Header.jsx'

export default function ErrorState({ message, onBack, onRetry }) {
  return (
    <div style={{
      height: 'calc(100vh - 64px - env(safe-area-inset-bottom, 0px))',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Header onBack={onBack} />
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 14,
        padding: 24,
        textAlign: 'center',
      }}>
        <p style={{ color: 'var(--color-text)', fontSize: 17, fontWeight: 700, margin: 0 }}>
          건물 정보를 찾을 수 없어요
        </p>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 13, lineHeight: 1.5, margin: 0 }}>
          {message}
        </p>
        <button
          type="button"
          onClick={onRetry}
          style={{
            minHeight: 44,
            padding: '0 18px',
            borderRadius: 12,
            border: '1px solid var(--color-border-soft)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            fontSize: 13,
            fontWeight: 700,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          Retry
        </button>
      </div>
    </div>
  )
}
