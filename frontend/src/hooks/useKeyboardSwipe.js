import { useEffect, useRef } from 'react'

const SWIPE_KEYS = { ArrowLeft: 'left', ArrowRight: 'right' }

/**
 * useKeyboardSwipe — binds ArrowLeft / ArrowRight to swipe actions.
 *
 * Parameters:
 *   onSwipe(dir)     — called with 'left' or 'right' when a key fires and the
 *                      guard passes. May be async.
 *   guardCondition() — () => boolean. Called on every keydown event. When it
 *                      returns true the event is ignored (no swipe issued).
 *
 * Internals:
 *   keySwipingRef — re-entrancy lock. Prevents queuing a second swipe while
 *   an async onSwipe is still in flight (e.g. cardRef.swipe() animation).
 *
 * Returns nothing — side-effect only hook.
 *
 * Note: both onSwipe and guardCondition are read from refs internally so that
 * callers do NOT need to wrap them in useCallback. The keydown listener is
 * registered exactly once (effect deps: []); onSwipe/guardCondition changes
 * only update the refs, they never cause the listener to re-register.
 */
export function useKeyboardSwipe({ onSwipe, guardCondition }) {
  const keySwipingRef = useRef(false)
  // Keep latest callbacks in refs so the effect's closure always reads the
  // current version without forcing an unnecessary re-registration.
  const onSwipeRef = useRef(onSwipe)
  const guardRef = useRef(guardCondition)

  useEffect(() => { onSwipeRef.current = onSwipe }, [onSwipe])
  useEffect(() => { guardRef.current = guardCondition }, [guardCondition])

  useEffect(() => {
    async function handleKeyDown(e) {
      if (guardRef.current && guardRef.current()) return
      const dir = SWIPE_KEYS[e.key]
      if (!dir) return
      if (keySwipingRef.current) return
      keySwipingRef.current = true
      try {
        await onSwipeRef.current?.(dir)
      } finally {
        keySwipingRef.current = false
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, []) // Registered once; live values read from refs above
}
