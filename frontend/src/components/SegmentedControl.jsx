import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import styles from './SegmentedControl.module.css'

// Per-`size` default for the highlight's own height / vertical anchoring.
// '100%' = fill the row (top:0, height:100%); a number = a fixed-height pill,
// vertically centered inside the row (top:50%, translateY(-50%)). Callers can
// always override via the `pillHeight` prop — these are just sane per-size
// fallbacks for a bare-bones consumer that doesn't pass one.
const DEFAULT_PILL_HEIGHT = { sm: 22, md: '100%', lg: 44 }

const NAV_KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']

function defaultRenderOption(opt) {
  return (
    <>
      {opt.icon && <span aria-hidden="true" style={{ display: 'flex' }}>{opt.icon}</span>}
      {opt.label != null && <span>{opt.label}</span>}
    </>
  )
}

/**
 * SegmentedControl — shared sliding-highlight control for choosing ONE value
 * from a small set of options (UI-CONSISTENCY-B Phase 2d).
 *
 * ONE absolutely-positioned highlight tracks the selected option's measured
 * content box (refs + ResizeObserver) and animates `transform: translateX()`
 * + `width` between selections — see DESIGN.md §3.5 motion tokens.
 *
 * This is INTERACTION motion (project rule — MEMORY
 * project_reduced_motion_gotcha.md): it is NEVER gated by
 * `prefers-reduced-motion`; only decorative motion honors that media query.
 * No animation plays on first mount, and no animation plays on a pure
 * geometry CORRECTION (window resize / web-font load / an option's label
 * changing width on a language switch) — only an actual selection change
 * animates. See the `measure(animate)` / `hasMountedRef` split below.
 *
 * Two concerns are deliberately split so every consumer keeps its own look:
 *  - the HIGHLIGHT (this component) owns background / border / shadow /
 *    radius — the "selected" chrome — via `highlightStyle` / `highlightClassName`.
 *  - per-option FOREGROUND styling (icon/text color, weight, filled-vs-outline
 *    icon swap) stays owned by the caller via `renderOption(option, isActive)`
 *    and/or `optionStyle` / `optionClassName` (both accept a plain value or a
 *    `(option, isActive) => value` function).
 *
 * `as` controls the ARIA role set:
 *  - 'radio' (default) — role="radiogroup" / role="radio" + aria-checked.
 *    For toggle groups (language pill, theme pill).
 *  - 'tabs' — role="tablist" / role="tab" + aria-selected. For in-page view
 *    switches (SocialSegment, profile Tabs).
 *  - 'nav' — no group role at all; each option renders as a plain button with
 *    `aria-current="page"` when active, and NO arrow-key handling. For
 *    TabBar: the WAI-ARIA APG tabs pattern assumes in-page panels, not real
 *    navigation to a new route — role="tab" + automatic activation on a real
 *    nav bar is the wrong pattern (and would fight `useKeyboardSwipe`'s
 *    window-level ArrowLeft/Right swipe listener on Discovery/Swipe if arrow
 *    keys were bound here too). The landmark + aria-label stay owned by the
 *    caller's own `<nav>` wrapper — this component renders no role/aria-label
 *    of its own in this mode, only the sliding visual + click/focus behavior.
 *
 * Keyboard (radio/tabs only): ArrowLeft/Up = previous option, ArrowRight/Down
 * = next (wrapping), Home/End = first/last — standard APG roving-tabindex
 * automatic-activation pattern (focus moves, selection follows immediately).
 * Every handled key calls `preventDefault` + `stopPropagation`: DiscoveryPage
 * / SwipePage bind ArrowLeft/ArrowRight at `window` for card swipe
 * (`useKeyboardSwipe`) and PageTopControls (radio-mode pills) renders on both
 * pages — stopping propagation here keeps a focused pill from also firing a
 * swipe.
 */
