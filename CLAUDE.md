# Make Web Service -- Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  For system architecture and API surface, see `.claude/Report.md`.

  ## Rules
  - All building references must use `building_id` -- never name, slug, or language-dependent field.
  - Do NOT create or migrate the `architecture_vectors` table -- it is owned by Make DB.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - When updating `.claude/Report.md`, update ONLY the `Last Updated (Claude)` section. NEVER overwrite or remove the `Last Updated (Gemini)` section.

  ## Target Structure
  frontend/   <- React 18 + Vite
  backend/    <- Django 4.2 LTS + DRF + pgvector + Gemini + social auth
  web-testing/ <- Playwright E2E visual test runner + dashboard

  ## Current State
  - frontend/: BUILT -- Phase 0+4 complete; rich inline-style UI, project sync from backend on login
  - backend/: BUILT -- Phase 1+2+3+4 complete; full recommendation engine + Gemini LLM + project persistence
  - web-testing/: BUILT -- E2E visual test runner with persona generation, Playwright tests, and dashboard
  - Integration fixes applied: JWT auth wired, field name normalizer in client.js, trailing slashes on all URL patterns
  - Google login: auth-code flow (VITE_GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET required)

  ## Frontend Conventions
  - **MUST READ `DESIGN.md`**: All front-maker tasks MUST consult `DESIGN.md` for our visual design system, colors, sizes, and UI rules before writing any code.
  - All component styles are inline JS objects -- Tailwind is NOT used in components
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom)
  - Accent colors are hardcoded hex in inline styles (not CSS vars) -- rely on `DESIGN.md` when applying colors
  - Do NOT rewrite inline styles arbitrarily; they are the intentional design

  ## Backend Conventions
  - Django 4.2 LTS required (Python 3.9.6 on this machine; Django 5+ needs Python 3.10+)
  - All URL patterns must have trailing slashes -- Django APPEND_SLASH only redirects GET, not POST
  - Neon PostgreSQL: use `sslmode=require` in DATABASE_URL; psycopg2-binary (not asyncpg)
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS)
  - `architecture_vectors` -- read-only via raw SQL; never use Django ORM or migrate this table
  - `images/batch/` POST -- batch-fetch building cards by `building_ids` list
  - Run: `cd backend && python3 manage.py runserver 8001`

  ## Web Testing (web-tester agent)

  ### Dev Login -- Authenticating Without OAuth
  The web-tester agent must use dev-login to get a JWT for testing authenticated flows.
  Google OAuth is not available in automated/headless contexts, so dev-login is the only path.

  **Endpoint:** `POST http://localhost:8001/api/v1/auth/dev-login/`
  **Request body:** `{"secret": "<value of DEV_LOGIN_SECRET from backend/.env>"}`
  **Availability:** DEBUG=True only. The URL itself is unroutable when DEBUG=False.
  **Rate limit:** 5 requests/minute (DevLoginThrottle).

  **Response (200):**
  ```json
  {
    "access": "<jwt_access_token>",
    "refresh": "<jwt_refresh_token>",
    "user": {
      "user_id": 1,
      "display_name": "Test User",
      "avatar_url": null,
      "providers": []
    }
  }
  ```

  **If DEV_LOGIN_SECRET is not set** in `backend/.env`, the endpoint returns 404.
  In that case, skip authenticated flows and test page load only.

  ### Injecting Tokens Into the Browser
  After a successful dev-login curl, inject tokens via `browser_evaluate`:
  ```js
  localStorage.setItem('archithon_access', '<access_token>')
  localStorage.setItem('archithon_refresh', '<refresh_token>')
  sessionStorage.setItem('archithon_user', '<user.user_id from response>')
  ```
  Then reload the page. The app reads these keys on mount to restore auth state.

  **localStorage keys:**
  - `archithon_access` -- JWT access token (1hr expiry)
  - `archithon_refresh` -- JWT refresh token (30d expiry)

  **sessionStorage keys:**
  - `archithon_user` -- user ID (integer, from `response.user.user_id`)

  ### Debug Overlay
  Enable richer test diagnostics by setting debug mode before reload:
  ```js
  localStorage.setItem('__debugMode', 'true')
  ```
  This activates `DebugOverlay.jsx`, a fixed panel showing:
  - JWT expiry time
  - Last API call (method, URL, status, latency)
  - Current session ID and swipe progress
  - User ID or "not logged in"

  The overlay is read-only (`pointerEvents: 'none'`) and survives page reloads.
  Web-tester should screenshot after enabling it to confirm login state.

  ### Django Admin
  - **URL:** `http://localhost:8001/admin/`
  - **Credentials:** username `admin`, password `admin1234` (set by `make setup`)
  - **Availability:** DEBUG=True only. The admin URL is unroutable when DEBUG=False.
  - Useful for inspecting user accounts, projects, and social accounts during testing.

  ### Authenticated Flows to Test
  Once logged in via dev-login, web-tester should test:
  1. **Home / LLM Search** -- AI search input visible, type query, submit
  2. **Swipe page** -- session creation works, cards load, swipe gestures function
  3. **Favorites page** -- project folders render, liked buildings display
  4. **Persona report** -- "Generate Persona Report" button visible when likes exist
  5. **API connectivity** -- no 401 errors on authenticated endpoints

  ### Important: Orchestrator Must NOT Pass skip_login
  The orchestrator should NOT tell web-tester to skip login. Dev-login exists specifically
  for automated testing. The orchestrator should let web-tester run its Step 0 (dev-login)
  before visual tests.

  ## E2E Visual Test Runner (web-testing/)

  ### Overview
  Standalone Playwright-based E2E test runner at `web-testing/`. Generates persona-driven test scenarios,
  runs them against the local dev servers, captures screenshots/timing/errors at every step,
  and serves a local dashboard for visual review.

  ### Structure
  ```
  web-testing/
  +-- research/persona.py      # PersonaProfile dataclass + template/LLM generation
  +-- research/scenarios.py    # TestScenario + keyword-overlap swipe decisions
  +-- runner/runner.py         # Playwright E2E orchestration (sync API)
  +-- runner/collector.py      # StepRecord, ApiCallRecord, ErrorRecord, Collector class
  +-- runner/reporter.py       # Generates report.json with summary + bottleneck classification
  +-- runner/feedback.py       # Generates feedback.json with endpoint->source file mapping
  +-- dashboard/               # Static HTML/JS/CSS dashboard (no build step)
  +-- reports/                 # Output dir (gitignored)
  +-- run.py                   # CLI entry point
  +-- requirements.txt         # playwright, google-generativeai
  ```

  ### Running
  ```bash
  # Install deps
  pip install -r web-testing/requirements.txt
  python -m playwright install chromium

  # Run single persona test (template mode)
  python web-testing/run.py

  # Run 3 personas with LLM-generated profiles
  python web-testing/run.py --personas 3 --mode llm

  # Serve dashboard only
  python web-testing/run.py --dashboard-only

  # Auto-fix mode (structured feedback to stdout)
  python web-testing/run.py --auto-fix
  ```

  ### Prerequisites
  - Frontend dev server running on `http://localhost:5174`
  - Backend dev server running on `http://localhost:8001`
  - `DEV_LOGIN_SECRET` set in `backend/.env`

  ### Output
  - `web-testing/reports/{run_id}/report.json` -- full test report
  - `web-testing/reports/{run_id}/feedback.json` -- orchestrator-consumable feedback
  - `web-testing/reports/{run_id}/screenshots/` -- step screenshots
  - `web-testing/dashboard/data/latest/` -- symlinked latest report for dashboard

  ## Code Review (`/deep-review`)

  A dedicated deep-review workflow lives at `.claude/commands/deep-review.md` (slash command)
  and `.claude/agents/deep-reviewer.md` (programmatic subagent). Both share the same
  7-axis checklist and report format.

  **Invocation:** on a separate "review terminal" Claude Code session, type
  `/deep-review` (default scope: `main...HEAD`) or `/deep-review <range>` (e.g.
  `/deep-review HEAD~5..HEAD`).

  **Output:**
  - `.claude/reviews/{sha_short}.md` -- per-commit archive
  - `.claude/reviews/latest.md` -- stable read path; main implementation terminal
    reads this on demand when relevant (never auto-loaded)

  **Scope:** branch since `main` diverged. Reads all changed files (full content, not
  just hunks) plus `.claude/Goal.md` + `.claude/Report.md` for architecture grounding.

  **7 axes:** architecture alignment, correctness/logic depth, performance/optimization,
  security in depth, code quality, test coverage, cross-commit drift. Severity:
  CRITICAL / MAJOR / MINOR.

  **Relationship to existing review agents:** `/deep-review` is **read-only and
  non-blocking** -- it does not participate in the orchestrator fix loop or gate
  commits. It **supplements** the fast `reviewer` (API contracts, logic bugs, obvious
  perf) and `security-manager` (SQLi/XSS/auth keyword scan) agents, filling their
  explicit exclusions: refactoring, optimization opportunities, test coverage,
  cross-commit drift, and architecture alignment.

  ## Database: architecture_vectors Schema
  Owned by Make DB. Django reads via raw SQL only -- never ORM, never migrate.

  ```sql
  CREATE TABLE architecture_vectors (
      building_id      TEXT PRIMARY KEY,   -- e.g. 'B00042', stable canonical key
      slug             TEXT UNIQUE NOT NULL,
      name_en          TEXT NOT NULL,
      project_name     TEXT NOT NULL,
      architect        TEXT,
      location_country TEXT,
      city             TEXT,
      year             INTEGER,
      area_sqm         NUMERIC,
      program          TEXT NOT NULL,      -- see normalized vocabulary below
      style            TEXT,               -- e.g. Brutalist, Classical, Contemporary
      atmosphere       TEXT NOT NULL,      -- free-form e.g. "fluid, sweeping, atmospheric"
      color_tone       TEXT,               -- e.g. Colorful, Cool White, Dark, Earthy
      material         TEXT,               -- nullable (977 rows NULL)
      material_visual  TEXT[] NOT NULL,    -- array of visual material descriptors
      visual_description TEXT NOT NULL,    -- rich text description
      description      TEXT,
      url              TEXT,
      tags             TEXT[],
      source_slugs     TEXT[],
      image_photos     TEXT[],             -- all photo filenames
      image_drawings   TEXT[],             -- all drawing filenames
      embedding        VECTOR(384) NOT NULL
  );
  ```

  ## Normalized `program` Values
  Used in filters and Gemini persona reports. Must use exactly these values -- no raw strings.

  `Housing` | `Office` | `Museum` | `Education` | `Religion` | `Sports` |
  `Transport` | `Hospitality` | `Healthcare` | `Public` | `Mixed Use` |
  `Landscape` | `Infrastructure` | `Other`
