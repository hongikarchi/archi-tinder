---
name: reporter-inline
description: Update Task.md + state.js + conditional algorithm.md to record a just-shipped change. Runs in the main session BEFORE `git-publish` admin squash merge so the audit ships in the SAME PR as the work — eliminates separate reporter PRs. Supersedes the `reporter` agent for routine session-end housekeeping.
---

# reporter-inline — audit recorded in same PR as work

Use this skill after `git-commit` skill creates the code commit on a feature branch, and AFTER `git-publish` opens the PR (so the PR number is known), but BEFORE `git-publish` admin-squash-merges. The audit lands as an additional commit on the same feature branch, gets squashed together with the code, and ends up as a single PR.

**Pipeline position**:
```
front-maker/back-maker → code commit (git-commit) → push + PR open (git-publish Steps 1-3)
   → [REPORTER-INLINE HERE] → audit commit (git-commit) → push → admin squash (git-publish Step 4)
```

Result: 1 PR carrying both code + audit. No separate reporter PR cycle.

**Do NOT dispatch `reporter` agent for routine housekeeping** — that agent is deprecated as of 2026-05-26.

---

## Hard scope — writes files only

Read git state for context. NEVER run state-mutating git/gh commands in this skill:
- ❌ `git commit`, `git push`, `git rebase`, `git checkout -b`
- ❌ `gh pr create`, `gh pr edit`, `gh pr merge`, `gh pr close`

You write only:
- `.codex/Task.md`
- `project/state.js`
- Conditionally: `docs/algorithm.md` (per Step 3 narrow scope)

After file writes, STOP. The main session's next step is `git-commit` skill for the audit commit, then `git-publish` Step 4 (admin squash).

---

## Step 0 — Preconditions

Verify all are true:
- Current branch is `feature/*` (not main/develop). Abort otherwise.
- A code commit already exists on this branch ahead of `origin/develop`.
- A PR has been opened (`gh pr view <PR_NUMBER>` returns success). Capture the PR number.
- The change you're auditing is "audit-worthy" — anything more than a typo / trivial whitespace fix. For genuinely trivial changes (single-character typo, comment fix), **skip this skill** entirely.

If the change closes a `## Now` entry in `.codex/Task.md`, capture the entry's ID + title for the Done section.

---

## Step 1 — Gather information

```bash
git log -1 --stat                        # last commit + files
git diff HEAD~1 --name-only               # files changed
TZ=Asia/Seoul date '+%Y-%m-%d %H:%M KST'  # writer time in KST
git rev-parse --short HEAD                # current feature branch tip
git rev-parse --abbrev-ref HEAD           # branch name
git fetch origin develop && git rev-parse --short origin/develop  # develop HEAD (used for meta.head)
```

Read `.codex/Task.md` once before editing.

---

## Step 2 — Update `.codex/Task.md`

Use `Edit` tool (NOT `Write`) so the rest of the file stays intact.

### 2a. Move `## Now` entry to `## Done`

If the change closes a `## Now` entry: cut the entry from `## Now`, paste at the TOP of `## Done` under a new header:

```
### <TASK_ID> — <Korean title> — RESOLVED YYYY-MM-DD (PR #<N> `<sha-pre-squash>`)
- <bullet 1 — what shipped>
- <bullet 2>
- ...
```

- `YYYY-MM-DD` = today's date in KST.
- `<N>` = PR number (captured in Step 0).
- `<sha-pre-squash>` = feature branch tip SHA from Step 1. Annotated as "pre-squash" because post-merge the canonical SHA will be the squash commit on `develop`, which we don't know yet. Next reporter-inline run can backfill.

Sub-task checkboxes that were completed by this commit get `[x]` before moving.

If NO `## Now` entry corresponds (small follow-up / standalone fix): create a fresh `### <ID> — <title> — RESOLVED ...` directly at the top of `## Done` with the new entry.

### 2b. Deferred-item surfacing (`Deferred:` line → new `## Next` entry)

If the new `## Done` entry's body contains a `Deferred: ...` line (a follow-up the session flagged but did not ship), append a `#### <SLUG>` entry under the appropriate bucket in `## Next`:

- Default bucket: `### MEDIUM` (uncategorised pending).
- `### HIGH` only if the Done note explicitly tags urgent.
- `### LOW` only if Done note tags non-actionable / explicit skip.

