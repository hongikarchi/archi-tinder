import { useNavigate } from 'react-router-dom'
import s from './FirmProfileHeader.module.css'

export default function FirmProfileHeader() {
  const navigate = useNavigate()

  return (
    /* Sticky Header — back left, title center, symmetric placeholder right (mirrors UserProfile) */
    <div
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'var(--color-header-bg, rgba(15, 15, 15, 0.72))',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--color-border-soft)',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
      }}
    >
      <button
        type="button"
        onClick={() => navigate(-1)}
        aria-label="Go back"
        className={s.backBtn}
        style={{
          width: 44,
          height: 44,
          minWidth: 44,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: 'none',
          color: 'var(--color-text)',
          cursor: 'pointer',
          borderRadius: 12,
          padding: 0,
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
      </button>

      <h2
        style={{
          color: 'var(--color-text)',
          fontSize: 17,
          fontWeight: 700,
          margin: 0,
          letterSpacing: '-0.01em',
          flex: 1,
          textAlign: 'center',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        Profile
      </h2>

      {/* Symmetric placeholder — keeps title optically centered */}
      <div style={{ width: 44, height: 44, flexShrink: 0 }} aria-hidden="true" />
    </div>
  )
}
