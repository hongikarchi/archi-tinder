/**
 * tinderCard.js — vendored fork of react-tinder-card 1.6.4 (PR #295, 2026-08-07).
 * Dependency removed from package.json; this file is now the canonical source.
 *
 * Semantic divergences from upstream:
 *   (a) handleSwipeReleased (position-mode) — swipe velocity multiplied x1.6.
 *       Fly-out travels ~1.6x the distance in a shortened duration —
 *       deliberate feel tuning (FRONT-UX-14), matches the (b) power constant
 *       change. Was x3 (bullet-fast, felt like a launch) prior to FRONT-UX-14.
 *   (b) Imperative swipe() power constant 1.3 -> 1.6 (was 3.0 prior to
 *       FRONT-UX-14 — 3.0 sent the card ~3 diagonals off-screen at constant
 *       speed; 1.6 preserves the fling feel with a shorter, decelerating exit).
 *   (c) animateOut duration clamped to Math.max(320, Math.min(diagonal /
 *       velocity, 560)) — fixes upstream's unbounded duration at near-zero
 *       release velocity AND floors it so a fast flick doesn't finish
 *       instantly (FRONT-UX-14; was an upper-bound-only cap of 500 before).
 *       Eased with easeOutCubic (fast launch, decelerating tail) instead of
 *       upstream's linear duration-mode default (FRONT-UX-14).
 *       animateBack / snap-back is untouched.
 *   (d) useWindowSize eagerly reads window.innerWidth/innerHeight as its
 *       initializer, replacing upstream's SSR guard. This app is CSR-only,
 *       and it also fixes upstream's first-render NaN-diagonal race.
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

const physics = {
  touchResponsive: { friction: 50, tension: 2000 },
  animateOut:      { friction: 30, tension: 400 },
  animateBack:     { friction: 10, tension: 200 }
}

const pythagoras = (x, y) => Math.sqrt(Math.pow(x, 2) + Math.pow(y, 2))

const normalize = (vector) => {
  const length = Math.sqrt(Math.pow(vector.x, 2) + Math.pow(vector.y, 2))
  return { x: vector.x / length, y: vector.y / length }
}

// easeOutCubic — fast launch preserving the fling feel, decelerating tail.
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3)

const animateOut = async (gesture, setSpringTarget, windowHeight, windowWidth) => {
  const diagonal = pythagoras(windowHeight, windowWidth)
  const velocity = pythagoras(gesture.x, gesture.y)
  const finalX = diagonal * gesture.x
  const finalY = diagonal * gesture.y
  const finalRotation = gesture.x * 45
  const duration = Math.max(320, Math.min(diagonal / velocity, 560))

  setSpringTarget.start({
    xyrot: [finalX, finalY, finalRotation],
    config: { duration, easing: easeOutCubic }
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
    const [{ xyrot }, setSpringTarget] = useSpring(() => ({
      xyrot: [0, 0, 0],
      config: physics.touchResponsive
    }))

    settings.swipeThreshold = swipeThreshold

    React.useImperativeHandle(ref, () => ({
      async swipe(dir = 'right') {
        if (onSwipe) onSwipe(dir)
        const power = 1.6
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
              : (() => { const n = normalize({ x: gesture.dx, y: gesture.dy }); return { x: n.x * 1.6, y: n.y * 1.6 } })()
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
      const vx = -(dx - lastPosition.dx) / (lastPosition.timeStamp - Date.now())
      const vy = -(dy - lastPosition.dy) / (lastPosition.timeStamp - Date.now())
      return { dx, dy, vx, vy, timeStamp: Date.now() }
    }

    const element = React.useRef()

    React.useLayoutEffect(() => {
      let startPositon = { x: 0, y: 0 }
      let lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: Date.now() }
      let isClicking = false

      const onTouchStart = (ev) => {
        if (!ev.srcElement.className.includes('pressable') && ev.cancelable) ev.preventDefault()
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
        let rot = gestureState.vx * 15
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
        lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: Date.now() }
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
        lastPosition = { dx: 0, dy: 0, vx: 0, vy: 0, timeStamp: Date.now() }
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
        transform: xyrot.to((x, y, rot) => `translate3d(${x}px, ${y}px, 0px) rotate(${rot}deg)`)
      },
      children
    })
  }
)

export default TinderCard
