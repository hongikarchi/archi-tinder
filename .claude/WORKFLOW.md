# ArchiTinder -- Agent Workflow

> **Read this when:** You want to understand how agents work, what triggers what, and when you
> will be flagged for manual review. All 6 workflow cases are covered here.
> For feature status: see `Report.md`. For task status: see `Task.md`. For vision: see `Goal.md`.

---

## Agent Roster

| Agent | Model | Role | Touches |
|-------|-------|------|---------|
| **orchestrator** | opus | Supervisor -- plans, delegates, manages fix loops | nothing directly |
| **back-maker** | sonnet | Django/DRF backend code | `backend/` only |
| **front-maker** | sonnet | React/Vite frontend code | `frontend/` only |
| **reviewer** | sonnet | API contracts, logic bugs, error handling | read-only |
| **security-manager** | sonnet | SQL injection, auth bypass, XSS, token leaks | read-only |
| **web-tester** | sonnet | Live Playwright browser tests | read-only |
| **git-manager** | haiku | Single commit per task | git only |
| **reporter** | sonnet | Updates Report.md + Task.md, emits REVIEW-REQUESTED handoff | `.claude/` only |
| **algo-tester** | sonnet | Runs optimizer script, interprets results, triggers orchestrator | runs script + calls orchestrator |
| **research** | opus | Explores complex problems, writes to research/ | `research/` only |
| **deep-reviewer** | opus | Pre-push deep review across 7 axes; writes `.claude/reviews/*.md` and REVIEW-PASSED/REVIEW-FAIL handoff | read-only on source; writes `.claude/reviews/` + Task.md Handoffs line |

---

## Multi-Terminal Coordination

The project is developed across **four parallel terminals**, each with a focused role and
isolated context window. All terminals work on the `main` Git branch — coordination is by
file/layer ownership + handoff signals in `Task.md`, not branches.

### Terminal Roster

| Terminal | Model | Role | Owns / Touches | Typical signals |
|----------|-------|------|----------------|-----------------|
| **main** | Claude Code (orchestrator: opus) | Full pipeline — backend, frontend integration, E2E tests, commit | `backend/`, `frontend/` (data layer), `.claude/` (excluding anything inside `research/`) | reporter emits `REVIEW-REQUESTED` to Handoffs; consumes `MOCKUP-READY`, `REVIEW-FAIL`, `REVIEW-ABORTED`, `SPEC-UPDATED` from Handoffs; `[SPEC-READY]` from Research Ready section. **READ-ONLY on `research/`** — never create/modify/delete/stage files there. |
| **research** | Claude Code (research agent: opus) | Ongoing algorithm / UX research dialog with user; consolidates findings into `research/spec/requirements.md` (living spec). `research/search/**` deep-dive reports are reasoning archive — accessed directly via filesystem, not via Task.md pointers. | **EXCLUSIVE owner of `research/`** (all subdirectories: `spec/`, `search/`, `investigations/`, `algorithm.md`). Also appends `[SPEC-READY]` to Task.md `## Research Ready` + `SPEC-UPDATED` to `## Handoffs` on version bump. Commits its own research/ changes from its own session. | emits `[SPEC-READY]`, `SPEC-UPDATED` |
| **review** | Claude Code (deep-reviewer: opus) | Pre-push deep review across all axes (architecture, perf, security, drift) + HEAD/`origin/main` drift checks on PASS | read-only on source; writes `.claude/reviews/*.md` and the handoff line in Task.md `## Handoffs`; user manually runs `git push` from this terminal on `REVIEW-PASSED`. **READ-ONLY on `research/`** (same rule as main). | emits `REVIEW-PASSED` (drift-verified, ready for manual push), `REVIEW-ABORTED` (PASS but drift detected), or `REVIEW-FAIL` to Handoffs |
| **antigravity** | Gemini (Chrome integration) | Continuous UI iteration — new mockups AND existing-page polish | `frontend/` (UI layer). **READ-ONLY on `research/`.** | emits `MOCKUP-READY` to Handoffs; drops inline `TODO(claude): ...` markers in source |

