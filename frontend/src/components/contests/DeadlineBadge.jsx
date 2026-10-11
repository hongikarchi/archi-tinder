import { useTranslation } from '../../i18n/index.js'
import { nextDeadline, ddayKst, isClosed } from '../../utils/contestDeadline.js'
import styles from './DeadlineBadge.module.css'

/**
 * DeadlineBadge — "D-5 · 신청 마감" (nearest remaining deadline, decision D9)
 * in the destructive token, or a neutral "마감" badge once the submission
 * deadline has passed. D-n is a KST calendar-date difference (utils/contestDeadline.js).
 * Shared by the list card and the detail header.
 */
export default function DeadlineBadge({ contest, now }) {
  const { t } = useTranslation()
  if (isClosed(contest, now)) {
    return <span className={`${styles.badge} ${styles.closed}`}>{t('contest.closed')}</span>
  }
  const next = nextDeadline(contest, now)
  if (!next) return null
  const dday = Math.max(0, ddayKst(next.at, now) ?? 0)
  const label = dday === 0 ? t('contest.ddayToday') : t('contest.dday', { d: dday })
  return (
    <span className={`${styles.badge} ${styles.open}`}>
      {label}
      <span className={styles.kind}> · {t(`contest.kind.${next.kind}`)}</span>
    </span>
  )
}
