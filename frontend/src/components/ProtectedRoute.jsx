import { Navigate } from 'react-router-dom'
import { isOnboardingPending } from '../utils/onboardingFlag.js'

export default function ProtectedRoute({ userId, children }) {
  if (!userId) return <Navigate to="/login" replace />
  // Social login users who have not finished onboarding (e.g. reloaded mid-flow).
  if (isOnboardingPending()) return <Navigate to="/onboarding" replace />
  return children
}