> **⚠️ `research/` ownership is absolute.** The research terminal is the ONLY terminal (and `research` is the ONLY agent) permitted to create, modify, delete, or stage files under `research/` (including `research/spec/`, `research/search/`, `research/investigations/`, `research/algorithm.md`, and any future subdirectory). Main, review, antigravity, and all their spawned subagents (orchestrator, back-maker, front-maker, reviewer, security-manager, git-manager, reporter, deep-reviewer, algo-tester, web-tester) are strictly READ-ONLY on `research/`. This is also the user's active study workspace — do not touch. See CLAUDE.md `## Rules` for the authoritative statement.

> **Note on Task.md sections:**
> - `## Handoffs` (near top) = short-lived review/mockup signals, rolling window.
> - `## Research Ready` (further down) = research terminal's append-only queue. Do not mix the two.

### Frontend Layer Ownership (antigravity vs main)

Both antigravity and main edit files under `frontend/`, so ownership is split **by layer within the same file**:

| Layer | Owner | Allowed edits |
|-------|-------|---------------|
| **UI** | antigravity | JSX return, `styles` objects, animations, transitions, colors, spacing, `MOCK_*` constants (pre-integration only) |
| **Data / Logic** | main | `useState`, `useEffect`, `callApi()`, error handling, data transformations, custom hooks |

Post-integration rules for antigravity returning to a polished page (full table in `GEMINI.md`):
- Allowed: JSX structure, styles, animations, colors
- Forbidden: re-inserting `MOCK_*`, editing `useState/useEffect/callApi`, removing `profile?.xxx` optional chaining

When antigravity needs behavior that requires API/backend work, it drops an inline marker
instead of wiring it:

```jsx
<button onClick={() => { /* TODO(claude): DELETE /api/v1/boards/${board_id}/ */ }}>
  Delete
</button>
```

Main's orchestrator batches these via `grep -r "TODO(claude)" frontend/` during the next
integration session.

### Git Discipline

- **All four terminals work on `main` branch.** No feature branches.
- **Always `git pull` before starting a session.**
- **Commit early, commit small** — avoid saving up many changes for one large commit.
  Git's 3-way merge handles most cases when two terminals touched the same file in
  different sections (e.g., antigravity edited JSX, main edited `useEffect`).
- Only `git-manager` commits from the orchestrator pipeline (one commit per task).
  Antigravity commits directly from its own terminal.
- **Research terminal commits its own `research/` changes** from its own session
  (the research terminal is the ONLY writer of `research/`; main cannot stage them per
  the ownership rule above). If `git status` in the main terminal shows uncommitted
  modifications under `research/`, those belong to the research terminal — leave them
  untouched and unstaged. `git-manager` actively excludes `research/` from staging.

### Research ↔ Main: Spec-based Coordination

Research terminal does not ship code or implementation plans to main directly. Instead,
research consolidates findings into a **living spec** at `research/spec/requirements.md`,
versioned via `**Version**: X.Y` in its header.

**Handoff protocol**:
- `[SPEC-READY]` in `## Research Ready` — the primary entry point. Main terminal reads
  `research/spec/requirements.md` when it sees this marker. No per-topic markers are
  published to Task.md; the 12 topic deep-dives at `research/search/**` are reasoning
  archive, accessed directly by filesystem only when main needs deep justification
  behind a Section 11 directive.
- `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` in `## Handoffs` on every
  non-trivial spec revision. Main terminal reads this at session start to discover
  changes since its last pickup.

**Main's re-read policy** (incremental, not full):
- On session start: scan Handoffs for new `SPEC-UPDATED` entries since last known version.
- If new entries: read only the affected sections in the spec (not the whole document).
- Full re-read is NOT required per task — only when the version bump touches work
  currently in progress.

**When a SPEC-UPDATED invalidates in-progress work**: orchestrator stops, flags the
conflict to the user, does NOT silently continue with the old spec. User decides
whether to finish the current task on the old spec or restart on the new.

**Concurrency (two terminals editing `.claude/Task.md`)**:
- Research appends to `## Research Ready` (or `## Handoffs` for SPEC-UPDATED).
- Main's reporter removes resolved markers from `## Research Ready` as each topic lands.
- Appends to different sections never conflict. Appends to the same section usually
  merge cleanly via git 3-way.
