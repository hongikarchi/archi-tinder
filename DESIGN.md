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
- **Hover lift applies to ALL cards** (including flip cards): `translateY(-4px)`, duration `0.25s` cubic-bezier(0.4,0,0.2,1). NO scale.
- **Hover border (pink at 55% opacity) applies to non-flip cards ONLY.** Flip cards (§3.5.4) omit the border because a static border lingers awkwardly behind a rotating card; lift alone is enough feedback.
- Image fills the card (`width:100%; height:100%; object-fit:cover; position:absolute; inset:0`).
- Bottom gradient overlay is required for legibility:
  `linear-gradient(to top, rgba(0,0,0,0.93) 0%, rgba(0,0,0,0.4) 50%, transparent 100%)`

#### 3.5.2 Card text hierarchy (overlay) — RICH PATTERN (default)

Use this exact rich hierarchy on every image-overlay card. The pattern is:
**title + content-type sub-italic + divider + 2-column info grid**. This
gives cards visual weight and information density without overcrowding the
overlay. Adapt the 2-col content per card type (Created/Saved for boards,
City/Year for projects, etc.).

```jsx
<div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '16px 18px 20px' }}>
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
    {title}      {/* board.name, project.name_en, etc. */}
  </h2>

  <p style={{
    color: 'rgba(255,255,255,0.55)',
    fontSize: 12,
    margin: '0 0 12px',
    fontStyle: 'italic',
  }}>
    {subLabel}   {/* "Curated Board" / "Project" / "Building" — content-type sub-italic */}
  </p>

  <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 12 }} />

  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
    <InfoCol label={leftLabel} value={leftValue} />     {/* "CREATED" / "CITY" */}
    <InfoCol label={rightLabel} value={rightValue} />   {/* "SAVED" / "YEAR" */}
  </div>
</div>
```

Where `InfoCol`:

```jsx
<div style={{ display: 'flex', flexDirection: 'column' }}>
  <span style={{
    color: 'rgba(255,255,255,0.5)',
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: 2,
  }}>
    {label}     {/* "CREATED" / "SAVED" / "CITY" / "YEAR" */}
  </span>
  <span style={{
    color: '#fff',
    fontSize: 13,
    fontWeight: 600,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }}>
    {value}
  </span>
</div>
```

**Rules:**
- Title: 18px / **weight 700** / white / 2-line clamp. **Do NOT exceed 700.**
- Sub-italic: 12px / italic / `rgba(255,255,255,0.55)` / no weight bump. Content-type label only ("Curated Board", "Project", "Building"), NOT metadata.
- Divider: thin 1px line `rgba(255,255,255,0.1)` between sub-italic and info grid.
- Info grid: 2 columns. **Caps label 10px / weight 600 (NOT 700)** with letter-spacing 0.06em + uppercase. Value 13px / weight 600 / white / single-line ellipsis.
- Padding `16px 18px 20px` (slightly more bottom).
- **Do NOT collapse to a single meta line** — that loses the information density that makes cards feel substantive. The 2-col grid is the standard.

**Single-line variant (use sparingly):** for very small cards (< 200px wide) or contexts where 2-col is overkill, fall back to title + sub-italic only (no divider, no grid). This is a downgrade, not the default.

#### 3.5.3 Corner chips (optional, sparing)

**Use chips only when conveying meaningful state — NOT decoration.** When
the same information already appears in the §3.5.2 info grid, do not also
add a chip. Default is no chip; add one only when state is binary and
status-like (private, matched, etc.).

Top-right placement only. Single chip per card (no chip stacking).

**Status: PRIVATE (icon-only, subtle):**

```jsx
{visibility === 'private' && (
  <div style={{
    position: 'absolute', top: 16, right: 16,
    background: 'rgba(0,0,0,0.4)',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    padding: 6,
    borderRadius: '50%',
  }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="rgba(255,255,255,0.85)" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
    </svg>
  </div>
)}
```

- Small circle, subtle dark blur, white-ish lock icon.
- **Public boards show NO chip** — public is the default; only flag the exception.

**Match score (small, subtle):**

