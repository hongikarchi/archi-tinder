---
name: orchestrate
description: Use this skill to implement any feature or fix end-to-end. It reads the project context, breaks the task into backend/frontend specs, dispatches back-maker and front-maker sub-agents, runs code-review and security-manager in parallel, manages the fix loop (max 2 cycles), then dispatches git-manager (commit), app-test (pre-push browser + drift gate), git-publisher (push/PR/merge), and reporter (session-end).
---

# Orchestrate — feature-implementation playbook

This skill runs in the **main session's context**, so it can dispatch sub-agents.
(An agent runs in an isolated sub-context and cannot dispatch other agents — which
is why the feature-pipeline supervisor is a skill, not an agent.) When this skill
is invoked, the main session itself executes the playbook below, dispatching the
work to sub-agents at each step.

## Dispatching sub-agents (tool reference)

Every "Dispatch `<agent>`" instruction in this file means: **call the `Agent` tool
with `subagent_type: "<agent>"`**.

Naming pitfalls — do not fall back to doing work yourself if you cannot locate the
spawner; these are NOT the subagent spawner:
- `Task` — obsolete name from older Claude Code; no longer exists. Use `Agent`.
- `TaskCreate` / `TaskUpdate` / `TaskList` / `TaskGet` — todo-list management tools
  (different purpose, they do not spawn subagents).

Minimal valid dispatch shape:
```
Agent({
  description: "<one-line summary>",
  subagent_type: "back-maker",  // or front-maker, code-review, security-manager, app-test, git-manager, git-publisher, reporter
  prompt: "<full self-contained brief for the subagent>"
})
```

For parallel dispatches (Step 4: code-review + security-manager), emit both `Agent`
calls in a single assistant message so they run concurrently.

If `Agent` returns an error, report the error to the user and stop — do NOT bypass
delegation by writing source code yourself. The no-direct-code rule in §Rules below
is absolute.

## Before every task
1. Read `CLAUDE.md` — conventions, rules, DB schema, coding standards
2. Read `.claude/Goal.md` — vision and acceptance criteria
3. Read `.claude/Task.md` — current problem board
4. Read `.claude/Report.md` — how code works now (architecture, API surface)
5. If algorithm task: read `docs/algorithm.md` for theory + production hyperparameters
6. If task references a spec: read the file under `docs/specs/`

## When user requests work
1. Read `.claude/Goal.md` + scan relevant code
2. Add or update the problem in `.claude/Task.md` (correct category, with context + sub-tasks)
3. Move to 🟡 In Progress
4. Execute (back-maker / front-maker / etc.)
5. On success: move to 🟢 Resolved with date
6. On failure after 2 cycles: leave in 🟡 In Progress, add failure notes, report to user

## When user says "오늘 개발 진행해" or "continue development"
Follow the **📋 Development Roadmap** at the top of `.claude/Task.md`:
1. Find the first incomplete Phase (earliest phase with unchecked items)
2. Within that Phase, pick the next task by ID (e.g., B4 → B1 → B2 → B3)
3. Execute each task through the full pipeline (plan → makers → review → security → commit → app-test → publish → report)
4. After completing a task, immediately proceed to the next one in the roadmap
5. Commit after EACH task (not batched) — one commit per task ID
6. Stop at the end of the current Phase and report progress to user before starting the next Phase

## Workflow

### Step 1 — Plan
Break the task into discrete changes. List:
- What back-maker must change (files, endpoints, logic)
- What front-maker must change (files, components, API calls)
- Acceptance criteria for code-review

### Step 2 — Back Maker
Dispatch `back-maker` with a precise spec:
- Which files to touch
- What to add / change / remove
- Expected API contract (endpoint, method, request, response shape)

Wait for back-maker to finish.

### Step 2.5 — Migration sanity check (defensive backstop)

After back-maker returns, inspect its changed-files list (or `git status --short`). If
ANY file under `backend/apps/*/migrations/` was created or modified, verify the
migration was actually applied to the local dev DB:

```bash
cd backend && python3 manage.py showmigrations 2>&1 | grep -E '\[ \]'
```

(No app filter — Step 2.5's trigger condition fires for migrations in ANY app under
`backend/apps/*/migrations/`, so the check must also be app-agnostic.)

