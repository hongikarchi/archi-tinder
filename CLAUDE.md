# Make Web Service -- Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  The running code is the source of truth for system architecture and API surface — derive it by reading the code.
  For collaboration / branch model / PR workflow / file ownership, see `CONTRIBUTING.md`.
  For the build workflow (the single session, its sub-agents, the `orchestrate` skill), see `.claude/WORKFLOW.md`.

  ## Branch Model — HARD RULES (must follow before any commit)

  **The team uses GitHub Flow with a develop integration branch:**

  - `main` — production (Railway auto-deploy). Protected: PR-only, force-push blocked, requires Code Owner approval.
  - `develop` — integration branch. Protected: PR + status check + Code Owner review. Sole-admin CODEOWNERS = PR author, so Code Owner review is structurally unsatisfiable → admin-bypass squash-merge (`gh pr merge --admin`) is the current workflow until collaborators join.
  - `feature/<role>-<topic>` — per-task work branches:
    - Role A (algorithm) → `feature/algo-<topic>`
    - Role B (SNS / profiles / boards) → `feature/sns-<topic>`
    - Role C (admin / everything else) → `feature/admin-<topic>`

  **Hard rules — NEVER violate:**

  1. **Never commit directly to `main` or `develop`.** Server-side branch protection will reject the push, but you should not even try. Always work on a `feature/*` branch.
  2. **Before any code edit, run `git status`** to confirm the current branch. If on `main` or `develop`, do not proceed with edits — first sync develop and create a feature branch:
     ```bash
     git checkout develop && git pull origin develop
     git checkout -b feature/<role>-<topic>
     ```
  3. **Never run `git push origin main` or `git push origin develop`** — pushes go from `feature/*` branches only, then to `develop` via PR, then to `main` via PR.
  4. **Never use `--no-verify`, `--force`, `--force-with-lease`, `git rebase -i`, `git reset --hard` on shared branches**, or any history-rewriting flag. **Single carve-out — post-deploy develop force-reset (Bug #5)**: immediately after a successful `develop → main` squash deploy merge, `origin/develop` MUST be force-reset to match `origin/main` to prevent commit-graph divergence that breaks the next deploy PR (see `.claude/agents/git-publisher.md` § Mode 3 for the exact `gh api -X PATCH refs/heads/develop --field force=true` command + safety checks). This is the ONLY permitted force on a shared branch and applies ONLY in the immediate post-deploy window. Precondition: every commit on `origin/develop` must be content-equal to `origin/main` (no unmerged in-flight feature PR targets `develop`).
  5. **PRs target `develop`, not `main`.** The admin batches features and opens a separate `develop → main` PR when ready to deploy.
  6. **One-time setup per clone (each collaborator must run once):**
     ```bash
     ./tools/install-hooks.sh
     ```
     Without this, your local does not have the migration-numbering pre-push hook, and you may push a duplicate-numbered Django migration that breaks the team.

  **If `git status` at session start shows you are on `main` or `develop` with uncommitted changes**: the previous session likely did not switch to a feature branch. Stash or save the work, then create a proper feature branch before continuing. Do not stage or commit while on a protected branch.

  Full details (workflow scripts, common pitfalls, file ownership table): see `CONTRIBUTING.md` at the repo root.

  ## Workflow — one session + sub-agents

  ArchiTinder Make Web is built from **one Claude Code session** (the orchestrator). It owns architecture, schema, auth, product + release decisions, and review — it does not write feature code itself; it dispatches sub-agents and runs the `orchestrate` skill.

  - **`orchestrate` skill** (`.claude/skills/orchestrate/`) — the feature-implementation playbook the session runs itself (a skill, not an agent, because only the main session can dispatch sub-agents).
  - **8 sub-agents** (`.claude/agents/`) — `back-maker` · `front-maker` (implementation) · `code-review` · `security-manager` (inner-loop review, pre-commit) · `app-test` (pre-push browser + drift gate) · `git-manager` (commit) · `git-publisher` (push / PR / merge / deploy) · `reporter` (session-end state).
  - **agent vs skill**: isolated work that returns a result → an agent. A procedure the main session runs itself, including anything that dispatches agents → a skill. There are no slash commands.

  Full pipeline, session model, planning protocol, token-saving rules: **`.claude/WORKFLOW.md`**.

  ## Rules
  - All building references must use `canonical_bld_id` (TEXT PK like `'bld_000344'`) -- never `name`, `slug`, or any language-dependent field.
  - Do NOT create or migrate the `canonical_v2_buildings` table -- it is owned by Make DB.
  - Every building query MUST gate on `is_publishable = true` (39 of 39,776 rows are non-publishable). `engine._build_filter_sql` already emits this clause; raw SQL elsewhere must add it.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - **`docs/algorithm.md` reporter sync (narrow write permission)**: only the `reporter` agent updates `docs/algorithm.md`, and only to keep it in sync with implementation. Permitted writes: (a) sync the **Production Value** column in the Hyperparameter Space table when `backend/config/settings.py` RECOMMENDATION dict changes; (b) append a one-line `_(Updated YYYY-MM-DD <sha_short>: <one-line>)_` annotation under any phase / formula / edge-case section whose corresponding implementation just changed; (c) maintain a `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` line near the top. Forbidden: rewriting algorithm theory, removing existing content, adding new sections. Other `docs/` files (specs, etc.) are admin-owned plain documents — anyone can edit via PR per CONTRIBUTING.md.
  - **Plan mode protocol — Korean summary + multiple choice + one question at a time** (durable across sessions). When entering plan mode:
    1. **Data gathering** — read-only exploration (Explore agent or direct reads). Collect facts before analysis.
    2. **Korean summary in chat** — a *short* (5-15 line) Korean summary of the diagnosis / proposal. Do NOT dump long English plan files into chat; the plan file can be detailed, the chat presentation is summarized + Korean.
    3. **Get user review** — wait for the user to acknowledge / correct / approve before introducing decisions.
    4. **Decisions one at a time, multiple choice** — `AskUserQuestion`, **one question per turn**, 3-4 options (label + description each, trade-off stated). Wait for the answer before the next. Never batch.
    5. **Plan file finalize** — once decisions are answered, update the plan file. Korean summary block; English for code identifiers.
    6. **ExitPlanMode** — only AFTER all decisions are settled. Do not ask "should I proceed?" — that is what `ExitPlanMode` does.
    Why: user request 2026-04-29 — long English plan dumps overwhelm; sequential multiple-choice supports careful per-topic decisions. Applies to all plan-mode entries.
  - **Implementation delegation — HARD RULE** (durable across sessions). The session owns *architecture, schema, auth, product + release decisions, and review* — it does **NOT** write production feature code directly. Every `backend/` or `frontend/` feature / bug-fix / refactor edit is delegated: full features, unclear-root-cause bugs, or cross-cutting refactors → the `orchestrate` skill; bounded mechanical changes → `back-maker` / `front-maker` (`model: sonnet`) sub-agents. The session picks the model / effort per task and dispatches — it does not fall back to implementing in opus because delegation feels like overhead. **Carve-out (direct edit OK)**: meta / infra (`tools/`, `hooks/`, `.github/`), single-line policy fixes, sub-MINOR follow-ups, and pure docs (`CLAUDE.md`, `.claude/*`, `docs/*`, `CONTRIBUTING.md`, `DESIGN.md`, `README.md`) — direct edit + `git-manager`. Why: codified 2026-05-15 — `back-maker` / `front-maker` carry `model: sonnet`; the session must not implement feature code in opus "because delegating feels like overhead."

  ## Product Constitution

  The highest-level decision reference — apply when two valid choices conflict.

  **Out-of-scope (do NOT build without explicit user reauthorization):**
  - Romance / dating — P2 person-to-person matching is *aesthetic taste* matching, not romantic.
  - Real-estate transactions, materials marketplace, contractor/construction matching, blueprint/CAD marketplace, design-as-a-service marketplace.
  - Markets outside Korea (English UI supported, but corpus + community are Korea-first; global is v3+).
  - Industries outside architecture (interior, landscape, furniture — the corpus is architecture).

  **Decision principles (tiebreakers, in order):**
  1. **Out-of-scope check first** — if a feature crosses a boundary, stop and ask the user; do not silently expand scope.
  2. **Persona priority** — P1 (Firm→Jobseeker) > P2 (Person→Person) > P3 (Firm→Client) > P4 (Individual/gateway). P1 wins a design conflict unless the user overrides.
  3. **Foundation correctness > feature breadth** — a correct algorithm with 3 features beats a buggy one with 30. Defer features that pile on shaky foundations.
  4. **Honest matching > engagement metrics** — never introduce patterns that boost session length / total swipes at the cost of taste-match quality.
  5. **External-dependency restraint** — prefer extending Gemini / HuggingFace / Imagen / Cloudflare R2 / Neon Postgres before adding a new external service; new dependencies need user approval.
  6. **Algorithm reference is the source of truth** for hyperparameters and phase semantics — if `docs/algorithm.md` says X, code does X.
  7. **Korea-first** — when localization decisions conflict, Korean UX wins; English is supported, not co-equal.

  **Working principle**: problem definition first → plan as a written artifact → architecture before tactical code → foundational correctness (data shape, matching algorithm, feedback loop) over polish.

  ## Audit Trail Locations
  | Category | Location | Writer |
  |---|---|---|
  | **Spec** (binding requirements / pending work) | `docs/specs/*.md` | admin |
  | **Algorithm reference** (theory + hyperparams) | `docs/algorithm.md` | admin (reporter syncs prod values) |
  | **Plan** (`/plan` artifacts) | `.claude/plans/*.md` | the session |
  | **Task board** (roadmap + tasks) | `.claude/Task.md` | reporter agent |
  | **Project dashboard** (live state, human-facing) | `project/dashboard.html` + `project/state.js` | reporter agent |

  ## Target Structure
  frontend/   <- React 18 + Vite
  backend/    <- Django 4.2 LTS + DRF + pgvector + Gemini + social auth
  web-testing/ <- Playwright E2E visual test runner + dashboard

  ## Current State
  - frontend/: BUILT -- rich UI, project sync from backend on login; design-system redesign in progress (light-mode tokens + 4-theme switcher)
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
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS).
  - `canonical_v2_buildings` -- read-only via raw SQL on the `'buildings'` connection; never ORM or migrate. Old `architecture_vectors` table is deprecated.
  - `images/batch/` POST -- batch-fetch building cards by `canonical_bld_ids` list.
  - Run: `cd backend && python3 manage.py runserver 8001`.

  ## Pre-Push Gate — `app-test`

  The pipeline commits but the `app-test` agent gates the push. It runs the live browser user-journey verification (dev-login → search → swipe lifecycle → results → error recovery, with card-data validation, phase-transition checks, spec-aligned latency budgets) plus the HEAD / `origin/develop` drift check. It returns one verdict — PASS / PASS-WITH-MINORS / FAIL / ABORTED (drift) — and persists nothing. `app-test` is auto-skipped for pure docs/config changes (no UI/runtime surface). Static code review is the separate `code-review` agent's job (inner loop, per change) — `app-test` does not re-do it. Spec: `.claude/agents/app-test.md`.

  ## Database
  See **`docs/database-schema.md`** for the `canonical_v2_buildings` CREATE TABLE
  + normalized `program` vocabulary + image-resolution semantics + Make-DB-
  ownership hard rules. Backend work touching the building data layer must
  consult this file. Hard rules (also in `## Rules` + `## Backend Conventions`):
  use `canonical_bld_id` only; read the building DB via the `'buildings'`
  connection; never ORM or migrate `canonical_v2_buildings`; gate every query on
  `is_publishable = true`; embeddings are pre-computed.