```jsx
<div style={{
  position: 'absolute', top: 12, right: 12,
  background: 'rgba(0,0,0,0.55)',
  backdropFilter: 'blur(10px)',
  WebkitBackdropFilter: 'blur(10px)',
  padding: '4px 9px',
  borderRadius: 999,
  fontSize: 11,
  fontWeight: 600,
  color: '#fff',
}}>
  {Math.round(score * 100)}% match
</div>
```

- Subtle dark backdrop, no branded color flood.
- Brand pink is reserved for primary CTAs and accent moments (active states, focus, gradient text). Don't burn it on small chips — that creates visual fatigue.

**Forbidden:**
- Branded color floods on chips (e.g., `rgba(236,72,153,0.85)` filling a corner pill) — too loud, conflicts with the brand-as-accent rule.
- Public/Public-equivalent chips when public is the default state.
- Stacking multiple chips (use one max).
- Decorative chips that repeat info already in §3.5.2 info grid.

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
- **Hover lift YES, hover border NO.** Per §3.5.1, the subtle `translateY(-4px)` lift applies to all cards including flip cards (it's the standard "interactive element" feedback that the rest of the site uses). The pink border is the only hover decoration that's omitted — a static border lingers awkwardly behind the rotating card during and after the flip. Lift alone is sufficient. Apply the lift on the OUTER perspective wrapper so it doesn't double-compose with the inner rotation.

**Hero Flip variant (text-on-surface, profile pages):** The same rotateY mechanics
apply to text-only flip cards used in profile heros. Front face shows a primary
intro layer (italic bio for users, italic description for offices). Back face
reveals a secondary identity layer (persona styles+programs+one-liner for users;
extended description + founded year + location for offices). Same `perspective:
1200`, `transformStyle: preserve-3d`, `transition: transform 0.5s
cubic-bezier(0.4, 0, 0.2, 1)`, `backfaceVisibility: hidden`, lift YES on outer
wrapper, no border. Surface is `var(--color-surface)` with subtle
`var(--color-border-soft)` outline (NOT the §3.5.1 transparent-default rule —
text-on-surface cards keep their resting outline because they have no image to
provide visual containment). Optional internal radial-gradient pink glow as a
hint of brand. A `tap to reveal` caption in caps label (10/600 letter-spacing
0.04em) at the bottom-right or top-right signals interactivity.

#### 3.5.6 Reference: SwipePage card is canonical

The full-screen swipe card on `frontend/src/pages/SwipePage.jsx` is the
**canonical card text reference** for the entire app. Its overlay text uses
the same primitives codified in §3.5.2:

```jsx
<h2 style={{ color:'#fff', fontSize:18, fontWeight:700, lineHeight:1.3, margin:'0 0 3px', /* 2-line clamp */ }}>
  {card.title}
</h2>
<p style={{ color:'rgba(255,255,255,0.55)', fontSize:12, margin:'0 0 12px', fontStyle:'italic' }}>
  {card.architects}
</p>
```

When in doubt about typography on any other card surface (project cards in
FirmProfile, board cards in UserProfile, recommendation cards in
PostSwipeLanding, building cards in BoardDetail), open SwipePage.jsx and
mirror its overlay text style. The full-screen size differs but **font size,
weight, italic, color, and spacing should match exactly** so all card
surfaces in the app feel like the same design system.

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

**Mandatory scroll indicators (chevron arrows):**
The horizontal back gallery MUST surface scroll affordance — without an explicit
hint users do not realize they can swipe across photos (and hidden scrollbars
remove the only browser-native cue). Place two static chevrons on the left and
right edges, vertically centered, layered above the scroll container with
`pointerEvents: 'none'` so they don't block touch.

```jsx
{/* Left scroll indicator */}
<div style={{
  position: 'absolute', left: 10, top: '50%',
  transform: 'translateY(-50%)',
  pointerEvents: 'none',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  width: 32, height: 32, borderRadius: '50%',
  background: 'rgba(0,0,0,0.32)', backdropFilter: 'blur(6px)',
  zIndex: 2,
}}>
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
       stroke="rgba(255,255,255,0.85)" strokeWidth="2.5"
       strokeLinecap="round" strokeLinejoin="round">
    <polyline points="15 18 9 12 15 6" />
  </svg>
</div>
{/* Right scroll indicator — mirror */}
<div style={{ position: 'absolute', right: 10, top: '50%', /* …same */ }}>
  <svg ...><polyline points="9 18 15 12 9 6" /></svg>
</div>
```

- Mirror SwipePage's gallery-face arrow style (which uses top/bottom for
  vertical scroll); only the orientation flips for horizontal context.
