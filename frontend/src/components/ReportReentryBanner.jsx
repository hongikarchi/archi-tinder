import { useTranslation } from '../i18n/index.js'
import { useReportImageJob } from '../hooks/useReportImageJob.js'
import { localizeReport } from '../utils/reportText.js'
import { safeImageMime } from '../utils/imageMime.js'
import s from './ReportReentryBanner.module.css'

/*
 * ReportReentryBanner — Taste-tab card shown when a finished, unsaved report
 * exists (FULL-REPORT-UI-1 WP4). Positioning (fixed under the logo) is owned
 * by the caller; this renders the card only.
 * Thumbnail = the persona image from the shared job store when present,
 * otherwise a neutral gradient.
 */
export default function ReportReentryBanner({ project, onSave, onDelete }) {
  const { t, language } = useTranslation()
  const job = useReportImageJob(project?.backendId)
  const name = localizeReport(project?.finalReport || {}, language)?.persona_type || ''
  const src = job.image ? `data:${safeImageMime(job.mime)};base64,${job.image}` : null

  return (
    <div className={s.card}>
      <div className={s.top}>
        <div className={s.thumb} aria-hidden="true">
          {src && <img className={s.thumbImg} src={src} alt="" />}
        </div>
        <div className={s.text}>
          <p className={s.title}>{t('modalB3.reportBanner.body')}</p>
          <p className={s.sub}>{t('modalB3.reportBanner.sub', { name })}</p>
        </div>
      </div>
      <div className={s.actions}>
        <button type="button" className={s.del} onClick={onDelete}>
          {t('modalB3.reportBanner.delete')}
        </button>
        <button type="button" className={s.save} onClick={onSave}>
          {t('results.saveAndProfile')}
        </button>
      </div>
    </div>
  )
}
