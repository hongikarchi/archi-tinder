import { useTranslation } from '../../i18n/index.js'
import PageLogoHeader from '../../components/PageLogoHeader.jsx'

export default function ErrorState({ message, onRetry }) {
  const { t } = useTranslation()
  return (
    <div style={{
      height: 'var(--page-height)',
      overflowY: 'auto',
      background: 'var(--color-bg)',
      color: 'var(--color-text)',
      display: 'flex',
      flexDirection: 'column',
      paddingBottom: 'var(--tabbar-clearance)',
    }}>
      <PageLogoHeader />
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
        <p style={{ color: 'var(--color-text)', fontSize: 'var(--fs-emphasis)', fontWeight: 'var(--fw-bold)', margin: 0 }}>
          {t('buildingDetail.notFound')}
        </p>
        <p style={{ color: 'var(--color-text-dim)', fontSize: 'var(--fs-caption)', lineHeight: 1.5, margin: 0 }}>
          {message}
        </p>
        <button
          type="button"
          onClick={onRetry}
          style={{
            minHeight: 44,
            padding: '0 18px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-soft)',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            fontSize: 'var(--fs-caption)',
            fontWeight: 'var(--fw-bold)',
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          {t('buildingDetail.retry')}
        </button>
      </div>
    </div>
  )
}
