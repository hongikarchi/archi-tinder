/**
 * PentagonChart.jsx
 * SVG radar chart for 5-axis personality vectors.
 *
 * Props:
 *   myVector      {number[]|null}  5-element array, values -1..+1
 *   theirVector   {number[]|null}  5-element array, values -1..+1
 *   size          {number}         SVG width/height (default 200)
 *   highlightAxis {number|null}    axis index 0-4 to emphasize
 *   interactive   {boolean}        enable vertex hover/click
 *   onAxisClick   {Function}       (axisIndex) => void
 *   mini          {boolean}        compact mode (auto-scales size to 120)
 */

import styles from './PentagonChart.module.css'
import { AXIS_LABELS } from '../constants/personalityTypes.js'

const DEFAULT_SIZE = 200
const MINI_SIZE = 120
const NUM_AXES = 5
const GRID_LEVELS = 3

/**
 * Compute SVG polygon points for a given vector.
 * Axis 0 is at the top (−π/2), subsequent axes at +72° increments (clockwise).
 */
function pentagonPoints(vector, cx, cy, maxR) {
  return vector.map((value, index) => {
    const angle = (Math.PI * 2 * index) / NUM_AXES - Math.PI / 2
    const r = maxR * ((value + 1) / 2) // -1..+1 → 0..1
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')
}

/**
 * Compute SVG grid polygon points (evenly-spaced levels).
 */
function gridPoints(level, cx, cy, maxR, levels) {
  const r = maxR * (level / levels)
  return Array.from({ length: NUM_AXES }, (_, i) => {
    const angle = (Math.PI * 2 * i) / NUM_AXES - Math.PI / 2
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')
}

/**
 * Get (x, y) for a given axis vertex at a given radius.
 */
function axisPoint(index, r, cx, cy) {
  const angle = (Math.PI * 2 * index) / NUM_AXES - Math.PI / 2
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
}

/**
 * Compute label position slightly beyond the grid edge.
 */
function labelPoint(index, maxR, cx, cy, offset = 16) {
  return axisPoint(index, maxR + offset, cx, cy)
}

export default function PentagonChart({
  myVector = null,
  theirVector = null,
  size: sizeProp,
  highlightAxis = null,
  interactive = false,
  onAxisClick,
  mini = false,
  // Opt-in legend for overlay comparison views (people discovery card back).
  // Rendered INSIDE the svg, on an extra strip below the chart, so the root
  // element stays an <svg> and existing callers' layout is untouched.
  legend = false,
  legendMineLabel = '나',
  legendTheirsLabel = '이 유저',
}) {
  const size = sizeProp ?? (mini ? MINI_SIZE : DEFAULT_SIZE)
  const padding = mini ? 24 : 32
  const cx = size / 2
  const cy = size / 2
  const maxR = size / 2 - padding

  // Fallback zero-vector for grid rendering when neither vector is provided
  const zeroVec = Array(NUM_AXES).fill(0)

  const legendH = legend ? (mini ? 18 : 22) : 0
  const legendFont = mini ? 9 : 11

  return (
    <svg
      width={size}
      height={size + legendH}
      viewBox={`0 0 ${size} ${size + legendH}`}
      aria-label="성향 오각형 차트"
      className={styles.root}
    >
      {/* Grid polygons */}
      {Array.from({ length: GRID_LEVELS }, (_, i) => (
        <polygon
          key={`grid-${i}`}
          points={gridPoints(i + 1, cx, cy, maxR, GRID_LEVELS)}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
      ))}

      {/* Axis lines from center to each vertex */}
      {Array.from({ length: NUM_AXES }, (_, i) => {
        const pt = axisPoint(i, maxR, cx, cy)
        return (
          <line
            key={`axis-${i}`}
            x1={cx}
            y1={cy}
            x2={pt.x}
            y2={pt.y}
            stroke="var(--color-border)"
            strokeWidth="1"
          />
        )
      })}

      {/* theirVector polygon (dashed, accent-2) */}
      {theirVector && theirVector.length === NUM_AXES && (
        <polygon
          points={pentagonPoints(theirVector, cx, cy, maxR)}
          fill="var(--accent-2)"
          fillOpacity="0.15"
          stroke="var(--accent-2)"
          strokeWidth="1.5"
          strokeDasharray="4 2"
        />
      )}

      {/* myVector polygon (solid, accent-1) */}
      {myVector && myVector.length === NUM_AXES && (
        <polygon
          points={pentagonPoints(myVector, cx, cy, maxR)}
          fill="var(--accent-1)"
          fillOpacity="0.2"
          stroke="var(--accent-1)"
          strokeWidth="1.5"
        />
      )}

      {/* Highlight axis marker — shown on myVector vertex if highlightAxis set */}
      {highlightAxis !== null && myVector && myVector.length === NUM_AXES && (() => {
        const val = myVector[highlightAxis]
        const r = maxR * ((val + 1) / 2)
        const pt = axisPoint(highlightAxis, r, cx, cy)
        return (
          <circle
            cx={pt.x}
            cy={pt.y}
            r={5}
            fill="var(--accent-1)"
            stroke="var(--color-bg)"
            strokeWidth="1.5"
          />
        )
      })()}

      {/* Axis labels */}
      {AXIS_LABELS.map((label, i) => {
        const labelOffset = mini ? 14 : 18
        const pt = labelPoint(i, maxR, cx, cy, labelOffset)
        const isHighlighted = highlightAxis === i
        return (
          <text
            key={`label-${i}`}
            x={pt.x}
            y={pt.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={mini ? 8 : 10}
            fontWeight={isHighlighted ? 700 : 400}
            fill={isHighlighted ? 'var(--accent-1)' : 'var(--color-text-muted)'}
            style={{ fontFamily: 'inherit', userSelect: 'none' }}
          >
            {label}
          </text>
        )
      })}

      {/* Interactive vertex hit areas (only when interactive=true) */}
      {interactive && Array.from({ length: NUM_AXES }, (_, i) => {
        // Prefer myVector vertex; fall back to grid edge
        const vec = myVector && myVector.length === NUM_AXES ? myVector : zeroVec
        const val = vec[i]
        const r = Math.max(maxR * ((val + 1) / 2), maxR * 0.25) // min 25% so tiny values are still clickable
        const pt = axisPoint(i, r, cx, cy)
        return (
          <circle
            key={`hit-${i}`}
            cx={pt.x}
            cy={pt.y}
            r={15}
            fill="transparent"
            className={styles.hitArea}
            onClick={() => onAxisClick?.(i)}
            role="button"
            aria-label={`${AXIS_LABELS[i]} 축 필터`}
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onAxisClick?.(i) }}
          />
        )
      })}

      {/* Legend — swatches mirror the polygon strokes above exactly:
          myVector = solid accent-1, theirVector = dashed 4 2 accent-2. */}
      {legend && (() => {
        const y = size + legendH / 2
        const swatchW = mini ? 12 : 16
        const gapAfterSwatch = 4
        const gapBetweenItems = mini ? 12 : 16
        const mineW = swatchW + gapAfterSwatch + legendMineLabel.length * legendFont * 0.62
        const theirsW = swatchW + gapAfterSwatch + legendTheirsLabel.length * legendFont * 0.62
        let x = Math.max(0, (size - (mineW + gapBetweenItems + theirsW)) / 2)
        const items = [
          { label: legendMineLabel, color: 'var(--accent-1)', dash: undefined, w: mineW },
          { label: legendTheirsLabel, color: 'var(--accent-2)', dash: '4 2', w: theirsW },
        ]
        return (
          <g aria-hidden="true">
            {items.map(item => {
              const startX = x
              x += item.w + gapBetweenItems
              return (
                <g key={item.label}>
                  <line
                    x1={startX}
                    y1={y}
                    x2={startX + swatchW}
                    y2={y}
                    stroke={item.color}
                    strokeWidth="1.5"
                    strokeDasharray={item.dash}
                  />
                  <text
                    x={startX + swatchW + gapAfterSwatch}
                    y={y}
                    fontSize={legendFont}
                    fill="var(--color-text-dim)"
                    dominantBaseline="middle"
                  >
                    {item.label}
                  </text>
                </g>
              )
            })}
          </g>
        )
      })()}
    </svg>
  )
}
