/**
 * ContestFormModal — create / edit one contest (FULL-CONTEST-2).
 *
 * Deadlines are KST wall-clock values: the stored ISO instant is converted to a
 * datetime-local string with fixed +09:00 math, and submitted back with an
 * explicit '+09:00' offset (utils/contestDeadline.js), never the device zone.
 * Server 400s ({field: [msg]}) are shown next to their fields; the publish rule
 * surfaces on source_url. Edit sends only the changed fields.
 */
import { useMemo, useState } from 'react'
import { updateAdminContest, createAdminContest } from '../../api/admin.js'
import { useTranslation } from '../../i18n/index.js'
import Modal from '../../components/Modal.jsx'
import { isoToKstInputValue, kstInputValueToIso } from '../../utils/contestDeadline.js'
import { safeHttpUrl } from '../../utils/safeUrl.js'
import { flattenApiErrors, fieldErrorMap } from './contestErrors.js'
import { CONTEST_STATUSES, ORGANIZER_TYPES, SUMMARY_MAX } from './contestConstants.js'
import adminStyles from './AdminPage.module.css'
import styles from './ContestsSection.module.css'


// Keep the panel (which scrolls internally) clear of the fixed TabBar / safe area.
const MODAL_PANEL_STYLE = { '--modal-max-h': 'calc(100dvh - 24px)', maxHeight: 'calc(100dvh - 40px)' }

const TEXT_FIELDS = [
  'title', 'organizer', 'theme', 'summary', 'eligibility', 'team_size',
  'source_url', 'listing_source', 'listing_url', 'poster_url', 'poster_credit',
]

function toForm(contest) {
  const c = contest || {}
  return {
    title: c.title || '',
    organizer: c.organizer || '',
    organizer_type: c.organizer_type || 'unknown',
    status: c.status || 'hidden',
    submission_deadline: isoToKstInputValue(c.submission_deadline),
    apply_deadline: isoToKstInputValue(c.apply_deadline),
    theme: c.theme || '',
    summary: c.summary || '',
    eligibility: c.eligibility || '',
    team_size: c.team_size == null ? '' : String(c.team_size),
    source_url: c.source_url || '',
    listing_source: c.listing_source || '',
    listing_url: c.listing_url || '',
    poster_url: c.poster_url || '',
    poster_credit: c.poster_credit || '',
  }
}

/** Form string -> API value for one field. */
function toApiValue(key, value) {
  if (key === 'submission_deadline') return kstInputValueToIso(value) ?? value
  if (key === 'apply_deadline') return value ? (kstInputValueToIso(value) ?? value) : null
  if (key === 'team_size' || key === 'poster_url') return value.trim() === '' ? null : value.trim()
  if (TEXT_FIELDS.includes(key)) return value.trim()
  return value
}

