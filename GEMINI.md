# Make Web Service -- Gemini (Antigravity) Instructions

## Core Directive
Gemini (Antigravity) is strictly responsible for **Frontend UI/UX development only**.
Claude (Terminal orchestrator/makers) handles all Backend and Database development.

## Strict Boundaries
1. **Do NOT touch backend code**: Never modify Python files, Django configurations, backend tests, or migrations.
2. **Immutable API Contracts**: Treat the backend REST API as an immutable black-box. Do not propose or make changes to the API schema to make frontend tasks easier. If an API limitation exists, solve it creatively on the frontend, or explicitly halt and request that Claude update the backend API first.
3. **Directory Sandbox**: Gemini should only read/write files within the `frontend/` directory (React, Vite, CSS) and specific cross-agent documentation files.

## Cross-Agent Documentation Protocols
- **DESIGN.md**: Gemini's ultimate source of truth for all styling, colors, and UI layout rules.
- **Goal.md** (`.claude/Goal.md`): Product vision, 4 target personas (P1-P4), acceptance criteria.
- **Task.md** (`.claude/Task.md`): Current phase and task IDs. Check which phase is active before starting work.
- **Report.md**: When documenting work, update the `Last Updated (Gemini)` section in `.claude/Report.md`. DO NOT modify Claude's sections.
- **Implementation Plans**: Formulate plans focusing entirely on React state, component structures, animations, and frontend logic.

## Frontend-First Mockup Workflow

New pages are built in two stages: **mockup** (Gemini, hardcoded data) → **integration** (Claude, API wiring).

### Rules for Mockup Stage
1. **Use `MOCK_` constants** for hardcoded data at the top of each page component:
   ```jsx
   const MOCK_OFFICE = { office_id: 'OFF001', name: 'OMA', verified: true, ... }
   ```
2. **Follow the API contract shapes below exactly** — field names, nesting, types must match so Claude can replace mocks with real API calls without refactoring.
3. **Use realistic field names** from the existing codebase: `building_id` (not `id`), `name_en` (not `title`), `image_url` (not `photo`), etc.
4. **Mark mock data clearly** with a `// TODO: Replace with API call` comment above each `MOCK_*` constant.
5. **Do NOT create api/client.js functions** for new endpoints — Claude will add those during integration.

### Current Phase: Phase 13 (Profile System)
Tasks: PROF1-PROF4 (see Task.md). Build these pages with mock data:
- Firm profile page (PROF3)
- User profile page (PROF4)

## Post-Integration Rules

Once a page has been integrated by Claude (i.e., `MOCK_*` replaced with real API calls,
`useState`/`useEffect` added), Gemini can still return to polish the UI — but inside a
narrower allowed zone, because the file is now layered.

### Layer Boundary in Integrated Files

| Layer | Owner | Edit freely |
|-------|-------|-------------|
| **UI** | Gemini (antigravity) | JSX return, `styles` objects, animations, transitions, colors, spacing, icons, layout, copy |
| **Data / Logic** | Claude (main) | `useState`, `useEffect`, `callApi()`, custom hooks, error handling, data transformations |

Gemini **reads** state variables in JSX (`{profile?.name}`, `{isLoading && <Spinner />}`) but
**never creates** them. Only Claude introduces state or data-fetching code.

### Allowed vs Forbidden After Integration

**Allowed (edit freely):**
- JSX structure, element order, conditional rendering that uses existing state
- `styles` object: colors, spacing, fonts, shadows, gradients
- Animation keyframes, `transition` props, Framer Motion props
- Text content (static labels, helper copy, placeholders)
- Adding icons, dividers, containers

**Forbidden:**
- **Do NOT re-insert `MOCK_*` constants** — they have already been replaced by real API calls.
- **Do NOT modify `useState`, `useEffect`, `callApi()`, or any data-fetching code.**
- **Do NOT remove `?.` optional chaining** (e.g., `profile?.name`) — it keeps the UI safe
  while data loads.
- **Do NOT call new API endpoints directly.** Drop a `TODO(claude): ...` marker instead and
  let Claude wire the call during the next integration pass.

### TODO Handoff Markers

When Gemini needs behavior that requires API/backend work, drop an inline marker and move on:

```jsx
// JS/TSX:
// TODO(claude): <what needs to happen>

// Inside JSX:
{/* TODO(claude): <what needs to happen> */}
```

Claude's orchestrator batches these via `grep -r "TODO(claude)" frontend/` during the next
main-terminal session. Reverse direction (`// TODO(antigravity): ...`) is rare and used by
Claude to request a specific UI change from Gemini.

### Three Worked Examples

**① Adding a button**

If the `onClick` is pure UI (open a modal, navigate, toggle a tab) — Gemini handles it
entirely, including local `useState` for toggles:

