import { useCallback, useRef, useSyncExternalStore } from 'react'

/**
 * Drag "lean" of a ChoiceCard ('left' | 'right' | null).
 *
 * Lives in a tiny external store instead of React state on purpose: the vendored
 * swipe lib re-runs its gesture effect whenever a callback prop changes identity
 * (onSwipe / onCardLeftScreen are re-created on every DiscoveryPage render), and
 * that resets the drag start position. A setState in DiscoveryPage mid-drag would
 * therefore kill the drag. Here the owner only holds refs (no re-render); only
 * the card subscribes.
 *
 * Usage (owner):  const lean = useCardLeanSource()
 *   <SwipeGestureFrame onSwipeRequirementFulfilled={lean.onFulfilled}
 *                      onSwipeRequirementUnfulfilled={lean.onUnfulfilled}>
 *     <ChoiceCard leanStore={lean.store} />
 * Usage (card):   const lean = useCardLean(leanStore)
 */
export function useCardLeanSource() {
  const ref = useRef(null)
  if (ref.current === null) {
    let value = null
    const listeners = new Set()
    const set = (next) => {
      if (next === value) return
      value = next
      listeners.forEach((l) => l())
    }
    ref.current = {
      store: {
        get: () => value,
        subscribe: (l) => { listeners.add(l); return () => listeners.delete(l) },
      },
      set,
    }
  }
  const { store, set } = ref.current
  // Stable identities (deps never change) — required by the swipe lib.
  const onFulfilled = useCallback((dir) => {
    set(dir === 'left' || dir === 'right' ? dir : null)
  }, [set])
  const onUnfulfilled = useCallback(() => set(null), [set])
  const reset = useCallback(() => set(null), [set])
  return { store, onFulfilled, onUnfulfilled, reset }
}

const NOOP_STORE = { get: () => null, subscribe: () => () => {} }

export function useCardLean(store) {
  const s = store || NOOP_STORE
  return useSyncExternalStore(s.subscribe, s.get, s.get)
}
