import { useTranslation } from '../i18n/index.js'
import s from './FinishReportButton.module.css'

/*
 * FinishReportButton — "Finish & View Report →" CTA (FULL-REPORT-UI-1 WP4).
 * Fixed just above the floating TabBar capsule; width/side margins come from
 * the shared `--tabbar-max-width` token (DESIGN §11 E9). Gating (disabled /
 * loading) is decided by the caller exactly as before.
 *
 * Optional `label` / `loadingLabel` override the swipe-page defaults. When
 * `loadingLabel` is given, a small spinner is shown beside it.
 */
export default function FinishReportButton({ onClick, disabled, loading, label, loadingLabel }) {
  const { t } = useTranslation()
  return (
    <div className={s.wrap}>
      <button type="button" className={s.btn} onClick={onClick} disabled={disabled}>
        {loading ? (
          <>
            {loadingLabel != null && (
              // animation inline: `spin` is a global keyframe (index.css); CSS modules would hash it.
              <span className={s.spinner} style={{ animation: 'spin 0.8s linear infinite' }} />
            )}
            {loadingLabel ?? t('swipe.finishPreparing')}
          </>
        ) : (
          label ?? t('swipe.finishCta')
        )}
      </button>
    </div>
  )
}
