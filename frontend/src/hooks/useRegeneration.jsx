import { useCallback, useEffect, useRef, useState } from 'react'
import { useReportImageJob, reportImageJobs } from './useReportImageJob.js'
import { generateReport } from '../api/projects.js'
import { isLegacyAxisScores } from '../utils/axisScores.js'
import { useTranslation } from '../i18n/index.js'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import Toast from '../components/Toast.jsx'

const TOAST_MS = 2000

/**
 * useRegeneration — owner-only persona IMAGE + REPORT regeneration (FULL-REPORT-UI-1 WP2).
 * Reusable on every screen that shows the persona image/report (report page,
 * result cards, post-save landing).
 *
 *   const regen = useRegeneration({ projectId, enabled: isOwner, axisScores, onReportRegenerated })
 *   <PersonaReportPage {...regen.imageProps} {...regen.reportProps} />   // or spread only imageProps
 *   {regen.overlay}                                                      // confirm dialog + toast
 *
 * Options
 *   projectId             project UUID
 *   enabled               owner gate. false -> no handlers are returned (controls stay hidden)
 *                         and nothing can POST; viewers must pass false.
 *   axisScores            current axis_scores (selects the legacy confirm copy)
 *   onReportRegenerated   ({ final_report, axis_scores }) => void, called on report success
 *                         (parent replaces its state; scroll position is untouched)
 *   withReport            default true; pass false on screens that only show the image
 *                         (reportProps handlers are then omitted)
 *
 * Returns
 *   imageProps  { onRegenerateImage, imageRegenerating, imageRegenFailed }
 *               (state comes from the shared reportImageJobs store, so every screen
 *               showing the same project agrees)
 *   reportProps { onRegenerateReport, regenerating, regenMessage }
 *   overlay     React node: the confirm dialog + toast; render once anywhere in the screen
 *   showToast   (text) => void  one at a time, 2 s
 */
export function useRegeneration({ projectId, enabled = false, axisScores = null, onReportRegenerated, withReport = true }) {
  const { t } = useTranslation()
  const job = useReportImageJob(projectId)
  const [confirm, setConfirm] = useState(null)       // null | 'image' | 'report'
  const [toast, setToast] = useState(null)
  const [reportBusy, setReportBusy] = useState(false)
  const [reportFailed, setReportFailed] = useState(false)
  const timerRef = useRef(null)
  const aliveRef = useRef(true)
  const busyRef = useRef(false)
  const onDoneRef = useRef(onReportRegenerated)
  useEffect(() => { onDoneRef.current = onReportRegenerated })
  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false; clearTimeout(timerRef.current) }
  }, [])

  const showToast = useCallback(text => {
    setToast({ text, key: Date.now() })
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setToast(null), TOAST_MS)
  }, [])

  const imageBusy = !!job.regen || job.status === 'generating'

  const onRegenerateImage = useCallback(() => {
    if (imageBusy) showToast(t('persona.imgRegenBusy'))
    else setConfirm('image')
  }, [imageBusy, showToast, t])

  const onRegenerateReport = useCallback(() => {
    if (!busyRef.current) setConfirm('report')
  }, [])

  const cancel = useCallback(() => setConfirm(null), [])

  const confirmImage = useCallback(() => {
    setConfirm(null)
    if (!enabled || !projectId) return
    reportImageJobs.regenerate(projectId)
  }, [enabled, projectId])

  const confirmReport = useCallback(async () => {
    setConfirm(null)
    if (!enabled || !projectId || busyRef.current) return
    busyRef.current = true
    setReportBusy(true)
    setReportFailed(false)
    try {
      const data = await generateReport(projectId, { regenerate: true })
      if (!data?.final_report) throw new Error('empty report')
      if (!aliveRef.current) return
      onDoneRef.current?.(data)
      showToast(t('persona.reportRegenDone'))
    } catch (err) {
      console.error('[useRegeneration] generateReport failed:', err)
      if (aliveRef.current) setReportFailed(true)
    } finally {
      busyRef.current = false
      if (aliveRef.current) setReportBusy(false)
    }
  }, [enabled, projectId, showToast, t])

  const legacy = isLegacyAxisScores(axisScores)
  const overlay = enabled ? (
    <>
      <ConfirmDialog
        open={confirm === 'image'}
        title={t('persona.imgRegenTitle')}
        body={t('persona.imgRegenBody')}
        confirmLabel={t('persona.regenOk')}
        cancelLabel={t('persona.regenCancel')}
        onConfirm={confirmImage}
        onCancel={cancel}
      />
      {withReport && (
        <ConfirmDialog
          open={confirm === 'report'}
          title={t('persona.reportRegenTitle')}
          body={t(legacy ? 'persona.reportRegenBodyLegacy' : 'persona.reportRegenBody')}
          confirmLabel={t('persona.regenOk')}
          cancelLabel={t('persona.regenCancel')}
          onConfirm={confirmReport}
          onCancel={cancel}
        />
      )}
      <Toast message={toast} />
    </>
  ) : null

  return {
    imageProps: {
      onRegenerateImage: enabled ? onRegenerateImage : undefined,
      imageRegenerating: !!job.regen,
      imageRegenFailed: !!job.regenFailed,
    },
    reportProps: {
      onRegenerateReport: enabled && withReport ? onRegenerateReport : undefined,
      regenerating: reportBusy,
      regenMessage: reportFailed ? t('persona.regenFail') : '',
    },
    overlay,
    showToast,
  }
}