```jsx
const [isModalOpen, setIsModalOpen] = useState(false)

<button style={styles.ctaButton} onClick={() => setIsModalOpen(true)}>
  Add Board
</button>
```

If the `onClick` calls an API (delete, follow, save) — Gemini drops a TODO and leaves the
handler body empty:

```jsx
<button
  style={styles.deleteButton}
  onClick={() => { /* TODO(claude): DELETE /api/v1/boards/${board_id}/ */ }}
>
  Delete Board
</button>
```

**② Modifying animations**

Entirely Gemini's territory. No TODO needed. Edit the `styles` object, `transition` props,
or Framer Motion props freely:

```jsx
const styles = {
  card: {
    transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
  },
}
```

**③ Deleting / adding informational text**

- **Static text** ("My Boards", "Settings saved", helper copy): Gemini only, no TODO.
- **Using an existing API field** that the page already fetches (`profile.bio` is already in
  state): Gemini only — just edit JSX to display it.
- **Needing a new API field** that doesn't exist yet (e.g., `profile.achievement_count`):
  display a placeholder and drop a TODO for Claude to extend the backend:

```jsx
<div style={styles.stat}>
  {profile?.achievement_count ?? 0} achievements
  {/* TODO(claude): add achievement_count to /users/me/ response */}
</div>
```

## API Contract Shapes (Phase 13+)

Gemini must use these exact shapes when hardcoding mock data. Claude will build backend endpoints returning these structures.

### Firm/Office Profile
```json
{
  "office_id": "OFF001",
  "name": "OMA",
  "verified": true,
  "website_url": "https://oma.com",
  "contact_email": "info@oma.com",
  "description": "Office for Metropolitan Architecture is a leading...",
  "logo_url": "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/offices/oma_logo.jpg",
  "location": "Rotterdam, Netherlands",
  "founded_year": 1975,
  "projects": [
    {
      "building_id": "B00042",
      "name_en": "Seattle Central Library",
      "image_url": "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/B00042_01.jpg",
      "year": 2004,
      "program": "Public",
      "city": "Seattle"
    }
  ],
  "articles": [
    {
      "title": "OMA Unveils New Campus Design",
      "source": "ArchDaily",
      "url": "https://archdaily.com/...",
      "date": "2025-01-15"
    }
  ]
}
```

### User Profile
```json
{
  "user_id": 1,
  "display_name": "Kim Minseo",
  "avatar_url": "https://...",
  "bio": "Architecture student at SNU, obsessed with brutalism",
  "mbti": "INTJ",
  "external_links": {
    "instagram": "@kimarch",
    "email": "kim@example.com"
  },
  "follower_count": 42,
  "following_count": 18,
  "is_following": false,
  "boards": [
    {
      "board_id": "proj_123",
      "name": "Museum References",
      "visibility": "public",
      "building_count": 15,
      "cover_image_url": "https://pub-5d2133d166fc4b65ad05295df352519f.r2.dev/photos/B00042_01.jpg"
    }
  ],
  "persona_summary": {
    "persona_type": "The Parametric Visionary",
    "one_liner": "They seek purity where form and light converge",
    "styles": ["Modern", "Parametric"],
    "programs": ["Museum", "Public"]
  }
}
```

### Board Detail
```json
{
  "board_id": "proj_123",
  "name": "Museum References",
  "visibility": "public",
  "owner": {
    "user_id": 1,
    "display_name": "Kim Minseo",
    "avatar_url": "https://..."
  },
  "buildings": [
    {
      "building_id": "B00042",
      "name_en": "Seattle Central Library",
      "image_url": "https://...",
      "architect": "OMA / Rem Koolhaas",
      "year": 2004,
      "program": "Public",
      "city": "Seattle"
    }
  ],
  "reaction_count": 7,
  "is_reacted": false
}
```

### Post-Swipe Landing (MATCHED! Tabs)
```json
{
  "projects": [
    {
      "building_id": "B00042",
      "name_en": "Seattle Central Library",
      "image_url": "https://...",
      "match_score": 0.92
    }
  ],
  "offices": [
    {
      "office_id": "OFF001",
      "name": "OMA",
      "logo_url": "https://...",
      "project_count": 12,
      "match_score": 0.87
    }
  ],
  "users": [
    {
      "user_id": 2,
      "display_name": "Park Jiwon",
      "avatar_url": "https://...",
      "shared_likes": 5,
      "match_score": 0.85
    }
  ]
}
```

### Follow / Reaction
```json
// POST /api/v1/users/{id}/follow/    → {"status": "followed"}
// DELETE /api/v1/users/{id}/follow/   → {"status": "unfollowed"}
// POST /api/v1/boards/{id}/react/     → {"reaction_count": 8, "is_reacted": true}
// DELETE /api/v1/boards/{id}/react/   → {"reaction_count": 7, "is_reacted": false}
```
