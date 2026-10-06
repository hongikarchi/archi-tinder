/**
 * ServicesSection — ADMIN-DASH-2a external service cards (status / account memo /
 * usage / dashboard link). Loads independently via useAdminSection; the refresh
 * button re-fetches with ?refresh=1 and replaces the local copy. Note edits patch
 * only the edited card locally (server merges notes post-cache).
 */
import { useState } from 'react'
import { getAdminServices, updateProviderNote } from '../../api/admin.js'
import { useTranslation } from '../../i18n/index.js'
import SectionCard from './SectionCard.jsx'
import { useAdminSection } from './useAdminSection.js'
import styles from './AdminPage.module.css'

const NOTE_MAX = 200

const INDICATOR_CLASS = {
  none: styles.ok,
  minor: styles.warn,
  major: styles.bad,
  critical: styles.bad,
}

const isHttps = url => typeof url === 'string' && url.startsWith('https://')

function fmtValue(value, language) {
  if (typeof value === 'number') return value.toLocaleString(language === 'ko' ? 'ko-KR' : 'en-US')
  return value == null ? '-' : String(value)
}

function fmtCost(cost, language) {
  const amount = Number(cost.amount)
  if (!Number.isFinite(amount)) return '-'
  const locale = language === 'ko' ? 'ko-KR' : 'en-US'
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency: cost.currency || 'USD' }).format(amount)
  } catch {
    return `${amount.toLocaleString(locale)} ${cost.currency || ''}`.trim()
  }
}

function Usage({ usage, language }) {
  const { t } = useTranslation()
  if (!usage) return null
  if (usage.configured === false) {
    return <p className={styles.muted}>{t('admin.services.notConfigured')}</p>
  }
  const items = Array.isArray(usage.items) ? usage.items : []
  return (
    <div className={styles.svcRow}>
      <span className={styles.svcRowLabel}>{t('admin.services.usage')}</span>
      {items.map((item, i) => (
        <div key={`${item.label}-${i}`} className={styles.usageRow}>
          <span>{item.label}</span>
          <span className={styles.usageValue}>
            {fmtValue(item.value, language)}{item.unit ? ` ${item.unit}` : ''}
          </span>
        </div>
      ))}
      {usage.cost && (
        <div className={styles.usageRow}>
          <span>
            {t('admin.services.cost')}
            {usage.cost.estimated && <> <span className={styles.badge}>{t('admin.services.estimated')}</span></>}
          </span>
          <span className={styles.usageValue}>{fmtCost(usage.cost, language)}</span>
        </div>
      )}
      {usage.error && <p className={styles.muted}>{t('admin.services.usageError', { error: usage.error })}</p>}
    </div>
  )
}

