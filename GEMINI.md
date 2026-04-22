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
