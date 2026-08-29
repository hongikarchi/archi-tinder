# ArchiTinder Design System

> This is the **single source of truth** for the ArchiTinder frontend design
> system. Anyone touching `frontend/` UI — JSX, layout, colors, animations,
> typography — MUST consult this file before writing code. The design system
> is load-bearing; deviations require explicit justification in the PR
> description.
>
> Editorial rights: admin-owned via PR (sibling of `CLAUDE.md`). Reporter
> updates are not applicable here. Other agents (`front-maker`, `code-review`,
> `app-test` (Claude) / `browser-verify` (Codex)) read but never write.
>
> **Adopted 2026-05-21 — full redesign.** Light-mode default, 4 user-selectable
> themes + theme switcher, font switcher, CSS-variable design tokens
> (`frontend/src/tokens.css`), CSS Modules + CSS `:hover` for interactive
> components. Rolled out across a multi-PR initiative — early PRs introduce the
> token/theme system; component visuals migrate per-PR afterward.

---

## Glossary

Mapping between **design-system terms** (code/docs) and **user-facing labels**
(what the user sees on screen). Consult this table first when a term is
ambiguous or you do not know what to search for in code.

| User term (UI label) | Design-system term (code/docs) | Defined in |
|---|---|---|
| **Board** | Folder Card | §8.7 |
| **Project** | Project Card | §8.6 |

> When a new term mapping appears, add a row here. The spec itself is managed in
> the relevant § section.

---

## 1. Color Tokens

**Default theme: GitHub Light.** Users can freely change the theme with the
theme switcher (see §5).

### 1.1 Surface & Text
```yaml
bg:         "#FFFFFF"
surface:    "#F6F8FA"
surface-2:  "#EFF2F5"
surface-3:  "#E1E4E8"
text:       "#1F2328"
text-2:     "#24292F"
text-muted: "#656D76"
text-dim:   "#8C959F"
border:     "rgba(0,0,0,0.08)"
border-soft: "rgba(0,0,0,0.12)"
```

### 1.2 Accent (themed)
```yaml
accent-1:   "#0969DA"
accent-2:   "#8250DF"
accent-3:   "#953800"
```

### 1.3 Destructive / Skip (themed)
**Each theme defines a red tone that fits its light/dark character.**
Current default (GitHub Light):
```yaml
destructive: "#D73A49"
```
Other themes (the theme switcher changes this in lockstep):
- Ayu Light → `#E5524B`
- GitHub Dark → `#F85149`
- SynthWave '84 → `#FF6188`

### 1.4 Scrim (themed)
Black-alpha overlay family for **content-over-content separation** — modal /
dialog backdrops and the opaque end of photo-caption gradients. Not for
shadows (see §8.6 `card-shadow`, which stays a literal box-shadow).

| Token | Purpose |
|---|---|
| `--color-scrim-strong` | heaviest overlay — opaque end of a photo-caption gradient, darkest modal backdrops |
| `--color-scrim` | standard modal / dialog backdrop |
| `--color-scrim-soft` | lighter backdrop / hover veil |
| `--color-scrim-faint` | barely-there wash — near-transparent end of a gradient |

Current default (GitHub Light):
```yaml
scrim-strong: "rgba(0,0,0,0.93)"
scrim:        "rgba(0,0,0,0.65)"
scrim-soft:   "rgba(0,0,0,0.55)"
scrim-faint:  "rgba(0,0,0,0.12)"
```
Other themes (the theme switcher changes this in lockstep):
- Ayu Light → same as GitHub Light (light ground, black-alpha reads correctly as-is)
- GitHub Dark → alpha raised (`0.94 / 0.78 / 0.68 / 0.18`) — a black veil over an
  already-dark ground (`#0d1117`) needs more opacity to still read as
  "deepening further"
- SynthWave '84 → alpha raised **and** tinted toward the theme's own
  purple-navy ground (`rgba(26,22,37,…)` instead of neutral black) — a neutral
  black scrim over this hue reads as muddy grey rather than a deepening

---

## 2. Typography

**Default body font: IBM Plex Sans KR.** Users can switch to Noto Serif KR with
the Font toggle (see §6).

### 2.1 Font Family
```yaml
font-family:        "IBM Plex Sans KR"
font-stack:         '"IBM Plex Sans KR", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "맑은 고딕", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
font-stack-serif:   '"Noto Serif KR", "본명조", "Nanum Myeongjo", "나눔명조", "AppleMyungjo", "Batang", "바탕", Georgia, serif'
```