Pattern:
```
Done note line:
  Deferred: _caches.py:92 IMP-5 cache create call bypass (gated default OFF).

New Next entry under ### MEDIUM:
  #### BACK-LLM-3 — Gemini cache 호출에 timeout 없음
  _caches.py:92 ... wrap on toggle-on.
```

ID convention: `<SURFACE>-<TOPIC>-<N>` (e.g. `BACK-LLM-3`, `FRONT-UX-5`). Pick next available `N` within the matching `<SURFACE>-<TOPIC>` namespace. Korean title ≤25 chars (problem/goal only). Never reuse a retired number.

If `Deferred:` already has a matching Next entry (pre-surfaced during this same commit), skip — do not duplicate.

### 2c. Section vocabulary

`.codex/Task.md` uses:
- `## Next` — backlog, bucketed `### HIGH` / `### MEDIUM` / `### LOW`. Each item = `#### <SLUG>` one level deeper.
- `## Now` — current initiative slice.
- `## Done` — resolved log, append-only at top, one dated group per shipped batch.

Do NOT use legacy labels `## Open` / `## In Progress` / `## Resolved` (renamed 2026-05-24).

---

## Step 3 — Sync `docs/algorithm.md` (conditional)

Run ONLY if the commit touched any of:
- `backend/config/settings.py` (`RECOMMENDATION` dict specifically)
- `backend/apps/recommendation/engine.py`
- `backend/apps/recommendation/views.py` (algorithm-relevant — phase transitions, convergence, swipe processing, fallback, MMR)

If diff doesn't touch any of those, skip this entire step.

### 3a. Hyperparameter Production Value sync (mechanical)

If `RECOMMENDATION` dict values changed, update the **Production Value** column of `docs/algorithm.md` Hyperparameter Space table to match. Read both, replace cell values where they diverge. Leave Type + Range alone.

New key in `RECOMMENDATION`: append new row with Type filled in from `settings.py`, Range blank.

Removed key: leave row in place, append `_(removed in <sha_short>)_` annotation to value cell.

### 3b. Inline annotation (semantic)

For each section in `algorithm.md` whose described behavior just changed, append exactly ONE italic line at the END of that section:

```
_(Updated YYYY-MM-DD <sha_short>: <one-line summary>.)_
```

Examples:
- Convergence detection bug fix → annotate "Convergence Detection" subsection.
- Pool-score normalization → annotate "Phase 0 / Bounded Pool Creation".
- Dislike threshold change → annotate "Edge Cases > Extreme Dislike Bias".

If no semantic section maps to the change, skip 3b.

### 3c. Top-of-file Last Synced line

Add or replace a single line right under the intro blockquote:

```
**Last Synced (Reporter):** YYYY-MM-DD <sha_short>
```

If line exists, replace its value. If not, insert as a new line after the blockquote.

### 3d. Hard limits (forbidden)

- Do NOT rewrite algorithm theory (Mathematical Formulas, Phase descriptions).
- Do NOT add new sections.
- Do NOT remove any existing line (only ANNOTATE / REPLACE Production Value cell / Last Synced line).
- Do NOT touch other `docs/*` files (database-schema.md, COLLAB_HANDOFF.md, etc.) — admin-owned, PR-edited.

If your edit would cross any of these, STOP and surface the constraint to the user.

---

## Step 4 — Refresh `project/state.js`

Read `project/state.js` first. State shape is FIXED:

```js
window.PROJECT_STATE = {
  meta: { name, updatedAt, head, branch },
  done: [{ id, title, completedAt, prs?, note }],
  now:  [{ id, title, startedAt?, note }],
  next: { high: [...], medium: [...], low: [...] },
  prs:  [{ number, title, mergedAt, mergedAtKST, sha? }],
  agents: [{ name, role, model, effort }],
  systemFlow: { title, mermaid },
  recommendationFlow: { title, mermaid },
  agentFlow: { title, mermaid },
  milestones: [{ phase, focus, status }],
};
```

Do NOT rename keys or change top-level structure. Dashboard reads positionally.

### 4a. `meta`

- `updatedAt` ← KST timestamp from Step 1.
- `head` ← `origin/develop` short SHA from Step 1. NOTE: this is the PRE-squash develop HEAD. Post-merge it will be stale by one PR until the next reporter-inline pass picks up the new develop HEAD. Documented stale window.
- `branch` ← current feature branch from Step 1.
- `name` ← preserve from prior state.js.

### 4b. `done`

