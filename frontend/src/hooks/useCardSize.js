import { useSyncExternalStore } from 'react'

/**
 * Reactive swipe-card size. Same formula the app always used:
 *   width  = min(420, vw - 32)
 *   height = min(round(width * 1.55), vh - 220)
 * but recomputed on resize / orientationchange / visualViewport resize instead
 * of frozen at module import. One module-level store shared by every consumer.
 */

// Height-only changes smaller than this are ignored on touch devices: mobile
// browsers collapse/expand the address bar (~50-80px) while the user scrolls or
// drags, and resizing the card mid-swipe would make it jump under the finger.
// Real changes (rotation, devtools emulation, split-screen) change width or
// move height by far more, so they still apply.
const TOUCH_HEIGHT_JITTER_PX = 80

const isBrowser = typeof window !== 'undefined'
const isTouch = () =>
  isBrowser && (('ontouchstart' in window) || (navigator.maxTouchPoints || 0) > 0)

export function computeCardSize(vw, vh) {
  const width = Math.min(420, vw - 32)
  const height = Math.min(Math.round(width * 1.55), vh - 220)
  return { width, height }
}

let appliedVw = isBrowser ? window.innerWidth : 375
let appliedVh = isBrowser ? window.innerHeight : 812
let current = computeCardSize(appliedVw, appliedVh)
const listeners = new Set()
let rafId = 0

function readViewport() {
  // innerWidth/innerHeight match the original formula; visualViewport only
  // serves as an extra trigger (it is affected by pinch-zoom/keyboard, so its
  // values are not used).
  return { vw: window.innerWidth, vh: window.innerHeight }
}

function update() {
  rafId = 0
  const { vw, vh } = readViewport()
  if (vw === appliedVw && vh === appliedVh) return
  if (vw === appliedVw && isTouch() && Math.abs(vh - appliedVh) < TOUCH_HEIGHT_JITTER_PX) return
  appliedVw = vw
  appliedVh = vh
  const next = computeCardSize(vw, vh)
  if (next.width === current.width && next.height === current.height) return
  current = next
  listeners.forEach((l) => l())
}

function schedule() {
  if (rafId) return
  rafId = requestAnimationFrame(update)
}

let attached = false
function attach() {
  if (attached || !isBrowser) return
  attached = true
  window.addEventListener('resize', schedule)
  window.addEventListener('orientationchange', schedule)
  window.visualViewport?.addEventListener('resize', schedule)
}
function detach() {
  if (!attached) return
  attached = false
  window.removeEventListener('resize', schedule)
  window.removeEventListener('orientationchange', schedule)
  window.visualViewport?.removeEventListener('resize', schedule)
  if (rafId) { cancelAnimationFrame(rafId); rafId = 0 }
}

function subscribe(listener) {
  listeners.add(listener)
  attach()
  // Viewport may have changed between module load and first subscription.
  schedule()
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) detach()
  }
}

const getSnapshot = () => current

/** Returns a referentially stable `{ width, height }` that updates on viewport change. */
export function useCardSize() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}
