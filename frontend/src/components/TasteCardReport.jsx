import { useState } from 'react'
import { tagKey } from '../utils/tasteStart.js'
import fb from './TasteFeedback.module.css'

const REASONS = [
  ['tag', 'tasteReasonTag'],
  ['photo', 'tasteReasonPhoto'],
  ['info', 'tasteReasonInfo'],
  ['etc', 'tasteReasonEtc'],
]
const SUBS = {
  photo: [
    ['other_building', 'tasteSubOtherBuilding'],
    ['drawing_or_logo', 'tasteSubDrawingOrLogo'],
    ['not_visible', 'tasteSubNotVisible'],
  ],
  info: [
    ['country', 'tasteSubCountry'],
    ['city', 'tasteSubCity'],
    ['year', 'tasteSubYear'],
    ['use', 'tasteSubUse'],
    ['unbuilt', 'tasteSubUnbuilt'],
    ['duplicate', 'tasteSubDuplicate'],
  ],
}

export function ReportIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
      <line x1="12" y1="6" x2="12" y2="13.5" />
      <line x1="12" y1="18" x2="12.01" y2="18" />
    </svg>
  )
}

/**
 * In-card report panel (anchored to the card bottom, over the dark veil).
 * `prev` = previously sent form ({reason, sub, tags, text}) or null.
 * `onSubmit(form)` / `onCancelReport()` return a promise<boolean> (true = done).
 */
export default function TasteCardReport({ chips, prev, onSubmit, onCancelReport, onClose, t, tagLabel }) {
  const [reason, setReason] = useState(prev?.reason || null)
  const [sub, setSub] = useState(() => prev?.sub || [])
  const [tagKeys, setTagKeys] = useState(() => (prev?.tags || []).map(tagKey))
  const [text, setText] = useState(prev?.text || '')
  const [sending, setSending] = useState(false)
  const reported = !!prev

  const toggle = (list, setList, v) => setList(list.includes(v) ? list.filter(x => x !== v) : [...list, v])
  const canSend = (!!reason || text.trim().length > 0) && !sending

  async function run(fn) {
    setSending(true)
    try { await fn() } finally { setSending(false) }
  }
  function send() {
    const form = {
      reason,
      sub: reason === 'photo' || reason === 'info' ? sub.filter(s => SUBS[reason].some(([code]) => code === s)) : [],
      tags: reason === 'tag'
        ? chips.filter(({ tag }) => tagKeys.includes(tagKey(tag))).map(({ tag }) => ({ axis: tag.axis, value: tag.value }))
        : [],
      text: text.trim(),
    }
    return run(() => onSubmit(form))
  }

  return (
    <div className={fb.panelIn} data-nodrag="">
      <h4 className={fb.panelTitle}>{t('search.tasteReportTitle')}</h4>
      <div className={fb.rtg}>
        {REASONS.map(([code, key]) => (
          <button
            key={code} type="button"
            className={`${fb.tgc} ${reason === code ? fb.tgcSel : ''}`}
            aria-pressed={reason === code}
            onClick={() => setReason(reason === code ? null : code)}
          >{t(`search.${key}`)}</button>
        ))}
      </div>

      {reason === 'tag' && (
        <div className={fb.sub2}>
          <div className={fb.subHint}>{t('search.tasteReportTagHint')}</div>
          <div className={fb.rtg}>
            {chips.map(({ tag, matched }) => {
              const k = tagKey(tag)
              const on = tagKeys.includes(k)
              return (
                <button
                  key={k} type="button" aria-pressed={on}
                  className={`${fb.tgc} ${on ? fb.tgcBad : ''}`}
                  onClick={() => toggle(tagKeys, setTagKeys, k)}
                >{matched ? '✓' : '✕'} {tagLabel(tag)}</button>
              )
            })}
          </div>
        </div>
      )}
      {SUBS[reason] && (
        <div className={fb.sub2}>
          <div className={fb.rtg}>
            {SUBS[reason].map(([code, key]) => (
              <button
                key={code} type="button" aria-pressed={sub.includes(code)}
                className={`${fb.tgc} ${sub.includes(code) ? fb.tgcBad : ''}`}
                onClick={() => toggle(sub, setSub, code)}
              >{t(`search.${key}`)}</button>
            ))}
          </div>
        </div>
      )}

      <div className={fb.pr2}>
        <input
          className={fb.pr2Input} value={text} maxLength={500}
          placeholder={t('search.tasteReportComment')}
          onChange={e => setText(e.target.value)}
        />
        {reported ? (
          <button type="button" className={`${fb.pr2Btn} ${fb.btnDel}`} disabled={sending} onClick={() => run(onCancelReport)}>
            {t('search.tasteReportCancel')}
          </button>
        ) : (
          <button type="button" className={`${fb.pr2Btn} ${fb.btnNo}`} onClick={onClose}>
            {t('search.tasteReportClose')}
          </button>
        )}
        <button type="button" className={`${fb.pr2Btn} ${fb.btnYes}`} disabled={!canSend} onClick={send}>
          {reported ? t('search.tasteReportEdit') : t('search.tasteReportSubmit')}
        </button>
      </div>
    </div>
  )
}
