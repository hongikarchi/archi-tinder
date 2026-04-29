# Make Web Service -- Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  For system architecture and API surface, see `.claude/Report.md`.

  ## Rules
  - All building references must use `building_id` -- never name, slug, or language-dependent field.
  - Do NOT create or migrate the `architecture_vectors` table -- it is owned by Make DB.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - When updating `.claude/Report.md`, update ONLY the `Last Updated (Claude)` section. NEVER overwrite or remove the `Last Updated (Designer)` section.
  - **`research/` folder is off-limits to the main and review terminals**, with **one narrow exception** noted below. It is the **research terminal's exclusive write territory** AND the **user's active study workspace**. All main-pipeline and review-terminal agents/commands — `orchestrator`, `back-maker`, `front-maker`, `reviewer`, `security-manager`, `git-manager`, `algo-tester`, `web-tester`, and the `/review` slash command — are **READ-ONLY** on `research/`. Never create, modify, delete, or stage files under `research/` (including `research/spec/`, `research/search/`, `research/investigations/`, and any future subdirectory) from the main pipeline. If you read research content, that is fine; writes are forbidden. If a file already exists under `research/` that appears to have been created by the main pipeline (governance violation), leave it for the user or research terminal to handle — do not delete or relocate it yourself. The only legitimate broad writer of `research/` is the `research` agent invoked from the research terminal.
  - **Narrow exception — `research/algorithm.md`:** the `reporter` agent (and only the reporter) is permitted to UPDATE `research/algorithm.md` to keep it in sync with implementation. Permitted writes: (a) sync the **Production Value** column in the Hyperparameter Space table when `backend/config/settings.py` RECOMMENDATION dict changes; (b) append a one-line `_(Updated YYYY-MM-DD <sha_short>: <one-line>)_` annotation under any phase / formula / edge-case section whose corresponding implementation just changed; (c) maintain a `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` line near the top. Forbidden: rewriting algorithm theory, removing existing content, adding new sections, or touching any other file under `research/`. Reporter must NEVER touch `research/spec/`, `research/search/`, or `research/investigations/`. The `git-manager` agent likewise allows `research/algorithm.md` (and only that file) into staged commits via an explicit override path; broad `research/*` exclusion otherwise stands.
  - **Design pipeline ownership**: the **`designer`** agent (and any `design-*` sub-agents it creates) exclusively owns the frontend UI layer (JSX styles, animations, colors, layout, `MOCK_*` constants), `DESIGN.md`, and `.claude/agents/design-*.md`. Main pipeline agents (`orchestrator`, `back-maker`, `front-maker`, `reviewer`, `security-manager`, `git-manager`, `reporter`, `algo-tester`, `web-tester`) and the review terminal (`/review`) are **READ-ONLY** on these. The frontend **data layer** (`useState`, `useEffect`, `callApi()`, custom hooks, error handling, data transformations) remains main pipeline's territory (`front-maker`). The UI vs Data split inside the same `.jsx` file is enforced **per-line, not per-file** — both terminals coexist via Git's 3-way merge. See `.claude/agents/designer.md` for the full layer-boundary rules and reciprocal `TODO(claude):` / `TODO(designer):` handoff markers.

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
  - **MUST READ `DESIGN.md`**: All UI work (designer + design-* sub-agents in the design terminal, and front-maker in the main pipeline whenever data-layer wiring touches surrounding JSX) MUST consult `DESIGN.md` for our visual design system, colors, sizes, and UI rules before writing any code.
  - All component styles are inline JS objects -- Tailwind is NOT used in components
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom)
  - Accent colors are hardcoded hex in inline styles (not CSS vars) -- rely on `DESIGN.md` when applying colors
  - Do NOT rewrite inline styles arbitrarily; they are the intentional design — the **design pipeline** (`designer` agent) owns this layer; main pipeline (`front-maker`) is read-only on JSX styles. See `.claude/agents/designer.md` for the full UI-vs-Data layer split.

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

  ## Pre-Push Review (`/review`)

  The pre-push gate is a single canonical workflow at `.claude/commands/review.md`,
  invoked in the review terminal via `/review` OR natural language (see "Natural
  language review trigger" below). It combines:

  - **Part A** — Static deep review across 7 axes (architecture, correctness,
    performance, security, code quality, test coverage, cross-commit drift). Writes
    report to `.claude/reviews/<sha>.md` + `latest.md`.
  - **Part B** — Strict browser verification (spec-aligned latency budgets, 3 personas
    × ≥25 swipes, zero-tolerance error gates, edge cases). **Runs only when
    UI-affecting paths are in scope** (frontend/, recommendation/views.py, engine.py,
    accounts/, urls.py, recommendation/migrations/, RECOMMENDATION settings); skipped
    automatically for pure docs/config commits.
  - **Part C** — HEAD + origin/main drift checks. Emits one of
    `REVIEW-PASSED` / `REVIEW-ABORTED` / `REVIEW-FAIL` to `.claude/Task.md ## Handoffs`.

  ### Natural language review trigger

  In the review terminal, the user typically types natural-language review requests
  rather than the explicit slash command. Recognize phrases like **"리뷰해줘"**,
  **"review"**, **"review please"**, **"검토해줘"**, **"리뷰"**, **"리뷰 좀"**,
  **"branch review"**, etc. as invocations of the `/review` workflow. Read
  `.claude/commands/review.md` and execute its steps in this session.

  This trigger applies primarily in the review terminal context. In the main terminal,
  the user typically uses orchestrator-driven flows for development; if they say
  "리뷰해줘" while working with the orchestrator, prefer the orchestrator's inner-loop
  `reviewer` subagent unless they explicitly say "pre-push review" or are clearly
  asking to run the full gate.

  ### Workflow details

  **Invocation:** on a separate "review terminal" Claude Code session, type
  `/review` (default scope: `origin/main..HEAD` — the unpushed commits on the
  current branch) or `/review <range>` (e.g. `/review HEAD~5..HEAD`). Or just say
  "리뷰해줘" / "review please" — the natural-language trigger above maps to the
  same workflow.

  **Output:**
  - `.claude/reviews/{sha_short}.md` -- per-commit archive
  - `.claude/reviews/latest.md` -- stable read path; main implementation terminal
    reads this on demand when relevant (never auto-loaded)
  - Appends one of `REVIEW-PASSED: <sha>` (drift-verified, ready for manual `git push`
    from the review terminal), `REVIEW-ABORTED: <sha> — <reason>` (PASS but drift
    detected), or `REVIEW-FAIL: <sha> — <summary>` to the `## Handoffs` section of
    `.claude/Task.md` so the main terminal can pick up the verdict on its next session

  **Scope:** unpushed commits on the current branch (`origin/main..HEAD` by default,
  or the user-supplied range). Reads all changed files (full content, not just hunks)
  plus `.claude/Goal.md` + `.claude/Report.md` for architecture grounding.

  **7 axes:** architecture alignment, correctness/logic depth, performance/optimization,
  security in depth, code quality, test coverage, cross-commit drift. Severity:
  CRITICAL / MAJOR / MINOR.

  **Pre-push gate semantics:** `/review` is **read-only on source code** (never edits
  backend / frontend / research) but acts as the **pre-push gate**. The main orchestrator
  pipeline commits via `git-manager` and stops — it never pushes. The user runs
  `/review` (or natural language) in the review terminal; the unified verdict lands in
  `.claude/reviews/latest.md` and a one-line signal is appended to the `## Handoffs`
  section of `.claude/Task.md`. The signal is one of:

  - `REVIEW-PASSED: <sha> — drift checks passed; run \`git push\` manually from this terminal`
    (clean PASS, no MINORs, browser test passed if applicable). On `PASS-WITH-MINORS` the
    signal inlines `<K> MINOR noted (see .claude/reviews/latest.md)` — the count is
    visible without opening the report; MINORs are non-blocking for push.
  - `REVIEW-ABORTED: <sha> — <reason>` — review verdict was PASS but drift was detected
    during the review. Either HEAD advanced (re-run `/review`) or origin/main moved
    (`git pull --rebase` + re-review).
  - `REVIEW-FAIL: <sha> — <summary>` — either Part A had CRITICAL/MAJOR findings, OR
    Part B browser test failed. Re-enters the orchestrator fix loop (max 2 cycles).

  **`/review` never runs `git push` itself; push is always user-initiated.**

  **Browser-verification conditional (Part B):** Part B runs ONLY when UI-affecting
  paths are in scope (frontend/, recommendation/views.py, engine.py, accounts/, urls.py,
  recommendation/migrations/, RECOMMENDATION settings). For pure docs/config commits,
  Part B is automatically skipped and the report notes the skip. The local dev server
  (frontend on :5174, backend on :8001, DEV_LOGIN_SECRET in `backend/.env`) must be
  running for Part B; otherwise it FAILs with that diagnostic.

  Part B's strict gates per spec Section 4: `time-to-first-card < 4 s` (5 s for bare
  queries), per-swipe p95 < 700 ms, zero console errors, zero unexpected 4xx/5xx
  (auth-401-refresh path explicitly allowed), no duplicate cards, expected phase
  transitions, strict API response shape assertion, edge cases (refresh-resume, action
  card flow, persona report, network failure injection), multi-session no-contamination,
  spec primary-metric infrastructure sentinel (Sprint 0 A3 `saved_ids` field).

  **Difference from inner-loop `web-tester`:** the orchestrator pipeline's inner loop
  uses the fast `web-tester` agent (1 persona, ≥10 swipes, no latency assertion,
  retries on flake, console errors reported but not failed) to avoid blocking
  iteration. Part B of `/review` is the strict pre-push variant — slower, no retries,
  all gates hard. The two are complementary; Part B does NOT replace `web-tester` in
  the inner loop.

  **Push-fail-then-rebase discipline:** if `git push` fails non-ff in the narrow window
  between the drift check and the user's push, and the user recovers with
  `git pull --rebase`, the rebase rewrites local commit SHAs. The existing
  `REVIEW-PASSED: <old_sha>` signal is now stale — it points to a SHA that no longer
  exists locally. Re-run `/review` (or just say "리뷰해줘") before retrying
  `git push`; only a `REVIEW-PASSED` at the current HEAD's SHA is a valid push ticket.

  `/review` **supplements** the fast inner-loop `reviewer` (API contracts, logic bugs,
  obvious perf), `security-manager` (SQLi/XSS/auth keyword scan), and `web-tester`
  agents, filling their explicit exclusions: refactoring, optimization opportunities,
  test coverage, cross-commit drift, architecture alignment, spec-strict latency
  budgets, and edge-case coverage. See `.claude/WORKFLOW.md` "Multi-Terminal
  Coordination" for the full pre-push sequence.

  ## Database: architecture_vectors Schema
  Owned by Make DB. Django reads via raw SQL only -- never ORM, never migrate.
  <!-- Last synced 2026-04-29 with Make DB v2 + Divisare migration. Reference: research/infra/03-make-db-snapshot.md §2 -->

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
      embedding        VECTOR(384) NOT NULL,

      -- Versioning (Make DB Phase 1)
      vocab_version            TEXT DEFAULT 'v2',          -- vocab_version snapshot per row
      prompt_version           TEXT,                       -- "{label}-{sha256(prompt)[:8]}"

      -- Divisare integration (Make DB Phase 8B+ canonical migration)
      divisare_id              INTEGER,                    -- canonical Divisare project ID
      divisare_slug            TEXT,                       -- divisare URL slug
      abstract                 TEXT,                       -- short Divisare abstract
      architect_canonical_ids  INTEGER[],                  -- canonical architect cluster IDs (PROF1 join key)
      divisare_tags            TEXT[],                     -- raw Divisare tag taxonomy
      divisare_credits         JSONB,                      -- {"structures":[...], "lighting":[...], ...}
      cover_image_url_divisare TEXT,                       -- single full external URL, hotlink target
      divisare_gallery_urls    TEXT[],                     -- ~10-19 per project, full external URLs

      -- Provenance metadata
      provenance               JSONB                       -- {"name":"divisare","description":"metalocus", ...}
  );
  ```

  ## Normalized `program` Values
  Used in filters and Gemini persona reports. Must use exactly these values -- no raw strings.

  `Housing` | `Office` | `Museum` | `Education` | `Religion` | `Sports` |
  `Transport` | `Hospitality` | `Healthcare` | `Public` | `Mixed Use` |
  `Landscape` | `Infrastructure` | `Other`