- Subtle dark-blur disc (32px, `rgba(0,0,0,0.32)`) gives the chevron contrast
  against any underlying image.
- 18px chevron, stroke `rgba(255,255,255,0.85)`.
- Static (do not auto-hide on edge) for v1 — simple is enough.

**Action bar gradient softening:**
The persistent action bar at the bottom MUST blend smoothly into the gallery
above it. A hard cut (e.g. opaque action bar starting abruptly) breaks the
cinematic feel users expect from the front face's bottom-gradient overlay.

```jsx
<div style={{
  padding: '20px 16px 16px',
  background: 'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.65) 45%, rgba(0,0,0,0.18) 80%, transparent 100%)',
}}>
  {/* "View Gallery · N photos" pill */}
</div>
```

- Multi-stop gradient (4 stops) so the fade reaches transparent over a longer
  range than the single-stop `0.95 20% → transparent 100%` shorthand.
- Top of the action bar dissolves into the last image; bottom is opaque enough
  to support the action button's contrast.
- Match the front face's `linear-gradient(to top, rgba(0,0,0,0.93) 0%,
  rgba(0,0,0,0.4) 50%, transparent 100%)` aesthetic — same direction, similar
  curve, slightly higher opacity at the base because the action bar lives there.

### 3.6 Profile Action Row (Instagram pattern)

Profile pages (`UserProfilePage`, `FirmProfilePage`) display a Follow / Following
toggle as the primary action when viewing OTHER users' / offices' profiles.
This mirrors Instagram's profile action row to leverage learned behavior.

**Layout:**
- A horizontal row directly below the hero block (or below the inline stats
  row, depending on hero composition).
- Primary button (Follow / Following) takes the major share; optional secondary
  Message icon-button sits beside it.
- Full-width on mobile (≤ 640 px); on desktop, max-width 320 + 44px message
  button to keep the row visually tight.
- Hidden entirely when `isMe` (own profile) — the row is only meaningful for
  cross-user / cross-office views.

**State machine:**

| State | Background | Text color | Border | Trailing icon |
|---|---|---|---|---|
| `Follow` (default) | `linear-gradient(135deg, #ec4899, #f43f5e)` | `#fff` | none | none |
| `Following` (after click) | `var(--color-surface)` (or `var(--color-surface-2)`) | `var(--color-text-2)` | `1px solid var(--color-border)` | chevron-down `▼` (12px stroke 2) |

```jsx
<button
  onClick={handleToggleFollow}
  onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
  onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
  onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.98)' }}
  onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-1px)' }}
  style={{
    flex: 1,
    minHeight: 44, padding: '12px 18px',
    borderRadius: 12,
    background: isFollowing ? 'var(--color-surface-2)' : 'linear-gradient(135deg, #ec4899, #f43f5e)',
    color: isFollowing ? 'var(--color-text-2)' : '#fff',
    border: isFollowing ? '1px solid var(--color-border)' : 'none',
    fontSize: 14, fontWeight: 700,
    cursor: 'pointer', fontFamily: 'inherit',
    boxShadow: isFollowing ? 'none' : '0 8px 22px rgba(236,72,153,0.32)',
    transition: 'transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s, color 0.2s, box-shadow 0.2s',
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  }}
>
  {isFollowing ? (
    <>Following<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg></>
  ) : 'Follow'}
</button>

{/* Optional Message icon button — ghost style */}
<button
  onClick={handleMessage}
  aria-label="Message"
  style={{
    width: 44, height: 44, minWidth: 44, flexShrink: 0,
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 12, cursor: 'pointer',
    color: 'var(--color-text-2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'border-color 0.18s, color 0.18s',
  }}
  onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(236,72,153,0.45)'; e.currentTarget.style.color = '#ec4899' }}
  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text-2)' }}
>
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
</button>
```

- Wrap the row in `<div style={{ display: 'flex', gap: 10, marginTop: 14 }}>`.
- Press `scale(0.98)`; hover `translateY(-1px)`. Both transitions cubic-bezier(0.4, 0, 0.2, 1).
- The Following state's chevron-down hints at the future "tap to unfollow / mute"
  sheet (mockup-only; an actual sheet ships when backend is wired).
- TODO(claude) marker on the toggle handler for the actual `POST /api/v1/users/{id}/follow/`
  / `DELETE` call.

**When `isMe` is true:** omit the entire row. The hero already shows external-link
pills (Instagram, email) and the sticky-header right-side controls (theme + logout)
cover settings — no Follow button is needed.

### 3.7 Compact stats row (Instagram pattern)

When stats live in the hero block (not as a separate StatsCard), use this
inline horizontal pattern instead of the larger 28px-number card. Three columns
divided by 1px vertical lines: Posts/Boards/Projects · Followers · Following.

```jsx
<div style={{
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  gap: 0, marginTop: 14, marginBottom: 18,
}}>
  {[
    { count: boards.length, label: 'Boards' },
    { count: followerCount, label: 'Followers' },
    { count: followingCount, label: 'Following' },
  ].map((stat, i, arr) => (
    <>
      <button key={stat.label} style={{
        flex: '0 0 auto',
        background: 'transparent', border: 'none', cursor: 'pointer',
        padding: '6px 18px', minHeight: 44,
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
        fontFamily: 'inherit', color: 'inherit',
      }}>
        <span style={{ color: 'var(--color-text)', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>
          {stat.count}
        </span>
        <span style={{ color: 'var(--color-text-dim)', fontSize: 12, fontWeight: 500 }}>
          {stat.label}
        </span>
      </button>
      {i < arr.length - 1 && (
        <div style={{ width: 1, height: 28, background: 'var(--color-border)' }} />
      )}
    </>
  ))}
</div>
```

- 18px / weight 700 number + 12px / weight 500 label (NOT caps — natural case
  for visual rhythm with the rest of the hero).
- 28px-tall vertical 1px dividers.
- Each stat is a button (44px touch) — tappable for the Followers/Following
  list when backend exposes those endpoints. Add TODO(claude) markers for
  click handlers.
- Uses the same pink accent NOT as a fill but as the page's ambient halo —
  the row sits inside that halo so it picks up brand presence indirectly.

### 3.8 Font-weight discipline (site-wide)

**700 maximum anywhere in the app.** No 800. No 900.

| Use | Weight |
|---|---|
| Hero h1, page titles, section h2 / h3 | 700 |
| Card titles (overlay or surface) | 700 (per §3.5.2) |
| Button labels, subtle sub-labels | 600 |
| Body paragraphs, descriptions | 500 |
| Caps labels, value lines | 600 |
| Inactive nav items | 400 |

The brand voice is "premium, sleek, confident" — that's achieved by tight letter-spacing
and a restrained gradient palette, NOT by display-weight type. 800 / 900 weights
look heavy and dated; the site reads as more sophisticated when constrained to 700.

This rule applies to every page, including `LoginPage`, `SetupPage`, `MainLayout`'s
empty-swipe state, `SwipePage`'s sticky header, and `FavoritesPage`'s legacy
sections. Any 800 / 900 weight you encounter while editing is drift — drop it
to 700 (or 600 if context calls for restraint).

## 4. Interaction Patterns
- **Desktop Mode:** Ensure swiping logic binds to `keydown` (`ArrowLeft`, `ArrowRight`).
- **Hover States:** Apply `cursor: 'pointer'` to interactables. For hover colors, use React inline event handlers (`onMouseEnter`, `onMouseLeave`)
- **Skeleton Loaders:** Do not block existing cards. Use overlay spinners on top of stale data instead of tearing down the UI to show a skeleton.
