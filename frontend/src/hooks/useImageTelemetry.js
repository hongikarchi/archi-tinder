import { useRef, useCallback, useEffect } from 'react'
import { emitImageLoadEvent } from '../api/client'

/**
 * useImageTelemetry — opt-in hook for image load telemetry.
 *
 * Emits to POST /api/v1/telemetry/image-load/ on load and error events.
 * Sample rate: 100% failures, 5% successes (avoid flooding telemetry).
 *
 * Usage:
 *   const { onLoad, onError } = useImageTelemetry({ buildingId, context, sessionId })
 *   <img onLoad={onLoad} onError={onError} ... />
 *
 * startTimeRef is reset via useEffect when buildingId changes, so load_ms is
 * measured from the moment the card/image was mounted (not from onLoadStart,
 * which has no native <img> equivalent).
 */
const SUCCESS_SAMPLE_RATE = 0.05

export function useImageTelemetry({ buildingId, context, sessionId } = {}) {
  const startTimeRef = useRef(null)

  // Reset timer whenever the image identity changes (new card shown)
  useEffect(() => {
    startTimeRef.current = performance.now()
  }, [buildingId])

  const onLoad = useCallback((event) => {
    if (Math.random() > SUCCESS_SAMPLE_RATE) return
    const url = event?.target?.src || ''
    const load_ms = startTimeRef.current != null
      ? Math.round(performance.now() - startTimeRef.current)
      : null
    emitImageLoadEvent({
      url,
      outcome: 'success',
      building_id: buildingId,
      context,
      load_ms,
      session_id: sessionId,
    })
  }, [buildingId, context, sessionId])

  const onError = useCallback((event) => {
    const url = event?.target?.src || ''
    const load_ms = startTimeRef.current != null
      ? Math.round(performance.now() - startTimeRef.current)
      : null
    emitImageLoadEvent({
      url,
      outcome: 'failure',
      building_id: buildingId,
      context,
      load_ms,
      session_id: sessionId,
    })
  }, [buildingId, context, sessionId])

  return { onLoad, onError }
}
