/**
 * useVisualViewportSheetStyle — keeps a bottom sheet above the mobile
 * keyboard (FULL-MESSAGING-1).
 *
 * The body is viewport-locked (overflow hidden) and the Modal backdrop is
 * `position: fixed`, so on iOS/Android the on-screen keyboard covers the
 * sheet's input unless the sheet is sized against `window.visualViewport`.
 * Returns CSS custom properties for Modal's `panelStyle`:
 *   --modal-kb-inset  gap between the layout-viewport bottom and the keyboard
 *   --modal-max-h     sheet height cap (85% of the visual viewport, or nearly
 *                     all of it while the keyboard is up)
 * Modal.module.css only consumes them inside the <=768px bottom-sheet rules,
 * so the centered desktop modal is unaffected.
 */
import { useEffect, useState } from 'react'

const KEYBOARD_THRESHOLD = 100

function measure() {
  const vv = typeof window !== 'undefined' ? window.visualViewport : null
  if (!vv) return null
  const inset = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop))
  const keyboardOpen = inset > KEYBOARD_THRESHOLD
  const maxH = Math.round(keyboardOpen ? vv.height - 8 : vv.height * 0.85)
  return { inset, maxH }
}

export function useVisualViewportSheetStyle() {
  const [m, setM] = useState(measure)

  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return undefined
    const update = () => setM(measure())
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    return () => {
      vv.removeEventListener('resize', update)
      vv.removeEventListener('scroll', update)
    }
  }, [])

  if (!m) return undefined
  return {
    '--modal-kb-inset': `${m.inset}px`,
    '--modal-max-h': `${m.maxH}px`,
  }
}
