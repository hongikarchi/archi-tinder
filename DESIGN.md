# ArchiTinder Design System

> This is the source of truth for all frontend styling. The **design pipeline**
> (`designer` agent + any `design-*` sub-agents in the design terminal) is the
> exclusive writer of this file. All other agents (main pipeline's `front-maker`,
> `orchestrator`, etc., and the review terminal's `/review`) MUST consult and follow
> these rules when reading or modifying frontend components, but are READ-ONLY on this
> file itself. See `.claude/agents/designer.md` and `CLAUDE.md ## Rules` for the full
> ownership boundary.

## Core Philosophy
- **Aesthetics First:** Premium, cinematic dark mode with vibrant neon accents.
- **Vibe:** Modern, sleek, glassmorphic, fluid, gesture-friendly.
- **Implementation:** React inline styles. NO Tailwind CSS. NO external UI libraries (like Material-UI or Chakra). Use raw HTML elements with inline `style={{...}}` objects.

## 1. Color Palette

### 1.1 Base Theme (Dark Mode Default)
*The app relies on CSS variables defined in `index.css` for structural colors.*
- **Background:** `var(--color-bg)` (`#0f0f0f`)
- **Surface/Cards:** `var(--color-surface)` (`#1a1a1a`), `var(--color-surface-2)` (`#1c1c1c`)
- **Borders:** `var(--color-border)` (`rgba(255,255,255,0.07)`), `var(--color-border-soft)` (`rgba(255,255,255,0.1)`)

### 1.2 Accent Colors (Hardcoded Inline)
*These MUST be hardcoded directly into inline styles, NOT read from CSS vars.*
- **Primary Brand (Hot Pink):** `#ec4899` (Used for active tabs, selected states, Save actions)
- **Secondary Accent (Rose):** `#f43f5e` (Used exclusively alongside Primary for gradients)
- **Primary Gradient:** `linear-gradient(135deg, #ec4899, #f43f5e)` (Used for main call-to-action buttons like 'Generate Report')
- **Destructive/Skip (Red):** `#ef4444` (Used for Skip/Dislike actions)

### 1.3 Text Colors
- **Primary Text:** `var(--color-text)` (`#ffffff`)
- **Secondary Text:** `var(--color-text-2)` (`#e2e8f0`)
- **Muted/Placeholder:** `var(--color-text-muted)` (`#9ca3af`)

## 2. Layout & Spacing

### 2.1 Viewport constraints
- The app is designed to prevent window scrolling. 
- `body` has `overflow: hidden`.
- Pages must take full height minus TabBar: `height: calc(100vh - 64px - env(safe-area-inset-bottom))`
- **TabBar Height:** `64px` fixed at the bottom.

### 2.2 Mobile Optimization (Crucial)
- Always include iOS Safe Area constraints:
  - `paddingBottom: 'env(safe-area-inset-bottom)'` on scrollable containers or TabBars.
- Minimum touch target for clickable elements (buttons, back arrows) must be **44px** (Apple HIG requirement).
- Border Radiuses:
  - Cards: `20px` to `24px`
  - Buttons/Tags: `8px` to `12px`

## 3. Component Stylings

### 3.1 Buttons
**Primary CTA Button:**
```jsx
<button style={{
  background: 'linear-gradient(135deg, #ec4899, #f43f5e)',
  color: '#fff',
  fontWeight: 600,
  padding: '16px 24px',
  borderRadius: '12px',
  border: 'none',
  minHeight: '44px',
  cursor: 'pointer'
}}>
  Complete Setup
</button>
```

### 3.2 Glassmorphic Inputs / Search Bars
```jsx
<input style={{
  backgroundColor: 'rgba(25, 28, 33, 0.95)', 
  border: '1px solid rgba(255, 255, 255, 0.1)',
  backdropFilter: 'blur(10px)',
  color: '#ffffff',
  borderRadius: '16px',
  padding: '16px',
}} />
```
**Focus State:** Inject logic to change `borderColor` to `#ec4899` `onFocus`.

### 3.3 Text & Typography constraints
- Component titles are extremely prone to overflow on mobile devices.
- Always apply absolute CSS clamping for Card titles:
```jsx
<h2 style={{
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  textOverflow: 'ellipsis'
}}>Building Title</h2>
```

### 3.4 Overlays (Modals, Tutorials)
- Do NOT use solid blocks.
- Use Semi-Transparent Blur Overlays to maintain immersion.
- Example Backdrop:
```jsx
<div style={{
  background: 'rgba(10, 10, 12, 0.65)',
  backdropFilter: 'blur(12px)',
  paddingBottom: 'env(safe-area-inset-bottom)'
}}>
  {children}
</div>
```

## 4. Interaction Patterns
- **Desktop Mode:** Ensure swiping logic binds to `keydown` (`ArrowLeft`, `ArrowRight`).
- **Hover States:** Apply `cursor: 'pointer'` to interactables. For hover colors, use React inline event handlers (`onMouseEnter`, `onMouseLeave`)
- **Skeleton Loaders:** Do not block existing cards. Use overlay spinners on top of stale data instead of tearing down the UI to show a skeleton.