Read `.codex/Task.md` `## Done` after your Step 2 edits. Take the most recent 5–8 dated groups (one per shipped batch). For each:
- `id` — stable slug from group title (or carry from prior state.js).
- `title` — human-readable line minus the "— RESOLVED …" suffix.
- `completedAt` — YYYY-MM-DD from group header.
- `prs` — array of PR numbers parsed from `(PRs #X / #Y)` / `(PR #N)` parenthetical.
- `note` — one-line summary; concatenate `[x]` sub-task headlines if present.

Older entries beyond the most-recent N stay in Task.md as durable ledger but NOT in state.js (sliding window).

### 4c. `now`

Read Task.md `## Now` after edits. For each `### <title>`:
- `id` — slug from title.
- `title` — sub-header text.
- `startedAt` — if body mentions start date, capture; otherwise omit.
- `note` — body collapsed to one line.

### 4d. `next`

Read Task.md `## Next` after edits. Emit:
```js
next: {
  high:   [items from ### HIGH],
  medium: [items from ### MEDIUM],
  low:    [items from ### LOW],
},
```

Each item: `{ id, title, note }` (no `startedAt`). Always emit all three keys even if a bucket is empty (`[]`).

### 4e. `prs` — MODIFIED for reporter-inline (advisor #1 policy)

Query merged PRs:
```bash
gh pr list --base develop --state merged --limit 8 --json number,title,mergedAt
```

Build 8 entries from this list. Then **prepend the in-flight PR** (the one this skill is auditing):

```js
{
  number: <PR_NUMBER>,
  title: <PR_TITLE>,
  mergedAt: null,           // sentinel: merge pending
  mergedAtKST: null,
  sha: null                 // sentinel: pre-squash SHA unknown until merge
}
```

Result: 9 entries total → drop the OLDEST to maintain the 8-entry window → final 8 entries with the in-flight PR at index 0.

**Backfill policy**: the NEXT reporter-inline invocation, on its Step 4e, reads `prs[]`, finds entries with `mergedAt: null`, runs `gh pr view <number> --json mergedAt,mergeCommit` to fill in the real merge timestamp + squash SHA, then proceeds with its own in-flight prepend. Steady-state backfill is automatic; no manual cleanup needed.

For non-null entries from `gh pr list`:
- `mergedAt` — raw ISO 8601 UTC from `gh` (e.g. `2026-05-23T16:32:04Z`). DO NOT transform.
- `mergedAtKST` — same timestamp formatted `YYYY-MM-DD HH:mm KST`:
  ```bash
  TZ=Asia/Seoul date -j -f '%Y-%m-%dT%H:%M:%SZ' '<mergedAt>' '+%Y-%m-%d %H:%M KST'
  # Linux: TZ=Asia/Seoul date -d '<mergedAt>' '+%Y-%m-%d %H:%M KST'
  ```

Do NOT swap `mergedAt` and `mergedAtKST`. Consumers parse `mergedAt`; humans read `mergedAtKST`.

### 4f. `agents`

Scan `.codex/agents/*.toml` config. For each agent file, emit:
- `name` — from `name =`.
- `role` — one-line role string from first sentence of `description =` (or first sentence of body if more concise).
- `model` — from `model =` when present.
- `effort` — from `effort =` when present. If missing, emit `"default"`.

If config has `deprecated = true`, append `" (deprecated)"` suffix to the role string. Don't omit the entry — keep it visible so the dashboard surfaces the migration status.

### 4g. `systemFlow` / `recommendationFlow` / `agentFlow`

**Preserve verbatim from prior state.js.** Reporter never regenerates Mermaid bodies — these are hand-curated diagrams maintained by admin / session, not derived from code.

If the commit touched any of:
- `backend/apps/recommendation/{views,engine,services}/**`
- `frontend/src/api/**`
- `frontend/src/pages/{LLMSearchPage,SwipePage,ResultsPage}.jsx`
- `.codex/agents/**`
- `.agents/skills/**` (added 2026-05-26)

then append (or replace) a single stale-flag comment near the top of `state.js`, after the existing header block:

```js
// Reporter: Mermaid sources may be stale — commit <short_sha> touched <one example path>. Next session should refresh the affected diagram by hand.
```

Replace any prior stale-flag with the newer one. If the commit did not touch any of the above, ensure no stale-flag is present (remove).

### 4h. `milestones`

**Preserve verbatim from prior state.js.** Phase archive. Only update when an entire phase status flips (rare, session-explicit).

