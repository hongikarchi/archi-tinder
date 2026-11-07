// Back bubble: large, upper-right, tail at bottom-right.
const BACK =
  'M17 3H24A5 5 0 0 1 29 8V14A5 5 0 0 1 26.6 18.3L27.6 23.2L22.4 19H17A5 5 0 0 1 12 14V8A5 5 0 0 1 17 3Z'
// Front bubble: smaller, lower-left, tail at bottom-left.
const FRONT =
  'M8 12H15.5A4.5 4.5 0 0 1 20 16.5V20.5A4.5 4.5 0 0 1 15.5 25H10L4.8 29.2L3.5 21V16.5A4.5 4.5 0 0 1 8 12Z'

/**
 * MessageIcon — decorative outline chat icon (two overlapping speech bubbles).
 * Strokes inherit `currentColor`, so it follows the button's theme/hover color.
 * The front bubble is filled with the button background (`--message-icon-bg`, falling back to `--color-surface`) so it
 * hides the back bubble's outline where they overlap.
 */
export default function MessageIcon({ size = 24, className, style }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className={className}
      style={style}
      stroke="currentColor"
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={BACK} fill="none" />
      <path d={FRONT} fill="var(--message-icon-bg, var(--color-surface))" />
    </svg>
  )
}
