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

### 3.5 Card System (Core)

Cards are the primary content carrier across the app — projects, boards,
buildings, recommendations all share the same structural shape. **Differences
are content (chips, text), not structure.** Use these primitives consistently
on every card surface to keep visual unity across pages.

#### 3.5.1 Image-overlay card (default)

Used for: project cards, board cards, building cards, recommendation cards.
Standard aspect ratios: 4:5 (portrait grid) or 3:4 (slightly wider).

```jsx
<div style={{
  background: 'rgba(255,255,255,0.03)',
  borderRadius: 20,
  overflow: 'hidden',
  cursor: 'pointer',
  border: '1px solid transparent',          // NO default light border
  position: 'relative',
  boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
  transition: 'transform 0.25s cubic-bezier(0.4,0,0.2,1), border-color 0.25s cubic-bezier(0.4,0,0.2,1)',
}}
onMouseEnter={e => {
  e.currentTarget.style.transform = 'translateY(-4px)'
  e.currentTarget.style.borderColor = 'rgba(236,72,153,0.55)'
}}
onMouseLeave={e => {
  e.currentTarget.style.transform = 'translateY(0)'
  e.currentTarget.style.borderColor = 'transparent'
}}>
  {/* image fill + bottom gradient + text overlay + optional corner chip */}
</div>
```

**Mandatory rules:**
- **NO default light border.** The border lives only in hover state (brand pink at 55% opacity). Resting state is `transparent`.
- Always include `boxShadow: '0 10px 25px rgba(0,0,0,0.3)'` for depth in dark mode.
- Hover behavior: lift `-4px` AND border to brand pink. Duration `0.25s` cubic-bezier(0.4,0,0.2,1). NO scale.
- Image fills the card (`width:100%; height:100%; object-fit:cover; position:absolute; inset:0`).
- Bottom gradient overlay is required for legibility:
  `linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)`

#### 3.5.2 Card text hierarchy (overlay)

Use this exact hierarchy on every image-overlay card overlay. No additional
chips below the meta line — the overlay stays simple and scannable.

```jsx
<div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: '16px 18px 20px' }}>
  <h2 style={{
    color: '#fff',
    fontSize: 18,
    fontWeight: 700,
    lineHeight: 1.3,
    margin: '0 0 3px',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  }}>
    {title}
  </h2>
  <p style={{
    color: 'rgba(255,255,255,0.55)',
    fontSize: 12,
    fontStyle: 'italic',
    margin: 0,
  }}>
    {meta}      {/* "OMA · 2004" or "Seattle · 2004" or "Kim Minseo" */}
  </p>
</div>
```

- Title: 18px, weight 700, white, **2-line clamp**.
- Meta: 12px, italic, `rgba(255,255,255,0.55)` — secondary info (architect · year, year · city, owner display_name, etc.).
- Padding `16px 18px 20px` (slightly more bottom).

#### 3.5.3 Corner chips (optional)

Top-right placement only. Single chip per card (no chip stacking).

```jsx
<div style={{
  position: 'absolute',
  top: 12,
  right: 12,
  background: 'rgba(0,0,0,0.45)',
  backdropFilter: 'blur(10px)',
  WebkitBackdropFilter: 'blur(10px)',
  padding: '6px 10px',
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 700,
  color: '#fff',
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
}}>
  {label}
</div>
```

**Variants by purpose:**
- **Default (program label, year):** background `rgba(0,0,0,0.45)` + blur, white text.
- **Branded (PUBLIC, match score):** background `rgba(236,72,153,0.85)` + blur, white text.
- **Destructive (PRIVATE):** background `rgba(239,68,68,0.85)` + blur, white text.

#### 3.5.4 Flip card (3D rotateY)

Used for: board cards (front: cover; back: gallery), persona card (front: type
label; back: full detail). Click flips, click again unflips.

```jsx
<div
  style={{ perspective: '1200px', cursor: 'pointer', /* outer dimensions */ }}
  onClick={e => {
    if (e.target.closest('button')) return       // let nested buttons through
    setIsFlipped(f => !f)
  }}
>
  <div style={{
    width: '100%', height: '100%',
    position: 'relative',
    transition: 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
    transformStyle: 'preserve-3d',
    transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
  }}>
    <div style={{
      position: 'absolute', inset: 0,
      backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
      borderRadius: 20, overflow: 'hidden',
    }}>
      {/* FRONT — image-overlay card per §3.5.1 */}
    </div>
    <div style={{
      position: 'absolute', inset: 0,
      backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
      transform: 'rotateY(180deg)',
      borderRadius: 20, overflow: 'hidden',
    }}>
      {/* BACK — see §3.5.5 for image gallery */}
    </div>
  </div>
</div>
```

- `perspective: '1200px'` on the outer element.
- `transformStyle: 'preserve-3d'` on the rotating layer.
- Both faces use `backfaceVisibility: 'hidden'` (+ `-webkit-` prefix).
- Stop propagation for nested buttons via `e.target.closest('button')` early-return.

#### 3.5.5 Card-back: swipe-style image gallery

When a flip card's back reveals multiple images (boards), use **full-bleed
horizontal-scrolling images styled like the SwipePage card — NOT a thumbnail
grid.** This preserves the cinematic feel of the brand's signature swipe
interaction.

```jsx
<div style={{
  position: 'absolute', inset: 0,
  background: '#000',
  display: 'flex',
  flexDirection: 'column',
}}>
  <div
    style={{
      flex: 1,
      overflowX: 'auto',
      overflowY: 'hidden',
      display: 'flex',
      scrollSnapType: 'x mandatory',
      WebkitOverflowScrolling: 'touch',
      scrollbarWidth: 'none',          // Firefox
      msOverflowStyle: 'none',         // IE/Edge legacy
    }}
    className="hide-scrollbar"          /* Webkit ::-webkit-scrollbar { display:none } */
  >
    {images.map((img, i) => (
      <div key={i} style={{
        flex: '0 0 100%',
        height: '100%',
        scrollSnapAlign: 'start',
        position: 'relative',
      }}>
        <img src={img} alt="" style={{
          width: '100%', height: '100%',
          objectFit: 'cover',
          display: 'block',
        }} />
      </div>
    ))}
  </div>

  {/* Persistent action bar at bottom */}
  <div style={{
    padding: 16,
    background: 'linear-gradient(to top, rgba(0,0,0,0.95) 20%, transparent 100%)',
  }}>
    <button style={{ /* "View Gallery · N photos" pill, full-width 44px+ touch */ }}>
      View Gallery · {images.length} photos
    </button>
  </div>
</div>
```

- `scroll-snap-type: x mandatory` snaps cleanly per image.
- Each slide is `flex: 0 0 100%` so the card width = one image at a time.
- Hide scrollbar across browsers (Firefox `scrollbarWidth: 'none'`, Webkit via class with `::-webkit-scrollbar { display: none }`, IE legacy `msOverflowStyle: 'none'`). Add the `.hide-scrollbar` class to `index.css` if it doesn't exist.
- Action button persists at the bottom — does not scroll with images.

## 4. Interaction Patterns
- **Desktop Mode:** Ensure swiping logic binds to `keydown` (`ArrowLeft`, `ArrowRight`).
- **Hover States:** Apply `cursor: 'pointer'` to interactables. For hover colors, use React inline event handlers (`onMouseEnter`, `onMouseLeave`)
- **Skeleton Loaders:** Do not block existing cards. Use overlay spinners on top of stale data instead of tearing down the UI to show a skeleton.
