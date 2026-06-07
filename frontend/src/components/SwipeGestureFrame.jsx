import { forwardRef } from 'react'
import TinderCard from 'react-tinder-card'
import {
  SWIPE_PREVENT_VERTICAL,
  SWIPE_REQUIREMENT_TYPE,
  SWIPE_THRESHOLD,
} from './swipeGestureConfig.js'

const SwipeGestureFrame = forwardRef(function SwipeGestureFrame({
  children,
  onSwipe,
  onCardLeftScreen,
  preventSwipe = SWIPE_PREVENT_VERTICAL,
  swipeThreshold = SWIPE_THRESHOLD,
  swipeRequirementType = SWIPE_REQUIREMENT_TYPE,
  ...props
}, ref) {
  return (
    <TinderCard
      ref={ref}
      onSwipe={onSwipe}
      onCardLeftScreen={onCardLeftScreen}
      preventSwipe={preventSwipe}
      swipeRequirementType={swipeRequirementType}
      swipeThreshold={swipeThreshold}
      {...props}
    >
      {children}
    </TinderCard>
  )
})

export default SwipeGestureFrame
