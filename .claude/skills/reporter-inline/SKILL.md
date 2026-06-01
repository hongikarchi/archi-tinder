---
name: reporter-inline
description: Update Task.md + state.js + conditional algorithm.md to record a just-shipped change. Runs in the main session BEFORE `git-publish` admin squash merge so the audit ships in the SAME PR as the work — eliminates separate reporter PRs. Supersedes the `reporter` agent for routine session-end housekeeping.
---

# reporter-inline — audit recorded in same PR as work

Use this skill after `git-commit` creates the code commit on a feature branch, and BEFORE `git-publish` ships the PR. The audit is keyed on the stable **TASK ID** (e.g. `SNS-RESULTS-UI-1`) — the GitHub PR# is NOT needed at write-time: `gh pr merge` auto-stamps `(#N)` onto the squash commit, recoverable from `git log`, so cite the PR# only as an optional backfill. The audit lands as an additional commit on the same feature branch, squashed together with the code into a single PR.

**Pipeline position**:
```
front-maker/back-maker → code commit (git-commit) → [REPORTER-INLINE HERE] → audit commit (git-commit) → git-publish (push + PR open + admin squash)
```

Result: 1 PR carrying both code + audit. No separate reporter PR cycle.

**(The `reporter` agent was removed 2026-05-31 — this skill replaces it.)**

---

## Hard scope — writes files only

Read git state for context. NEVER run state-mutating git/gh commands in this skill:
- ❌ `git commit`, `git push`, `git rebase`, `git checkout -b`
- ❌ `gh pr create`, `gh pr edit`, `gh pr merge`, `gh pr close`

You write only:
- `Task.md`
- `project/state.js`
- Conditionally: `docs/algorithm.md` (per Step 3 narrow scope)

After file writes, STOP. The main session's next step is `git-commit` skill for the audit commit, then `git-publish` Step 4 (admin squash).

---

## Step 0 — Preconditions

Verify all are true:
- Current branch is `feature/*` (not main/develop). Abort otherwise.
- A code commit already exists on this branch ahead of `origin/develop`.
- No PR is needed yet — this skill runs BEFORE `git-publish`. The audit is keyed on the TASK ID; the GitHub PR# is optional (backfilled once known).
- The change you're auditing is "audit-worthy" — anything more than a typo / trivial whitespace fix. For genuinely trivial changes (single-character typo, comment fix), **skip this skill** entirely.

If the change closes a `## Now` entry in `Task.md`, capture the entry's ID + title for the Done section.

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

Read `Task.md` once before editing.

---

## Step 2 — Update `Task.md`

Use `Edit` tool (NOT `Write`) so the rest of the file stays intact.

### 2a. Move `## Now` entry to `## Done`

If the change closes a `## Now` entry: cut the entry from `## Now`, paste at the TOP of `## Done` under a new header:

```
### <TASK_ID> — <Korean title> — RESOLVED YYYY-MM-DD (`<sha-pre-squash>`)
- <bullet 1 — what shipped>
- <bullet 2>
- ...
```

- `<TASK_ID>` = the stable task identifier — the PRIMARY key for the entry.
- `YYYY-MM-DD` = today's date in KST.
- `<sha-pre-squash>` = feature branch tip SHA from Step 1. "pre-squash" because post-merge the canonical SHA is the squash commit on `develop`, not yet known. A later reporter-inline pass can backfill the post-squash SHA and the GitHub PR# `(#N)` if desired — neither is required at write-time (the TASK ID is the key).

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

`Task.md` uses:
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

## Step 4 — Refresh `project/state.js` (run the generator)

`project/state.js` is **auto-generated** — do NOT hand-author it. After the Step 2
`Task.md` edits are in place, run:

```bash
node tools/gen-state.js
```

The generator (`tools/gen-state.js`, DASHBOARD-AUTOGEN-1) derives every key from the
canonical sources and writes `project/state.js`:

- `meta` ← git (`origin/develop` short SHA + current branch) + KST clock; `meta.name` preserved.
- `done` / `now` / `next` ← `Task.md` parse (top-8 Done; Next buckets X-HIGH/HIGH/MEDIUM/LOW).
  Structural fields (id/title/date/prs) are mechanical; each entry's **`note` is carried by
  id from the prior `state.js`**, and a NEW entry's note **seeds from its first body line**
  in `Task.md` — so write each Done/Next entry's first bullet as a standalone summary.
- `agents` ← `.claude/agents/*.md` frontmatter (role carried by name, else first sentence).
- `prs` ← `gh pr list --base develop --state merged --limit 8` (falls back to prior on offline).
- `fileTree` ← `git ls-files` ∪ `project/file-roles.json`.
- `systemFlow` / `recommendationFlow` / `agentFlow` / `milestones` ← **carried verbatim** from
  the prior `state.js`. To change a diagram, hand-edit it in `project/state.js`, then re-run the
  generator (it preserves your edit). The generator never regenerates Mermaid.

