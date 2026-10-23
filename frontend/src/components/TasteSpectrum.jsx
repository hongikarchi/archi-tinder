import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from '../i18n/index.js'

/* ── Constants ──────────────────────────────────────────────────────────── */
// Form is intentionally excluded — no reliable per-building score exists yet
// (embeddings carry weak geometric-form signal). See docs/algorithm.md.
const SPECTRUM_AXES = [
  { key: 'materiality', leftKey: 'persona.spectrum.materiality.left', rightKey: 'persona.spectrum.materiality.right' },
  { key: 'scale',       leftKey: 'persona.spectrum.scale.left',       rightKey: 'persona.spectrum.scale.right' },
  { key: 'energy',      leftKey: 'persona.spectrum.energy.left',      rightKey: 'persona.spectrum.energy.right' },
  { key: 'tradition',   leftKey: 'persona.spectrum.tradition.left',   rightKey: 'persona.spectrum.tradition.right' },
]

// Persona report redesign (2026-10-22) — off-scale values, DESIGN.md §11 E4 / E8 / E10.
// Kept in one block so they can be promoted to tokens later; do not round to the scale.
const LABEL_W = 58          // fixed label column width, both sides
const GAP = 8               // gap between the line and its pole label
const TOP = 8               // top padding before the first row
const DEFAULT_ROW = 64      // row height (report page uses 64; 48 is the compact variant)
const AXIS_NAME_SIZE = 12   // E4
const POLE_SIZE = 11        // E4
const TRACK_WIDTH = 4       // E10 — track is var(--color-border)
const BIG_R = 8
const SMALL_R = 3
const BIG_RING = 3          // surface-coloured ring around the big dot
const SMALL_OPACITY = 0.4   // E10
const TRAVEL_MS = 900       // E8 — dot travel from the centre to its value
const ROW_STAGGER_MS = 140  // E8 — per-row stagger
const SMALL_DOT_LAG_MS = 60

const easeOutCubic = p => 1 - Math.pow(1 - p, 3)

/**
 * Normalizes one axis's raw value into { score, dots } or null.
 *   - null/undefined            → null (no evidence)
 *   - plain number (legacy)     → { score, dots: [] } — big dot only
 *   - { score, dots, ... } (current shape) → passed through
 */
function normalizeAxis(raw) {
  if (raw === null || raw === undefined) return null
  if (typeof raw === 'number') return { score: raw, dots: [] }
  if (typeof raw.score !== 'number') return null
  return { score: raw.score, dots: Array.isArray(raw.dots) ? raw.dots : [] }
}

/**
 * TasteSpectrum — SVG taste-axis visualization (grey track, accent dots; no
 * blob, no legend).
 * Props:
 *   axisScores  object  - { materiality, scale, energy, tradition } where each
 *                          value is null | number (legacy) | { score, dots, n,
 *                          iqr, confidence }.
 *   rowHeight   number  - row height in px (default 64).
 *   animate     bool    - when true, dots start at the centre and travel to
 *                          their value once `play` becomes true (DESIGN.md
 *                          §3.5a rule 4). When false the final values render
 *                          immediately (prefers-reduced-motion, static use).
 *   play        bool    - start signal for the travel (default true).
 */
export default function TasteSpectrum({ axisScores, rowHeight = DEFAULT_ROW, animate = false, play = true }) {
  const { t } = useTranslation()
  const containerRef = useRef(null)
  const [width, setWidth] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const startedRef = useRef(false)

  useLayoutEffect(() => {
    const el = containerRef.current
    if (!el) return
    const measure = () => setWidth(el.getBoundingClientRect().width)
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Dot travel — one rAF loop, runs once when `play` flips true.
  useEffect(() => {
    if (!animate || !play || startedRef.current) return
    startedRef.current = true
    let raf = 0
    const t0 = performance.now()
    const step = now => {
      const e = now - t0
      setElapsed(e)
      const total = TRAVEL_MS + ROW_STAGGER_MS * (SPECTRUM_AXES.length - 1) + SMALL_DOT_LAG_MS
      if (e < total) raf = requestAnimationFrame(step)
      else setElapsed(Infinity)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [animate, play])

  const H = TOP + rowHeight * SPECTRUM_AXES.length
  const x0 = LABEL_W + GAP
  const x1 = Math.max(x0 + 1, width - LABEL_W - GAP)
  const lineWidth = x1 - x0
  const x = v => x0 + ((v + 1) / 2) * lineWidth
  const mid = width / 2

  const rows = SPECTRUM_AXES.map((ax, i) => {
    const axis = normalizeAxis(axisScores?.[ax.key])
    const y0 = TOP + rowHeight * i
    const by = y0 + Math.round(rowHeight * 0.56)
    return { ax, axis, y0, by, none: !axis }
  })

  // Only axes with evidence get dots; their order index drives the stagger.
  const pts = rows
    .filter(r => r.axis)
    .map((r, order) => ({ x: x(r.axis.score), y: r.by, dots: r.axis.dots, order }))

  // Travelled x for a dot whose final x is `fx` (centre → value, eased, staggered).
  const travel = (fx, order, lag) => {
    if (!animate || elapsed === Infinity) return fx
    const p = Math.min(1, Math.max(0, (elapsed - order * ROW_STAGGER_MS - lag) / TRAVEL_MS))
    return mid + (fx - mid) * easeOutCubic(p)
  }

  return (
    <div ref={containerRef} style={{ width: '100%', minHeight: H }}>
      {width > 0 && (
        <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} style={{ display: 'block', overflow: 'visible' }}>
          {/* axis rows — name, grey track, pole labels, no-evidence note */}
          {rows.map(({ ax, none, y0, by }) => (
            <g key={ax.key}>
              <text x={0} y={y0 + 12} fontSize={AXIS_NAME_SIZE} fontWeight={700} letterSpacing=".02em" fill={none ? 'var(--color-text-dim)' : 'var(--color-text)'}>
                {t(`persona.axis.${ax.key}`)}
              </text>
              <g opacity={none ? 0.35 : 1}>
                <line x1={x0} y1={by} x2={x1} y2={by} stroke="var(--color-border)" strokeWidth={TRACK_WIDTH} strokeLinecap="round" />
              </g>
              <text x={x0 - GAP} y={by + 4} fontSize={POLE_SIZE} fontWeight={600} textAnchor="end" fill="var(--color-text-muted)" opacity={none ? 0.5 : 1}>
                {t(ax.leftKey)}
              </text>
              <text x={x1 + GAP} y={by + 4} fontSize={POLE_SIZE} fontWeight={600} textAnchor="start" fill="var(--color-text-muted)" opacity={none ? 0.5 : 1}>
                {t(ax.rightKey)}
              </text>
              {none && (
                <text x={(x0 + x1) / 2} y={by - 8} fontSize={POLE_SIZE} textAnchor="middle" fill="var(--color-text-dim)">
                  {t('persona.noEvidence')}
                </text>
              )}
            </g>
          ))}

          {/* dots — small dots at 40 % opacity, big accent dot with a surface ring */}
          {pts.map((p, i) => (
            <g key={`dots-${i}`}>
              {p.dots.map((d, di) => (
                <circle key={di} cx={travel(x(d), p.order, SMALL_DOT_LAG_MS)} cy={p.y} r={SMALL_R} fill="var(--accent-1)" opacity={SMALL_OPACITY} />
              ))}
              <circle cx={travel(p.x, p.order, 0)} cy={p.y} r={BIG_R} fill="var(--accent-1)" stroke="var(--color-surface)" strokeWidth={BIG_RING} />
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}
