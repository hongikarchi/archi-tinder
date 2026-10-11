# frontend/ — conventions (shared: Claude Code, Codex, humans)

Loaded on top of the root `AGENTS.md` when working under `frontend/`.

- **Read `DESIGN.md` first** for any UI change (layout, colors, motion, components).
  It is the design authority; CSS variable names, radii, type scale and component
  specs come from there and from `frontend/src/tokens.css`.
- **Styling = hybrid** (DESIGN.md §4): themed values as `tokens.css` CSS variables;
  interactive components own `:hover/:focus/:active` in a co-located
  `*.module.css`; layout / one-off / dynamic values inline `style={{}}`. No
  Tailwind, Bootstrap, MUI, styled-components or emotion.
- **Viewport lock**: body is `height:100vh; overflow:hidden`; page shells use
  `height: var(--page-height)` (never a hand-written `calc(100vh - 64px)`); the
  TabBar height is `--tabbar-height`.
- Colors are themed variables (`--accent-1/2/3`, `--color-*`) defined per theme in
  `tokens.css` (4 themes). Never hardcode hex in components.
- Treat existing inline styles as load-bearing; do not rewrite them without a
  DESIGN.md rule — surface such changes in the PR description.
- User-facing strings go through i18n (`t()` / `i18n/locales.js`); Korean is the
  primary locale, English is supported.
- API calls go through `src/api/client.js`; never build URL paths from user input.
  JWT lives in `localStorage` (`archithon_access` / `archithon_refresh`) — never in
  URLs or logs.
- Dev: `make frontend` (Vite on :5174, API on :8001). `./tools/front-validate.sh` =
  eslint + build; CI runs the same.
- Swipe deck uses a vendored `react-tinder-card` fork (`lib/tinderCard.js`):
  callback identity must be stable (`useCallback` + latest-ref) or an in-progress
  drag is killed; interactive card children need `className="pressable"`.