**Editing an existing note / agent role:** `note` (done/now/next) and agent `role` are
**carried by id/name** from the prior `state.js`, so editing them in `Task.md` does NOT
change them once the id already exists (the carry wins — this is why a Task.md note edit
may "not take"). To rewrite an existing note/role, edit the string **directly in
`project/state.js`** (it is the carried source for that field) and re-run — the generator
preserves it; or delete the id's prior entry so the next run re-seeds from Task.md's first
body line. Asymmetry to remember: `id` / `title` / `completedAt` / `prs` re-derive from
`Task.md` every run, but `note` / `role` are **sticky after the first seed**.

The generator self-checks (re-evals output, asserts the 11 keys + array shapes), exits
non-zero on malformed output, and prints a one-line summary + a drift report to stderr
(files lacking a `file-roles.json` role; role entries for deleted files).

**Your only Step-4 obligation:** make the Step 2 `Task.md` edits, then run the generator.
No manual JSON, no `*/`-comment pitfall, no timestamp/SHA bookkeeping. Commit the regenerated
`project/state.js` together with the `Task.md` change in the same audit commit.

> The previous hand-authoring procedure (4a–4i) is superseded by the generator. The fixed
> state shape and the carry-forward rules are now enforced by `tools/gen-state.js`. Note:
> `prs` lists `--state merged` only — the old in-flight-PR `mergedAt: null` sentinel is
> dropped (the just-merged PR appears on the next generator run after the squash). To open
> the dashboard with a fresher local view, run `make dashboard` (writes the gitignored
> `project/state.local.js`; does not touch the committed `project/state.js`).

## Step 5 — Report

After file writes complete, report:

```
REPORTER-INLINE: WRITTEN
Files: Task.md[, docs/algorithm.md] + project/state.js (regenerated via tools/gen-state.js)
Task.md ## Done: <new entry header>
gen-state.js: done:<N> prs:<M> files:<K>  (generator summary line)
algorithm.md sync: <SKIPPED|3a-only|3a+3b+3c>
```

Then STOP. Next step is `git-commit` skill (audit commit on the same feature branch), followed by `git-publish` Step 4 (admin squash).

---

## Discriminating test (post-implementation verification)

`reporter-inline` is correct when, after the Step 2 `Task.md` edits and `node tools/gen-state.js`:
- (a) the new `## Done` / `## Next` entry appears in the regenerated `state.js` (id/title/date/prs from the header; `note` seeded from the entry's first body line since it is new this pass).
- (b) the carried keys (`systemFlow` / `recommendationFlow` / `agentFlow` / `milestones`) are byte-identical to the prior `state.js` — the generator copies them verbatim, so any diff there is a BUG.
- (c) `prs[]` reflects `gh pr list` (the just-merged PRs) and `meta.head` / `meta.updatedAt` advanced.

The generator's self-check asserts the 11 keys + array shapes; a non-zero exit means malformed output — fix the cause (Task.md format / file-roles.json), do not hand-patch state.js.

---

## Rules

- NEVER delete existing content in Task.md.
- Use `Edit` (NOT `Write`) for Task.md so the rest stays untouched.
- Writes are: `Task.md`, `project/state.js`, narrow `docs/algorithm.md`. All other `docs/*` files are admin-owned (PR-edited).
- Time convention: every human-facing timestamp is `YYYY-MM-DD HH:mm KST`. PR records also carry raw ISO 8601 UTC (`mergedAt`).
- 2026-05-24 vocabulary: `## Done` / `## Now` / `## Next` (NOT `Resolved` / `In Progress` / `Open`).
- 2026-05-26 (this skill): runs INLINE before squash merge. Separate reporter PR is deprecated.

---

## If this skill fails

`node tools/gen-state.js` self-checks and exits non-zero on malformed output. On
failure, read its stderr and fix the ROOT CAUSE — almost always a `Task.md`
formatting deviation (a `### `/`#### ` header the parser cannot split, a missing
`— RESOLVED <date>` anchor) or a `project/file-roles.json` JSON error — then re-run.
Do NOT hand-patch the auto-derived sections of `project/state.js`; they are generated and
your edit is overwritten on the next run. Hand-edits belong only in carried fields — the
Mermaid / milestones blocks and the string values of carried `note` / `role` (see Step 4). The
deprecated `reporter` agent fallback was removed 2026-05-31 — there is no agent to
dispatch.

---

## Related skills
- `git-commit` — runs AFTER this skill to commit the audit changes.
- `git-publish` — runs AFTER `git-commit` to push and squash-merge.