- On merge conflict: one terminal pulls + re-appends. No data loss because both
  terminals work append-only or remove-only.

**What research NEVER does**:
- Does not prescribe task breakdown, sprint ordering, or implementation pacing — those
  are entirely main's judgment. Research documents (like
  `research/spec/research-priority-rebaselined.md`) carry proposed groupings but are
  explicitly non-binding (see its "Authority Boundary" section).
- Does not modify `backend/`, `frontend/`, `web-testing/`, or any `.claude/` file
  outside Task.md's research sections and this WORKFLOW.md's research rows.
- Does not commit or push.

**What research DOES continuously**:
- Ongoing user ↔ research dialog: elicitation, clarification, gap hunting, algorithm
  audit, optimization ideas.
- Updates `research/spec/requirements.md` in place (version bump + changelog entry).
- Appends `SPEC-UPDATED` handoff signal so main picks up changes efficiently.
- Keeps `research/search/**` as reasoning archive — expanded when a new question
  requires fresh exploration.

### Pre-Push Review Gate

The orchestrator pipeline **commits but does not push**. `/deep-review` is the pre-push gate,
and the review terminal performs two drift checks before signalling that push is safe:

```
main orchestrator
  |-> git-manager commits  (stays local)
  |-> reporter updates Report.md + Task.md
  |        -> appends `REVIEW-REQUESTED: <sha>` to Task.md Handoffs
  -> orchestrator STOPS and tells user:
       "run /deep-review in the review terminal; on REVIEW-PASSED
        run git push from that same terminal"
     (no push here)

(user opens / switches to review terminal — stays there through the rest of the cycle)

review terminal — `/deep-review`
  |- Step 1 captures REVIEWED_SHA = git rev-parse HEAD
  |                  REVIEWED_ORIGIN_MAIN = git rev-parse origin/main
  |- Steps 2-5 produce .claude/reviews/<sha>.md + latest.md + stdout summary
  -> Step 6 branches on verdict:
       FAIL → append REVIEW-FAIL: <sha> — ... → STOP
       PASS / PASS-WITH-MINORS:
         6b HEAD-drift check: re-read HEAD. If ≠ REVIEWED_SHA
              → append REVIEW-ABORTED: <sha> — HEAD advanced to <new_sha> ... → STOP
         6c remote-drift check: fetch + re-read origin/main. If ≠ REVIEWED_ORIGIN_MAIN
              → append REVIEW-ABORTED: <sha> — origin/main moved ... → STOP
         6d both drifts clear
              → append REVIEW-PASSED: <sha> — drift checks passed; run `git push` manually from this terminal
                (on PASS-WITH-MINORS the signal inlines "<K> MINOR noted (see .claude/reviews/latest.md)")

(still in the review terminal)
  - REVIEW-PASSED  → user runs `git push` directly (the review terminal never pushes by itself)
  - REVIEW-ABORTED → user returns to main terminal; orchestrator handles the follow-up
                      (re-run /deep-review after HEAD drift; pull --rebase + re-review after remote drift)
  - REVIEW-FAIL    → user returns to main terminal; orchestrator re-enters fix loop (max 2 cycles)
```

This means:
1. `git push` happens from the review terminal, not the main terminal — after the review
   verified both that the range is clean AND that HEAD and origin/main still match what
   was reviewed. No context-switch, no "review one range, push another" race.
2. The review terminal still never edits source code and never runs `git push` itself —
   the push is always user-initiated by explicit `git push` in the review terminal.
3. `git-manager`'s "never pushes unless explicitly told to" default (see Key Rules
   below) is what keeps the orchestrator side clean; no existing agent code changes.

---

## Case 1: Normal feature or bug fix

