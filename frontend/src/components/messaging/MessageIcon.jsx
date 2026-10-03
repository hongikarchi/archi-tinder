import { useId } from 'react'

const BODY =
  'M12 4H20C25.5 4 29 7.5 29 13V15C29 20.5 25.5 24 20 24H14.6L9.7 28.1C8.9 28.8 7.8 28.1 8 27.1L8.8 23.6C5.2 22.7 3 19.4 3 15V13C3 7.5 6.5 4 12 4Z'

/**
 * MessageIcon — decorative 3D glossy chat bubble.
 * Colors are intentionally fixed (approved design: same blue across all
 * themes), so they do not use theme tokens.
 */
export default function MessageIcon({ size = 24, className, style }) {
  const uid = useId().replace(/:/g, '')
  const g = `mi-g-${uid}`
  const s = `mi-s-${uid}`
  const h = `mi-h-${uid}`
  const c = `mi-c-${uid}`
  const f = `mi-f-${uid}`
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={className}
      style={style}
    >
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9AD8FF" />
          <stop offset="0.55" stopColor="#4FA6F6" />
          <stop offset="1" stopColor="#2563D9" />
        </linearGradient>
        <linearGradient id={s} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0.55" stopColor="#0B2E7A" stopOpacity="0" />
          <stop offset="1" stopColor="#0B2E7A" stopOpacity="0.38" />
        </linearGradient>
        <radialGradient id={h} cx="0.42" cy="0.18" r="0.55">
          <stop offset="0" stopColor="#fff" stopOpacity="0.9" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <clipPath id={c}>
          <path d={BODY} />
        </clipPath>
        <filter id={f} x="-30%" y="-30%" width="160%" height="170%">
          <feDropShadow dx="0" dy="1.2" stdDeviation="1.1" floodColor="#2563D9" floodOpacity="0.35" />
        </filter>
      </defs>
      <path d={BODY} fill={`url(#${g})`} filter={`url(#${f})`} />
      <g clipPath={`url(#${c})`}>
        <path d={BODY} fill={`url(#${s})`} />
        <ellipse cx="14.5" cy="8.6" rx="10" ry="4.6" fill={`url(#${h})`} />
        <path d={BODY} fill="none" stroke="#fff" strokeOpacity="0.5" strokeWidth="1.4" />
      </g>
      {[11, 16, 21].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="14.9" r="1.95" fill="rgba(11,46,122,0.28)" />
          <circle cx={cx} cy="14" r="1.95" fill="#fff" />
        </g>
      ))}
    </svg>
  )
}
