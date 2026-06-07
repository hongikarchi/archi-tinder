# Workflow Skill Absorption — agent → skill migration

## 한글 요약 (5-15줄)

현재 사이클:
- 매 작업마다 reporter / git-manager / git-publisher 3개 agent dispatch.
- 추가로 reporter PR이 feature PR 별도로 생성 → 작업 1개 = PR 2개.
- 측정: git-manager 14k tok/27s · git-publisher 19-23k tok/47-293s · reporter 46k tok/150s.
- 단순 commit/push에 agent overhead가 실제 work보다 큼.

목표:
- reporter + git-manager 작업을 main session이 직접 수행하는 skill로 흡수.
- reporter audit를 feature PR에 inline (PR 개수 절반).
- git-publisher는 유지 (deploy mode / external PR triage / 복잡 rebase 등 edge case).
- CLAUDE.md HARD RULE이 skill enforcement 보장.

예상 절감 (1 PR 사이클):
- 현재: 8 agent dispatch, ~150-200초, ~30-40k 토큰
- 새 방식: 3 agent dispatch (front-maker + code-review + security), ~60-80초, ~10-15k 토큰

---

## Decision audit trail

- A 옵션 채택 (이번 세션에 끝까지) — git-publisher 유지.
- Skill 3개 작성 + agent 2개 **deprecate marker** (삭제는 다음 PR — advisor #2 반영).
- PR #118 + #120 reporter housekeeping을 새 skill로 첫 검증.
- Advisor 4개 critique 다 반영.

---

## Advisor adjustments (codified 2026-05-26)

### 1. `prs[]` not-yet-merged PR policy (Critical)

`reporter-inline` runs BEFORE squash merge. `gh pr list --base develop --state merged --limit 8` doesn't include the in-flight PR. To avoid silently excluding the freshest item from `prs[]`:

**Policy**: in the skill body, manually construct the in-flight PR entry with these fields:
```js
{ number: <new_pr_number>, title: <PR title>, mergedAt: null, mergedAtKST: null }
```
Prepend it to the existing `prs[]` window. `null` is the sentinel for "merge pending — backfill at next reporter pass". The next `reporter-inline` invocation reads `prs[]`, finds entries with `mergedAt: null`, queries `gh pr view <number>` to fill in the real merge time + sha, then proceeds with its own PR entry.

If a daily batch script (out of scope this session) wants to do the backfill, it follows the same procedure.

### 2. Two-PR deletion migration (High)

Don't delete agent files in the same PR as skill creation. Use deprecation markers in this PR; delete in a follow-up PR after validation.

- `.claude/agents/git-manager.md` → add `deprecated: true` to frontmatter + body note: `# DEPRECATED — superseded by .claude/skills/git-commit/. Kept for fallback during the 2026-05-26 migration. Slated for removal in a follow-up PR after 1 week of skill-only usage.`
- `.claude/agents/reporter.md` → same pattern, pointing to `.claude/skills/reporter-inline/`.
- `.claude/agents/git-publisher.md` → no marker (kept indefinitely for edge cases).

Cost analysis: keeping the two agent files adds ~150 tokens to system prompt. Cost of premature deletion if a skill has a gap: blocked workflow mid-session, no graceful fallback, recovery requires writing the agent back from git history. Defer-and-validate wins.

### 3. Reporter behavior 9-step checklist (High)

Before writing `reporter-inline/SKILL.md`, enumerate every behavior from `.claude/agents/reporter.md` that must survive:

| # | Behavior | Survives in skill? |
|---|---|---|
| Step 1 | Gather git info (last commit SHA, branch, KST timestamp) | ✓ |
| Step 2 | Task.md `## Done` prepend with new entry | ✓ |
| Step 2a | Deferred-item surfacing — `Deferred:` line in Done → new `#### <SLUG>` in `## Next ### MEDIUM` (default) | ✓ |
| Step 3a | `docs/algorithm.md` Hyperparameter Production Value sync (conditional) | ✓ |
| Step 3b | `_(Updated YYYY-MM-DD <sha_short>: ...)_` inline annotation (conditional) | ✓ |
| Step 3c | `**Last Synced (Reporter):** YYYY-MM-DD <sha_short>` top-of-file line (conditional) | ✓ |
| Step 3d | Hard limits — no theory rewrite, no new sections, no other `docs/` files | ✓ |
| Step 4a | `meta.head`, `meta.updatedAt`, `meta.branch` bump | ✓ (head = previous develop HEAD; updatedAt = KST now; branch = current feature branch) |
| Step 4b | `done[]` prepend (most recent 5-8 dated groups from Task.md) | ✓ |
| Step 4c | `now[]` mirror from Task.md `## Now` | ✓ |
| Step 4d | `next` priority-bucketed object (HIGH / MEDIUM / LOW) | ✓ |
| Step 4e | `prs[]` 8-entry window from `gh pr list --base develop --state merged --limit 8` | ✓ MODIFIED — also prepend in-flight PR with `mergedAt: null` (advisor #1) |
| Step 4f | `agents[]` from `.claude/agents/*.md` frontmatter | ✓ — and now includes deprecated marker if present |
| Step 4g | Mermaid bodies (`systemFlow` / `recommendationFlow` / `agentFlow`) — preserve verbatim + stale-flag comment | ✓ |
| Step 4h | `milestones[]` — preserve verbatim | ✓ |
| Step 4i | Write file with stable structure | ✓ |

After writing skill, verify each row is addressed.

### 4. Publish-gate precondition in skill body (Medium)

`git-publish/SKILL.md` Step 0 (entry precondition):

```
Step 0 — Publish gate (HARD precondition)
  Before any push/PR/merge action, verify ONE of:
  (a) The most recent user message contains an explicit publish keyword:
      Korean: 올려, 푸시, 배포, merge, PR 만들어, 배포해, deploy
      English: push, open PR, merge, deploy, ship
  (b) An active `.claude/plans/<slug>.md` file in scope authorizes the action.
  
  If NEITHER condition holds, STOP and surface to user: "Commit ready at <sha>. Publish gate not opened — explicit trigger needed." Do NOT proceed to step 1.
  
  Reason: prevent premature push (PR #105 / #116 / #117 incident pattern).
```

This was the most-violated rule in past sessions; codifying it in the skill body removes "main session remembers" failure mode.

---

## Discriminating test (advisor)

Does `reporter-inline` produce a state.js diff that, compared to what current `reporter` agent would produce post-merge, differs ONLY in:
- (a) SHA placeholder fields (`mergedAt: null` vs real timestamp)
- (b) Freshest-PR inclusion (in-flight entry prepended)

Other deltas (Mermaid changes, milestone changes, Task.md formatting) must be ZERO.

**Test fixture**: PR #121 reporter pass — `e36648b` commit. Mentally dry-run `reporter-inline` skill against the same input state. Compare expected diff.

---

## Skills to create

### 1. `.claude/skills/reporter-inline/SKILL.md`

**Trigger**: main session before push, after final code commit on a feature branch. Runs inline as part of the feature PR (not a separate PR).

**Scope**:
- Update `Task.md` `## Done` (prepend new entry with ID + title + body + PR #).
- Update `project/state.js`:
  - `done[]` prepend new entry
  - `prs[]` prepend new PR (sha field `null` or feature branch SHA — post-squash backfill happens at next reporter pass or daily batch)
  - `meta.updatedAt` bump KST
  - `meta.head` left at the previous develop SHA (not feature branch SHA) until next sync; or feature branch SHA marked stale.
- Conditional `docs/algorithm.md` sync (preserve agent step 3 rules).

**Differences from current reporter agent**:
- Runs in main session context (no Agent dispatch).
- SHA in audit entries uses feature branch tip SHA (pre-squash). Annotated as `<sha-pre-squash>` to flag potential drift.
- No commit/push — just file writes. The next git-commit skill picks them up into the feature commit.

**Guards**:
- Must be on `feature/*` branch (not main/develop).
- Must not duplicate an existing `## Done` entry (read first, prepend only).
- Preserve `state.js` Mermaid bodies + milestones verbatim.

---

### 2. `.claude/skills/git-commit/SKILL.md`

**Trigger**: after a coherent change is ready to commit on a feature branch.

**Scope**:
- Verify branch (`feature/*`, not main/develop).
- Stage with secret exclusions (`.env`, `.key`, `.pem`, `credentials.*`, etc.).
- Write caveman conventional-commit message.
- Run `git commit` with HEREDOC + `Co-Authored-By` trailer.

**Guards** (HARD RULE 4 mirror):
- Never `--no-verify`, `--amend`, `--force`, `git rebase -i`, `git reset --hard`.
- Abort if on main/develop.
- Abort if `.env` / secrets in staging.

**Output**: report SHA + branch + files-changed count.

---

### 3. `.claude/skills/git-publish/SKILL.md`

**Trigger**: main session, after explicit publish keyword from user (`push`, `올려`, `PR`, `배포`, etc.) AND a commit exists on a feature branch.

**Scope (Mode 2 — feature → develop, the 80% case)**:
1. Drift check (`git fetch origin develop && git log HEAD..origin/develop` empty).
2. Push (`git push -u origin feature/...`).
3. PR open (`gh pr create --base develop --title ... --body ...`).
4. Admin squash merge (`gh pr merge <#> --admin --squash --delete-branch`).
5. Local cleanup (`git checkout develop && git pull && git branch -D feature/...`).

**Guards** (HARD RULE 4 + 5 mirror):
- PR base = `develop` (Mode 2). For `main` base, escalate to git-publisher agent (Mode 3 deploy or carve-out).
- Never `git push origin develop` / `git push origin main` directly.
- Never `--force` / `--force-with-lease` on a shared branch (carve-out: post-deploy develop force-reset → escalate to git-publisher agent's Mode 3).
- Publish gate: require explicit user trigger or active deploy plan (per `[[feedback_publish_gate]]`).

**Escalate to git-publisher agent for**:
- External collaborator PR triage.
- Deploy mode (`develop → main` batch + post-deploy force-reset).
- Rebase conflicts requiring multi-step recovery.
- Failed push needing force-with-lease + retry decision.

**Output**: PR number + squash SHA + final local state.

---

## Agents

| Agent | Action |
|---|---|
| `git-manager` | DELETE — fully absorbed by `git-commit` skill |
| `reporter` | DELETE — fully absorbed by `reporter-inline` skill |
| `git-publisher` | KEEP — used for edge case escalation only; default workflow is `git-publish` skill |
| `back-maker`, `front-maker`, `code-review`, `security-manager`, `app-test` | KEEP — agents remain primary (isolated context still valuable) |

---

## CLAUDE.md updates

Add `## Git Operations — HARD RULE` block:

```markdown
## Git Operations — HARD RULE

- Default git ops (commit / push / PR open / squash merge) → use the appropriate skill (`git-commit`, `git-publish`), executed by the main session. Do NOT dispatch `git-manager` or a generic agent for routine ops.
- Audit recording (Task.md `## Done` + state.js + conditional algorithm.md) → use `reporter-inline` skill BEFORE the publish step, in the same feature PR. Reporter no longer ships a separate PR.
- Edge cases that escalate to `git-publisher` agent: external collaborator PR triage; `develop → main` deploy mode (multi-PR batch + post-deploy force-reset); rebase conflicts; failed push requiring force-with-lease decisions.
- Forbidden: ad-hoc `git push origin develop` / `git push origin main`; raw `gh pr create --base main` outside Mode 3 deploy.
- Skill guards mirror the existing HARD RULE 1-4 (branch protection, force/no-verify/history-rewrite prohibition) — see each `.claude/skills/<skill>/SKILL.md`.
```

Also remove obsolete agent references in CLAUDE.md `## Workflow` section.

---

## .claude/WORKFLOW.md updates

- Update Mermaid diagram: 3-agent chain → main-session-direct + skill labels.
- Update text section enumerating sub-agents to mark `git-manager` and `reporter` as `(deprecated — see skills/...)`.
- Add new section `## Skills` enumerating the three new skills + when each fires.

---

## MEMORY.md feedback updates

- Update `feedback_orchestrator.md`: direct/skill/agent matrix — sub-MINOR + git ops + reporter all go through skills now.
- Add new memory `feedback_workflow_skill_absorption.md`:
  - Background (why migration)
  - Skills + when to use
  - Agents still used + when to escalate
  - Codified 2026-05-26 PR # to be filled.

---

## Validation in this session

1. Apply all changes (skill files + agent deletions + doc updates).
2. Process PR #118 + #120 reporter housekeeping using `reporter-inline` skill + `git-commit` skill + `git-publish` skill — main session executes directly, no agent dispatch.
3. If skill execution surfaces a gap (missing guard, ambiguous step), fix the skill and continue.
4. Commit all changes (workflow rewrite + reporter housekeeping) on a single feature branch.
5. Push + admin squash → develop.

---

## Branch + PR plan

- Branch: `feature/admin-workflow-skill-absorption`
- Base: `develop` (currently `8f90104`)
- Commits expected:
  1. New skill files + agent file deletions + CLAUDE.md/WORKFLOW.md/MEMORY updates (workflow rewrite).
  2. (validation) Reporter-inline audit for PR #118 + #120 (Task.md + state.js).
  3. Possibly: small fix-ups if skill execution exposed gaps.
- Squash-merge to develop via admin bypass.

---

## Risks + mitigations

- **Skill command sequence wrong** → main session executes destructive command. Mitigation: each step explicitly documented + dual-write of HARD RULE in CLAUDE.md.
- **SHA staleness in audit entries** → dashboard shows pre-squash SHA briefly. Mitigation: documented limitation; daily batch / next-PR backfill.
- **Agent file deletion irreversible in this commit** → if a future case proves the skill insufficient, restoration requires git revert. Mitigation: git-publisher kept for edge cases.
- **CLAUDE.md not auto-loaded for old conversations** → existing in-flight sessions might keep dispatching deleted agents. Mitigation: this is a one-shot migration; restart sessions after merge.

---

## Out of scope

- Renaming or restructuring `orchestrate` skill — it stays as-is (it already dispatches the kept agents).
- Changing `app-test`, `code-review`, `security-manager` workflows — they continue as agents because they're isolated-context valuable.
- `develop → main` deploy mode itself — git-publisher Mode 3 stays in agent (rare + complex).
