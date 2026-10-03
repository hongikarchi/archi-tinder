/**
 * tinderCard.js — vendored fork of react-tinder-card 1.6.4 (PR #295, 2026-08-07).
 * Dependency removed from package.json; this file is now the canonical source.
 *
 * Semantic divergences from upstream:
 *   (a) handleSwipeReleased (position-mode) — normalize multiplier 1.6 -> 1.0
 *       (FRONT-UX-14-TUNE): at 1.6 the card was offscreen after ~35% of the
 *       animated distance, so most of the flight was invisible.
 *   (b) Imperative swipe() power constant 1.6 -> 1.0 (FRONT-UX-14-TUNE): at
 *       1.6 + easeOutCubic's front-loaded speed, the visible portion of the
 *       exit was ~10% of duration (~56ms, "bullet-fast").
 *   (c) animateOut duration clamped to Math.max(480, Math.min(diagonal /
 *       velocity, 680)) (FRONT-UX-14-TUNE, was [320,560]), eased with
 *       easeInOutCubic instead of easeOutCubic — slow start keeps the
 *       departure visible for ~35-40% of duration (~250ms) before the card
 *       accelerates off-screen. animateBack / snap-back is untouched.
 *   (d) useWindowSize eagerly reads window.innerWidth/innerHeight as its
 *       initializer, replacing upstream's SSR guard. This app is CSR-only,
 *       and it also fixes upstream's first-render NaN-diagonal race.
 *   (f) FRONT-MOBILE-FIX: drag rotation is position-based (dx / windowWidth,
 *       ~15deg at half-window drag, clamped to maxTilt) instead of
 *       instantaneous velocity x 15, which jumped frame to frame. Velocity now
 *       uses ev.timeStamp (sub-ms, dt<=0 keeps previous velocity) and only
 *       feeds release logic. touchstart preventDefault skips any target inside
 *       a `.pressable` ancestor (closest(), SVG-safe). AnimatedDiv has
 *       willChange: transform.
 *   (e) Upstream's `isClicking` closure-local state bug is inherited as-is
 *       and is now team-owned (not fixed here).
 */
import React from 'react'
import { useSpring, animated } from '@react-spring/web'
import { useWindowSize } from '../hooks/useWindowSize.js'

const settings = {
  maxTilt: 25,
  rotationPower: 50,
  swipeThreshold: 0.5
}

// Exported (2026-08-25) so callers that animate a card back INTO the deck —
// AssessmentPage's "previous question" — reuse the same snap-back spring the
// card itself uses when a drag is released below threshold, instead of
// inventing a second set of numbers.
export const physics = {
  touchResponsive: { friction: 50, tension: 2000 },
  animateOut:      { friction: 30, tension: 400 },
  animateBack:     { friction: 10, tension: 200 }
}

const pythagoras = (x, y) => Math.sqrt(Math.pow(x, 2) + Math.pow(y, 2))

const normalize = (vector) => {
  const length = Math.sqrt(Math.pow(vector.x, 2) + Math.pow(vector.y, 2))
  return { x: vector.x / length, y: vector.y / length }
}

// easeInOutCubic — slow start (departure stays visible), fast middle, slow
// settle at the end. Replaces easeOutCubic (FRONT-UX-14-TUNE): easeOutCubic's
// front-loaded speed made the card offscreen before the eye could track it.
const easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

const animateOut = async (gesture, setSpringTarget, windowHeight, windowWidth) => {
  const diagonal = pythagoras(windowHeight, windowWidth)
  const velocity = pythagoras(gesture.x, gesture.y)
  const finalX = diagonal * gesture.x
  const finalY = diagonal * gesture.y
  const finalRotation = gesture.x * 45
  const duration = Math.max(480, Math.min(diagonal / velocity, 680))

  setSpringTarget.start({
    xyrot: [finalX, finalY, finalRotation],
    config: { duration, easing: easeInOutCubic }
  })

  return await new Promise((resolve) => setTimeout(resolve, duration))
}

