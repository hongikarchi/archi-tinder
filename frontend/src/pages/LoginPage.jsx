export default function LoginPage({ onLogin, theme, onToggleTheme }) {
  function handleSocialLogin(provider) {
    const userId = `user_${provider}_${Date.now()}`
    onLogin(userId)
  }

  return (
    <div style={{
      height: '100vh', overflow: 'hidden', background: 'var(--color-bg)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: 24, position: 'relative',
    }}>
      {/* Theme toggle */}
      <button
        onClick={onToggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          position: 'absolute', top: 16, right: 16,
          background: 'var(--color-surface)', border: '1px solid var(--color-border-soft)',
          borderRadius: 8, padding: '6px 10px',
          color: 'var(--color-text-dim)', fontSize: 16, cursor: 'pointer',
          fontFamily: 'inherit', lineHeight: 1,
        }}
      >
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>

      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <h1 style={{ fontSize: 36, fontWeight: 900, margin: '0 0 10px', letterSpacing: '-0.02em' }}>
          <span style={{ color: 'var(--color-text)' }}>Archi</span>
          <span style={{ color: '#ec4899' }}>Tinder</span>
        </h1>
        <p style={{ color: 'var(--color-text-dimmer)', fontSize: 14, margin: 0 }}>
          Discover architecture that inspires you
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%', maxWidth: 320 }}>
        <SocialButton
          onClick={() => handleSocialLogin('google')}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
          }
          label="Continue with Google"
          style={{ background: '#fff', color: '#111', border: '1px solid rgba(0,0,0,0.1)' }}
        />
        <SocialButton
          onClick={() => handleSocialLogin('kakao')}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#3C1E1E">
              <path d="M12 3C6.477 3 2 6.477 2 10.8c0 2.713 1.644 5.09 4.125 6.56L5.25 21l4.313-2.813A11.3 11.3 0 0012 18.6c5.523 0 10-3.477 10-7.8S17.523 3 12 3z"/>
            </svg>
          }
          label="Continue with Kakao"
          style={{ background: '#FEE500', color: '#3C1E1E' }}
        />
        <SocialButton
          onClick={() => handleSocialLogin('naver')}
          icon={
            <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff">
              <path d="M16.273 12.845L7.376 0H0v24h7.727V11.155L16.624 24H24V0h-7.727z"/>
            </svg>
          }
          label="Continue with Naver"
          style={{ background: '#03C75A', color: '#fff' }}
        />
      </div>

      <p style={{ color: 'var(--color-text-dimmest)', fontSize: 11, marginTop: 32, textAlign: 'center' }}>
        By continuing, you agree to our terms of service
      </p>
    </div>
  )
}

function SocialButton({ onClick, icon, label, style }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        width: '100%', padding: '14px 20px', borderRadius: 14, border: 'none',
        fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
        transition: 'opacity 0.15s',
        ...style,
      }}
      onMouseEnter={e => e.currentTarget.style.opacity = '0.88'}
      onMouseLeave={e => e.currentTarget.style.opacity = '1'}
    >
      {icon}
      {label}
    </button>
  )
}