**Fallback policy** — guarantees Korean glyph availability per environment:
1. **Primary**: web font (loaded from Google Fonts)
2. **Web fallback**: Noto Sans KR (Sans) / Nanum Myeongjo (Serif) — more likely
   to be cached already
3. **macOS / iOS**: Apple SD Gothic Neo (Sans) / AppleMyungjo (Serif)
4. **Windows**: Malgun Gothic (Sans) / Batang (Serif)
5. **Last resort**: `system-ui` / `Georgia` / `sans-serif` / `serif`

Korean names (`맑은 고딕`, `본명조`, etc.) are listed alongside the English
names in case the OS locale fails to match the English name.

### 2.2 Type Scale — Desktop (≥ 769px)
```yaml
h1-size-desktop:      48
h2-size-desktop:      30
body-size-desktop:    18
caption-size-desktop: 14
```

### 2.3 Type Scale — Mobile (≤ 768px)
```yaml
h1-size-mobile:      32
h2-size-mobile:      24
body-size-mobile:    16
caption-size-mobile: 13
```

### 2.4 Weights (shared across environments)
```yaml
h1-weight:      700
h2-weight:      600
body-weight:    400
caption-weight: 500
```

### 2.5 Font-weight discipline
**Maximum 700. 800/900 forbidden.** The "premium, sleek, confident" tone is
expressed through letter-spacing, whitespace, and palette — not weight.

### 2.5a Single-font policy
- **Headings, body, and captions all use the same font family** (no dual-font
  operation).
- Hierarchy is expressed only via size + weight + letter-spacing + whitespace.
- The Font toggle (§6) switches the whole system at once — no partial switching.
- Pairings like editorial serif headings + sans body are deliberately excluded
  → simpler mental model, consistent user toggle behavior.

### 2.6 Legacy aliases (gradual migration)
```yaml
h1-size:      48   # → h1-size-desktop
h2-size:      30   # → h2-size-desktop
body-size:    18   # → body-size-desktop
caption-size: 14   # → caption-size-desktop
```

---

## 3. Layout & Shape

### 3.1 Border Radius Scale (tokenized)
```yaml
radius-sm:   8     # small chips, inputs
radius-md:   12    # buttons, small cards
radius-lg:   20    # default card
radius-xl:   24    # large cards, modals
radius-pill: 999   # pill shape
```

### 3.2 Touch Target (per device)
```yaml
touch-target-mobile:  44    # Apple HIG recommendation
touch-target-desktop: 32    # exploits mouse precision
```

### 3.3 TabBar Height (conditional)
```yaml
tabbar-height-with-label: 64    # icon + keyword (current default)
tabbar-height-icon-only:  56    # icon only
tabbar-height:            64    # value currently in use
```
> ⚠️ If nav labels are removed during development, change `tabbar-height` to 56.

### 3.4 Legacy aliases (gradual migration)
```yaml
radius-card:    20   # → radius-lg
radius-button:  12   # → radius-md
```

### 3.5 Motion Tokens
All transitions use only the tokens below. Inline ms / cubic-bezier hardcoding
is forbidden.

**Duration (4 tiers)**
```yaml
motion-fast:    180ms   # micro: hover, focus border, chip toggle, filter
motion-normal:  220ms   # standard: transforms, lifts (most frequently used)
motion-slow:    400ms   # fade-outs: glow dispersion, color shift
motion-flip:    500ms   # heavy: Discovery card 3D rotateY flip
```

**Easing (2)**
```yaml
motion-ease:     cubic-bezier(0.4, 0, 0.2, 1)   # most transforms/lifts (Material standard)
motion-ease-out: cubic-bezier(0, 0, 0.2, 1)     # decelerate fade (glow disappearing, etc.)
```

**Click-moment exception**
Instant display at the click moment (0s) — e.g. glow — keeps a literal `0s`
without a token. "Instant" is an intent, not a timing.

**Usage example**
```css
.button       { transition: transform var(--motion-normal) var(--motion-ease); }
.input        { transition: border-color var(--motion-fast),
                            box-shadow   var(--motion-slow) var(--motion-ease-out); }
.input:active { transition: box-shadow 0s; }   /* click moment — instant */
.card-flip    { transition: transform var(--motion-flip) var(--motion-ease); }
```

---

## 4. Design Philosophy

