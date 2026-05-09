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
  - All building references must use `building_id` -- never name, slug, or language-dependent field.
  - Do NOT create or migrate the `architecture_vectors` table -- it is owned by Make DB.
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
  - **Token-saving workflow rules** (per `.claude/agents/orchestrator.md` Rules + `.claude/agents/reporter.md` Step 3.5; see also memory `feedback_token_saving_workflow.md` for full rationale):
    - **Defer reporter to session end** — do NOT spawn `reporter` after every commit; accumulate `.claude/Report.md` + `.claude/Task.md` working-tree changes and run reporter ONCE at session end (or before `git push`). User override: "지금 reporter 돌려".
    - **Skip reviewer + security on trivial commits** — *trivial* = (<50 LOC OR pure docs/policy/agent-file commit with zero source code) + no migration + no production code (only test, config, docs, `.claude/` policy/agent files, `web-testing/`, or `.claude/commands/review.md`) + no auth/network/model layer change. The "pure docs/policy" branch handles cases like CLAUDE.md / agent-md / AGENTS.md cross-cutting policy commits that legitimately exceed 50 LOC (e.g. the 121-LOC hybrid pre-commit policy commit in `756b247`) but introduce zero runtime risk. Trivial commits go back-maker → git-manager directly. User override: "리뷰 돌려" or any explicit request.
    - **Hybrid pre-commit policy for Codex team output** — when `back-maker` or `front-maker` work was dispatched to WEB-BACK / WEB-FRONT (Codex teams), the team's **own self-review** (per `.claude/agents/team-back.md` § "Self-review checklist before BACK-DONE" / `team-front.md` § "Self-review checklist before FRONT-DONE") is the **default pre-commit gate**. WEB-MAIN trusts the BACK-DONE / FRONT-DONE report and skips the in-session Claude `reviewer` + `security-manager` agents. Cross-model verification still happens at `/review` (Claude Opus on WEB-REVIEW vs Codex gpt-5.5 on the teams). **Risky-commit override**: Codex teams append `(claude-review-requested)` to their DONE message when work touches auth flow, token-handling, new external API integration, migrations with data backfill, or cross-cutting refactors ≥4 unrelated apps; WEB-MAIN then runs the in-session reviewer/security pass on top of the self-review. Same applies to Claude `back-maker` / `front-maker` direct work — the in-session reviewer/security run when the orchestrator believes the change is risky, otherwise relies on /review's Part A as the canonical static analysis. Rationale: pre-commit Claude reviewer + security on Codex output ate ~150-200 K Claude tokens per BOARD-class deliverable (3-cycle fix loop) while /review's Part A already covers the 7-axis static analysis. The hybrid keeps the cross-model verification (which catches genuine bugs — see BOARD3 cycle 0 `resp.is_reacted` vs `resp.reacted` contract mismatch) at `/review` time, where Part B browser test ALSO runs and provides empirical end-to-end verification of the same code.
    - **Auto-archive Task.md handoffs** — when `## Handoffs` section exceeds 30 entries, reporter trims oldest to `.claude/handoffs-archive/<YYYY-MM>.md`, keeping recent 30 in Task.md.
    - **Slim back-maker prompts** — target 1.5-2 K tokens per delegation (vs 3-5 K previously). Use spec section pointers + minimal scope; back-maker reads spec directly when needed.
    - **Don't read full /review reports in main** — when user reports verdict, summarize verdict + key findings in chat; do NOT pull the 25-30 K report body into main context.
    - **Bundle trivial commits — push only on milestone / push-worthy commits** — Don't `/review + push` after every trivial commit. Accumulate locally and sweep them in with the next push-worthy commit's `/review` (which scans the whole `origin/main..HEAD` range, so no extra cost). Empirical from 2026-05-06 session: 8 push events for 16 commits ≈ ~2 commits/push. Bundling could have reduced to 4-5 push events (~30-40% `/review` token savings = ~450-600 K Claude per session).
      - **Push-worthy** (immediately `/review` + push when committed):
        1. **Milestone commit** — closes a Task.md `## Development Roadmap` task ID (PROF1, BOARD3, SOC3-back, REC1, etc).
        2. **Production code commit** — `backend/apps/*/{models,views,serializers,urls,migrations}.py` or `frontend/src/{pages,hooks,api,contexts}/*.{js,jsx}` with logic change.
        3. **Migration commit** — schema change in any app.
        4. **Risky-zone touch** — auth / token-handling / new external API integration / cross-cutting refactor ≥ 4 unrelated apps (matches CLAUDE.md hybrid-policy risky-commit list).
        5. **User explicit request** — "지금 push" / "리뷰 돌려".
      - **Bundle-worthy** (commit locally; push deferred to next push-worthy or session-end):
        1. **Pure docs / policy** — `CLAUDE.md`, `.claude/agents/*.md`, `AGENTS.md`, `CONTRIBUTING.md`, `DESIGN.md`, `docs/*.md`, `Goal.md`, `Report.md`, `Task.md` (handoff entries, status updates).
        2. **Tooling** — `tools/*.sh`, `hooks/*`, `.github/*`, `.gitignore` whitelist additions, cmux config (per 2026-05-07 user decision: tooling-self-use is local-effective from commit time; remote sync waits for next code push).
        3. **Sub-MINOR follow-ups** — cosmetic fixes from `/review` reports (typo in docstring, dead-code branch, etc).
        4. **Handoff entries** — single-line additions to `Task.md ## Handoffs`.
        5. **Session-end housekeeping** — reporter pass output (Report.md sync, Task.md trim, handoffs archive).
      - **Forced push triggers** (sweep accumulated bundle even without a push-worthy commit):
        1. **Push-worthy commit lands** (automatic — sweeps everything in `origin/main..HEAD`).
        2. **Session end** (cleanup batch — explicit user "끝내자" or context wind-down).
        3. **Bundle accumulator > 5 commits** (heuristic — review scope and history clarity start to suffer).
        4. **24 hours since first bundle commit** (anti-stale; rarely triggers).
        5. **User explicit "지금 push"**.
      - **Drift safety**: each push still triggers `/review` Part C drift check on the entire `origin/main..HEAD` range, so bundling does NOT lose drift protection. Larger range simply means slightly larger Part A scope (Part B browser test cost is fixed-per-session regardless of range size).
    - **Rule 7 — Post-push session-memory cleanup** — After a push completes (origin/main caught up to local HEAD), the WEB-MAIN operator runs `tools/cleanup-after-push.sh` to send `/clear` to WEB-BACK / WEB-FRONT / WEB-REVIEW. Then WEB-MAIN itself runs `/compact` manually (Claude cannot self-`/clear` from inside the same session). This bounds each push cycle's accumulated context so the next cycle starts fresh and avoids the 2026-05-07-class context-bloat bugs (WEB-REVIEW stuck-prompt at 464K tokens; WEB-REVIEW server-side rate-limit mid-review). The codex teams' `/clear` is followed by an automatic init prompt re-send (self-discovery against AGENTS.md + team-{back,front}.md + CLAUDE.md + Task.md Handoffs) so they're ready for the next dispatch. Estimated savings: ~30-50% Claude tokens per cycle when applied consistently. Rule applies to push-completion events only — mid-session `/clear` on a busy tab is destructive and can interrupt running work.
    - **Rule 8 — Codex model standardization** — Both WEB-BACK and WEB-FRONT use `gpt-5.5` with `model_reasoning_effort=high` (NOT medium/xhigh/etc). The `/fast` mode toggle is left to operator discretion (currently on for both — empirically 1.5-3 min for 200-400 LOC mechanical work). **Critical empirical (2026-05-08)**: codex's `~/.codex/config.toml` setting `model_reasoning_effort = "xhigh"` is NOT auto-applied on codex restart, AND the `/model` slash menu resets effort to medium when re-selecting. The only way to make `high` stick is the `-c model_reasoning_effort=high` command-line flag at codex launch. `tools/cmux_setup.sh` codifies this: TEAMS array uses `codex -c model_reasoning_effort=high`. When a codex tab is restarted manually, also use `-c model_reasoning_effort=high` (not just `codex`). Operator: do NOT use `/model` slash inside codex — it triggers the medium-default reset bug.

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
  - `architecture_vectors` -- read-only via raw SQL; never use Django ORM or migrate this table
  - `images/batch/` POST -- batch-fetch building cards by `building_ids` list
  - Run: `cd backend && python3 manage.py runserver 8001`

  ## Codex Multi-Workspace (stateful 4-tab cmux setup)

  Make Web runs as 4 cmux workspaces in one window, mirroring Make DB's stateful
  multi-team architecture. WEB-MAIN is this Claude Code session (orchestrator).
  WEB-BACK and WEB-FRONT each host a persistent Codex CLI session that auto-loads
  `AGENTS.md` from cwd + its team file when WEB-MAIN dispatches a task.

  | Workspace | Runs | Owns |
  |---|---|---|
  | WEB-MAIN | Claude Code (this session) | Pipeline, dispatch, in-session reviewer/security |
  | WEB-BACK | Codex CLI | `backend/*` (apps, serializers, views, migrations, tests) |
  | WEB-FRONT | Codex CLI | `frontend/*` (data layer + UI — but consult `DESIGN.md` before changing inline styles) |
  | WEB-REVIEW | Claude Code | `/review` pre-push gate only |

  **Files that define this architecture** (ground truth — edit these, not policy here):
  - `AGENTS.md` — Codex baseline + hard guardrails (auto-loaded from cwd by codex CLI on startup)
  - `.claude/agents/team-back.md`, `team-front.md` — per-team owned files + DRF gotchas + fix loop
  - `tools/cmux_setup.sh` — idempotent 4-workspace creator + init prompts
  - `tools/dispatch.sh <team> "<msg>"` — WEB-MAIN sends a task to a team
  - `tools/poll.sh <team> [lines]` — WEB-MAIN reads a team's screen output

  **When to dispatch to a Codex team** (vs an in-session Claude sub-agent):
  - Mechanical, well-bounded task (single feature, clear file scope)
  - Plan can include verbatim code blocks; acceptance is `pytest`/lint green
  - Stay with Claude `back-maker`/`front-maker` for: open-ended refactors,
    bug fixes with unclear root cause, algorithm tuning, UI work that needs `DESIGN.md` judgment

  **DRF gotcha** (lesson from empirical test 001 v1, codified in `team-back.md`):
  `serializers.CharField` defaults to `trim_whitespace=True, allow_blank=False` —
  validators receive already-stripped input. To validate whitespace-only, declare
  the field with `trim_whitespace=False, allow_blank=True`. Tests must cover
  whitespace-only explicitly.

  **Handoff signals** (`.claude/Task.md` § Handoffs):
  - `BACK-DONE: <slug>` / `FRONT-DONE: <slug>` — team finished
  - `BACK-BLOCKED: <reason>` / `FRONT-BLOCKED: <reason>` — team escalates
  - `<TEAM>-NEEDS-CLARIFICATION: <question>` — team waits

  **Fix loop**: WEB-MAIN's in-session `reviewer` or `security-manager` agent
  evaluates Codex output (same bar as Claude `back-maker`/`front-maker` output —
  no separate Codex-reviewer). On FAIL, dispatch to team with the diagnosis;
  cap at 2 cycles, then escalate to Claude sub-agent.

  Historical note: pre-2026-05-06 used a stateless `codex exec` pattern
  (commits `27fee9b`, `042bed4`, `59d2af4`, `51dd387`); deprecated in favor
  of the stateful pattern after empirical comparison with Make DB's setup.

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
  backend / frontend / docs) but acts as the **pre-push gate**. The main orchestrator
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
  <!-- Last synced 2026-04-29 with Make DB v2 + Divisare migration. -->

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
