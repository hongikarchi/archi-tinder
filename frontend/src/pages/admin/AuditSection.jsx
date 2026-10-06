/** AuditSection — paginated admin audit log (newest first). */
import { useCallback, useState } from 'react'
import { getAdminAuditLog } from '../../api/admin.js'
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import { useAdminSection } from './useAdminSection.js'
import styles from './AdminPage.module.css'

const PAGE_SIZE = 50

export default function AuditSection() {
  const { t, language } = useTranslation()
  const [page, setPage] = useState(1)
  const fetcher = useCallback(() => getAdminAuditLog({ page, pageSize: PAGE_SIZE }), [page])
  const { data, loading, error, reload } = useAdminSection(fetcher, String(page))

  const rows = Array.isArray(data?.results) ? data.results : []
  const count = typeof data?.count === 'number' ? data.count : 0
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  const fmtTime = iso => {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso || '-'
    return d.toLocaleString(language === 'ko' ? 'ko-KR' : 'en-US', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  }

  return (
    <SectionCard
      title={t('admin.audit.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      skeletonRows={5}
    >
      {rows.length === 0 ? (
        <p className={styles.muted}>{t('admin.audit.empty')}</p>
      ) : (
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t('admin.audit.time')}</th>
                <th>{t('admin.audit.actor')}</th>
                <th>{t('admin.audit.action')}</th>
                <th>{t('admin.audit.target')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{fmtTime(row.created_at)}</td>
                  <td style={{ overflowWrap: 'anywhere' }}>{row.actor_email || t('admin.audit.system')}</td>
                  <td className={styles.mono}>{row.action}</td>
                  <td className={styles.mono} style={{ overflowWrap: 'anywhere' }}>
                    {[row.target_type, row.target_id].filter(Boolean).join(' #') || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {count > PAGE_SIZE && (
        <div className={styles.pager}>
          <button type="button" className={styles.btn} disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            {t('admin.audit.prev')}
          </button>
          <span className={styles.muted}>{t('admin.audit.pageOf', { page, pages, count })}</span>
          <button type="button" className={styles.btn} disabled={page >= pages} onClick={() => setPage(p => Math.min(pages, p + 1))}>
            {t('admin.audit.next')}
          </button>
        </div>
      )}
    </SectionCard>
  )
}
