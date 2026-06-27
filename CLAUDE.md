# Make Web Service -- Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  The running code is the source of truth for system architecture and API surface — derive it by reading the code.
  For collaboration / branch model / PR workflow / file ownership, see `CONTRIBUTING.md`.
  For the build workflow (the single session, its sub-agents, the `orchestrate` skill), see `.claude/WORKFLOW.md`.

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
    - Local AI agents → `feature/claude-<topic>` (Claude Code) / `feature/codex-<topic>` (Codex) — each in its OWN clone

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
  7. **One clone per worker — never operate in another worker's directory (concurrent-agent isolation).** Every worker (remote human OR local AI tool) owns ONE working directory with its OWN `.git`, on its own `feature/*` branch, with its own PR. **Claude's working dir = the main clone `make_web/`** (cmux terminal; tendency: backend / API / recommendation-algorithm / DB — a default, not a hard wall, scope assigned per task). **Codex** works in its OWN separate clone `make_web-codex/` (browser, UI/UX), never in the main clone. **Do NOT use `git worktree` for session isolation** — worktrees share one `.git`, and on 2026-05-31 that shared `.git` let a Codex session move the main checkout's `HEAD` onto its branch (`feature/codex-loginpage`); a separate clone (own `.git`) is structurally immune. (The Agent tool's `isolation:"worktree"` is for parallel *sub-agents* within one session — unrelated to session isolation.) **Session-start check**: confirm you are in the main clone `make_web/` on `develop` or a `feature/claude-*` branch; if you are in the wrong directory, switch to the main clone before editing — do NOT `git reset` (separate clones make cross-contamination structurally impossible, so a wrong working dir is the only failure mode). Local branch prefix: `feature/claude-<topic>`. Full model: `CONTRIBUTING.md` § "Concurrent agents — one clone per worker".

  **If `git status` at session start shows you are on `main` or `develop` with uncommitted changes**: the previous session likely did not switch to a feature branch. Stash or save the work, then create a proper feature branch before continuing. Do not stage or commit while on a protected branch.

  Full details (workflow scripts, common pitfalls, file ownership table): see `CONTRIBUTING.md` at the repo root.

  ## Workflow — ultracode-main (Opus 4.8): one session + feature workflow + agents + skills

  ArchiTinder Make Web's Claude side runs as **one Claude Code orchestrator session on Opus 4.8** (concurrent with Codex in its own clone — HARD RULE 7). It owns architecture, schema, auth, product + release decisions, and review — it does not write feature code itself. The primary workflow is **ultracode = the Workflow tool**: the build+review CORE runs as a deterministic multi-agent Workflow script, and the session gates around it. Trivial mechanical edits stay solo (no workflow).

  - **Workflow** (`.claude/workflows/`) — deterministic multi-agent fan-out the session launches via the Workflow tool:
    - `feature` (`feature.js`) — build+review CORE: decompose → back-maker/front-maker (Sonnet) → code-review + security-manager (Sonnet, parallel) → **Opus adversarial-verify** of findings → 2-cycle fix loop. Returns `{ commitReady, ... }` and **performs NO git operations** — the publish gate lives in the session, outside the autonomous workflow (HARD RULE 1).
  - **Model tier map** (cost control = tiering inside the workflow, not avoiding fan-out): **Opus 4.8** = orchestrator + adversarial-verify/judge; **Sonnet 4.6** = back/front-maker, code-review, security-manager, app-test; **Haiku 4.5** = exploration/search. Every workflow `agent()` call MUST pin `model` explicitly — `agentType` does not carry the frontmatter tier; the default is inherit-Opus, which silently runs every worker on Opus.
  - **Skills** (`.claude/skills/`) — procedures the main session runs itself:
    - `orchestrate` — feature playbook: decompose → launch the `feature` workflow → git-commit → app-test → reporter-inline → publish gate.
    - `reporter-inline` — session-end audit (Task.md + state.js + algorithm.md). Runs inline before squash so audit ships in the SAME PR. **Replaces the `reporter` agent** (2026-05-26).
    - `git-commit` — single-commit creator with branch + secret guards. **Replaces the `git-manager` agent** (2026-05-26).
    - `git-publish` — feature → develop push + PR open + admin squash + cleanup (Mode 2). **Replaces the `git-publisher` agent's Mode 2** (2026-05-26).
  - **6 sub-agents** (`.claude/agents/`) — the workflow's `agentType` building blocks AND directly dispatchable by the session:
    - `back-maker` · `front-maker` — implementation (isolated context, sonnet).
    - `code-review` · `security-manager` — review (run inside the `feature` workflow).
    - `app-test` — pre-push browser + drift gate (dispatched by the session, post-commit, OUTSIDE the workflow).
    - `git-publisher` — push/PR/merge/deploy (Mode 2 via `git-publish` skill; agent only for Mode 3 + edge cases).
  - **Removed agents** (deleted 2026-05-31): `git-manager` · `reporter` — replaced by the `git-commit` / `reporter-inline` skills. Recoverable from git history.
  - **agent vs skill vs workflow**: isolated work returning a result → agent. A procedure the main session runs itself → skill. A deterministic multi-agent fan-out (loops, parallel, verify) → workflow. There are no slash commands.

  Full pipeline, session model, model tier map, planning protocol, token-saving rules: **`.claude/WORKFLOW.md`**.

  ## Git Operations — HARD RULE (2026-05-26)

  - **Default git ops** (commit / push / PR open / squash merge) → use the appropriate **skill** (`git-commit`, `git-publish`), executed by the main session. Routine commits use the `git-commit` skill (the `git-manager` agent was removed 2026-05-31). The `git-publisher` agent still fires for Mode 3 / edge cases (see escalation matrix below).
  - **Audit recording** (`Task.md ## Done` + `project/state.js` + conditional `docs/algorithm.md`) → use the **`reporter-inline` skill** BEFORE the publish step, in the same feature PR. **Reporter no longer ships a separate PR** — the audit commit lands on the same feature branch as the code commit and gets squashed together. (The `reporter` agent was removed 2026-05-31.)
  - **Escalation matrix → `git-publisher` agent** (Mode 3 territory or edge cases the skill cannot safely handle):
    - `develop → main` deploy mode (multi-PR batch + post-deploy `develop` force-reset to match `main`; requires explicit deploy keyword AND HARD RULE 4 carve-out citation).
    - External collaborator PR triage (PR from someone other than admin needs review + decision).
    - Rebase conflicts requiring multi-step recovery (`--force-with-lease` lease retries).
    - Push rejection with unclear cause.
    - Mid-merge failure with non-trivial error.
  - **`reporter-inline` skill failure** → fix the `state.js` / `Task.md` issue directly (e.g. a parse error from Mermaid escaping). The deprecated `reporter` agent fallback was removed 2026-05-31 — there is no agent to escalate to.
  - **Forbidden** (mirror HARD RULE 1, 3, 4):
    - Ad-hoc `git push origin develop` / `git push origin main`. Pushes go from `feature/*` only.
    - `gh pr create --base main` outside Mode 3 deploy. Default base is `develop`.
    - `--force` / `--force-with-lease` on a shared branch (single carve-out = post-deploy develop force-reset, agent Mode 3 only).
    - `--no-verify`, `--amend` on a pushed commit, `git rebase -i`, `git reset --hard` on shared branches.
  - **Deterministic enforcement** — `.claude/hooks/git-guard.py` (`PreToolUse(Bash)`, wired in project `.claude/settings.json`) blocks the Forbidden push/PR commands at the tool layer (direct/force push to develop/main, `git push --no-verify`, `gh pr create --base main` except the `--head develop` deploy PR). Fail-open; GitHub branch protection is the server-side backstop. Edit + re-test the guard standalone (stdin JSON, exit 2 = block).
  - **Publish gate** (mirror `[[feedback_publish_gate]]`): the `git-publish` skill Step 0 enforces. After commit, default action is STOP. Push / PR / merge requires explicit publish keyword (Korean: `올려`, `푸시`, `배포`, `merge`, `PR 만들어`, `배포해`, `deploy`, `ship`; English: `push`, `open PR`, `merge`, `deploy`, `ship`) OR an active `.claude/plans/<slug>.md` authorizing the action.

  ## Rules
  - All building references must use `canonical_bld_id` (TEXT PK like `'bld_000344'`) -- never `name`, `slug`, or any language-dependent field.
  - Do NOT create or migrate the `canonical_v2_buildings` table -- it is owned by Make DB.
  - Every building query MUST gate on `is_publishable = true` (2,614 of 39,478 rows ~6.6% are non-publishable as of C23 on 2026-05-24). `engine._build_filter_sql` already emits this clause; raw SQL elsewhere must add it.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - **`docs/algorithm.md` reporter sync (narrow write permission)**: only the `reporter-inline` skill updates `docs/algorithm.md`, and only to keep it in sync with implementation. Permitted writes: (a) sync the **Production Value** column in the Hyperparameter Space table when `backend/config/settings.py` RECOMMENDATION dict changes; (b) append a one-line `_(Updated YYYY-MM-DD <sha_short>: <one-line>)_` annotation under any phase / formula / edge-case section whose corresponding implementation just changed; (c) maintain a `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` line near the top. Forbidden: rewriting algorithm theory, removing existing content, adding new sections. Other `docs/` files (specs, etc.) are admin-owned plain documents — anyone can edit via PR per CONTRIBUTING.md.
  - **Plan mode protocol — Korean summary + multiple choice + one question at a time** (durable across sessions). When entering plan mode:
    1. **Data gathering** — read-only exploration (Explore agent or direct reads). Collect facts before analysis.
    2. **Korean summary in chat** — a *short* (5-15 line) Korean summary of the diagnosis / proposal. Do NOT dump long English plan files into chat; the plan file can be detailed, the chat presentation is summarized + Korean.
    3. **Get user review** — wait for the user to acknowledge / correct / approve before introducing decisions.
    4. **Decisions one at a time, multiple choice** — `AskUserQuestion`, **one question per turn**, 3-4 options (label + description each, trade-off stated). Wait for the answer before the next. Never batch.
    5. **Plan file finalize** — once decisions are answered, update the plan file. Korean summary block; English for code identifiers.
    6. **ExitPlanMode** — only AFTER all decisions are settled. Do not ask "should I proceed?" — that is what `ExitPlanMode` does.
    Why: user request 2026-04-29 — long English plan dumps overwhelm; sequential multiple-choice supports careful per-topic decisions. Applies to all plan-mode entries.
  - **Implementation delegation — HARD RULE** (durable across sessions). The session owns *architecture, schema, auth, product + release decisions, and review* — it does **NOT** write production feature code directly. Every `backend/` or `frontend/` feature / bug-fix / refactor edit is delegated: full features, unclear-root-cause bugs, or cross-cutting refactors → the `orchestrate` skill; bounded mechanical changes → `back-maker` / `front-maker` (`model: sonnet`) sub-agents. The session picks the model / effort per task and dispatches — it does not fall back to implementing in opus because delegation feels like overhead. **Carve-out (direct edit OK)**: meta / infra (`tools/`, `hooks/`, `.github/`), single-line policy fixes, sub-MINOR follow-ups, and pure docs (`CLAUDE.md`, `.claude/*`, `docs/*`, `CONTRIBUTING.md`, `DESIGN.md`, `README.md`) — direct edit + `git-commit` skill (the `git-manager` agent was removed 2026-05-31). Why: codified 2026-05-15 — `back-maker` / `front-maker` carry `model: sonnet`; the session must not implement feature code in opus "because delegating feels like overhead."

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
  | **Task board** (roadmap + Next backlog + Done log) | `Task.md` | reporter-inline skill (Phase 16-18 dimensions inlined here as of 2026-05-24; the prior `docs/specs/*.md` folder was absorbed) |
  | **Algorithm reference** (theory + hyperparams) | `docs/algorithm.md` | admin (reporter syncs prod values) |
  | **Plan** (`/plan` artifacts) | `.claude/plans/*.md` | the session |
  | **Project dashboard** (live state, human-facing) | `project/dashboard.html` + `project/state.js` | reporter-inline skill |

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
  - **Neon role separation** (INFRA-DB-1, 2026-05-25): Django runtime (Railway prod + local) logs into `user_data` as `make_web_app` (LOGIN + SELECT/INSERT/UPDATE/DELETE on `public.*` + USAGE/SELECT on sequences; **no DDL**, **no role mgmt**, **no extension** privileges, NOT a member of `neon_superuser`). `manage.py migrate` requires DDL → run from operator machine with a temporary `DB_USER=neondb_owner` swap; never leave `neondb_owner` as the long-running runtime user. **Local shortcut: `make migrate-local`** — prompts for the `neondb_owner` password (`read -s`, never written to disk), applies pending migrations against the LOCAL `DB_HOST`/`DB_NAME` from `backend/.env` (DDL hits your local dev branch, never prod), and leaves the runtime `.env` (`make_web_app`) untouched. Local dev DB falls behind whenever merged migrations aren't applied locally (git moves migration files, not schema — no auto-migrate locally); run `make migrate-local` after pulling `develop`. **Local pytest: `make test-local`** (INFRA-DB-2) — same `neondb_owner` prompt + inline `DB_USER` override; the runtime `make_web_app` lacks CREATEDB so plain `pytest` dies with *"permission denied to create database"*. `make test-local` runs pytest as `neondb_owner` (HAS CREATEDB), creating a throwaway `test_<DB_NAME>` on your LOCAL branch (never prod), running the CI-shape real-Postgres+pgvector suite, then dropping it; pass pytest args via `ARGS="-x -k foo"`. The `backend/conftest.py` SQLite override is NOT load-bearing (many tests bypass it) — CI is still the canonical gate; `make test-local` just lets you reproduce it locally. The buildings DB uses `make_web` (SELECT-only on `archi_data`) per PR #93. Create roles via psql `CREATE ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`, **not** `neonctl roles create` (that grants `neon_superuser`).
  - **Cache backend** (INFRA-REDIS-1, 2026-05-26): Django runtime cache uses Redis in prod (`REDIS_URL` env on Railway pointing at the managed Redis service), LocMemCache for local dev when `REDIS_URL` is unset. Never bypass Django's cache abstraction — no direct `redis-py` calls; use `from django.core.cache import cache` so the same code works both backends. Multi-worker prod correctness for PR 3 (BACK-AUTH-1) + PR 4 (PERF-PREFETCH-CHAIN) depends on this swap.
  - **Local-vs-prod Neon branches** (INFRA-ENV-1, 2026-05-25): local `backend/.env` points at a Neon CHILD branch off `production` (currently `local-dev-2`, endpoint `ep-holy-band-a1w0u5am`). Railway prod injects its own env vars pointing at the `production` branch endpoint (currently `ep-broad-hat-a1jaomn7`). Never point local at the production endpoint — local writes would land in real prod rows. Re-provision via `neonctl branches create --name local-dev-N --parent production --project-id holy-pond-45504245`.
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS).
  - `canonical_v2_buildings` -- read-only via raw SQL on the `'buildings'` connection; never ORM or migrate. (Legacy `architecture_vectors` table was dropped 2026-05-24.)
  - `images/batch/` POST -- batch-fetch building cards by `canonical_bld_ids` list.
  - Run: `cd backend && python3 manage.py runserver 8001`.

  ## Pre-Push Gate — `app-test`

  The pipeline commits but the `app-test` agent gates the push. It runs the live browser user-journey verification (dev-login → search → swipe lifecycle → results → error recovery, with card-data validation, phase-transition checks, spec-aligned latency budgets) plus the HEAD / `origin/develop` drift check. It returns one verdict — PASS / PASS-WITH-MINORS / FAIL / ABORTED (drift) — and persists nothing. It runs in one of two modes — FULL (the 3-persona swipe journey, for changes touching the recommendation/swipe path) or FEATURE-SCOPED (preflight + a caller-supplied feature checklist + a light regression smoke, for changes that don't); the caller picks, default FULL. `app-test` is auto-skipped for pure docs/config changes (no UI/runtime surface). Static code review is the separate `code-review` agent's job (inner loop, per change) — `app-test` does not re-do it. Spec: `.claude/agents/app-test.md`.

  ## Database
  See **`docs/database-schema.md`** for the `canonical_v2_buildings` CREATE TABLE
  + normalized `program` vocabulary + image-resolution semantics + Make-DB-
  ownership hard rules. Backend work touching the building data layer must
  consult this file. Hard rules (also in `## Rules` + `## Backend Conventions`):
  use `canonical_bld_id` only; read the building DB via the `'buildings'`
  connection; never ORM or migrate `canonical_v2_buildings`; gate every query on
  `is_publishable = true`; embeddings are pre-computed.
