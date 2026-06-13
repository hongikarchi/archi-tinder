---
name: orchestrate
description: Use this skill to implement any feature or fix end-to-end. It reads project context, decomposes the task into backend/frontend specs, launches the `feature` Workflow (build -> review -> security -> Opus adversarial-verify -> 2-cycle fix loop) which STOPS at commit-ready, then the main session runs the git-commit skill, dispatches app-test (pre-push browser + drift gate), runs the reporter-inline skill, and stops at the publish gate (git-publish only on explicit trigger). The git-publisher agent is reserved for Mode 3 deploy, external PR triage, and complex rebase recovery.
---

# Orchestrate — feature-implementation playbook (Workflow-tool era)

This skill runs in the **main session's context**. As of the Opus 4.8 + ultracode
refactor, the build+review CORE is a **Workflow script** (`.claude/workflows/feature.js`),
not an inline sequence of `Agent` dispatches. The skill's job is now:

1. **Decompose** the task into a backend/frontend spec (the session owns this).
2. **Launch** the `feature` workflow — it builds (back-maker/front-maker on Sonnet),
   reviews (code-review + security-manager on Sonnet), adversarially verifies findings
   (Opus), runs a 2-cycle fix loop, and **returns a structured result. It performs NO
   git operations.**
3. **Own the gate** — the main session runs `git-commit` -> `app-test` -> `reporter-inline`
   around the workflow, and **STOPS at the publish gate**. Push/PR/merge happens only on
   an explicit trigger, via the `git-publish` skill.