export default function SegmentedControl({
  options,
  value,
  onChange,
  variant = 'pill',       // 'pill' | 'underline'
  size = 'md',            // 'sm' | 'md' | 'lg'
  as = 'radio',           // 'radio' | 'tabs' | 'nav'
  ariaLabel,
  fullWidth = false,
  pillHeight,             // '100%' | number | px-string — see DEFAULT_PILL_HEIGHT
  measureContent = false, // false (default) = highlight tracks the OPTION BUTTON's
                          // own box; true = tracks the inner content span instead
                          // (opt-in for a highlight smaller than its button — e.g.
                          // TabBar's fixed 68x44 pill inside a wider flex cell).
                          // Default is the button because a percentage `width:100%`
                          // on the content span cannot fill a button whose own
                          // width is intrinsic/shrink-to-fit (e.g. PageTopControls'
                          // pills) — percentages against an indefinite size resolve
                          // as `auto`, collapsing the span (and thus the highlight)
                          // to the text's own width instead of the button's.
  renderOption,
  optionClassName,
  optionStyle,
  optionContentStyle,
  highlightClassName,
  highlightStyle,
  className = '',
  style,
}) {
  const containerRef = useRef(null)
  const buttonRefs = useRef([])
  const contentRefs = useRef([])
  const measureRefs = measureContent ? contentRefs : buttonRefs
  const hasMountedRef = useRef(false)

  // -1 (no match) is a legitimate state, NOT a bug to floor to 0 — e.g.
  // PageTopControls' theme pill only lists 'github-light'/'github-dark';
  // on ayu-light/synthwave-84 NEITHER button should read as selected (see
  // that component's docblock). Handled explicitly below (hides the
  // highlight; every option stays keyboard-reachable rather than roving to
  // a single, now-nonexistent, active tab stop).
  const activeIndex = options.findIndex((o) => o.value === value)
  const resolvedPillHeight = pillHeight ?? DEFAULT_PILL_HEIGHT[size] ?? '100%'

  const [rect, setRect] = useState(null) // { x, width, animate } | null until first measured

  const measure = useCallback((animate) => {
    const container = containerRef.current
    const el = measureRefs.current[activeIndex]
    if (!container || !el) return
    const cRect = container.getBoundingClientRect()
    const eRect = el.getBoundingClientRect()
    // `left:0` on the absolutely-positioned highlight resolves against the
    // container's PADDING box, but getBoundingClientRect deltas are measured
    // border-box-to-border-box — subtract the container's own left border
    // width so a bordered track (e.g. PageTopControls' pill) doesn't shift
    // the highlight right by that border's width.
    const x = eRect.left - cRect.left - container.clientLeft
    const width = eRect.width
    setRect((prev) => {
      // Bail when unchanged: a geometry-correction pass (RO/resize/fonts)
      // landing mid-slide with the SAME target would otherwise still flip
      // `animate:false` and snap an in-flight CSS transition to its end.
      if (prev && Math.abs(prev.x - x) < 0.5 && Math.abs(prev.width - width) < 0.5) return prev
      return { x, width, animate }
    })
  }, [activeIndex, measureRefs])

  // Selection change (or mount) — animate on every run EXCEPT the very first,
  // so the highlight appears already in place with no first-paint slide.
  useLayoutEffect(() => {
    if (activeIndex === -1) {
      // No option matches `value` — hide the highlight entirely rather than
      // leaving it stuck at whatever the last matched position was.
      setRect(null)
      hasMountedRef.current = true
      return
    }
    measure(hasMountedRef.current)
    hasMountedRef.current = true
  }, [measure, activeIndex])

  // Geometry corrections — window resize, web-font load (label reflow), or
  // any option's content box changing size (e.g. a label growing/shrinking
  // on a language switch, which can also shift every LATER option's offset).
  // Always instant (see the animate:false split above).
  useEffect(() => {
    const handle = () => measure(false)
    let ro
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(handle)
      if (containerRef.current) ro.observe(containerRef.current)
      measureRefs.current.forEach((el) => el && ro.observe(el))
    }
    window.addEventListener('resize', handle)
    document.fonts?.ready?.then(handle)
    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', handle)
    }
  }, [measure, options.length, measureRefs])

  function handleSelect(opt) {
    if (opt.value !== value) onChange(opt.value)
  }

  function handleKeyDown(e) {
    if (as === 'nav') return
    if (!NAV_KEYS.includes(e.key)) return
    e.preventDefault()
    e.stopPropagation()
    let nextIndex = activeIndex
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') nextIndex = (activeIndex - 1 + options.length) % options.length
    else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextIndex = (activeIndex + 1) % options.length
    else if (e.key === 'Home') nextIndex = 0
    else if (e.key === 'End') nextIndex = options.length - 1
    const next = options[nextIndex]
    if (!next) return
    onChange(next.value)
    // `.focus()` works regardless of the target's current `tabIndex` value
    // (tabIndex only gates Tab-key reachability, not programmatic focus), so
    // this is safe to call before the roving-tabindex re-render commits.
    buttonRefs.current[nextIndex]?.focus()
  }

  const groupRole = as === 'radio' ? 'radiogroup' : as === 'tabs' ? 'tablist' : undefined
  const optionRole = as === 'radio' ? 'radio' : as === 'tabs' ? 'tab' : undefined
  const centered = variant !== 'underline' && resolvedPillHeight !== '100%'

  const highlightPositionStyle = variant === 'underline'
    ? {}
    : centered
      ? { top: '50%', height: resolvedPillHeight }
      : { top: 0, height: '100%' }

  const highlightTransform = centered
    ? `translateY(-50%) translateX(${rect ? rect.x : 0}px)`
    : `translateX(${rect ? rect.x : 0}px)`

  return (
    <div
      ref={containerRef}
      role={groupRole}
      aria-label={as !== 'nav' ? ariaLabel : undefined}
      data-size={size}
      className={[styles.container, fullWidth ? styles.fullWidth : '', className].filter(Boolean).join(' ')}
      style={style}
      onKeyDown={handleKeyDown}
    >
      <span
        aria-hidden="true"
        className={[
          styles.highlight,
          variant === 'underline' ? styles.highlightUnderline : styles.highlightPill,
          rect && !rect.animate ? styles.noAnimate : '',
          highlightClassName,
        ].filter(Boolean).join(' ')}
        style={{
          ...highlightPositionStyle,
          transform: highlightTransform,
          width: rect ? rect.width : 0,
          visibility: rect ? 'visible' : 'hidden',
          ...highlightStyle,
        }}
      />
      {options.map((opt, i) => {
        const isActive = i === activeIndex
        const content = renderOption ? renderOption(opt, isActive) : defaultRenderOption(opt, isActive)
        const resolvedOptionClassName = typeof optionClassName === 'function' ? optionClassName(opt, isActive) : optionClassName
        const resolvedOptionStyle = typeof optionStyle === 'function' ? optionStyle(opt, isActive) : optionStyle
        const resolvedContentStyle = typeof optionContentStyle === 'function' ? optionContentStyle(opt, isActive) : optionContentStyle
        const a11yLabel = opt.ariaLabel ?? (typeof opt.label === 'string' ? opt.label : undefined)
        return (
          <button
            key={opt.value}
            ref={(el) => { buttonRefs.current[i] = el }}
            type="button"
            role={optionRole}
            aria-checked={as === 'radio' ? isActive : undefined}
            aria-selected={as === 'tabs' ? isActive : undefined}
            aria-current={as === 'nav' && isActive ? 'page' : undefined}
            aria-label={a11yLabel}
            title={opt.title !== undefined ? opt.title : a11yLabel}
            tabIndex={as === 'nav' ? undefined : (activeIndex === -1 || isActive ? 0 : -1)}
            onClick={() => handleSelect(opt)}
            className={[styles.option, resolvedOptionClassName].filter(Boolean).join(' ')}
            style={resolvedOptionStyle}
          >
            <span
              ref={(el) => { contentRefs.current[i] = el }}
              className={styles.optionContent}
              style={resolvedContentStyle}
            >
              {content}
            </span>
          </button>
        )
      })}
    </div>
  )
}