### 4i. Write the file

Use `Write` — small structured JS file. Keep `window.PROJECT_STATE = { ... };` shape + header comment block intact (including stale-flag if applicable).

**CRITICAL — block comment `*/` early-termination pitfall (2026-05-26 incident)**:
The opening `/* … */` header block contains backtick-wrapped path examples
(e.g., `` `.agents/skills/<slug>/SKILL.md` ``). Any backtick path that includes
`*/` as a literal substring (e.g., `` `.agents/skills/*/SKILL.md` ``) closes
the block comment prematurely — the JS parser sees `*/`, ends the comment,
treats everything after as code, errors out on the next identifier → 
`window.PROJECT_STATE` is never assigned → `dashboard.html` renders blank
(panels all empty).

Forbidden inside the opening block comment:
- ``...`.../*` `... ` — backtick path that contains `*/` substring.
- Any literal `*/` that you did not intend to close the comment.

Safe substitutions: use `<slug>`, `<name>`, `<*>` placeholders instead of
glob-style `*/`. The skill body uses `` `.agents/skills/<slug>/SKILL.md` ``
(safe) instead of `` `.agents/skills/*/SKILL.md` `` (bug).

**Always verify** state.js parses after write:

```bash
node -e "global.window={}; eval(require('fs').readFileSync('project/state.js','utf8')); console.log('OK keys:', Object.keys(window.PROJECT_STATE).length, 'done:', window.PROJECT_STATE.done.length, 'prs:', window.PROJECT_STATE.prs.length)"
```

Must print `OK keys: 9 done: N prs: M` (or similar). If it errors, scan the
opening block comment line-by-line for `*/` substrings inside backticks.

---

## Step 5 — Report

After file writes complete, report:

```
REPORTER-INLINE: WRITTEN
Files: .codex/Task.md, project/state.js[, docs/algorithm.md]
Task.md ## Done: <new entry header>
state.js prs[]: prepended in-flight PR #<N> (mergedAt: null)
state.js meta.head: <pre-squash develop SHA — stale by 1 PR until next pass>
algorithm.md sync: <SKIPPED|3a-only|3a+3b+3c>
```

Then STOP. Next step is `git-commit` skill (audit commit on the same feature branch), followed by `git-publish` Step 4 (admin squash).

---

## Discriminating test (post-implementation verification)

`reporter-inline` is correct if its state.js diff differs from what the legacy `reporter` agent would produce POST-MERGE ONLY in:
- (a) `meta.head` — one PR stale (vs. agent's squash SHA).
- (b) `prs[]` — in-flight entry has `mergedAt: null, mergedAtKST: null, sha: null` (vs. agent's filled real values).

Any other delta (Mermaid changes, milestones changes, Task.md formatting deviation) is a BUG. Catch it before commit.

Test fixture: PR #121's `reporter` agent pass (commit `e36648b`) shows the canonical post-merge state. Compare reporter-inline output mentally against that.

---

## Rules (mirror reporter agent's Rules section)

- NEVER delete existing content in Task.md.
- Use `Edit` (NOT `Write`) for Task.md so the rest stays untouched.
- Writes are: `.codex/Task.md`, `project/state.js`, narrow `docs/algorithm.md`. All other `docs/*` files are admin-owned (PR-edited).
- Time convention: every human-facing timestamp is `YYYY-MM-DD HH:mm KST`. PR records also carry raw ISO 8601 UTC (`mergedAt`).
- 2026-05-24 vocabulary: `## Done` / `## Now` / `## Next` (NOT `Resolved` / `In Progress` / `Open`).
- 2026-05-26 (this skill): runs INLINE before squash merge. Separate reporter PR is deprecated.

---

## When to escalate to reporter agent

The reporter agent (deprecated marker) remains available for fallback during the 2026-05-26 migration window. Escalate if:

- The change touched an unfamiliar `state.js` field structure not covered by Step 4.
- A multi-PR batch must be audited at once (deploy mode) — escalate to keep audit consistent.
- This skill produces a state.js that fails JSON-like parse (Mermaid escaping issue, etc.) and quick fix is unclear.

Dispatch:
```json
{
  "agent_type": "reporter",
  "message": "reporter fallback — <reason>. <precise problem + current state>"
}
```

---

## Related skills
- `git-commit` — runs AFTER this skill to commit the audit changes.
- `git-publish` — runs AFTER `git-commit` to push and squash-merge.
