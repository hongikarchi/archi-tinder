// sessionStorage flag: set at login when the backend says the user still has to
// complete onboarding; ProtectedRoute redirects to /onboarding while it is set.
export const ONBOARDING_FLAG_KEY = 'archithon_onboarding_required'

export function isOnboardingPending() {
  return sessionStorage.getItem(ONBOARDING_FLAG_KEY) === '1'
}