const animateBack = (setSpringTarget) => {
  return new Promise((resolve) => {
    setSpringTarget.start({ xyrot: [0, 0, 0], config: physics.animateBack, onRest: resolve })
  })
}

const getSwipeDirection = (property) => {
  if (Math.abs(property.x) > Math.abs(property.y)) {
    if (property.x > settings.swipeThreshold) return 'right'
    if (property.x < -settings.swipeThreshold) return 'left'
  } else {
    if (property.y > settings.swipeThreshold) return 'down'
    if (property.y < -settings.swipeThreshold) return 'up'
  }
  return 'none'
}

const AnimatedDiv = animated.div

const TinderCard = React.forwardRef(
  ({ flickOnSwipe = true, children, onSwipe, onCardLeftScreen, className, preventSwipe = [], swipeRequirementType = 'velocity', swipeThreshold = settings.swipeThreshold, onSwipeRequirementFulfilled, onSwipeRequirementUnfulfilled }, ref) => {
    const { width, height } = useWindowSize()
    // Read through a ref inside the gesture effect so a resize never re-runs
    // it mid-drag (which would reset the start position).
    const widthRef = React.useRef(width)
    widthRef.current = width
    const [{ xyrot }, setSpringTarget] = useSpring(() => ({
      xyrot: [0, 0, 0],
      config: physics.touchResponsive
    }))

    settings.swipeThreshold = swipeThreshold

    React.useImperativeHandle(ref, () => ({
      async swipe(dir = 'right') {
        if (onSwipe) onSwipe(dir)
        const power = 1.0
        const disturbance = (Math.random() - 0.5) / 2
        if (dir === 'right')      await animateOut({ x: power, y: disturbance }, setSpringTarget, width, height)
        else if (dir === 'left')  await animateOut({ x: -power, y: disturbance }, setSpringTarget, width, height)
        else if (dir === 'up')    await animateOut({ x: disturbance, y: -power }, setSpringTarget, width, height)
        else if (dir === 'down')  await animateOut({ x: disturbance, y: power }, setSpringTarget, width, height)
        if (onCardLeftScreen) onCardLeftScreen(dir)
      },
      async restoreCard() { await animateBack(setSpringTarget) }
    }))

    const handleSwipeReleased = React.useCallback(
      async (setSpringTarget, gesture) => {
        const dir = getSwipeDirection({
          x: swipeRequirementType === 'velocity' ? gesture.vx : gesture.dx,
          y: swipeRequirementType === 'velocity' ? gesture.vy : gesture.dy
        })
        if (dir !== 'none') {
          if (flickOnSwipe && !preventSwipe.includes(dir)) {
            if (onSwipe) onSwipe(dir)
            const v = swipeRequirementType === 'velocity'
              ? { x: gesture.vx, y: gesture.vy }
              : (() => { const n = normalize({ x: gesture.dx, y: gesture.dy }); return { x: n.x * 1.0, y: n.y * 1.0 } })()
            await animateOut(v, setSpringTarget, width, height)
            if (onCardLeftScreen) onCardLeftScreen(dir)
            return
          }
        }
        animateBack(setSpringTarget)
      },
      [swipeRequirementType, flickOnSwipe, preventSwipe, onSwipe, onCardLeftScreen, width, height]
    )

    let swipeThresholdFulfilledDirection = 'none'

    const gestureStateFromWebEvent = (ev, startPositon, lastPosition, isTouch) => {
      let dx = isTouch ? ev.touches[0].clientX - startPositon.x : ev.clientX - startPositon.x
      let dy = isTouch ? ev.touches[0].clientY - startPositon.y : ev.clientY - startPositon.y
      if (startPositon.x === 0 && startPositon.y === 0) { dx = 0; dy = 0 }
      const now = ev.timeStamp || performance.now()
      const dt = now - lastPosition.timeStamp
      let vx = lastPosition.vx
      let vy = lastPosition.vy
      if (dt > 0) {
        vx = (dx - lastPosition.dx) / dt
        vy = (dy - lastPosition.dy) / dt
        // Sign convention preserved from upstream: upstream computed
        // -(d)/(last - now) == d/(now - last), i.e. positive for rightward.
      }
      return { dx, dy, vx, vy, timeStamp: now }
    }

    const element = React.useRef()

    React.useLayoutEffect(() => {
      let startPositon = { x: 0, y: 0 }
      let lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: performance.now() }
      let isClicking = false

      const onTouchStart = (ev) => {
        const pressable = ev.target && ev.target.closest && ev.target.closest('.pressable')
        if (!pressable && ev.cancelable) ev.preventDefault()
        const gestureState = gestureStateFromWebEvent(ev, startPositon, lastPosition, true)
        lastPosition = gestureState
        startPositon = { x: ev.touches[0].clientX, y: ev.touches[0].clientY }
      }
      element.current.addEventListener('touchstart', onTouchStart)

      const onMouseDown = (ev) => {
        isClicking = true
        const gestureState = gestureStateFromWebEvent(ev, startPositon, lastPosition, false)
        lastPosition = gestureState
        startPositon = { x: ev.clientX, y: ev.clientY }
      }
      element.current.addEventListener('mousedown', onMouseDown)

      const handleMove = (gestureState) => {
        if (onSwipeRequirementFulfilled || onSwipeRequirementUnfulfilled) {
          const dir = getSwipeDirection({
            x: swipeRequirementType === 'velocity' ? gestureState.vx : gestureState.dx,
            y: swipeRequirementType === 'velocity' ? gestureState.vy : gestureState.dy
          })
          if (dir !== swipeThresholdFulfilledDirection) {
            swipeThresholdFulfilledDirection = dir
            if (swipeThresholdFulfilledDirection === 'none') {
              if (onSwipeRequirementUnfulfilled) onSwipeRequirementUnfulfilled()
            } else {
              if (onSwipeRequirementFulfilled) onSwipeRequirementFulfilled(dir)
            }
          }
        }
        // Position-based tilt: ~15deg when dragged half the window width.
        let rot = (gestureState.dx / (widthRef.current || 1)) * 30
        if (isNaN(rot)) rot = 0
        rot = Math.max(Math.min(rot, settings.maxTilt), -settings.maxTilt)
        setSpringTarget.start({ xyrot: [gestureState.dx, gestureState.dy, rot], config: physics.touchResponsive })
      }

      const onMouseMove = (ev) => {
        if (!isClicking) return
        const gestureState = gestureStateFromWebEvent(ev, startPositon, lastPosition, false)
        lastPosition = gestureState
        handleMove(gestureState)
      }
      window.addEventListener('mousemove', onMouseMove)

      const onMouseUp = () => {
        if (!isClicking) return
        isClicking = false
        handleSwipeReleased(setSpringTarget, lastPosition)
        startPositon = { x: 0, y: 0 }
        lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: performance.now() }
      }
      window.addEventListener('mouseup', onMouseUp)

      const onTouchMove = (ev) => {
        const gestureState = gestureStateFromWebEvent(ev, startPositon, lastPosition, true)
        lastPosition = gestureState
        handleMove(gestureState)
      }
      element.current.addEventListener('touchmove', onTouchMove)

      const onTouchEnd = () => {
        handleSwipeReleased(setSpringTarget, lastPosition)
        startPositon = { x: 0, y: 0 }
        lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: performance.now() }
      }
      element.current.addEventListener('touchend', onTouchEnd)

      return () => {
        element.current.removeEventListener('touchstart', onTouchStart)
        element.current.removeEventListener('touchmove', onTouchMove)
        element.current.removeEventListener('touchend', onTouchEnd)
        element.current.removeEventListener('mousedown', onMouseDown)
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('mouseup', onMouseUp)
      }
    }, [handleSwipeReleased, setSpringTarget, onSwipeRequirementFulfilled, onSwipeRequirementUnfulfilled])

    return React.createElement(AnimatedDiv, {
      ref: element,
      className,
      style: {
        willChange: 'transform',
        transform: xyrot.to((x, y, rot) => `translate3d(${x}px, ${y}px, 0px) rotate(${rot}deg)`)
      },
      children
    })
  }
)

export default TinderCard
