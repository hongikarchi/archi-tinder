/**
 * components/KakaoLoginButton.jsx
 * Kakao OAuth authorization-code redirect. Callback handled by
 * pages/KakaoCallbackPage.jsx. Renders nothing when VITE_KAKAO_REST_KEY is unset.
 */

import styles from './KakaoLoginButton.module.css'
import { useTranslation } from '../i18n/index.js'

export const KAKAO_STATE_KEY = 'kakao_oauth_state'

function KakaoIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24">
      <path
        fill="currentColor"
        d="M12 3C6.48 3 2 6.58 2 11c0 2.86 1.87 5.37 4.68 6.78l-.95 3.47a.4.4 0 0 0 .6.43L10.5 19.1c.49.06.99.1 1.5.1 5.52 0 10-3.58 10-8S17.52 3 12 3z"
      />
    </svg>
  )
}

export default function KakaoLoginButton({ disabled = false }) {
  const { t } = useTranslation()
  const restKey = import.meta.env.VITE_KAKAO_REST_KEY
  if (!restKey) return null

  function handleClick() {
    const state = crypto.randomUUID()
    sessionStorage.setItem(KAKAO_STATE_KEY, state)
    const params = new URLSearchParams({
      client_id: restKey,
      redirect_uri: window.location.origin + '/auth/kakao/callback',
      response_type: 'code',
      state,
    })
    window.location.assign('https://kauth.kakao.com/oauth/authorize?' + params.toString())
  }

  return (
    <button type="button" className={styles.btn} onClick={handleClick} disabled={disabled}>
      <KakaoIcon />
      {t('login.kakao')}
    </button>
  )
}
