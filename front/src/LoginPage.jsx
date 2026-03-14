import { useState } from 'react'

const USERS_KEY = 'archithon_users'

async function hashPassword(password) {
  const data = new TextEncoder().encode(password)
  const buf = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

function getUsers() {
  return JSON.parse(localStorage.getItem(USERS_KEY) || '[]')
}

function saveUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users))
}

export default function LoginPage({ onLogin }) {
  const [id, setId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 4) { setError('비밀번호는 4자 이상이어야 합니다.'); return }
    setLoading(true)

    const userId = id.trim()
    const hash = await hashPassword(password)
    const users = getUsers()
    const existing = users.find(u => u.id === userId)

    if (existing) {
      if (existing.password !== hash) {
        setError('비밀번호가 틀렸습니다.')
        setLoading(false)
        return
      }
      onLogin(userId)
    } else {
      saveUsers([...users, { id: userId, password: hash, createdAt: new Date().toISOString() }])
      onLogin(userId)
    }

    setLoading(false)
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#0f0f0f',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{ textAlign: 'center', marginBottom: 36 }}>
        <h1 style={{ fontSize: 28, fontWeight: 900, margin: '0 0 8px' }}>
          <span style={{ color: '#fff' }}>Archi</span>
          <span style={{ color: '#3b82f6' }}>Tinder</span>
        </h1>
        <p style={{ color: '#4b5563', fontSize: 13, margin: 0 }}>
          ID 입력 후 처음이면 자동으로 계정이 만들어집니다
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        style={{ width: '100%', maxWidth: 320, display: 'flex', flexDirection: 'column', gap: 12 }}
      >
        <input
          type="text"
          placeholder="ID"
          value={id}
          onChange={e => setId(e.target.value)}
          autoComplete="username"
          style={inputStyle}
        />
        <input
          type="password"
          placeholder="비밀번호 (4자 이상)"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
          style={inputStyle}
        />

        {error && (
          <p style={{ color: '#f87171', fontSize: 13, margin: 0, textAlign: 'center' }}>{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !id.trim() || !password}
          style={{
            marginTop: 4, padding: '14px 0', borderRadius: 12,
            background: loading || !id.trim() || !password
              ? '#1f2937' : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            color: loading || !id.trim() || !password ? '#4b5563' : '#fff',
            fontSize: 15, fontWeight: 700, border: 'none',
            cursor: loading || !id.trim() || !password ? 'default' : 'pointer',
            fontFamily: 'inherit', transition: 'background 0.2s',
          }}
        >
          {loading ? '확인 중...' : '시작하기'}
        </button>
      </form>
    </div>
  )
}

const inputStyle = {
  padding: '14px 16px', borderRadius: 12,
  background: '#1a1a1a', border: '1px solid #2d2d2d',
  color: '#fff', fontSize: 15, fontFamily: 'inherit',
  outline: 'none', width: '100%', boxSizing: 'border-box',
}
