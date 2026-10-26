import { useEffect, useRef } from 'react'
import { Navigate } from 'react-router-dom'
import { isOnboardingPending } from '../utils/onboardingFlag.js'

/*
 * NotFoundRedirect — catch-all route. Signed-in users get a one-shot toast and
 * land on /discovery. Signed-out (or onboarding-pending) users keep the old
 * behavior: Navigate to "/", where ProtectedRoute sends them to /login or
 * /onboarding — no toast.
 */
export default function NotFoundRedirect({ userId, showToast, message }) {
  const firedRef = useRef(false)
  const signedIn = Boolean(userId) && !isOnboardingPending()

  useEffect(() => {
    if (!signedIn || firedRef.current) return
    firedRef.current = true // survives StrictMode's mount/unmount/mount
    showToast?.({ message, type: 'info' })
  }, [signedIn, showToast, message])

  return <Navigate to={signedIn ? '/discovery' : '/'} replace />
}
