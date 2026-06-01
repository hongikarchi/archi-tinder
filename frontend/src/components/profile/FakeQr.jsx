/**
 * FakeQr.jsx — STUB QR placeholder.
 *
 * Renders a deterministic 21×21 module grid that LOOKS like a QR code
 * but is NOT scannable. It is a pure visual placeholder for the BusinessCard
 * share feature which is not yet implemented backend-side.
 *
 * Props:
 *   seed  {string|number} — deterministic seed (use user_id or similar)
 *   size  {number}        — rendered pixel size (default: 72)
 *   color {string}        — module fill color (default: '#0A0A0A')
 */
export default function FakeQr({ seed = 0, size = 72, color = '#0A0A0A' }) {
  const MODULES = 21
  const cellSize = size / MODULES

  // Deterministic pseudo-random from seed (xor-shift variant — reproducible, no import needed)
  function prng(s) {
    let h = typeof s === 'string'
      ? [...s].reduce((a, c) => (Math.imul(31, a) + c.charCodeAt(0)) | 0, 0)
      : Number(s) | 0
    return () => {
      h ^= h << 13; h ^= h >> 17; h ^= h << 5
      return ((h >>> 0) / 0xffffffff)
    }
  }

  const rand = prng(seed)

  // Build module grid: finder patterns are always filled, rest are probabilistic
  const grid = []
  for (let row = 0; row < MODULES; row++) {
    const cols = []
    for (let col = 0; col < MODULES; col++) {
      // Finder patterns: top-left, top-right, bottom-left (7×7 corners)
      const inFinder =
        (row < 7 && col < 7) ||
        (row < 7 && col >= MODULES - 7) ||
        (row >= MODULES - 7 && col < 7)

      // Timing pattern (row 6 / col 6 alternating stripes)
      const isTiming = (row === 6 || col === 6)

      if (inFinder) {
        // Simulate the finder border+center pattern
        const localR = row < 7 ? row : (row >= MODULES - 7 ? row - (MODULES - 7) : row)
        const localC = col < 7 ? col : (col >= MODULES - 7 ? col - (MODULES - 7) : col)
        const onBorder = localR === 0 || localR === 6 || localC === 0 || localC === 6
        const inCenter = localR >= 2 && localR <= 4 && localC >= 2 && localC <= 4
        cols.push(onBorder || inCenter)
      } else if (isTiming) {
        cols.push((row + col) % 2 === 0)
      } else {
        cols.push(rand() > 0.45)
      }
    }
    grid.push(cols)
  }

  const rects = []
  for (let row = 0; row < MODULES; row++) {
    for (let col = 0; col < MODULES; col++) {
      if (grid[row][col]) {
        rects.push(
          <rect
            key={`${row}-${col}`}
            x={col * cellSize}
            y={row * cellSize}
            width={cellSize}
            height={cellSize}
            fill={color}
          />
        )
      }
    }
  }

  return (
    /* aria-hidden: this is purely decorative — not scannable */
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ display: 'block', flexShrink: 0 }}
    >
      {/* White background so the stub is legible on any parent color */}
      <rect width={size} height={size} fill="#FFFFFF" />
      {rects}
    </svg>
  )
}