- **Aesthetics — tone split by mode**
  - **Light themes** (GitHub Light · Ayu Light): **Clear · Editorial ·
    Content-first.** Restrained backgrounds that do not obscure architecture
    imagery, clear text hierarchy, sharp typography. Restrained shadows +
    consistent surfaces = the tone of a magazine / archive.
  - **Dark themes** (GitHub Dark · SynthWave '84): **Cinematic · Atmospheric ·
    Dramatic.** Deep backgrounds that make imagery glow, rich contrast,
    glow/neon accents. Deeper shadows + atmospheric gradients = the tone of a
    film / a gallery at night.
  - Both tones keep the common denominator "premium, refined, confident." The
    mode difference is expressed in contrast and atmosphere.
- **Vibe**: `glassmorphic` · `fluid` · `gesture-friendly (swipe hint only)` —
  all adopted.
  - Glassmorphic: `backdrop-filter: blur(12px)` on headers, input bars, gallery
    hints, etc.
  - Fluid: `translateY(-3px)` + 0.22s transition on card/button hover.
  - Gesture-friendly: a "← swipe ✕ · swipe ♥ →" hint at the top of Discovery
    cards (the action buttons themselves are not emphasized).
- **Implementation — CSS variables + Inline hybrid**
  - **CSS variables own**: themeable values — color, font, spacing tokens,
    motion tokens, radius, etc. (see §3.5 motion, §1 color).
  - **Inline styles own**: fixed / one-dimensional values — one-off layout,
    dynamically computed values, emphasis gradients.
  - **Forbidden**: Tailwind, Bootstrap, MUI, Chakra, styled-components, emotion,
    and other external UI / CSS-in-JS libraries.
  - **Allowed**: plain CSS files (`tokens.css`, see §10.2), CSS Modules.
  - Rationale: editing a token applies a consistent change everywhere + zero
    runtime overhead + minimal bundle size.
- **Hover implementation**: visual transitions (color, shadow, transform) use
  **only the CSS `:hover` pseudo-class.** The inline `onMouseEnter/Leave` +
  React-state pattern is retired — performance and simplicity first.
- **Theme switching**: only explicit user choice is honored. No automatic
  `prefers-color-scheme` switching.
- **Line-clamp**: 2-line clamp applies only to card titles. Other text wraps
  naturally.

---

## 5. Theme Switcher (end-user facing)

ArchiTinder provides a feature that lets **the user freely choose a color
theme.**

### 5.1 Exposure
- The theme selection button is a chip composed of a **background color +
  accent color**.
- Each chip visually previews its theme's background + accent.
- Clicking switches instantly (no page reload).

### 5.2 Chip Spec (example)
```yaml
chip-bg-preview-size:     20    # diameter of the background-color preview circle (px)
chip-accent-preview-size: 12    # diameter of the accent-color preview circle (px, overlapped on the bg)
chip-padding:             "6px 14px"
chip-radius:              999
```

### 5.3 Candidate Themes
- **GitHub Light** ← default
- Ayu Light
- GitHub Dark
- SynthWave '84

### 5.4 Exposure Location
- Exposed inside **Profile tab → Settings section → Appearance**.
- Does not clutter the main UI (header / sidebar) — the theme is not a
  frequently changed setting.
- Same location on mobile and desktop (inside Profile → Settings).

### 5.5 Persistence
- **Stored on the user account (cross-device).**
- Logged-in users: stored as a server-side user preference → the same theme
  applies automatically on other devices.
- Guests: applied only for the session (next visit reverts to the default
  GitHub Light).
- No automatic `prefers-color-scheme` switching (settled in §7).

### 5.6 Labels / Copy
- Section title: **"Appearance"**
- Sub-items: **"Theme"** (theme chip list), **"Font"** (same location as the §6
  font toggle).

---

## 6. Font Switcher (end-user facing)

ArchiTinder also lets the user switch the body font.

### 6.1 Toggle Button — "the button label is itself a preview of the font it will switch to"
- Button label: always the single word **`Font`**.
- The label's **font-family is rendered in the font *other* than the current
  one** → clicking shows directly which font it will switch to.
- Clicking toggles between the two fonts.

### 6.2 State Machine

| Current body font | Button label | Button label's font-family |
|---|---|---|
| IBM Plex Sans KR (default) | `Font` | Noto Serif KR (the font it switches to) |
| Noto Serif KR | `Font` | IBM Plex Sans KR (the font it switches to) |

### 6.3 Candidate Fonts
- **IBM Plex Sans KR** ← default (geometric sans-serif, technical)
- Noto Serif KR (classic serif, editorial)

### 6.4 Exposure Location
**Same as §5.4** — inside Profile → Settings → Appearance, in the same place as
the Theme chips. Per the §5.6 label definitions, placed as the "Font" item
directly below Theme.

---

## 7. Responsive Layout

ArchiTinder is mobile-first but must also behave naturally on desktop.

### 7.1 Mobile (≤ 768px)
- Bottom-fixed nav bar (Search · Discover · Boards · Profile, 4-column grid).
- Page left/right padding 16px.
- Card grid: 2 columns.
- iOS Safe Area support (`padding-bottom: env(safe-area-inset-bottom)`).

### 7.2 Desktop (≥ 769px)
- Left 220px fixed sidebar nav (vertical, icon + label).
- Main content area: no horizontal scroll, max-width 1200px.
- Card grid: 3 columns.
- Page left/right padding 32px.

### 7.3 Breakpoints
```yaml
breakpoint-mobile-max:  768   # ≤ 768px → mobile layout
breakpoint-desktop-min: 769   # ≥ 769px → desktop layout
```

---

## 8. Components

### 8.1 Primary CTA Button
Main action buttons (core CTAs like sign-up / share / purchase).

```css
background: var(--accent-1);
color: #fff;
border: 0;
border-radius: calc(var(--radius-md) * 1px);
padding: 14-16px;
font-weight: 600;
min-height: 44px;
transition: transform 0.22s, background-color 0.22s, box-shadow 0.4s ease-out;
```

> **Changed 2026-08-29 — flat, was `linear-gradient(135deg, var(--accent-1), var(--accent-2))`.**
> User decision during the canvas design port: every one of the 37 Claude Design
> boards draws the primary CTA as flat `var(--accent-1)`; not one uses the
> gradient. The gradient is retired as the CTA background. Existing gradient
> call sites (31 occurrences across 22 files as of this date) migrate to flat
> **inside their own host-page PR**, so each change is seen before it ships —
> not in one sweep. Interaction spec below (`:active` glow, transitions) is
> unchanged. The gradient itself remains valid elsewhere (e.g. decorative
> surfaces); this rule governs the CTA background only.

**Click moment (`:active`) — glow shadow**
Like the input focus pattern (§8.5), the glow appears instantly on click and
fades out over 0.4s.

```css
.primary-cta:active {
  box-shadow: 0 0 0 6px color-mix(in srgb, var(--accent-1) 28%, transparent);
  transition: transform 0.22s, box-shadow 0s;  /* glow appears instantly */
}
```

- When the theme changes, the gradient colors change with it.
- Applied to: Persona "View persona report", Discovery ♥ (Save), AI Search chat
  send ↑.
- Buttons that already have a depth shadow (e.g. Discovery ♥) stack both
  shadows (`0 6px 16px rgba(0,0,0,0.25), 0 0 0 6px ...`).

### 8.2 Secondary Button
Secondary actions (close an option that doesn't resonate, Skip, etc.).

```css
background: var(--surface);
color: var(--text);
border: 1px solid var(--border);
border-radius: calc(var(--radius-md) * 1px);
padding: 14px 16px;
font-weight: 500-600;
min-height: 44px;
```

### 8.3 Ghost Button
Weakest emphasis (Share, View more, etc.).

```css
background: transparent;
color: var(--text);
border: 1px solid var(--border);
border-radius: calc(var(--radius-md) * 1px);
padding: 14px 16px;
font-weight: 500;
min-height: 44px;
```

### 8.4 Destructive Button
Dangerous actions — delete / block / cancel.

```css
background: transparent;
color: var(--destructive);
border: 1px solid var(--destructive);
border-radius: calc(var(--radius-md) * 1px);
padding: 14px 16px;
font-weight: 600;
min-height: 44px;
```

> Whether hover switches to a filled style (`bg: var(--destructive); color:
> #fff`) is decided at the interaction-design stage.

### 8.5 Input (Glassmorphic, 3-state focus)

```css
.input {
  background: color-mix(in srgb, var(--surface) 72%, transparent);
  border: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: calc(var(--radius-pill) * 1px);  /* or radius-md for square inputs */
  padding: 12px 18px;
  color: var(--text);
  transition: border-color 0.18s, box-shadow 0.4s ease-out;
}

.input:focus-within {
  border-color: var(--accent-1);
}

.input:has(input:active) {  /* the brief click moment */
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent-1) 28%, transparent);
  transition: border-color 0.18s, box-shadow 0s;  /* glow appears instantly */
}
```

**3-tier focus states:**
- Default: gray border
- Focused (focus held): accent-1 border (no glow, restrained)
- Click moment (mouse just pressed): accent-1 border + glow shadow → fades out
  smoothly over 0.4s

### 8.6 Project Card (Discovery canonical)
ArchiTinder's core card — combines the image-overlay card, the 3D flip, and the
back-face gallery.

**Front face**
```
+-------------------------------+
|  [project main image]      ↻  |  ← flip hint top-right
|                               |
|                               |
|         (gradient fade)       |
|                               |
| Title (h2, 22px, 700)         |
| Architects (13px italic, 60%) |
| ─────── divider ───────       |
| YEAR  | LOCATION | PROGRAM    |  ← 3-col info grid
| 2004  | Kanazawa | Museum     |
+-------------------------------+
```

```yaml
card-radius: 20         # var(--radius-lg)
card-shadow: "0 12px 32px rgba(0,0,0,0.3)"
card-bottom-gradient: "linear-gradient(180deg, transparent 30%, rgba(0,0,0,0.82))"
card-text-color: "#fff"
card-title: 22px / 700 / line-clamp 2
card-architects: 13px / regular / rgba(255,255,255,0.6)
card-divider: "1px rgba(255,255,255,0.15)"
card-info-label: 10px / 600 / uppercase 0.06em / rgba(255,255,255,0.5)
card-info-value: 13px / 600 / #fff / single-line ellipsis
card-info-columns: 3  # YEAR + LOCATION + PROGRAM
card-info-layout: "flex / justify-content: space-between"
```

**Back face (3D rotateY)**
- Click anywhere on the card → `transform: rotateY(180deg)` on the inner
  wrapper.
- Back face: full-bleed horizontal-scrolling gallery of sub-images.
- `scroll-snap-type: x mandatory` for clean image-per-frame snapping.
- Left/Right chevron arrows (32px, dark blur) as a visual affordance.
- Bottom action: "View Gallery · N photos" pill with a 4-stop gradient backdrop.

```yaml
flip-perspective: 1200px
flip-duration: 0.5s
flip-easing: "cubic-bezier(0.4, 0, 0.2, 1)"
back-action-gradient: "linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.65) 45%, rgba(0,0,0,0.18) 80%, transparent 100%)"
```

**Geometry**
```yaml
card-aspect-ratio: "4 / 5"   # portrait, Tinder-like ratio
                              # mobile: fills screen (flex:1) / desktop: explicit 4/5
```

**Border / Hover policy**
- **No border** — the card edge is expressed only with `radius-lg` +
  `box-shadow: 0 12px 32px rgba(0,0,0,0.3)` (avoids conflict with the
  background image / gradient).
- **No hover effect** — Discovery is a swipe-centric UX; hover is not a natural
  interaction. Card actions happen only through click (flip) / swipe /
  Like·Skip buttons.

**Interaction** — every per-environment input method is supported equally.

| Action | Mobile | Desktop |
|---|---|---|
| **Skip** (← swipe) | left swipe gesture | `ArrowLeft` key OR mouse left-drag OR ✕ button click |
| **Like** (→ swipe) | right swipe gesture | `ArrowRight` key OR mouse right-drag OR ♥ button click |
| **Flip (front ↔ back)** | tap the card photo | `Enter` key OR photo click |

Principles:
- **Drag threshold**: a swipe is confirmed at ≥ 25% of card width of movement;
  below that, spring back to position.
- **Keyboard visibility**: shortcut listeners are bound only while the active
  screen is Discovery (disabled on other screens).
- **Focus state**: explicit focus ring (`:focus-visible`) on cards/buttons for
  keyboard users.

**Text legibility** — the same black gradient fade is applied to both
Front/Back faces. Because white text sits on real project photos (varied
tones), a black fade at the bottom secures contrast. After comparing 8
alternatives (glassmorphic panel / solid scrim / text-shadow / per-element
chips / mix-blend, etc.), the black gradient fade was the most natural, does
not obscure the photo, and gives reliable legibility.

Front:
```css
.discovery-face.front::before {
  content: ""; position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 30%, rgba(0,0,0,0.82));
}
```

Back (the "View Gallery · N photos" action on the gallery face follows the same
principle):
```css
.back-action {
  background: linear-gradient(to top,
    rgba(0,0,0,0.96) 0%,
    rgba(0,0,0,0.65) 45%,
    rgba(0,0,0,0.18) 80%,
    transparent 100%);
}
/* no pill background — "View Gallery · 6 photos" is text, placed directly on the gradient */
.back-action button {
  background: transparent;
  border: 0;
  color: #fff;
  font-weight: 600;
}
```

Core principles:
- All white text on the card sits **on top of the bottom black gradient** (front
  title/architects/info, back action label alike).
- No separate panel/scrim/chip background — the gradient is the only legibility
  aid.
- Even a button, if it is text, is placed directly on the gradient with no pill
  bg.

### 8.7 Folder Card (Boards canonical)
A "folder" metaphor card. The top tab (label) narrows diagonally toward the
right.

**Structure / content order**
```
+----------------+
| Tab title (⋯)   \              ← 1. folder title (inside the tab, ⋯ if long)
+------------------+----+
|                       |
|  Overview (long desc) |        ← 2. overview
|  Summary (one line)   |        ← 3. summary
|  ─── divider ───      |        ← 4. divider (1px solid --border)
|  [img] [img] [img]    |        ← 5. 3 project main images
|                       |
|  N projects   2026.x  |        ← 6. project count + creation date (justified)
+-----------------------+
```

```yaml
folder-tab-color:        "var(--accent-1)"
folder-tab-text-color:   "#fff"
folder-tab-height-visible: 32      # visible height (total 48 — 16px covered by the body corner)
folder-tab-offset-x:     4         # starts 4px inside the body's left edge
folder-tab-radius-tl:    10        # body radius / 1.6
folder-tab-radius-tr:    7         # roundness of the slant start point
folder-tab-min-width:    "calc((50% - 4px) / 0.7)"   # slant start point aligns to body center
folder-tab-max-width:    "calc(100% - 20px)"
folder-tab-label-padding: "0 28% 0 18px"             # right 28% is the slant-avoidance area

folder-body-bg:          "var(--surface-2)"
folder-body-radius:      16
folder-body-padding:     18

folder-title-font-size:    13
folder-title-font-weight:  600
folder-title-ellipsis:     "⋯"     # U+22EF midline (NOT … U+2026, NOT ...)
```

**Title truncation**
- Short title: shown in full (no truncation).
- Long title: a JS binary search finds the longest prefix that fits the tab's
  inner width, rendered as `prefix + ⋯`.
- Use `text-overflow: clip` (blocks the browser default `…`).

**Hover** — **lift + 1px accent outline, no shadow/glow**
```css
.folder-card {
  transition: transform 0.2s ease, filter 0.18s;
  /* base: no filter — flat, no drop-shadow */
}
.folder-card:hover {
  transform: translateY(-3px);
  filter:
    drop-shadow( 1px  0   0 var(--accent-1))
    drop-shadow(-1px  0   0 var(--accent-1))
    drop-shadow( 0    1px 0 var(--accent-1))
    drop-shadow( 0   -1px 0 var(--accent-1));
}
```

- 4-directional stacked `drop-shadow` traces an outline that follows the tab's
  slanted corners (CSS `outline` is rectangular and cannot follow the slant
  curve).
- No underneath drop-shadow in either default or hover state (flat design).
- `box-shadow` not used.

### 8.8 Loading State (Skeleton + Spinner combination)
- **Card / list skeletons** → **Skeleton** (mimics the real layout with radius +
  gray blocks).
- **Buttons / short actions** → **inline spinner** (replace the button label
  with a spinner, disabled).
- No shimmer animation (performance cost + unrelated to the Vibe keywords).

```yaml
skeleton-bg:           "var(--surface-2)"
skeleton-radius:       "var(--radius-sm)"   # 8px
skeleton-block-height: 16                   # one text line; cards use aspect-ratio
spinner-size:          20
spinner-stroke-width:  2
spinner-duration:      "1.2s"   # one rotation
```

### 8.9 Error / Empty State (3-tier)
| Scenario | Pattern | Location |
|---|---|---|
| No data at all (e.g. first board, end of recommendations) | **Empty component** — friendly illustration + one-line description + Primary CTA | page / list area |
| Component load failure (network/server) | **Inline Error** — specific message + "Try again" button | the component's own slot |
| Action failure (save/send, transient) | **Toast** (§8.11) | bottom-center |

Principle: **never build a catastrophic full-screen error** — always isolate at
the component level so the user can keep using the rest.

### 8.10 Modal / Bottom Sheet
**Auto-selected per environment**
- Mobile (≤768px): **Bottom Sheet** — swipe-up from the bottom. Matches the
  gesture-friendly Vibe.
- Desktop (≥769px): **Centered Modal** — center-aligned, dimmed backdrop.

```yaml
sheet-radius-top:    "calc(var(--radius-xl) * 1px)"  # 24px, top corners only
sheet-handle:        "4px × 36px"                    # top swipe handle bar
sheet-max-height:    "85vh"                          # up to 85% of the screen
sheet-backdrop:      "rgba(0,0,0,0.4)"
modal-max-width:     "480px"
modal-radius:        "calc(var(--radius-lg) * 1px)"  # 20px
modal-padding:       "24px"
sheet-anim-duration: "var(--motion-flip)"            # 500ms slide-up
sheet-anim-easing:   "var(--motion-ease)"
```

Closing: mobile = swipe-down + backdrop tap; desktop = ESC + backdrop click +
top-right ✕ button.

### 8.11 Toast
- **Position**: **bottom-center** (does not cover the mobile nav bar, natural on
  desktop too).
- **Duration**: **3s** default (the longer-toast option is 5s).
- **Style**: **Glassmorphic** (matches the Vibe) — the same frosted-glass
  pattern as headers/input bars.

```yaml
toast-position:       "bottom-center"
toast-bottom-offset:  "calc(var(--tabbar-height) + 16px)"  # mobile: above the nav
toast-duration:       3000   # ms
toast-duration-long:  5000   # ms (long / important messages)
toast-bg:             "color-mix(in srgb, var(--surface) 72%, transparent)"
toast-backdrop:       "blur(12px)"
toast-border:         "1px solid var(--border)"
toast-radius:         "var(--radius-pill)"
toast-padding:        "10px 16px"
toast-enter:          "var(--motion-normal) var(--motion-ease)"    # slide-up + fade-in
toast-exit:           "var(--motion-fast) var(--motion-ease-out)"  # fade-out
```

Type color tints:
- info: default
- success: `border-color: var(--accent-2)`
- warning: `border-color: var(--accent-3)`
- error: `border-color: var(--destructive)`

---

## 9. Decisions

| Item | Decision | Note |
|---|---|---|
| Default Theme | **GitHub Light** | §1.1 ✅ |
| Theme Switching | exposed to end users (background + accent chips) | §5 ✅ |
| Body Font | **IBM Plex Sans KR** | §2.1 ✅ |
| Font Switching | exposed to end users (Font label rendered in the font it switches to) | §6 ✅ |
| Font-weight cap | **700** (800/900 forbidden) | §2.5 ✅ |
| Type Scale | **split per environment (Desktop / Mobile)** | §2.2 / §2.3 ✅ |
| Destructive color | **themed** (an appropriate red per theme) | §1.3 ✅ |
| Text hierarchy | **4 tiers retained** | §1.1 ✅ |
| iOS Safe Area | **bottom TabBar / CTA only** | §7.1 ✅ |
| Implementation | hybrid (inline + CSS variables) | §4 ✅ |
| Accent policy | **themed (CSS variables)** | §1.2 ✅ |
| Responsive | **mobile-first + desktop left-sidebar re-layout** | §7 ✅ |
| TabBar Height | **64px (with label) / 56px (icon only)** | §3.3 ✅ |
| Border Radius | **4-tier tokenized (sm/md/lg/xl)** | §3.1 ✅ |
| Touch Target | **mobile 44px / desktop 32px+** | §3.2 ✅ |
| Vibe Keywords | **Glassmorphic · Fluid · Gesture-friendly (hint only)** | §4 ✅ |
| Folder Card Hover | **lift + 1px accent outline, no shadow/glow** | §8.7 ✅ |
| Theme Switcher location | **Profile → Settings → Appearance** | §5.4 ✅ |
| Theme persistence | **user account (cross-device), guests session-only** | §5.5 ✅ |
| Project Card Aspect | **4 / 5 portrait** | §8.6 ✅ |
| Project Card Border | **none — radius + shadow only** | §8.6 ✅ |
| Project Card Hover | **no effect (swipe UX)** | §8.6 ✅ |
| Project Card Text legibility | **bottom black gradient fade (front/back identical)** | §8.6 ✅ |
| Motion Tokens | **Duration 4 tiers (fast/normal/slow/flip) + Easing 2 (standard/ease-out)** | §3.5 ✅ |
| Dual-font operation | **single font only — headings/body same family, toggle = full switch** | §2.5a ✅ |
| Loading State | **Skeleton + Spinner combination (no shimmer)** | §8.8 ✅ |
| Error / Empty | **3-tier: Empty component / Inline Error / Toast** | §8.9 ✅ |
| Modal / Sheet | **auto per environment: mobile Bottom Sheet, desktop Centered Modal** | §8.10 ✅ |
| Toast | **bottom-center · 3s · glassmorphic** | §8.11 ✅ |
| Discovery Interaction | **keyboard ←/→ + drag → swipe, Enter + photo click → flip** | §8.6 ✅ |
| Hover implementation | **CSS `:hover` pseudo-class only (inline JS forbidden)** | §4 ✅ |
| Korean font fallback | **Web → OS Korean → system-ui (Sans/Serif each)** | §2.1 ✅ |
| Design doc structure | **`DESIGN.md` is the single source of truth** | §10.1 ✅ |
| Design token location | **dedicated `tokens.css` file** | §10.2 ✅ |
| Theme/font addition process | **`tokens.css` + switcher edit + DESIGN.md update + PR design review** | §10.3 ✅ |
| Component isolation policy | **extract when used on 2+ pages (design-system granularity always)** | §10.4 ✅ |
| Aesthetics tone | **tone split by mode: Light=clear/editorial, Dark=cinematic/atmospheric** | §4 ✅ |
| Implementation rule | **CSS variables + Inline hybrid (external UI / CSS-in-JS libraries forbidden)** | §4 ✅ |

---

## 10. Code Structure

### 10.1 Markdown File Policy
- **`DESIGN.md` is the single source of truth.** All tokens / decisions / specs
  are recorded here.
- New decisions and changes are added only to `DESIGN.md`, via PR.
- There is no separate `design.md` or `DECISIONS.md` in the repo — this file is
  canonical. (The redesign was originally drafted in an external `design.md`;
  its content was absorbed here on adoption, 2026-05-21.)

### 10.2 Design Token Location
- **A dedicated `tokens.css` file** — `frontend/src/tokens.css` holds
  `:root { --bg, --accent-*, --motion-*, ... }` plus the per-theme
  `[data-theme="..."]` override blocks and the `[data-font="..."]` font block.
- Separated from component styles so it owns only the token concern.
- Imported in `frontend/src/main.jsx` before `index.css`.
- A single file so cache invalidation works cleanly on change.

### 10.3 Theme / Font Addition Process
New themes / fonts are added or removed **only via PR**. Steps:
1. **Edit `tokens.css`**: add a new `[data-theme="..."]` block (theme) or extend
   the `[data-font="..."]` block (font).
2. **Wire the switcher**: add the new option to `ThemeContext` + the Appearance
   switcher component.
3. **Update `DESIGN.md`**: sync the §1.2 (theme) or §2 (font) tables, yaml
   blocks, and descriptions.
4. **Submit a PR**: include a preview screenshot of the new option + the
   rationale.
5. **Design review**: merge only after approval from at least one design
   reviewer.
- Free-form additions are forbidden — a review step is mandatory for
  consistency and quality.

### 10.4 Component Isolation Policy
**Extraction criteria (extract into a component if ANY one applies)**
- A pattern used on 2+ pages / screens.
- A JSX block over 50 lines even if used on a single page.
- Design-system granularity (Button / Input / Card / Toast / Modal, etc.) —
  always a component.

**When keeping it inline (within a component) is appropriate**
- Short layout code used only on a single page.
- A one-off static composition.
- Page composition that sits above the design-system layer.

> Intent: balance reusability and readability. Extracting too early yields the
> wrong abstraction; too late accumulates duplication.

**Styling form per the §4 hybrid rule**: interactive components that own
`:hover` / `:focus` / `:active` get a co-located `*.module.css` (CSS Module).
Themeable values come from `tokens.css` variables. Inline styles remain only for
pure layout/positioning and runtime-dynamic values.

---

## 11. In Progress / Undecided

- [ ] **Persona screen components** (Profile Action Row + Stats Row)
  - Proceed when persona-screen design work begins.
- All other categories are resolved in the §9 decision table.

---

## Usage

1. The running app (`cd frontend && npm run dev`) is the live preview of this
   design system — there is no separate preview server.
2. To change a token value, edit `frontend/src/tokens.css` and update the
   corresponding yaml block + description in this file in the same PR.
3. To add a token, add a `--key: value` line to `tokens.css` and document it
   here.
