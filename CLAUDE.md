# Make Web Service -- Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB (reference-crawling repo).
  For system architecture and API surface, see `.claude/Report.md`.
  For 3-developer collaboration / branch model / PR workflow / file ownership, see `CONTRIBUTING.md`.

  ## Branch Model — HARD RULES (must follow before any commit)

  **The team uses GitHub Flow with a develop integration branch:**

  - `main` — production (Railway auto-deploy). Protected: PR-only, force-push blocked, requires Code Owner approval.
  - `develop` — integration branch. Protected: PR + status check required (admin bypass disabled).
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
  4. **Never use `--no-verify`, `--force`, `--force-with-lease`, `git rebase -i`, `git reset --hard` on shared branches**, or any history-rewriting flag.
  5. **PRs target `develop`, not `main`.** The admin batches features and opens a separate `develop → main` PR when ready to deploy.
  6. **One-time setup per clone (each collaborator must run once):**
     ```bash
     ./tools/install-hooks.sh
     ```
     Without this, your local does not have the migration-numbering pre-push hook, and you may push a duplicate-numbered Django migration that breaks the team.

  **If `git status` at session start shows you are on `main` or `develop` with uncommitted changes**: the previous session likely did not switch to a feature branch. Stash or save the work, then create a proper feature branch before continuing. Do not stage or commit while on a protected branch.

  Full details (workflow scripts, common pitfalls, file ownership table): see `CONTRIBUTING.md` at the repo root.

  ## Audit Trail Locations
  Different categories of historical / decision documents live in distinct directories
  so that agents and collaborators always know where to look. Do NOT scatter audit
  documents into ad-hoc paths.

  | Category | Location | Writer | Lifecycle |
  |---|---|---|---|
  | **Spec** (binding requirements / pending work) | `docs/specs/*.md` | admin | Long-lived; versioned |
  | **Algorithm reference** (theory + hyperparams) | `docs/algorithm.md` | admin (reporter syncs prod values) | Live; reporter updates Production Value column when settings.py changes |
  | **Plan** (`/plan` artifacts) | `.claude/plans/*.md` | Claude main session | Random-named per `/plan` invocation |
  | **Review verdict** (pre-push gate) | `.claude/reviews/*.md` | review terminal | Per-commit; `latest.md` symlink |
  | **Validation** (staging A/B results) | `.claude/validations/*.md` | main pipeline | Per-feature (e.g. `imp5.md`, `imp6.md`) |
  | **Postmortem** (bug-fix retrospective) | `.claude/postmortems/*.md` | main pipeline | Per-incident, named descriptively |
  | **System report** (live state) | `.claude/Report.md` | reporter agent | Single file; updated each commit |
  | **Task board** (roadmap + handoffs) | `.claude/Task.md` | reporter agent | Single file; Handoffs trim at >30 |
  | **Handoffs archive** (auto-trim) | `.claude/handoffs-archive/<YYYY-MM>.md` | reporter agent | Created when Handoffs >30 |

  Cross-references:
  - Staging validation outputs (e.g. `validate_imp5.py` Django management command)
    must write to `.claude/validations/<imp>.md`, NOT to `backend/` root.
  - Bug-fix retrospectives (post-incident analysis) go in `.claude/postmortems/` with
    descriptive filenames (e.g. `swipe-infinite-loading-fix.md`), not in `.claude/plans/`
    (plans is for `/plan`-mode artifacts only).

  ## Rules
  - All building references must use `canonical_bld_id` (TEXT PK like `'bld_000344'`) -- never `name`, `slug`, or any language-dependent field.
  - Do NOT create or migrate the `canonical_v2_buildings` table -- it is owned by Make DB.
  - Every building query MUST gate on `is_publishable = true` (39 of 39,776 rows are non-publishable). `engine._build_filter_sql` already emits this clause; raw SQL elsewhere must add it.
  - SentenceTransformers is NOT a dependency here -- embeddings are pre-computed.
  - When updating `.claude/Report.md`, update ONLY the `Last Updated (Claude)` section.
  - **`docs/algorithm.md` reporter sync (narrow write permission)**: only the `reporter` agent updates `docs/algorithm.md`, and only to keep it in sync with implementation. Permitted writes: (a) sync the **Production Value** column in the Hyperparameter Space table when `backend/config/settings.py` RECOMMENDATION dict changes; (b) append a one-line `_(Updated YYYY-MM-DD <sha_short>: <one-line>)_` annotation under any phase / formula / edge-case section whose corresponding implementation just changed; (c) maintain a `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` line near the top. Forbidden: rewriting algorithm theory, removing existing content, adding new sections. Other `docs/` files (specs, etc.) are admin-owned plain documents — anyone can edit via PR per CONTRIBUTING.md.
  - **Plan mode protocol — Korean summary + multiple choice + one question at a time** (durable across sessions). When entering plan mode, follow this exact procedure:
    1. **Data gathering** (Phase 1) — read-only exploration. Use Explore agent or direct read tools. Collect facts before analysis.
    2. **Korean summary in chat** — present a *short* (5-15 lines) Korean summary of the diagnosis / proposal / data. Do NOT dump 500-line English plan files into chat. The plan file (the only writable file in plan mode) can be more detailed but the chat presentation is summarized + Korean.
    3. **Get user review** — wait for the user to acknowledge / correct / approve the summary before introducing decisions.
    4. **Decisions one at a time, multiple choice** — when user input is needed, use `AskUserQuestion` with **one question per turn**, **3-4 multiple-choice options** (label + description per option, "Other" auto-added by the tool). Each option's description should briefly state the trade-off. Wait for the answer before asking the next question. Never batch multiple decisions in one turn.
    5. **Plan file finalize** — once all decisions are answered, update the plan file with the agreed approach. Keep it concise enough to scan quickly, detailed enough to execute. Korean preferred for the summary block; technical specifics can stay in English where they reference code identifiers.
    6. **ExitPlanMode** — only call this AFTER all decisions are settled in the plan file. Do not ask "should I proceed?" via text or `AskUserQuestion`; that is exactly what `ExitPlanMode` does.
    Why: the user requested this on 2026-04-29 ("내가 요청한 사항에 대해서 지금처럼 한번에 무지막지한 영어로 한번에 제시하지 말고, 좀 요약해서 한글로 나한테 한번 검토 받은 다음에... 객관식으로 고르는 방식으로 진행하도록"). Long English plan dumps overwhelm; sequential multiple-choice walks support careful per-topic decision-making. This rule applies to ALL plan-mode entries from any terminal session, not just one-off.
  - **Session protocol** — see **`.claude/SESSION_PROTOCOL.md`** for the push-단위 session model, session-start/end checklists, the standard plan-table template (terminals + agents + token estimates + risk + decisions), Korean-summary rule, and bundle-vs-push thresholds. WEB-MAIN session start MUST run the § 2 checklist (git status / git pull / Task.md Handoffs scan + `SESSION-START-TODO` surfacing) BEFORE substantive work. Plan reporting (§ 3) MUST happen before any `Edit` / `Write` / multi-step `Bash` action — not after. The protocol applies to all collaborators (admin + Role A + Role B), not Claude self only. Why: codified 2026-05-09 after the user requested "작업 시작 전에 표 형식으로 분담 + 추정 + 객관식 보고" — bundles plan-mode protocol (above) + token-saving rules (below) into one operational doc.
  - **Token-saving workflow rules** — see **`docs/token-saving.md`** for
    the 8-rule operational policy: (1) defer reporter to session end,
    (2) skip reviewer + security on trivial commits, (3) hybrid Codex
    self-review pre-commit gate, (4) auto-archive Task.md handoffs,
    (5) slim back-maker prompts, (6) bundle trivial commits / push only
    push-worthy, (7) post-push cleanup, (8) Codex `-c model_reasoning_effort=high`.
    User overrides apply: "지금 reporter 돌려" / "리뷰 돌려" / "지금 push".
    Don't read full /review reports in main — summarize verdict in chat
    instead of pulling the 25-30 K body.

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
  - **MUST READ `DESIGN.md`**: All UI work (any role's frontend changes — JSX styles, layout, colors, animations) MUST consult `DESIGN.md` (root) for our visual design system, colors, sizes, and UI rules before writing any code.
  - All component styles are inline JS objects -- Tailwind is NOT used in components
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom)
  - Accent colors are hardcoded hex in inline styles (not CSS vars) -- rely on `DESIGN.md` when applying colors
  - Do NOT rewrite inline styles arbitrarily; they are the intentional design. Treat existing inline styles as load-bearing unless `DESIGN.md` rules say otherwise — when in doubt, consult `DESIGN.md` and surface the change in the PR description.

  ## Backend Conventions
  - Django 4.2 LTS required (Python 3.9.6 on this machine; Django 5+ needs Python 3.10+)
  - All URL patterns must have trailing slashes -- Django APPEND_SLASH only redirects GET, not POST
  - Neon PostgreSQL: use `sslmode=require` in DATABASE_URL; psycopg2-binary (not asyncpg)
  - JWT: access=1hr, refresh=30days, rotate+blacklist (simplejwt TokenBlacklist app must be in INSTALLED_APPS)
  - `canonical_v2_buildings` -- read-only via raw SQL; never use Django ORM or migrate this table. Old `architecture_vectors` table is deprecated and untouched by Make Web code.
  - `images/batch/` POST -- batch-fetch building cards by `canonical_bld_ids` list (request body field `canonical_bld_ids`; legacy `building_ids` accepted for one rollout cycle)
  - Run: `cd backend && python3 manage.py runserver 8001`

  ## Claude Architect + Codex Implementer Workflow

  **Operating principle**: *Claude-main owns architecture, product, schema, auth,
  release. Codex implements bounded tasks. Final verification = diff / test / PR.*

  Codex workers run as stateful Codex CLI sessions in cmux workspaces and
  auto-load `AGENTS.md` from cwd. Each worker reads its own baseline file
  (`.claude/codex/backend-worker.md` or `frontend-worker.md`) plus the
  dispatched bounded task file. WEB-MAIN dispatches via `cmux send`. WEB-REVIEW
  runs Claude Code for the `/review` pre-push gate. WEB-GIT runs Claude Code
  for the `git-publisher` agent.

  ### Lean 3-lane (default — most work)

  One Codex worker (back OR front) + WEB-MAIN + WEB-REVIEW + WEB-GIT.

  - **Setup**: `tools/cmux_lean_setup.sh <back|front|both>` (idempotent).
  - **Dispatch (default)**: `tools/dispatch-codex-task.sh <team> <slug> <task-file>`
    — Claude-main writes a task file from `tools/codex-task-template.md` (scope /
    allowed files / contracts / verification / handoff), the wrapper embeds it in
    a bounded-implementer contract message and sends it to the worker. **This is
    the default dispatch path; bounded task files are required for any non-trivial
    task.**
  - **Dispatch (fallback)**: `tools/dispatch.sh <team> "<free-form msg>"` for
    quick pings, scope-clear follow-ups, or fix-loop dispatches where re-writing
    a task file is overhead. Same bounded-implementer rules apply on the worker
    side.

  ### Full 5-tab (opt-in — both workers concurrently active)

  WEB-MAIN + WEB-BACK + WEB-FRONT + WEB-REVIEW + WEB-GIT — used when a full-stack
  task wants backend and frontend workers running in parallel.

  - **Setup**: `tools/cmux_setup.sh` (idempotent).
  - **Dispatch**: same `tools/dispatch-codex-task.sh` (default) /
    `tools/dispatch.sh` (fallback) — the wrapper detects the team.

  ### Workspaces (both lanes)

  | Workspace | Runs | Owns |
  |---|---|---|
  | WEB-MAIN | Claude Code (this session, architect) | Pipeline, dispatch, in-session reviewer/security, **commit via git-manager** (never push) |
  | WEB-BACK | Codex CLI | `backend/*` (apps, serializers, views, migrations, tests) |
  | WEB-FRONT | Codex CLI | `frontend/*` (data layer + UI — but consult `DESIGN.md` before changing inline styles) |
  | WEB-REVIEW | Claude Code | `/review` pre-push gate only (read-only on source) |
  | WEB-GIT | Claude Code (git-publisher) | **push / PR open / PR poll / squash merge / branch cleanup / external PR triage / develop→main deploy** (only `git` + `gh` commands; never commits source) |

  **Two-agent split for git operations** (per 2026-05-09 architecture decision):
  - `git-manager.md` (WEB-MAIN, ~0.8K tokens) — single commit only, secret skip,
    branch rule check, never push.
  - `git-publisher.md` (WEB-GIT, ~3K tokens) — 3 modes: (1) Internal push+PR,
    (2) External PR triage with hybrid `/review` trigger (admin manual after
    `PR-READY-FOR-REVIEW` signal), (3) Deploy PR (develop→main).
  - Cross-terminal handshake via `Task.md § Handoffs` signals: `READY-FOR-PUSH`,
    `PR-OPENED`, `PR-CI-GREEN`, `PR-MERGED`, `PR-READY-FOR-REVIEW`,
    `PR-CHANGES-REQUESTED`, `DEPLOY-PR-OPENED`, `DEPLOY-MERGED`,
    `GIT-PUBLISH-{BLOCKED,RETRY,NOOP}`.

  **Files that define this architecture** (ground truth — edit these, not policy here):
  - `AGENTS.md` — Codex baseline + hard guardrails (auto-loaded from cwd by codex CLI on startup)
  - `.claude/codex/backend-worker.md`, `.claude/codex/frontend-worker.md` — per-worker owned files + DRF gotchas + self-review checklist + fix loop
  - `.claude/agents/git-manager.md` — slim commit-only agent (WEB-MAIN)
  - `.claude/agents/git-publisher.md` — push/PR/merge/external/deploy agent (WEB-GIT)
  - `tools/cmux_lean_setup.sh <back|front|both>` — lean 3-lane workspace creator + init prompts (default)
  - `tools/cmux_setup.sh` — full 5-tab workspace creator + init prompts (opt-in)
  - `tools/codex-task-template.md` — bounded task file template Claude-main copies + fills per dispatch
  - `tools/dispatch-codex-task.sh <team> <slug> <task-file>` — default dispatch (bounded task file required)
  - `tools/dispatch.sh <team> "<msg>"` — fallback free-form dispatch (`team ∈ {back, front, review, git}`)
  - `tools/print-claude-codex-handoff.sh` — prints the Codex→Claude-main handoff prompt for lean-workflow adoption
  - `tools/poll.sh <team> [lines]` — WEB-MAIN reads a team's screen output
  - `tools/git-new-feature.sh <role> <topic>` — sync develop + create feature branch
  - `tools/git-stage-and-commit.sh "<msg>"` — single safe commit (called by git-manager)
  - `tools/git-push-pr.sh` — push + `gh pr create --base develop` (called by git-publisher Mode 1)
  - `tools/git-poll-merge.sh <PR#>` — poll CI status (called by git-publisher)
  - `tools/back-validate.sh [app]` — flake8 + migrate-if-needed + pytest (called by back-maker / backend-worker)
  - `tools/front-validate.sh` — npm lint + build (called by front-maker / frontend-worker)
  - `tools/migrate.sh [app]`, `tools/test-backend.sh`, `tools/check-frontend.sh` — finer-grained wrappers

  **When to dispatch to a Codex worker (with bounded task file)** vs an in-session Claude sub-agent:
  - Mechanical, well-bounded task (single feature, clear file scope)
  - Plan can include verbatim code blocks; acceptance is `pytest` / lint green
  - Stay with Claude `back-maker`/`front-maker` for: open-ended refactors,
    bug fixes with unclear root cause, algorithm tuning, UI work that needs `DESIGN.md` judgment

  **DRF gotcha** (lesson from empirical test 001 v1, codified in `backend-worker.md`):
  `serializers.CharField` defaults to `trim_whitespace=True, allow_blank=False` —
  validators receive already-stripped input. To validate whitespace-only, declare
  the field with `trim_whitespace=False, allow_blank=True`. Tests must cover
  whitespace-only explicitly.

  **Handoff signals** (`.claude/Task.md` § Handoffs):
  - `BACK-DONE: <slug>` / `FRONT-DONE: <slug>` — worker finished
  - `BACK-BLOCKED: <reason>` / `FRONT-BLOCKED: <reason>` — worker escalates
  - `<TEAM>-NEEDS-CLARIFICATION: <question>` — worker waits
  - `READY-FOR-PUSH: <branch>` — WEB-MAIN → WEB-GIT (after REVIEW-PASSED)
  - `BRANCH-CREATED: <branch>` / `PR-OPENED: #<N>` / `PR-CI-GREEN: #<N>` / `PR-CI-FAIL: #<N>` / `PR-MERGED: #<N>` — WEB-GIT internal PR lifecycle
  - `PR-READY-FOR-REVIEW: #<N>` — WEB-GIT → admin (external PR triage; admin manually triggers `/review` per hybrid policy)
  - `PR-CHANGES-REQUESTED: #<N>` — WEB-GIT after external PR FAIL verdict
  - `DEPLOY-PR-OPENED: #<N>` / `DEPLOY-MERGED: #<N>` — WEB-GIT develop→main deploy
  - `GIT-PUBLISH-{BLOCKED,RETRY,NOOP}: <reason>` — WEB-GIT refuses or special case

  **Fix loop**: WEB-MAIN's in-session `reviewer` or `security-manager` agent
  evaluates Codex output (same bar as Claude `back-maker`/`front-maker` output —
  no separate Codex-reviewer). On FAIL, dispatch to worker with the diagnosis;
  cap at 2 cycles, then escalate to Claude sub-agent.

  Historical note: pre-2026-05-06 used a stateless `codex exec` pattern
  (commits `27fee9b`, `042bed4`, `59d2af4`, `51dd387`); deprecated in favor
  of the stateful pattern after empirical comparison with Make DB's setup.
  The bounded-task-file dispatch protocol (2026-05-13) hardens the stateful
  pattern by making per-task scope explicit instead of folkloric.

  ## Web Testing
  See **`web-testing/AGENTS.md`** for: dev-login flow + token injection +
  debug overlay + Django admin + authenticated flows the agent should test
  + the standalone E2E visual test runner CLI + strict (Part B) vs fast
  (inner loop) modes. The orchestrator must NOT pass `skip_login` to
  `web-tester`; dev-login is the only path in headless contexts.

  ## Pre-Push Review (`/review`)

  Pre-push gate runs in WEB-REVIEW. **Canonical spec: `.claude/commands/review.md`.**
  Three parts:
  - **Part A** — static 7-axis review (architecture / correctness / perf /
    security / quality / test coverage / drift); writes `.claude/reviews/<sha>.md`
    + `latest.md`.
  - **Part B** — strict browser verification (spec-aligned latency, 3 personas
    × ≥25 swipes, zero-error gates, edge cases). Runs only when UI-affecting
    paths are in scope; auto-skipped for pure docs/config.
  - **Part C** — HEAD + origin/main drift check.

  Verdict signals appended to `.claude/Task.md ## Handoffs`:
  `REVIEW-PASSED` / `REVIEW-ABORTED` / `REVIEW-FAIL`. `/review` is **read-only on
  source code** + **never runs `git push` itself** — push is always user-initiated
  from WEB-GIT (`git-publisher`).

  ### Natural language trigger
  In WEB-REVIEW, recognize **"리뷰해줘"** / **"review"** / **"검토해줘"** / similar
  Korean/English variants as `/review` invocation. In WEB-MAIN, prefer the orchestrator
  inner-loop `reviewer` subagent for those phrases, unless the user explicitly says
  "pre-push review".

  ### Push-fail-then-rebase discipline
  If `git push` fails non-ff and you recover with `git pull --rebase`, the rebase
  rewrites local commit SHAs. The existing `REVIEW-PASSED: <old_sha>` signal is now
  stale. Re-run `/review` (or "리뷰해줘") before retrying push — only a
  `REVIEW-PASSED` at the current HEAD SHA is a valid push ticket.

  See `.claude/commands/review.md` for: full Part B gates, scope rules,
  push-fail-then-rebase discipline, complementarity with inner-loop agents.
  See `.claude/WORKFLOW.md` "Multi-Terminal Coordination" for the full pre-push
  sequence diagram.

  ## Database
  See **`docs/database-schema.md`** for the `canonical_v2_buildings` CREATE TABLE
  + normalized `program` vocabulary + image-resolution semantics + Make-DB-
  ownership hard rules. Backend work touching the building data layer must
  consult this file. Hard rules (already enforced in `## Rules` above): use
  `canonical_bld_id` only; never ORM or migrate `canonical_v2_buildings`; gate
  every query on `is_publishable = true`; embeddings are pre-computed (no
  SentenceTransformers runtime dep).