- **No output** (all migrations applied): proceed to Step 3.
- **Any `[ ]` entry** (unapplied migration in working tree): back-maker should have run
  `manage.py migrate` per its own Rules (see back-maker.md "After writing > 2. Apply
  migrations"). If they didn't, run it now yourself:
  ```bash
  cd backend && python3 manage.py migrate
  ```
  If `migrate` fails, treat it as a back-maker failure: enter the Fix Loop (Step 5b)
  with the migrate stderr as the spec — the migration file itself needs fixing, not
  the surrounding code.

This is belt-and-suspenders to back-maker's own rule. Postmortem reference: commit
`190c830` shipped a migration without applying it, and the pre-push browser gate
failed with a 500 ("column saved_ids does not exist"). Applying the migration is
non-negotiable before any browser test runs.

### Step 3 — Front Maker
Dispatch `front-maker` with a precise spec:
- Which files to touch
- What to add / change / remove
- The API contract back-maker implemented (from Step 2 result)

Wait for front-maker to finish.

### Step 4 — Review + Security (run both, wait for both)
Dispatch `code-review` with: changed files list + original spec + acceptance criteria.
Dispatch `security-manager` with: changed files list.
Emit both `Agent` calls in a single assistant message so they run in parallel.
Wait for both to complete.

### Step 5 — Decision
**If both PASS:**
→ Check architectural fit yourself: does this match `.claude/Goal.md` acceptance
  criteria and `CLAUDE.md` conventions?
→ If YES: go to Step 6 (commit)
→ If NO: go to the Fix Loop (Step 5b)

**If code-review or security-manager FAIL:**
→ Go to the Fix Loop (Step 5b)

### Step 5b — Fix Loop (max 2 cycles total across all iterations)
1. Send all issues (code-review + security-manager + your own concerns) to `code-review`
2. code-review translates them into specific fix orders for back-maker and/or front-maker
3. Dispatch the relevant maker(s) with those fix orders
4. Re-run Step 4
5. If still failing after cycle 2: STOP. Report to user with the exact issues. Ask for guidance.

The fix-cycle count is **shared across all loops** — Step 4 failures, Step 7
app-test failures, and architectural-fit rejections all draw from the same budget
of 2. Track it explicitly.

### Step 6 — Commit (local only)
Dispatch `git-manager` with a one-line commit message describing what was done.
`git-manager` commits but never pushes — pushing happens in Step 8 via `git-publisher`.

### Step 7 — Pre-push browser test + drift gate
Dispatch `app-test`. It does two things:
1. Runs the live-browser user-journey test (dev-login → page load → AI search →
   swipe lifecycle → results → error recovery) against the local dev server.
2. Checks for drift between local HEAD and `origin/develop`.

It returns a single PASS/FAIL verdict.

- **app-test PASS:** → Step 8
- **app-test FAIL (browser test failed):** treat as a code-review FAIL — go to the
  Fix Loop (Step 5b). app-test failures count toward the shared 2-cycle limit. The
  fix cycle re-runs back-maker / front-maker → code-review + security-manager →
  git-manager (a new commit) → app-test.
- **app-test FAIL (drift detected — `origin/develop` moved):** no code fix is
  needed. Inform the user, run `git pull --rebase origin develop` (resolving any
  conflicts via the Fix Loop if they arise), then re-dispatch `app-test`. Drift does
  NOT count toward the 2-cycle limit (no findings to fix).
- **Local dev server not running:** app-test reports this; note it in your report
  and proceed to Step 8 (the browser test could not run, but the drift check still
  applies).

### Step 8 — Publish (push / PR / merge)
Dispatch `git-publisher` to push the branch, open a PR against `develop`, poll CI,
and merge once green. `git-publisher` owns all `git push` / `gh` operations — the
orchestrate skill itself never pushes.

### Step 9 — Report (session-end)
Dispatch `reporter`. It will:
1. Update `.claude/Report.md` (system state)
2. Mark completed tasks in `.claude/Task.md` (Resolved section)

### Step 10 — Stop and report to user
After reporter finishes, STOP. Summarize for the user what was implemented, the
commit/PR, the app-test verdict, and any open follow-ups.

## Algorithm work — externally owned

Per `.claude/Goal.md` § Algorithm ownership (2026-05-18), algorithm-side work
(`engine.py`, `services/embeddings.py`, `services/rerank.py`,
`services/_caches.py`, Topic 01-12 in `docs/algorithm.md`, IMP-1/7/8, A2
hyperparameter optimization) is owned by a separate collaborator — this skill does
NOT dispatch algorithm tuning work. If the user asks for algorithm tuning, surface
the ownership boundary and decline.

LLM-chat-module work (`services/parse_query.py`, `services/generation.py`,
`services/_gemini.py`, chat-phase Gemini latency IMP-4/5/6, Phase 17 reverse-Q +
persona) remains in scope — dispatch as a normal feature through back-maker.

## Rules
- Never write source code yourself. Always delegate to back-maker or front-maker via
  the `Agent` tool. If `Agent` appears unavailable, STOP and report the blockage to
  the user — do not work around it by editing files directly.
- Never commit yourself. Always delegate to git-manager.
- Never push yourself. Always delegate to git-publisher. With `main` + `develop`
  branch protection, even admin pushes go via PR — see `CONTRIBUTING.md`.
- If a task is ambiguous, ask the user ONE clarifying question before planning.
- The fix-cycle count is shared across all loops. Track it.
- If you notice a `CLAUDE.md` convention that needs updating, propose the change in
  your final output — do not write it yourself.
- Write new learnings (architectural decisions, patterns, gotchas) to memory immediately.
- **Feature work** must go through this pipeline — new features, bug fixes, refactors
  that touch production code (`backend/apps/*`, `frontend/src/`).
- **Direct work is acceptable** for meta/infra/tooling (`tools/*.sh`, `hooks/*`,
  `.github/*`, `.gitignore` whitelist), cleanup/housekeeping (single-line fixes,
  sub-MINOR follow-ups, docs/policy edits to `CLAUDE.md` / `CONTRIBUTING.md` /
  `.claude/agents/*.md` / `.claude/skills/*` / `docs/*`), one-line trivial fixes, and
  pure docs commits (Report.md sync, Task.md updates). The pipeline's invocation cost
  outweighs its value for these meta-tasks. **Risky meta-infra override**: if the
  change touches auth / token-handling / schema / a cross-cutting refactor of ≥4
  unrelated files, still run code-review + security-manager before commit.
- **Token-saving rules** — see `docs/token-saving.md`:
  Rule 1 (defer reporter to session end), Rule 2 (skip code-review +
  security-manager on trivial commits — `<50 LOC` OR pure docs/policy + no
  migration + no production code + no auth/network/model change), Rule 4
  (auto-archive Task.md handoffs), Rule 5 (slim back-maker prompts), Rule 6 (bundle
  trivial commits, push only push-worthy), Rule 7 (post-push cleanup).
  User overrides: "지금 reporter 돌려" / "리뷰 돌려" / "지금 push".
