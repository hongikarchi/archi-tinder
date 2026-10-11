/**
 * ContestsSection — FULL-CONTEST-2 admin contests (공모전) management.
 *
 * Lists ALL contests (hidden / pending / past-deadline included) with a status
 * filter + pagination, quick status actions (PATCH; the server's publish-rule 400
 * is shown inline on the row) and a create/edit form modal. Deadlines render in
 * KST regardless of the device timezone (utils/contestDeadline.js).
 */
import { useCallback, useEffect, useState } from 'react'
import { getAdminContests, updateAdminContest } from '../../api/admin.js'
import { useTranslation } from '../../i18n/index.js'
import Tabs from '../../components/Tabs.jsx'
import { formatKstDateTime } from '../../utils/contestDeadline.js'
import { safeHttpUrl } from '../../utils/safeUrl.js'
import SectionCard from './SectionCard.jsx'
import ContestFormModal from './ContestFormModal.jsx'
import { CONTEST_STATUSES } from './contestConstants.js'
import { flattenApiErrors } from './contestErrors.js'
import { useAdminSection } from './useAdminSection.js'
import adminStyles from './AdminPage.module.css'
import styles from './ContestsSection.module.css'

const PAGE_SIZE = 50
const STATUS_BADGE = { published: adminStyles.ok, pending: adminStyles.warn, hidden: '' }

function ExternalLink({ href, label }) {
  const safe = safeHttpUrl(href)
  if (!safe) return null
  return (
    <a className={adminStyles.badge} href={safe} target="_blank" rel="noopener noreferrer">
      {label} ↗
    </a>
  )
}