> **Why the split:** a Workflow runs autonomously to completion in the background. The
> team's safety model is the opposite — STOP after commit, explicit human keyword before
> any push (publish gate, incident-driven: PR #105, Codex HEAD-move). So the autonomous
> workflow stays strictly inside Build+Review; the human gate stays in the session,
> outside the workflow. Never add a `git push`/`gh pr`/`merge` to `feature.js`.

## Launching the workflow (tool reference)

Call the **`Workflow` tool** with `name: 'feature'` (resolves `.claude/workflows/feature.js`
by its `meta.name`) and an `args` object:

```
Workflow({
  name: 'feature',
  args: {
    taskId: 'BACK-LLM-1',
    backend:  { spec: '<precise backend spec>', files: ['backend/apps/...'], contract: null } /* or null */,
    frontend: { spec: '<precise frontend spec>', files: ['frontend/src/...'] }              /* or null */,
    acceptance: ['<criterion 1>', '<criterion 2>'],
    cyclesUsed: 0,        // raise on an app-test FAIL re-launch (see Step 5)
    fixOrders: null       // confirmed findings to fix on a re-launch
  }
})
```

Pass `backend: null` for a frontend-only task (and vice-versa). The workflow pins every
worker's model explicitly (Sonnet workers, Opus verify) — you do not manage models here.

It returns: `{ commitReady, cyclesUsed, built, apiContract, confirmedFindings,
reviewVerdict, securityVerdict, rationale, blocked? }`.

**Do NOT write source code yourself, and do NOT re-implement the build/review loop with
raw `Agent` calls — launch the workflow.** If `Workflow` is unavailable, STOP and report
the blockage; do not work around it by editing `backend/`/`frontend/` directly. (Meta/infra
+ docs are the carve-out — see Rules.)

## Before every task
1. Read `CLAUDE.md` — conventions, rules, DB schema, `## Product Identity` + `## Product Constitution`.
2. Read `Task.md` — `## Now` / `## Next` / `## Done` board.
3. Read code directly — the running code is the source of truth for architecture + API surface.
4. If algorithm task: read `docs/algorithm.md` for theory + production hyperparameters (but see "Algorithm work — externally owned" below).
5. If the task references a Phase / open question: read the matching `#### <SLUG>` entry under `### HIGH`/`### MEDIUM`/`### LOW` in `Task.md` `## Next`.

## Now / Next discipline
1. **Session start** — open `Task.md`, read `## Now` first.
   - `## Now` non-empty + matches request: continue that entry.
   - Empty: promote a matching `#### <SLUG>` from `## Next` into `## Now` (cut from bucket, paste into Now, raise heading one level). One slice at a time; prefer `### HIGH`.
   - Brand-new request: write a fresh `### <ID> — <Korean title>` into `## Now` (ID convention from `Task.md ## Workflow Rules`, e.g. `BACK-LLM-1`).
2. **Mid-session deferral** ("미루자" / "later" / "defer") — move the Now entry back to `## Next` (demote to `#### <SLUG>` under the matching bucket) with a one-line rationale. Never silently leave it in Now.
3. **Session end (success)** — the `reporter-inline` skill moves the Now entry to `## Done` (Step 6).
4. **Failure after 2 cycles** — leave the entry in `## Now`, add failure notes inline, report to user. Do not move to Done.

## "오늘 개발 진행해" / "continue development"
Read `## Now` first; if empty, promote the highest-priority `## Next ### HIGH` item. Execute one slice through the full pipeline below. After the PR merges, ask before pulling the next HIGH item — do not auto-chain.

## Workflow

### Step 1 — Decompose (session)
Break the task into a precise spec for the workflow `args`:
- **backend**: files, what to add/change/remove, expected API contract (endpoint, method, request/response).
- **frontend**: files, components, which API to call.
- **acceptance**: the criteria code-review will check.
Set `backend`/`frontend` to `null` for one-sided tasks.

### Step 2 — Launch the `feature` workflow
Call `Workflow({ name: 'feature', args: {...} })` with the decomposition. Watch progress via `/workflows` if needed. The workflow handles build -> review -> security -> verify -> fix loop internally (max 2 fix cycles).

### Step 3 — Read the structured result
- `result.blocked` set → a maker hit a hard blocker. Surface it to the user; do not commit. Treat as a failure (leave Task.md Now entry, report).
- `result.commitReady === false` (fix budget exhausted) → STOP. Report `confirmedFindings` to the user, ask for guidance. Do not commit.
- `result.commitReady === true` → architectural-fit check yourself: does it match `CLAUDE.md` `## Product Identity` + `## Product Constitution`? If NO, re-launch the workflow with `fixOrders` describing the misfit and `cyclesUsed: result.cyclesUsed` (counts against the shared budget). If YES → Step 4.

### Step 3.5 — Migration backstop (defensive)
If the workflow's `built` list shows any `backend/apps/*/migrations/` file, confirm it was applied:
```bash
cd backend && python3 manage.py showmigrations 2>&1 | grep -E '\[ \]'
```
No output → proceed. Any `[ ]` → `cd backend && python3 manage.py migrate` (back-maker should have, but this is belt-and-suspenders; postmortem `190c830`).

### Step 4 — Commit (local only)
Run the **`git-commit` skill** in the main session. Stages with secret exclusions, builds a caveman conventional-commit message, commits on the feature branch. Never pushes.

### Step 5 — Pre-push browser test + drift gate
Dispatch the **`app-test` agent** (it runs *outside* the workflow — it is post-commit, pre-push). It runs the live-browser user-journey + the HEAD/`origin/develop` drift check; returns one verdict.

- **PASS** → Step 6.
- **FAIL (browser)** — re-launch the `feature` workflow with `fixOrders` = the app-test failure spec and `cyclesUsed` raised by 1 (the app-test FAIL consumes one of the shared 2 cycles, since the workflow already returned and cannot re-enter its own loop). After it returns commit-ready, re-run `git-commit` (new commit, same branch) → re-dispatch `app-test`. If the shared budget is exhausted, STOP and report.
- **FAIL (drift — `origin/develop` moved)** — no code fix. Inform the user, `git pull --rebase origin develop` (resolve conflicts via a fix re-launch if needed), re-dispatch `app-test`. Drift does NOT count toward the 2-cycle budget.
- **Dev server not running** — app-test reports it; note it and proceed to Step 6 (drift check still applied).

### Step 6 — Audit (reporter-inline skill)
Run the **`reporter-inline` skill** in the main session BEFORE publishing. It updates `Task.md` `## Done`, regenerates `project/state.js`, and conditionally syncs `docs/algorithm.md`, then commits the audit on the SAME feature branch (via `git-commit`) so it squashes together with the work — no separate reporter PR.

### Step 7 — Publish gate (BLOCKING by default)
**Default: STOP after the audit commit. Do NOT run `git-publish`, do NOT dispatch `git-publisher`.**

The gate opens only when one is explicitly true:
- **(a) Explicit trigger this turn** — user typed `"PR 올려"` / `"push"` / `"publish"` / `"merge"` / `"PR 열어"` / `"deploy"` / `"배포"` / `"release"`. Cite the literal phrase.
- **(b) Active plan with `## PR Plan`** — `.claude/plans/<name>.md` listing N slices authorizes those N PRs.
- **(c) In-flight fix-loop continuation** — a tiny follow-up commit from a fix loop continues the original (a)/(b) authorization.

If none true: STOP. Report `commit <SHA> ready on <branch>. Say "PR 올려" when ready to publish.` and wait.

Once open: run the **`git-publish` skill** (base=`develop` only). Escalate to the `git-publisher` agent only for the CLAUDE.md `## Git Operations` edge cases (Mode 3 develop→main deploy, external PR triage, complex rebase, push rejection unclear cause, mid-merge failure).

**Hard rule — base=main is a separate gate.** Base=main needs `"deploy"`/`"release"`/`"배포"` specifically; plain `"PR 올려"` authorizes only base=develop. base=main is always Mode 3 via the `git-publisher` agent. (Codified post-PR #105.)

### Step 8 — Stop and report
Summarize: what was implemented, the commit/PR, the app-test verdict, the workflow's `confirmedFindings` (if any shipped as medium/low), open follow-ups. STOP.

## Algorithm work — externally owned
Per `CLAUDE.md` `## Rules`, algorithm-side work (`engine.py`, `services/embeddings.py`, `services/rerank.py`, `services/_caches.py`, Topic 01-12 in `docs/algorithm.md`, IMP-1/7/8, A2 hyperparameter optimization) is owned by a separate collaborator — this skill does NOT decompose algorithm tuning into the workflow. Surface the ownership boundary and decline.

LLM-chat-module work (`services/parse_query.py`, `services/generation.py`, `services/_gemini.py`, chat-phase Gemini latency IMP-4/5/6, Phase 17 reverse-Q + persona) stays in scope — decompose as a normal feature.

## Rules
- **Never write source code yourself.** Launch the `feature` workflow. If `Workflow` appears unavailable, STOP and report — do not edit `backend/`/`frontend/` directly.
- **Never commit ad-hoc.** Default: `git-commit` skill. Escalate to `git-publisher` agent only for multi-commit reorganization / diagnosis failure.
- **Never push ad-hoc.** Default: `git-publish` skill for feature → develop (base=develop only). Escalate to `git-publisher` agent only for Mode 3 deploy / external PR / complex rebase / push rejection / mid-merge failure.
- **Fix-cycle budget = 2, shared** across the workflow's internal loop AND session-side app-test FAIL re-launches. Track it via `args.cyclesUsed` / `result.cyclesUsed`.
- If a task is ambiguous, ask ONE clarifying question before decomposing.
- If you notice a `CLAUDE.md` convention that needs updating, propose it in your final output — do not write it yourself.
- Write new learnings (architectural decisions, patterns, gotchas) to memory immediately.
- **Feature work** (touching `backend/apps/*`, `frontend/src/`) must go through this pipeline.
- **Direct work is acceptable** for meta/infra (`tools/*.sh`, `hooks/*`, `.github/*`, `.claude/workflows/*`), cleanup/housekeeping (single-line fixes, sub-MINOR follow-ups), and docs (`CLAUDE.md`, `CONTRIBUTING.md`, `.claude/agents/*.md`, `.claude/skills/*`, `docs/*`, Task.md / state.js) — direct edit + `git-commit` skill. **Risky meta-infra override**: changes touching auth / token-handling / schema / a ≥4-file cross-cutting refactor still go through the `feature` workflow (or at least code-review + security-manager) before commit.
- **Token-saving rules** — see `.claude/WORKFLOW.md` § Token-saving rules. Overrides: "지금 reporter 돌려" / "리뷰 돌려" / "지금 push".