```
User request
  |-> orchestrator
       |- reads CLAUDE.md + Goal.md + Task.md + Report.md
       |- adds/updates task in Task.md (-> In Progress)
       |- breaks task into back-maker spec + front-maker spec
       |
       |-> back-maker          backend code, runs flake8
       |    -> BACK-MAKER DONE + API contract
       |
       |-> front-maker         frontend code, runs ESLint
       |    -> FRONT-MAKER DONE + API calls made
       |
       |-> reviewer --+  (parallel)
       |-> security --+  (parallel)
       |
       |   Both PASS?
       |   |- YES --> web-tester (10+ swipes, dev-login auth)
       |   |           |- PASS --> git-manager --> reporter --> done
       |   |           -> FAIL --> Fix Loop (counts as 1 cycle)
       |   |
       |   -> NO  --> Fix Loop (max 2 cycles total)
       |               |- reviewer (Mode B) translates issues -> fix orders
       |               |-> back-maker / front-maker fix
       |               |-> reviewer + security again
       |               |- PASS --> web-tester --> git-manager --> reporter
       |               -> still FAIL after cycle 2 --> STOP, report to user
       |
       -> git-manager --> reporter (updates Report.md + marks Task.md resolved)
```

---

## Case 2: Question or explanation

```
User question
  -> Claude answers directly
       No agents spawned. No code changed.
```

---

## Case 3: Algorithm optimizer run

```
User: "run the algorithm tester"
  -> algo-tester
       |- reads CLAUDE.md + research/algorithm.md
       |- runs: python3 tools/algorithm_tester.py --personas N --trials T
       |   (~5-10 min, shows progress)
       |
       |- reads: backend/tools/optimization_results.json
       |
       |- WEAKNESS DETECTED?
       |   (precision < 0.02, avg_swipes > 40, std > 0.15, archetype near-zero)
       |   -> YES --> STOP. Report exact numbers to user.
       |               Wait for manual guidance. No files changed.
       |
       |- IMPROVEMENT vs baseline?
       |   -> NO  --> "Current params are optimal." --> reporter --> done
       |
       -> YES: improvement found
            |- Print summary table (current vs best, % improvement)
            -> orchestrator: "apply changed params to settings.py"
                 |-> back-maker (updates RECOMMENDATION dict only)
                 |-> reviewer + security
                 |-> git-manager ("chore: apply optimized hyperparameters")
                 -> reporter
```

---

## Case 4: Fix loop detail

```
reviewer or security returns FAIL
  -> orchestrator sends all issues to reviewer (Mode B: Fix Translation)
       -> reviewer returns precise fix orders per maker
            |-> back-maker (if backend fix)
            |-> front-maker (if frontend fix)
            -> reviewer + security (parallel, second pass)
                 |- PASS --> web-tester --> git-manager --> reporter
                 -> FAIL --> cycle 2 (same loop)
                      -> still FAIL --> STOP, report to user, ask guidance
```

Web test FAIL counts as 1 fix cycle. Max 2 cycles total across all loops.

---

## Case 5: Web tester flow

```
web-tester starts
  |
  |- Step 0: dev-login
  |   -> POST /api/v1/auth/dev-login/  ->  inject JWT to browser localStorage
  |       if 404 (DEV_LOGIN_SECRET not set): test page-load only
  |
  |- Step 1: Playwright Bash script
  |   -> captures: network requests, console errors, page errors
  |
  |- Step 2: MCP visual tests
  |   |- page load + screenshot
  |   |- UI structure (TabBar, theme toggle, search input)
  |   |- AI search -> submit -> wait for Gemini response
  |   |- start swiping -> 5-10 swipes -> verify next_image on every swipe
  |   -> check phase transitions (exploring -> analyzing)
  |
  -> returns: WEB TEST: PASS or FAIL
      FAIL includes: exact error, failing URL, console log excerpt
```

---

## Case 6: Research flow (separate terminal, ongoing)

Research runs in its **own dedicated terminal** (see "Multi-Terminal Coordination" →
Terminal Roster above). It is **not orchestrator-triggered** — it is a long-running,
user-driven dialog.