export default function ContestsSection() {
  const { t, language } = useTranslation()
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  // null = closed, 'new' = create form, otherwise the contest row being edited.
  const [formTarget, setFormTarget] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [rowErrors, setRowErrors] = useState({})

  const fetcher = useCallback(
    () => getAdminContests({ status: status === 'all' ? undefined : status, page, pageSize: PAGE_SIZE }),
    [status, page],
  )
  const { data, loading, error, reload } = useAdminSection(fetcher, `${status}|${page}`)

  const rows = Array.isArray(data?.results) ? data.results : []
  const count = typeof data?.count === 'number' ? data.count : 0
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  // A mutation can empty the current page; step back to the last real page.
  useEffect(() => {
    if (loading || error || !data) return
    if (count > 0 && page > pages) setPage(pages)
  }, [loading, error, data, count, page, pages])

  const filterTabs = ['all', ...CONTEST_STATUSES].map(id => ({ id, label: t(`admin.contests.filter.${id}`) }))

  const changeFilter = next => {
    setStatus(next)
    setPage(1)
  }

  const changeStatus = async (row, next) => {
    if (busyId != null) return
    setBusyId(row.id)
    setRowErrors(prev => ({ ...prev, [row.id]: '' }))
    try {
      await updateAdminContest(row.id, { status: next })
      reload()
    } catch (err) {
      const messages = err?.status === 400 ? flattenApiErrors(err?.data) : []
      setRowErrors(prev => ({
        ...prev,
        [row.id]: messages.length > 0 ? messages.join(' ') : t('admin.contests.statusError'),
      }))
    } finally {
      setBusyId(null)
    }
  }

  const afterSave = () => {
    setFormTarget(null)
    reload()
  }

  const right = (
    <button type="button" className={`${adminStyles.btn} ${adminStyles.btnSmall}`} onClick={() => setFormTarget('new')}>
      {t('admin.contests.create')}
    </button>
  )

  return (
    <>
    <SectionCard
      title={t('admin.contests.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      right={right}
      skeletonRows={5}
    >
      <div className={styles.toolbar}>
        <div className={styles.filterTabs}>
          <Tabs tabs={filterTabs} value={status} onChange={changeFilter} />
        </div>
        <span className={adminStyles.muted}>{t('admin.contests.total', { count })}</span>
      </div>

      {rows.length === 0 ? (
        <p className={adminStyles.muted}>{t('admin.contests.empty')}</p>
      ) : (
        <div className={adminStyles.tableScroll}>
          <table className={`${adminStyles.table} ${styles.table}`}>
            <thead>
              <tr>
                <th>{t('admin.contests.col.title')}</th>
                <th>{t('admin.contests.col.status')}</th>
                <th>{t('admin.contests.col.deadlines')}</th>
                <th>{t('admin.contests.col.closed')}</th>
                <th className={styles.num}>{t('admin.contests.col.interest')}</th>
                <th>{t('admin.contests.col.poster')}</th>
                <th>{t('admin.contests.col.links')}</th>
                <th>{t('admin.contests.col.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const rowBusy = busyId === row.id
                return (
                  <tr key={row.id}>
                    <td>
                      <div className={styles.titleCell}>
                        <span className={styles.titleText}>{row.title}</span>
                        <span className={adminStyles.muted}>{row.organizer}</span>
                        {rowErrors[row.id] && (
                          <p className={adminStyles.errorText} role="alert">{rowErrors[row.id]}</p>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`${adminStyles.badge} ${STATUS_BADGE[row.status] || ''}`}>
                        {t(`admin.contests.status.${row.status}`)}
                      </span>
                    </td>
                    <td>
                      <div className={styles.dateCell}>
                        <span>
                          <span className={styles.dateLabel}>{t('admin.contests.submission')} </span>
                          {formatKstDateTime(row.submission_deadline, language) || '-'}
                        </span>
                        <span>
                          <span className={styles.dateLabel}>{t('admin.contests.apply')} </span>
                          {formatKstDateTime(row.apply_deadline, language) || '-'}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className={`${adminStyles.badge} ${row.is_closed ? adminStyles.bad : ''}`}>
                        {row.is_closed ? t('admin.contests.closed') : t('admin.contests.open')}
                      </span>
                    </td>
                    <td className={styles.num}>{row.interest_count ?? 0}</td>
                    <td>
                      {row.poster_url
                        ? <span className={`${adminStyles.badge} ${adminStyles.ok}`}>{t('admin.contests.posterSet')}</span>
                        : <span className={styles.dim}>{t('admin.contests.posterNone')}</span>}
                    </td>
                    <td>
                      <div className={styles.linkCol}>
                        <ExternalLink href={row.source_url} label={t('admin.contests.sourceLink')} />
                        <ExternalLink href={row.listing_url} label={t('admin.contests.listingLink')} />
                        {!safeHttpUrl(row.source_url) && !safeHttpUrl(row.listing_url) && <span className={styles.dim}>-</span>}
                      </div>
                    </td>
                    <td>
                      <div className={styles.rowActions}>
                        {CONTEST_STATUSES.filter(s => s !== row.status).map(s => (
                          <button
                            key={s}
                            type="button"
                            className={`${adminStyles.btn} ${adminStyles.btnSmall}`}
                            disabled={busyId != null}
                            onClick={() => changeStatus(row, s)}
                            aria-label={t('admin.contests.setStatusAria', { title: row.title, status: t(`admin.contests.status.${s}`) })}
                          >
                            {rowBusy ? t('admin.contests.working') : t(`admin.contests.action.${s}`)}
                          </button>
                        ))}
                        <button
                          type="button"
                          className={`${adminStyles.btn} ${adminStyles.btnSmall}`}
                          disabled={busyId != null}
                          onClick={() => setFormTarget(row)}
                          aria-label={t('admin.contests.editAria', { title: row.title })}
                        >
                          {t('admin.contests.edit')}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {count > PAGE_SIZE && (
        <div className={adminStyles.pager}>
          <button type="button" className={adminStyles.btn} disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            {t('admin.audit.prev')}
          </button>
          <span className={adminStyles.muted}>{t('admin.audit.pageOf', { page, pages, count })}</span>
          <button type="button" className={adminStyles.btn} disabled={page >= pages} onClick={() => setPage(p => Math.min(pages, p + 1))}>
            {t('admin.audit.next')}
          </button>
        </div>
      )}

    </SectionCard>
    {formTarget && (
      <ContestFormModal
        key={formTarget === 'new' ? 'new' : formTarget.id}
        contest={formTarget === 'new' ? null : formTarget}
        onClose={() => setFormTarget(null)}
        onSaved={afterSave}
        onChanged={reload}
      />
    )}
    </>
  )
}
