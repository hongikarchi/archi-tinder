import s from './FinishReportButton.module.css'

/*
 * FinishReportButton — "Finish & View Report →" CTA (FULL-REPORT-UI-1 WP4).
 * Fixed just above the floating TabBar capsule; width/side margins come from
 * the shared `--tabbar-max-width` token (DESIGN §11 E9). Gating (disabled /
 * loading) is decided by the caller exactly as before.
 */
export default function FinishReportButton({ onClick, disabled, loading }) {
  return (
    <div className={s.wrap}>
      <button type="button" className={s.btn} onClick={onClick} disabled={disabled}>
        {loading ? 'Preparing report...' : 'Finish & View Report →'}
      </button>
    </div>
  )
}