```
User starts/resumes research terminal
  |
  |- [ongoing dialog: user ↔ research terminal]
  |    elicitation, clarification, gap-hunting, algorithm audit, optimization ideas
  |
  |- research terminal writes / updates:
  |    research/spec/requirements.md   (living spec, versioned X.Y)
  |    research/spec/research-priority-rebaselined.md   (research recommendation, non-binding)
  |    research/search/NN-*.md   (reasoning archive, 12 topic deep-dives)
  |
  |- On spec revision:
  |    1. bumps **Version**: X.Y in requirements.md header
  |    2. appends Changelog entry at bottom of requirements.md
  |    3. appends `SPEC-UPDATED: vX.Y → vX.Z — <sections> — <summary>` to
  |        .claude/Task.md ## Handoffs
  |    4. if first publication: appends `[SPEC-READY]` to ## Research Ready
  |
  -> main terminal (separate, in its own session):
       |- at session start, reads ## Handoffs for new SPEC-UPDATED
       |- if new version: reads only affected sections in requirements.md
       |- plans task breakdown + sequencing INDEPENDENTLY
       |    (research/spec/research-priority-rebaselined.md is reference, not mandate)
       |- runs its orchestrator pipeline (Case 1) to implement
```

**Research terminal writes only**: `research/**` (full), `.claude/Task.md` (append-only
research sections), `.claude/WORKFLOW.md` (research rows only, by explicit user grant).
Never `backend/`, `frontend/`, agent definitions, `Report.md`, or git commits.

**Main terminal reads** (in order): spec → plans → code. Main does NOT read
`research/search/**` under normal flow — Section 11 of `requirements.md` absorbs
all actionable directives. Main may consult `research/search/NN-*.md` for deep
justification only when debugging a spec decision or exploring a variant.

The **old orchestrator-triggered research pattern** (main's orchestrator invoking the
research agent mid-pipeline for a complex sub-question) is still available in
principle, but in practice all substantial research now lives in the dedicated
research terminal.

---

## Case 7: Reporter (updates system docs + emits REVIEW-REQUESTED)

```
reporter runs after every git-manager commit
  |
  |- git log -1 --stat           (what changed)
  |- reads .claude/Report.md    (system documentation)
  |- reads .claude/Task.md      (task board)
  |
  |- updates Report.md:
  |   |- Last Updated section for Claude ONLY (Do NOT overwrite Gemini's section)
  |   |- Structure tables (if new files created)
  |   |- API Surface (if new endpoints)
  |   |- Feature Status (if features completed)
  |   -> Mermaid diagrams (if architecture changed)
  |
  |- updates Task.md:
  |   -> moves completed tasks to Resolved with date
  |
  -> appends REVIEW-REQUESTED to Task.md Handoffs:
       `- [YYYY-MM-DD] REVIEW-REQUESTED: <sha_short> — <one-line summary>`
       (uses Edit tool; does NOT touch the Research Ready section)
```

---

## Key rules

| Rule | Detail |
|------|--------|
| All changes go through orchestrator | Never implement directly from main conversation |
| Questions answered directly | No agents needed for explanations |
| Makers are sandboxed | back-maker: `backend/` only -- front-maker: `frontend/` only |
| orchestrator never writes code | Always delegates to makers |
| git-manager never pushes | Unless explicitly told to push |
| Reporter updates, never appends | Report.md is live state (but preserve Gemini section for Last Updated); Task.md Resolved is historical |
| Algorithm weakness = manual review | orchestrator stops and flags; does not auto-fix |
| Fix cycle limit = 2 | After 2 failed cycles, stop and report to user |
| Research before complex coding | Algorithm/UX tasks without precedent trigger research first |

---

## File locations

| File | Purpose |
|------|---------|
| `.claude/agents/*.md` | Agent definitions (this system) |
| `.claude/Goal.md` | Vision + acceptance criteria (north star) |
| `.claude/Task.md` | Problem board -- open/in-progress/resolved by category |
| `.claude/Report.md` | Live system documentation -- architecture, API, diagrams |
| `.claude/WORKFLOW.md` | This file -- agent workflow documentation |
| `research/` | Deep exploration files (algorithm, UX patterns) |
| `backend/tools/algorithm_tester.py` | Hyperparameter optimizer script |
| `backend/tools/optimization_results.json` | Latest tester output |
| `CLAUDE.md` | Project conventions (read by all agents) |
