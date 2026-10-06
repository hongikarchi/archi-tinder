import PageLogoHeader from '../../components/PageLogoHeader.jsx'
import Skeleton from '../../components/Skeleton.jsx'

export default function LoadingState() {
  return (
    <div style={{
      height: 'var(--page-height)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
      paddingBottom: 'var(--tabbar-clearance)',
    }}>
      <PageLogoHeader />
      <Skeleton width="100%" height="50vh" radius="0" />
      <div style={{ padding: '22px 20px' }}>
        <Skeleton width="72%" height={28} radius="var(--radius-sm)" style={{ marginBottom: 14 }} />
        <Skeleton width="46%" height={16} radius="var(--radius-sm)" style={{ marginBottom: 24 }} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {[0, 1, 2, 3].map(i => (
            <Skeleton key={i} width="100%" height={58} radius="var(--radius-md)" />
          ))}
        </div>
      </div>
    </div>
  )
}
