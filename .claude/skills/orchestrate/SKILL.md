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
1. Read `CLAUDE.md` — conventions, rules, DB schema, coding standards, and `## Product Identity` + `## Product Constitution` (the vision + acceptance + decision principles anchor)
2. Read `.claude/Task.md` — current problem board (`## Now` / `## Next` / `## Done`); Phase 16-18 dimensions live in `## Next` directly (the prior `docs/specs/*.md` folder was absorbed 2026-05-24)
3. Read code directly — the running code is the source of truth for architecture and API surface (per CLAUDE.md `## What This Repo Does`). No standalone Report.md.
4. If algorithm task: read `docs/algorithm.md` for theory + production hyperparameters
5. If task references a Phase or open question: read the matching `#### <SLUG>` entry under one of the `### HIGH` / `### MEDIUM` / `### LOW` buckets in `.claude/Task.md` `## Next`

## When user requests work
1. **Session start (Now/Next discipline)** — open `.claude/Task.md`. Read `## Now` first.
   - If `## Now` is non-empty and matches the user's request: continue that entry.
   - If empty: look in `## Next` for a matching `#### <SLUG>` entry under one of the `### HIGH` / `### MEDIUM` / `### LOW` buckets. Promote it into `## Now` as `### <SLUG> — <one-line title>` (cut from the bucket in Next, paste into Now, raise heading level one). One initiative slice at a time. Prefer `### HIGH` first when picking.
   - If the user's request is brand-new: write a fresh `### <ID> — <Korean title>` directly into `## Now` using the ID convention from `.claude/Task.md ## Workflow Rules` (e.g. `BACK-LLM-1`, `FRONT-UX-1`, `INFRA-DB-1`).
2. Read `CLAUDE.md` `## Product Identity` + `## Product Constitution` + scan relevant code.
3. Execute (back-maker / front-maker / etc.).
4. **Mid-session deferral** — if the user says "미루자" / "later" / "defer", move the Now entry **back to `## Next`** with a one-line rationale note (demote one heading level to `#### <SLUG>` and place under the bucket that matches its new status — usually `### MEDIUM` for normal deferrals, `### LOW` for explicit skip). Do not silently leave it in Now.
5. **Session end (success)** — `reporter` agent moves the Now entry to `## Done` under `### <title> — RESOLVED YYYY-MM-DD (PR #N)` with PR ref + SHA. Any `Deferred: ...` text in the Done note auto-surfaces as a new `#### <SLUG>` under `### MEDIUM` in `## Next` (reporter sub-step 2a; HIGH / LOW only when the Done note explicitly tags it).
6. **Failure after 2 cycles** — leave the entry in `## Now`, add failure notes inline, report to user. Do not move to Done.

## When user says "오늘 개발 진행해" or "continue development"
Follow the `## Now` / `## Next` discipline at the top of `.claude/Task.md`:
1. Read `## Now` first. If non-empty, continue that entry.
2. If empty, pull the highest-priority item from `## Next ### HIGH` and promote it to `## Now` (cut from Next, paste into Now, raise heading level one — see `.claude/Task.md ## Workflow Rules`).
3. Execute that one initiative slice through the full pipeline (plan → makers → review → security → commit → app-test → publish → reporter at session end).
4. After the PR merges, ask the user before pulling the next HIGH item — do not auto-chain across initiatives.

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
→ Check architectural fit yourself: does this match `CLAUDE.md` `## Product Identity`
  (Core Promise + Two Pillars) and `## Product Constitution` (out-of-scope +
  decision principles)?
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
Run the `git-commit` skill directly in the main session. **Do NOT dispatch the
`git-manager` agent — it is deprecated as of 2026-05-26.** The skill stages with
secret exclusions, builds a caveman conventional-commit message, and commits on
the feature branch. It never pushes — pushing happens in Step 9 via the
`git-publish` skill.

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

### Step 8 — Publish gate (BLOCKING by default)

**Default behavior: STOP after commit (Step 6). Do NOT dispatch `git-publisher`.**

Check the publish gate before dispatching `git-publisher`. The gate opens only when one of the following is explicitly true:

