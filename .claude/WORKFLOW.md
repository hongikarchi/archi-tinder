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
| **reporter** | sonnet | Updates Report.md + Task.md | `.claude/` only |
| **algo-tester** | sonnet | Runs optimizer script, interprets results, triggers orchestrator | runs script + calls orchestrator |
| **research** | opus | Explores complex problems, writes to research/ | `research/` only |

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

## Case 6: Research flow

```
Orchestrator detects complex problem (algorithm, UX, performance)
  -> research agent
       |- reads Goal.md + existing research/ files
       |- WebSearch for papers, best practices
       |- reads current code for constraints
       |
       -> writes research/<topic>.md
            |- Question
            |- Findings (with sources)
            |- Options (2-3 approaches)
            |- Recommendation
            -> Open questions
       |
       -> returns to orchestrator:
            summary + recommended approach + proposed Task.md items
```

---

## Case 7: Reporter (updates system docs)

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
  -> updates Task.md:
      -> moves completed tasks to Resolved with date
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
