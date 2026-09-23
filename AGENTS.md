# Make Web Service -- Codex Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  The running code is the source of truth for system architecture and API surface — derive it by reading the code.
  For collaboration / branch model / PR workflow / file ownership, see `CONTRIBUTING.md`.
  Work directly in the current checkout. Agent delegation and local workflow skills are optional.

  ## Product Identity

  ### Core Promise
  10-15 swipes → Aha! moment (taste captured).
  > "이 앱이 내 미묘한 취향을 벌써 눈치챘네?"

  Two pillars (물리적 직관성 + 마법 같은 반응성). Detail → `docs/algorithm.md`.

  ## Branch Model — HARD RULES (must follow before any commit)

  **The team uses GitHub Flow with a develop integration branch:**

  - `main` — production (Railway auto-deploy). Protected: PR-only, force-push blocked, requires Code Owner approval.
  - `develop` — integration branch. Protected: PR + status check + Code Owner review. Sole-admin CODEOWNERS = PR author, so Code Owner review is structurally unsatisfiable → admin-bypass squash-merge (`gh pr merge --admin`) is the current workflow until collaborators join.
  - `feature/<role>-<topic>` — per-task work branches:
    - Role A (algorithm) → `feature/algo-<topic>`
    - Role B (SNS / profiles / boards) → `feature/sns-<topic>`
    - Role C (admin / everything else) → `feature/admin-<topic>`
    - Local AI agents → `feature/codex-<topic>` (Codex) / `feature/claude-<topic>` (Claude Code)

  **Hard rules — NEVER violate:**

  1. **Never commit directly to `main` or `develop`.** Server-side branch protection will reject the push, but you should not even try. Always work on a `feature/*` branch.
  2. **Before any code edit, run `git status`** to confirm the current branch. If on `main` or `develop`, do not proceed with edits — first sync develop and create a feature branch:
     ```bash
     git checkout develop && git pull origin develop
     git checkout -b feature/<role>-<topic>
     ```
  3. **Never run `git push origin main` or `git push origin develop`** — pushes go from `feature/*` branches only, then to `develop` via PR, then to `main` via PR.
  4. **Never use `--no-verify`, `--force`, `--force-with-lease`, `git rebase -i`, `git reset --hard` on shared branches**, or any history-rewriting flag. **Single carve-out — post-deploy develop force-reset (Bug #5)**: immediately after a successful `develop → main` squash deploy merge, `origin/develop` MUST be force-reset to match `origin/main` to prevent commit-graph divergence that breaks the next deploy PR (see `.codex/agents/git-publisher.toml` § Mode 3 for the exact `gh api -X PATCH refs/heads/develop --field force=true` command + safety checks). This is the ONLY permitted force on a shared branch and applies ONLY in the immediate post-deploy window. Precondition: every commit on `origin/develop` must be content-equal to `origin/main` (no unmerged in-flight feature PR targets `develop`).
  5. **PRs target `develop`, not `main`.** The admin batches features and opens a separate `develop → main` PR when ready to deploy.
  6. **One-time setup per clone (each collaborator must run once):**
     ```bash
     ./tools/install-hooks.sh
     ```
     Without this, your local does not have the migration-numbering pre-push hook, and you may push a duplicate-numbered Django migration that breaks the team.
  7. Work in the user-selected checkout on a feature branch. A separate Codex clone is not required. Coordinate concurrent work and preserve unrelated changes.

  **If `git status` at session start shows you are on `main` or `develop` with uncommitted changes**: the previous session likely did not switch to a feature branch. Stash or save the work, then create a proper feature branch before continuing. Do not stage or commit while on a protected branch.

  Full details (workflow scripts, common pitfalls, file ownership table): see `CONTRIBUTING.md` at the repo root.

  ## Working and publishing

  Implement and verify changes directly; no mandatory orchestrator, maker agents,
  review agents, audit skills, or fixed pipeline. Use tools or delegation when useful.
  Keep the branch protections and PR workflow above. Review the diff and run checks
  appropriate to the change before committing or publishing. Never commit secrets.
  Push / PR / merge requires explicit user authorization or an active approved plan.
  Feature PRs target develop; deploying develop to main requires explicit deploy authorization.

  ## Rules
  - All building references must use `canonical_bld_id` (TEXT PK like `'bld_000344'`) -- never `name`, `slug`, or any language-dependent field.
  - Do NOT create or migrate the `canonical_v2_buildings` table -- it is owned by Make DB.
  - Every building query MUST gate on `is_publishable = true` (2,614 of 39,478 rows ~6.6% are non-publishable as of C23 on 2026-05-24). `engine._build_filter_sql` already emits this clause; raw SQL elsewhere must add it.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - **`docs/algorithm.md` reporter sync (narrow write permission)**: implementation work may update `docs/algorithm.md`, and only to keep it in sync with implementation. Permitted writes: (a) sync the **Production Value** column in the Hyperparameter Space table when `backend/config/settings.py` RECOMMENDATION dict changes; (b) append a one-line `_(Updated YYYY-MM-DD <sha_short>: <one-line>)_` annotation under any phase / formula / edge-case section whose corresponding implementation just changed; (c) maintain a `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` line near the top. Forbidden: rewriting algorithm theory, removing existing content, adding new sections. Other `docs/` files (specs, etc.) are admin-owned plain documents — anyone can edit via PR per CONTRIBUTING.md.
  - **Plan mode protocol — Korean summary + multiple choice + one question at a time** (durable across sessions). When entering plan mode:
    1. **Data gathering** — read-only exploration (Explore agent or direct reads). Collect facts before analysis.
    2. **Korean summary in chat** — a *short* (5-15 line) Korean summary of the diagnosis / proposal. Do NOT dump long English plan files into chat; the plan file can be detailed, the chat presentation is summarized + Korean.
    3. **Get user review** — wait for the user to acknowledge / correct / approve before introducing decisions.
    4. **Decisions one at a time, multiple choice** — `AskUserQuestion`, **one question per turn**, 3-4 options (label + description each, trade-off stated). Wait for the answer before the next. Never batch.
    5. **Plan file finalize** — once decisions are answered, update the plan file. Korean summary block; English for code identifiers.
    6. **ExitPlanMode** — only AFTER all decisions are settled. Do not ask "should I proceed?" — that is what `ExitPlanMode` does.
    Why: user request 2026-04-29 — long English plan dumps overwhelm; sequential multiple-choice supports careful per-topic decisions. Applies to all plan-mode entries.


  ## Product Constitution

  The highest-level decision reference — apply when two valid choices conflict.

  **Out-of-scope (do NOT build without explicit user reauthorization):**
  - Romance / dating — P2 person-to-person matching is *aesthetic taste* matching, not romantic.
  - Real-estate transactions, materials marketplace, contractor/construction matching, blueprint/CAD marketplace, design-as-a-service marketplace.
  - Markets outside Korea (English UI supported, but corpus + community are Korea-first; global is v3+).
  - Industries outside architecture (interior, landscape, furniture — the corpus is architecture).

  **Decision principles (tiebreakers, in order):**
  1. **Out-of-scope check first** — if a feature crosses a boundary, stop and ask the user; do not silently expand scope.
  2. **Persona priority** — P2 (Person→Person) > P1 (Firm→Jobseeker) > P3 (Firm→Client) > P4 (Individual/gateway). P2 wins a design conflict unless the user overrides. (Reordered 2026-09-17 by user decision — see `docs/plans/2026-09-17-competition-team-design.md` §1; previously P1 > P2.)
  3. **Foundation correctness > feature breadth** — a correct algorithm with 3 features beats a buggy one with 30. Defer features that pile on shaky foundations.
  4. **Honest matching > engagement metrics** — never introduce patterns that boost session length / total swipes at the cost of taste-match quality.
  5. **External-dependency restraint** — prefer extending Gemini / HuggingFace / Imagen / Cloudflare R2 / Neon Postgres before adding a new external service; new dependencies need user approval.
  6. **Algorithm reference is the source of truth** for hyperparameters and phase semantics — if `docs/algorithm.md` says X, code does X.
  7. **Korea-first** — when localization decisions conflict, Korean UX wins; English is supported, not co-equal.

  **Working principle**: problem definition first → plan as a written artifact → architecture before tactical code → foundational correctness (data shape, matching algorithm, feedback loop) over polish.

  ## Audit Trail Locations
  | Category | Location | Writer |
  |---|---|---|
  | **Task board** (roadmap + Next backlog + Done log) | `Task.md` | the session |
  | **Algorithm reference** (theory + hyperparams) | `docs/algorithm.md` | admin (reporter syncs prod values) |
  | **Plan** (`/plan` artifacts) | `.codex/plans/*.md` | the session |
  | **Project dashboard** (live state, human-facing) | `project/dashboard.html` + `project/state.js` | the session |

  ## Target Structure
  frontend/   <- React 18 + Vite
  backend/    <- Django 4.2 LTS + DRF + pgvector + Gemini + social auth
  web-testing/ <- Playwright E2E visual test runner + dashboard

  ## Current State
  - frontend/: BUILT -- rich UI, project sync from backend on login; design-system foundation shipped (PR #54 tokens.css 4 themes + PR #59 theme/font server persistence). Per-component visual rework paused (see Task.md `## Next` § `FRONT-DESIGN-1`).
  - backend/: BUILT -- full recommendation engine + Gemini LLM + project persistence; app DB split from the Make-DB building DB (two `DATABASES` aliases)
  - web-testing/: BUILT -- E2E visual test runner with persona generation, Playwright tests, and dashboard
  - Google login: auth-code flow (VITE_GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET required)

  ## Frontend Conventions
  - **MUST READ `DESIGN.md`**: All UI work (any role's frontend changes — JSX styles, layout, colors, animations) MUST consult `DESIGN.md` (root) for our visual design system, colors, sizes, and UI rules before writing any code.
  - Component styling = hybrid per `DESIGN.md` §4: `tokens.css` CSS variables (themeable values) + co-located CSS Modules (`*.module.css`) for interactive components owning `:hover`/`:focus`/`:active` + inline `style={{}}` for layout / one-off / dynamic values. No Tailwind / Bootstrap / MUI / styled-components / emotion.
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom).
  - Accent colors are themed CSS variables (`var(--accent-1/2/3)`, `var(--color-destructive)`) defined per-theme in `tokens.css` — see `DESIGN.md` §1.2/§1.3.
  - Do NOT rewrite inline styles arbitrarily; treat existing inline styles as load-bearing unless `DESIGN.md` rules say otherwise — when in doubt, consult `DESIGN.md` and surface the change in the PR description.

  ## Backend Conventions
  - Django 4.2 LTS required (Python 3.9.6 on this machine; Django 5+ needs Python 3.10+).
  - All URL patterns must have trailing slashes -- Django APPEND_SLASH only redirects GET, not POST.
  - Neon PostgreSQL: use `sslmode=require`; psycopg2-binary (not asyncpg).
  - **Two `DATABASES` aliases**: `'default'` = the Make Web app DB (`DB_*` env vars) — Django ORM + migrations target this only; `'buildings'` = the Make-DB-owned building DB (`BUILDINGS_DB_*` env vars) — read-only raw SQL via `connections['buildings']`, NEVER ORM or migrate. `config/db_router.py` blocks `migrate` on `'buildings'`.
  - **Neon role separation** (INFRA-DB-1, 2026-05-25): Django runtime (Railway prod + local) logs into `user_data` as `make_web_app` (LOGIN + SELECT/INSERT/UPDATE/DELETE on `public.*` + USAGE/SELECT on sequences; **no DDL**, **no role mgmt**, **no extension** privileges, NOT a member of `neon_superuser`). `manage.py migrate` requires DDL → run from operator machine with a temporary `DB_USER=neondb_owner` swap; never leave `neondb_owner` as the long-running runtime user. The buildings DB uses `make_web` (SELECT-only on `archi_data`) per PR #93. Create roles via psql `CREATE ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`, **not** `neonctl roles create` (that grants `neon_superuser`).
  - **Cache backend** (INFRA-REDIS-1, 2026-05-26): Django runtime cache uses Redis in prod (`REDIS_URL` env on Railway pointing at the managed Redis service), LocMemCache for local dev when `REDIS_URL` is unset. Never bypass Django's cache abstraction — no direct `redis-py` calls; use `from django.core.cache import cache` so the same code works both backends. Multi-worker prod correctness for PR 3 (BACK-AUTH-1) + PR 4 (PERF-PREFETCH-CHAIN) depends on this swap.
  - **Local-vs-prod Neon branches** (INFRA-ENV-1, 2026-05-25): local `backend/.env` points at a Neon CHILD branch off `production` (currently `local-dev-2`, endpoint `ep-holy-band-a1w0u5am`). Railway prod injects its own env vars pointing at the `production` branch endpoint (currently `ep-broad-hat-a1jaomn7`). Never point local at the production endpoint — local writes would land in real prod rows. Re-provision via `neonctl branches create --name local-dev-N --parent production --project-id holy-pond-45504245`.
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS).
  - `canonical_v2_buildings` -- read-only via raw SQL on the `'buildings'` connection; never ORM or migrate. (Legacy `architecture_vectors` table was dropped 2026-05-24.)
  - `images/batch/` POST -- batch-fetch building cards by `canonical_bld_ids` list.
  - Run: `cd backend && python3 manage.py runserver 8001`.

  ## Verification before publishing

  Review the diff and run relevant lint/build checks. For UI changes, verify the
  changed surface at desktop and mobile widths when browser access is available.
  Report any verification that could not run. No specific agent or skill is required.

  ## Database
  See **`docs/database-schema.md`** for the `canonical_v2_buildings` CREATE TABLE
  + normalized `program` vocabulary + image-resolution semantics + Make-DB-
  ownership hard rules. Backend work touching the building data layer must
  consult this file. Hard rules (also in `## Rules` + `## Backend Conventions`):
  use `canonical_bld_id` only; read the building DB via the `'buildings'`
  connection; never ORM or migrate `canonical_v2_buildings`; gate every query on
  `is_publishable = true`; embeddings are pre-computed.
