import { useId, useLayoutEffect, useRef, useState } from 'react'
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

const LABEL_W = 58   // fixed label column width, both sides
const GAP = 8        // gap between the line and its pole label
const TOP = 8         // top padding before the first row
const ROW = 64        // row height

/**
 * Normalizes one axis's raw value into { score, dots, confidence } or null.
 *   - null/undefined            → null (no evidence)
 *   - plain number (legacy)     → { score, dots: [], confidence: 0 } — big dot only
 *   - { score, dots, confidence, ... } (current shape) → passed through
 */
function normalizeAxis(raw) {
  if (raw === null || raw === undefined) return null
  if (typeof raw === 'number') return { score: raw, dots: [], confidence: 0 }
  if (typeof raw.score !== 'number') return null
  return {
    score: raw.score,
    dots: Array.isArray(raw.dots) ? raw.dots : [],
    confidence: typeof raw.confidence === 'number' ? raw.confidence : 0,
  }
}

/**
 * TasteSpectrum — SVG taste-axis visualization.
 * Props:
 *   axisScores  object  - { materiality, scale, energy, tradition } where each
 *                          value is null | number (legacy) | { score, dots, n,
 *                          iqr, confidence }.
 */
export default function TasteSpectrum({ axisScores }) {
  const { t } = useTranslation()
  const containerRef = useRef(null)
  const [width, setWidth] = useState(0)
  const rawId = useId()
  const filterId = `personaGoo${rawId.replace(/[^a-zA-Z0-9]/g, '')}`

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

  const H = TOP + ROW * SPECTRUM_AXES.length
  const x0 = LABEL_W + GAP
  const x1 = Math.max(x0 + 1, width - LABEL_W - GAP)
  const lineWidth = x1 - x0
  const x = v => x0 + ((v + 1) / 2) * lineWidth

  const rows = SPECTRUM_AXES.map((ax, i) => {
    const axis = normalizeAxis(axisScores?.[ax.key])
    const y0 = TOP + ROW * i
    const by = y0 + 36
    return { ax, axis, y0, by, none: !axis }
  })

  // Only axes with evidence get a point; the S-curve connector below walks
  // this filtered list, so a null (no-evidence) axis is naturally skipped —
  // its neighbors connect directly to each other.
  const pts = rows
    .filter(r => r.axis)
    .map(r => ({ x: x(r.axis.score), y: r.by, c: r.axis.confidence, dots: r.axis.dots }))

  return (
    <div ref={containerRef} style={{ width: '100%', minHeight: H }}>
      {width > 0 && (
        <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} style={{ display: 'block', overflow: 'visible' }}>
          <defs>
            <filter id={filterId} filterUnits="userSpaceOnUse" x={-40} y={-40} width={width + 80} height={H + 80}>
              <feGaussianBlur in="SourceGraphic" stdDeviation={8} result="b" />
              <feColorMatrix in="b" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 22 -9" />
            </filter>
          </defs>

          {/* confidence blob — behind the dots, blurred + alpha-boosted into a goo shape */}
          <g opacity={0.18}>
            <g filter={`url(#${filterId})`}>
              {pts.map((p, i) => (
                <circle key={`blob-${i}`} cx={p.x} cy={p.y} r={12 + p.c * 22} fill="var(--accent-1)" />
              ))}
              {pts.slice(0, -1).map((p, i) => {
                const q = pts[i + 1]
                const my = (p.y + q.y) / 2
                return (
                  <path
                    key={`connector-${i}`}
                    d={`M${p.x},${p.y} C${p.x},${my} ${q.x},${my} ${q.x},${q.y}`}
                    fill="none"
                    stroke="var(--accent-1)"
                    strokeWidth={16}
                    strokeLinecap="round"
                  />
                )
              })}
            </g>
          </g>

          {/* axis rows — name, line + end ticks, pole labels, no-evidence note */}
          {rows.map(({ ax, none, y0, by }) => (
            <g key={ax.key}>
              <text x={0} y={y0 + 12} fontSize={13} fontWeight={700} fill={none ? 'var(--color-text-dim)' : 'var(--color-text)'}>
                {t(`persona.axis.${ax.key}`)}
              </text>
              <g opacity={none ? 0.35 : 1}>
                <line x1={x0} y1={by} x2={x1} y2={by} stroke="var(--color-text)" strokeWidth={0.5} />
                <line x1={x0} y1={by - 4} x2={x0} y2={by + 4} stroke="var(--color-text)" strokeWidth={0.5} />
                <line x1={x1} y1={by - 4} x2={x1} y2={by + 4} stroke="var(--color-text)" strokeWidth={0.5} />
              </g>
              <text x={x0 - GAP} y={by + 4} fontSize={11} fontWeight={600} textAnchor="end" fill="var(--color-text-muted)" opacity={none ? 0.5 : 1}>
                {t(ax.leftKey)}
              </text>
              <text x={x1 + GAP} y={by + 4} fontSize={11} fontWeight={600} textAnchor="start" fill="var(--color-text-muted)" opacity={none ? 0.5 : 1}>
                {t(ax.rightKey)}
              </text>
              {none && (
                <text x={(x0 + x1) / 2} y={by - 8} fontSize={11} textAnchor="middle" fill="var(--color-text-dim)">
                  {t('persona.noEvidence')}
                </text>
              )}
            </g>
          ))}

          {/* dots — foreground, on top of the blob */}
          {pts.map((p, i) => (
            <g key={`dots-${i}`}>
              {p.dots.map((d, di) => (
                <circle key={di} cx={x(d)} cy={p.y} r={3.5} fill="var(--color-text)" />
              ))}
              <circle cx={p.x} cy={p.y} r={9} fill="var(--color-text)" />
            </g>
          ))}
        </svg>
      )}
    </div>
  )
}
