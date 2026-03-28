# Make Web Service — Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB.
  Full spec is in `02_MAKE_WEB.md`. Shared DB schema is in `00_FLOW.md`.

  ## Rules
  - Read `00_FLOW.md` and `02_MAKE_WEB.md` before writing any code.
  - One phase per session. Do not mix phases.
  - Use `/plan` before coding each phase.
  - All building references must use `building_id` — never name, slug, or language-dependent field.
  - Do NOT create or migrate the `architecture_vectors` table — it is owned by Make DB.
  - SentenceTransformers is NOT a dependency here — embeddings are pre-computed.

  ## Target Structure
  frontend/   ← React 18 + Vite + Tailwind
  backend/    ← Django 4.2 LTS + DRF + pgvector + Gemini + social auth

  ## Current State
  - frontend/: BUILT — Phase 0+4 complete; rich inline-style UI, project sync from backend on login
  - backend/: BUILT — Phase 1+2+3+4 complete; full recommendation engine + Gemini LLM + project persistence
  - Integration fixes applied: JWT auth wired, field name normalizer in client.js, trailing slashes on all URL patterns
  - Google login: real OAuth wired (VITE_GOOGLE_CLIENT_ID required)
  - PostgreSQL: populated by Make DB before Phase 1 starts

  ## Frontend Conventions
  - All component styles are inline JS objects — Tailwind is NOT used in components
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom)
  - Accent colors are hardcoded hex in inline styles (not CSS vars) — grep all page files when changing colors
  - Do NOT rewrite inline styles; they are the intentional design

  ## Backend Architecture
  - `engine.py` — recommendation algorithm (diverse-random, epsilon-greedy, pgvector queries, preference vector, batch fetch)
  - `services.py` — Gemini LLM integration (query parsing `gemini-2.5-flash`, persona report generation)
  - `views.py` — all endpoints implemented; no stubs remaining; `SessionCreateView` returns `project_id` in response
  - `architecture_vectors` — read-only via raw SQL; never use Django ORM or migrate this table
  - `images/batch/` POST — batch-fetch building cards by `building_ids` list

  ## Frontend Architecture
  - `api/client.js` — `listProjects`, `createProject`, `deleteProject`, `generateReport`, `getBuildings` added
  - `App.jsx` — `handleLogin` async: syncs backend projects on login, batch-fetches liked buildings
  - `App.jsx` — `initSession` stores `backendId` (backend UUID) from session create response
  - `App.jsx` — `handleDeleteProject` calls `api.deleteProject(backendId)` when backend ID is available
  - `FavoritesPage.jsx` — `PersonaReport` component displays `finalReport` (persona_type, one_liner, description, dominant_*)
  - `FavoritesPage.jsx` — "Generate Persona Report" button calls `onGenerateReport` when liked buildings exist

  ## Backend Conventions
  - Django 4.2 LTS required (Python 3.9.6 on this machine; Django 5+ needs Python 3.10+)
  - All URL patterns must have trailing slashes — Django APPEND_SLASH only redirects GET, not POST
  - Neon PostgreSQL: use `sslmode=require` in DATABASE_URL; psycopg2-binary (not asyncpg)
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS)
  - Run: `cd backend && python3 manage.py runserver 8001`

  ## Prerequisite Before Phase 1
  architecture_vectors table must have data.
  Verify: SELECT COUNT(*) FROM architecture_vectors;

  ## Session Prompts
  - Phase 0: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 0. Build frontend/ from scratch: React+Vite+Tailwind, AppContext, all pages as empty shells."
  - Phase 1: "Read CLAUDE.md, 00_FLOW.md Section 4.4, 02_MAKE_WEB.md Phase 1. Set up Django backend, social auth (Google/Kakao/Naver), connect to existing
  PostgreSQL."
  - Phase 2: "Read CLAUDE.md, 00_FLOW.md Section 4.4, 02_MAKE_WEB.md Phase 2. Build recommendation engine in engine.py."
  - Phase 3: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 3. Add Gemini LLM: query parsing + persona reports."
  - Phase 4: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 4. Wire frontend ↔ backend, configure image serving."
  - Phase 5: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 5. Testing and polish."