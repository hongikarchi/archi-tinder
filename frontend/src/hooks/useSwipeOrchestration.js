import { useRef } from 'react'

/**
 * useSwipeOrchestration — shared swipe action state for tinder-style card pages.
 *
 * Manages the two-phase swipe lifecycle:
 *   1. onTinderSwipe(dir)  — fired by SwipeGestureFrame when the drag direction
 *      is decided. Sets pendingActionRef, or lets the caller intercept via
 *      onBeforeSwipe.
 *   2. onCardLeftScreen()  — fired by SwipeGestureFrame when the card is gone.
 *      Reads + clears pendingActionRef, then calls onCommit(action).
 *
 * Parameters:
 *   likeAction     — action string for right swipe  (default 'like')
 *   dismissAction  — action string for left swipe   (default 'dislike')
 *   onBeforeSwipe  — optional (dir) => boolean. Return true to intercept
 *                    (pendingActionRef is NOT set; the caller handles the swipe
 *                    itself — e.g. show a confirmation dialog).
 *   onCommit       — (action) => void. Called when the card leaves the screen
 *                    with a non-null action.
 *
 * Returns:
 *   pendingActionRef   — the ref holding the in-flight action string
 *   onTinderSwipe(dir) — pass to SwipeGestureFrame's onSwipe prop
 *   onCardLeftScreen() — pass to SwipeGestureFrame's onCardLeftScreen prop
 */
export function useSwipeOrchestration({
  likeAction = 'like',
  dismissAction = 'dislike',
  onBeforeSwipe,
  onCommit,
} = {}) {
  const pendingActionRef = useRef(null)

  function onTinderSwipe(dir) {
    if (onBeforeSwipe) {
      const intercepted = onBeforeSwipe(dir)
      if (intercepted) return
    }
    pendingActionRef.current = dir === 'right' ? likeAction : dismissAction
  }

  function onCardLeftScreen() {
    const action = pendingActionRef.current
    pendingActionRef.current = null
    if (action && onCommit) {
      onCommit(action)
    }
  }

  return { pendingActionRef, onTinderSwipe, onCardLeftScreen }
}
