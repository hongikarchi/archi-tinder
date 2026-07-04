/**
 * ProfileQr.jsx — Real, scannable per-user profile QR.
 *
 * Encodes `${window.location.origin}/user/${userId}` — the existing public
 * profile route. Replaces FakeQr.jsx (deleted).
 *
 * Props:
 *   userId  {string|number} — user_id from UserProfileSerializer. Required.
 *                             If absent/falsy, renders nothing (no crash).
 *   size    {number}        — rendered pixel size (default: 72)
 *   fgColor {string}        — module fill color (default: '#0A0A0A' = INK1)
 *   bgColor {string}        — background color (default: '#FFFFFF' = PAPER)
 *
 * Design note: QR is intentionally hardcoded dark-on-white (theme-independent).
 * The business card is a white paper artifact across all 4 app themes.
 * marginSize={2} provides the quiet zone needed for reliable scanning.
 */

import { QRCodeSVG } from 'qrcode.react'

export default function ProfileQr({
  userId,
  size = 72,
  fgColor = '#0A0A0A',
  bgColor = '#FFFFFF',
}) {
  if (!userId) return null

  const url = `${window.location.origin}/user/${userId}`

  return (
    <QRCodeSVG
      value={url}
      size={size}
      level="M"
      marginSize={2}
      fgColor={fgColor}
      bgColor={bgColor}
      role="img"
      aria-label="프로필 QR 코드"
      style={{ display: 'block', flexShrink: 0 }}
    />
  )
}