- **(a) User explicit trigger in current turn** — the user typed one of: `"PR 올려"`, `"push"`, `"publish"`, `"merge"`, `"PR 열어"`, `"deploy"`, `"배포"`, `"release"`. Cite the user's literal phrase when invoking the gate.
- **(b) Active plan with `## PR Plan` section** — if a plan file `.claude/plans/<name>.md` is active for this work and contains an explicit `## PR Plan` section listing N slices, the plan acts as authorization for those N PRs. Each slice's commit may dispatch `git-publisher` automatically. After the last planned slice, the gate closes (returns to default).
- **(c) In-flight fix-loop** — if `app-test` or `code-review` already gated this work in the current dispatch and a tiny follow-up commit is the result of the fix-loop, that continues the original (a) or (b) authorization. No fresh trigger needed.

If neither (a), (b), nor (c) is true:
1. STOP. Do NOT dispatch `git-publisher`.
2. Report to user: `commit <SHA> ready on <branch>. Say "PR 올려" when ready to publish, or accumulate more commits first.`
3. Wait for explicit signal.

Once the gate opens, dispatch `git-publisher` with the work and cite the trigger in the dispatch prompt.

**Hard rule — base=main is a separate gate.** `git-publisher` enforces a second precondition: base=main PRs require the trigger keyword to be `"deploy"` / `"release"` / `"배포"` specifically. Plain `"PR 올려"` authorizes only base=develop. Codified post-PR #105 main-merge incident (2026-05-25).

### Step 9 — Audit-then-publish (reporter-inline + git-publish)

Run the `reporter-inline` skill directly in the main session **BEFORE** the
publish step. **Do NOT dispatch the `reporter` agent — it is deprecated as of
2026-05-26.** The skill updates `.claude/Task.md`, `project/state.js`, and
conditionally `docs/algorithm.md`, then calls the `git-commit` skill to commit
the audit on the SAME feature branch as the work commit. The audit + work
squash together into a single commit on `develop`. The legacy 2-PR pattern
(feature PR + separate reporter PR) is dropped.

`reporter-inline` outputs:
1. Move completed tasks from `.claude/Task.md` `## Now` / `## Next` into
   `## Done` under a dated `### <title> — RESOLVED YYYY-MM-DD (PR #N)` header
   (PR # may be a placeholder if PR not yet opened — backfill on next pass).
2. Regenerate `project/state.js` (meta + done[] + now[] + next[] + prs[] +
   agents[]) so `project/dashboard.html` reflects current state. `meta.head`
   captures pre-squash `origin/develop` SHA — 1-PR stale window is intentional.
3. Conditionally sync `docs/algorithm.md` (Production Value column + section
   annotations + Last Synced line) when the commit touched algorithm-relevant
   code.

After `reporter-inline` + audit commit, run the `git-publish` skill (Step 0
publish gate first, then push + PR open base=`develop` + admin squash + delete
branch). **Do NOT dispatch the `git-publisher` agent for Mode 2 / feature →
develop merges — that agent is reserved for Mode 3 deploy, external PR triage,
or complex rebase conflicts.**

### Step 10 — Stop and report to user
After reporter finishes, STOP. Summarize for the user what was implemented, the
commit/PR, the app-test verdict, and any open follow-ups.

## Algorithm work — externally owned

Per `CLAUDE.md` `## Rules` (`docs/algorithm.md` narrow write permission, codified
post-2026-05-18), algorithm-side work (`engine.py`, `services/embeddings.py`,
`services/rerank.py`, `services/_caches.py`, Topic 01-12 in `docs/algorithm.md`,
IMP-1/7/8, A2 hyperparameter optimization) is owned by a separate collaborator —
this skill does NOT dispatch algorithm tuning work. If the user asks for
algorithm tuning, surface the ownership boundary and decline.

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
  pure docs commits (Task.md / state.js updates). The pipeline's invocation cost
  outweighs its value for these meta-tasks. **Risky meta-infra override**: if the
  change touches auth / token-handling / schema / a cross-cutting refactor of ≥4
  unrelated files, still run code-review + security-manager before commit.
- **Token-saving rules** — see `.claude/WORKFLOW.md` § Token-saving rules:
  Rule 1 (defer reporter to session end), Rule 2 (skip code-review +
  security-manager on trivial commits — `<50 LOC` OR pure docs/policy + no
  migration + no production code + no auth/network/model change), Rule 3 (bundle
  trivial commits, push only on push-worthy).
  User overrides: "지금 reporter 돌려" / "리뷰 돌려" / "지금 push".