export default function ContestFormModal({ contest, onClose, onSaved, onChanged }) {
  const { t } = useTranslation()
  const isEdit = Boolean(contest)
  // `base` is the last-known server row (updated when the poster is cleared).
  const [base, setBase] = useState(contest)
  const initial = useMemo(() => toForm(base), [base])
  const [form, setForm] = useState(() => toForm(contest))
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [badPoster, setBadPoster] = useState('')

  const busy = saving || clearing
  const set = key => e => setForm(prev => ({ ...prev, [key]: e.target.value }))
  const posterSrc = safeHttpUrl(form.poster_url)
  const hasStoredPoster = isEdit && Boolean(base?.poster_url)

  const applyServerError = err => {
    const data = err?.data
    if (err?.status === 400 && data && typeof data === 'object') {
      const { byField, general } = fieldErrorMap(data)
      // Errors on keys with no form field (e.g. a stray server-side field) still surface.
      const stray = Object.entries(byField).filter(([k]) => !(k in form)).map(([, m]) => m)
      setErrors(byField)
      setFormError([...general, ...stray].join(' '))
    } else {
      setErrors({})
      setFormError(t('admin.contests.form.saveError'))
    }
  }

  const submit = async e => {
    e.preventDefault()
    if (busy) return
    const missing = {}
    for (const key of ['title', 'organizer', 'submission_deadline']) {
      if (!form[key].trim()) missing[key] = t('admin.contests.form.required')
    }
    if (form.submission_deadline.trim() && !kstInputValueToIso(form.submission_deadline)) {
      missing.submission_deadline = t('admin.contests.form.invalidDate')
    }
    if (form.apply_deadline.trim() && !kstInputValueToIso(form.apply_deadline)) {
      missing.apply_deadline = t('admin.contests.form.invalidDate')
    }
    if (Object.keys(missing).length > 0) {
      setErrors(missing)
      setFormError('')
      return
    }

    const payload = {}
    for (const key of Object.keys(form)) {
      if (isEdit && form[key] === initial[key]) continue
      payload[key] = toApiValue(key, form[key])
    }

    setSaving(true)
    setErrors({})
    setFormError('')
    try {
      if (isEdit) await updateAdminContest(contest.id, payload)
      else await createAdminContest(payload)
      onSaved()
    } catch (err) {
      applyServerError(err)
    } finally {
      setSaving(false)
    }
  }

  const clearPoster = async () => {
    if (busy || !isEdit) return
    setClearing(true)
    setErrors({})
    setFormError('')
    try {
      const row = await updateAdminContest(contest.id, { poster_url: null })
      setBase(prev => ({ ...prev, ...(row && typeof row === 'object' ? row : {}), poster_url: null }))
      setForm(prev => ({ ...prev, poster_url: '' }))
      onChanged()
    } catch (err) {
      const data = err?.data
      if (err?.status === 400 && data && typeof data === 'object') {
        setFormError(flattenApiErrors(data).join(' '))
      } else {
        setFormError(t('admin.contests.form.saveError'))
      }
    } finally {
      setClearing(false)
    }
  }

  const field = (key, label, { required = false, children, hint } = {}) => (
    <label className={styles.field}>
      <span className={styles.label}>
        {label}{required && <span className={styles.req} aria-hidden="true"> *</span>}
      </span>
      {children}
      {hint && <span className={styles.hint}>{hint}</span>}
      {errors[key] && <span className={adminStyles.errorText} role="alert">{errors[key]}</span>}
    </label>
  )

  const text = (key, label, opts = {}) => field(key, label, {
    ...opts,
    children: (
      <input
        className={`${styles.input} ${errors[key] ? styles.inputError : ''}`}
        type="text"
        value={form[key]}
        onChange={set(key)}
        disabled={busy}
        maxLength={opts.maxLength}
        inputMode={opts.inputMode}
        aria-invalid={errors[key] ? 'true' : undefined}
      />
    ),
  })

  const select = (key, label, values, labelOf) => field(key, label, {
    children: (
      <select className={styles.input} value={form[key]} onChange={set(key)} disabled={busy}>
        {values.map(v => <option key={v} value={v}>{labelOf(v)}</option>)}
      </select>
    ),
  })

  const dateTime = (key, label, required) => field(key, `${label} ${t('admin.contests.form.kstSuffix')}`, {
    required,
    children: (
      <input
        className={`${styles.input} ${errors[key] ? styles.inputError : ''}`}
        type="datetime-local"
        value={form[key]}
        onChange={set(key)}
        disabled={busy}
        aria-invalid={errors[key] ? 'true' : undefined}
      />
    ),
  })

  return (
    <Modal
      open
      portal
      zIndex={400}
      panelStyle={MODAL_PANEL_STYLE}
      width={560}
      onClose={busy ? () => {} : onClose}
      closeLabel={t('admin.contests.form.close')}
      title={isEdit ? t('admin.contests.form.editTitle') : t('admin.contests.form.createTitle')}
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        {text('title', t('admin.contests.form.title'), { required: true, maxLength: 200 })}
        <div className={styles.grid2}>
          {text('organizer', t('admin.contests.form.organizer'), { required: true, maxLength: 120 })}
          {select('organizer_type', t('admin.contests.form.organizerType'), ORGANIZER_TYPES, v => t(`admin.contests.organizerType.${v}`))}
        </div>
        {select('status', t('admin.contests.form.status'), CONTEST_STATUSES, v => t(`admin.contests.status.${v}`))}
        <div className={styles.grid2}>
          {dateTime('submission_deadline', t('admin.contests.form.submissionDeadline'), true)}
          {dateTime('apply_deadline', t('admin.contests.form.applyDeadline'), false)}
        </div>
        {text('theme', t('admin.contests.form.theme'), { maxLength: 200 })}
        {field('summary', t('admin.contests.form.summary'), {
          children: (
            <>
              <textarea
                className={`${styles.input} ${styles.area} ${errors.summary ? styles.inputError : ''}`}
                value={form.summary}
                maxLength={SUMMARY_MAX}
                onChange={set('summary')}
                disabled={busy}
              />
              <span className={styles.counter}>{form.summary.length}/{SUMMARY_MAX}</span>
            </>
          ),
        })}
        <div className={styles.grid2}>
          {text('eligibility', t('admin.contests.form.eligibility'), { maxLength: 120 })}
          {text('team_size', t('admin.contests.form.teamSize'), { maxLength: 60 })}
        </div>
        {text('source_url', t('admin.contests.form.sourceUrl'), {
          inputMode: 'url',
          hint: t('admin.contests.form.sourceUrlHint'),
        })}
        <div className={styles.grid2}>
          {text('listing_source', t('admin.contests.form.listingSource'), { maxLength: 40 })}
          {text('listing_url', t('admin.contests.form.listingUrl'), { inputMode: 'url' })}
        </div>
        <div className={styles.posterRow}>
          <div className={styles.posterFields}>
            {text('poster_url', t('admin.contests.form.posterUrl'), { inputMode: 'url' })}
            {hasStoredPoster && (
              <div>
                <button type="button" className={`${adminStyles.btn} ${adminStyles.btnSmall}`} disabled={busy} onClick={clearPoster}>
                  {clearing ? t('admin.contests.form.clearingPoster') : t('admin.contests.form.clearPoster')}
                </button>
              </div>
            )}
          </div>
          {posterSrc && badPoster !== posterSrc && (
            <img
              className={styles.thumb}
              src={posterSrc}
              alt={t('admin.contests.form.posterPreview')}
              referrerPolicy="no-referrer"
              loading="lazy"
              onError={() => setBadPoster(posterSrc)}
            />
          )}
        </div>
        {text('poster_credit', t('admin.contests.form.posterCredit'))}

        {formError && <p className={adminStyles.errorText} role="alert">{formError}</p>}
        <div className={styles.formActions}>
          <button type="button" className={adminStyles.btn} disabled={busy} onClick={onClose}>
            {t('admin.contests.form.cancel')}
          </button>
          <button type="submit" className={adminStyles.btn} disabled={busy}>
            {saving ? t('admin.contests.form.saving') : t('admin.contests.form.save')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