function ServiceCard({ service, note, onNoteSaved, language }) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  const status = service.status || {}
  const indicator = INDICATOR_CLASS[status.indicator] ? status.indicator : 'unknown'
  const auto = service.account?.auto

  const startEdit = () => {
    setDraft(note)
    setSaveError(false)
    setEditing(true)
  }

  const save = async () => {
    setSaving(true)
    setSaveError(false)
    try {
      const res = await updateProviderNote(service.slug, draft.trim())
      onNoteSaved(service.slug, typeof res?.login_note === 'string' ? res.login_note : draft.trim())
      setEditing(false)
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className={styles.svcCard}>
      <div className={styles.svcHead}>
        <h3 className={styles.svcName}>{service.name}</h3>
        <span
          className={`${styles.badge} ${INDICATOR_CLASS[indicator] || ''}`}
          title={status.description || undefined}
        >
          {t(`admin.services.status.${indicator}`)}
        </span>
      </div>
      {status.description && <p className={styles.muted}>{status.description}</p>}

      <div className={styles.svcRow}>
        <span className={styles.svcRowLabel}>{t('admin.services.account')}</span>
        {auto && <span className={styles.mono}>{auto}</span>}
        {!editing && (
          <span style={note ? undefined : { color: 'var(--color-text-dim)' }}>
            {note || t('admin.services.noNote')}
          </span>
        )}
      </div>

      {editing ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <textarea
            className={styles.textarea}
            value={draft}
            maxLength={NOTE_MAX}
            disabled={saving}
            onChange={e => setDraft(e.target.value)}
            aria-label={t('admin.services.noteLabel', { name: service.name })}
          />
          <div className={styles.actionRow}>
            <span className={styles.muted}>{draft.length}/{NOTE_MAX}</span>
            <span style={{ flex: 1 }} />
            <button type="button" className={`${styles.btn} ${styles.btnSmall}`} disabled={saving} onClick={() => setEditing(false)}>
              {t('admin.services.cancel')}
            </button>
            <button type="button" className={`${styles.btn} ${styles.btnSmall}`} disabled={saving} onClick={save}>
              {saving ? t('admin.services.saving') : t('admin.services.save')}
            </button>
          </div>
          {saveError && <p className={styles.errorText} role="alert">{t('admin.services.saveError')}</p>}
        </div>
      ) : (
        <div className={styles.actionRow}>
          <button type="button" className={`${styles.btn} ${styles.btnSmall}`} onClick={startEdit}>
            {t('admin.services.editNote')}
          </button>
        </div>
      )}

      <Usage usage={service.usage} language={language} />

      {isHttps(service.dashboard_url) && (
        <div className={styles.svcFooter}>
          <a
            className={styles.badge}
            href={service.dashboard_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${service.name} - ${t('admin.services.openDashboard')}`}
          >
            {t('admin.services.openDashboard')} ↗
          </a>
        </div>
      )}
    </article>
  )
}

export default function ServicesSection() {
  const { t, language } = useTranslation()
  const section = useAdminSection(getAdminServices)
  const { loading, error, reload } = section
  // Refreshed payload (replaces the initial one) + per-slug saved notes.
  const [refreshed, setRefreshed] = useState(null)
  const [noteOverrides, setNoteOverrides] = useState({})
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(false)

  const data = refreshed || section.data
  const services = Array.isArray(data?.services) ? data.services : []

  const refresh = async () => {
    setRefreshing(true)
    setRefreshError(false)
    try {
      const res = await getAdminServices({ refresh: true })
      setRefreshed(res)
      setNoteOverrides({})
    } catch {
      setRefreshError(true)
    } finally {
      setRefreshing(false)
    }
  }

  const onNoteSaved = (slug, loginNote) => setNoteOverrides(prev => ({ ...prev, [slug]: loginNote }))

  const fmtTime = iso => {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return null
    return d.toLocaleString(language === 'ko' ? 'ko-KR' : 'en-US', {
      month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  }
  const fetchedAt = data?.fetched_at ? fmtTime(data.fetched_at) : null

  const right = (
    <div className={styles.actionRow}>
      {fetchedAt && <span className={styles.muted}>{t('admin.services.fetchedAt', { time: fetchedAt })}</span>}
      <button type="button" className={`${styles.btn} ${styles.btnSmall}`} disabled={refreshing} onClick={refresh}>
        {refreshing ? t('admin.services.refreshing') : t('admin.services.refresh')}
      </button>
    </div>
  )

  return (
    <SectionCard
      title={t('admin.services.title')}
      loading={loading}
      error={error}
      onRetry={reload}
      right={right}
      skeletonRows={4}
    >
      {refreshError && <p className={styles.errorText} role="alert">{t('admin.services.refreshError')}</p>}
      {services.length === 0 ? (
        <p className={styles.muted}>{t('admin.services.empty')}</p>
      ) : (
        <div className={styles.svcGrid}>
          {services.map(service => (
            <ServiceCard
              key={service.slug}
              service={service}
              note={noteOverrides[service.slug] ?? service.account?.note ?? ''}
              onNoteSaved={onNoteSaved}
              language={language}
            />
          ))}
        </div>
      )}
    </SectionCard>
  )
}
