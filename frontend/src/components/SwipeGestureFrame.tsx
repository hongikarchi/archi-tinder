import { forwardRef } from 'react'
import TinderCard from '../lib/tinderCard.ts'
import type { TinderCardHandle, TinderCardProps } from '../lib/tinderCard.ts'
import {
  SWIPE_PREVENT_VERTICAL,
  SWIPE_REQUIREMENT_TYPE,
  SWIPE_THRESHOLD,
} from './swipeGestureConfig.ts'

const SwipeGestureFrame = forwardRef<TinderCardHandle, TinderCardProps>(function SwipeGestureFrame({
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
