---
name: git-publish
description: "Push a feature branch, open a PR against develop, admin-squash-merge it, clean up. Main session runs this directly (no Agent dispatch); supersedes `git-publisher` agent's Mode 2 (the 80% case). Escalates to git-publisher agent for: develop→main deploy mode, external collaborator PR triage, complex rebase/force conflicts."
---

# git-publish — feature → develop, main-session-direct

Use this skill when a feature branch has committed work ready to ship to `develop`. The main session executes the steps below itself. **Do NOT dispatch `git-publisher` agent for routine Mode-2 (feature → develop) squash merges** — that agent is reserved for edge cases as of 2026-05-26.

## Hard rules (mirror AGENTS.md HARD RULE 1, 3, 4, 5)

1. **PR base is `develop` only.** Mode 3 (`develop → main` deploy) is git-publisher agent's job.
2. **Never `git push origin develop` / `git push origin main` directly.** Pushes go from `feature/*` only.
3. **Never `--force` / `--force-with-lease` on a shared branch.** Single carve-out (post-deploy `develop` force-reset) is git-publisher Mode 3; this skill never does it.
4. **No `--no-verify` on the push.** Pre-push hooks must run.
5. **Publish gate (Step 0) is a HARD precondition.** Do not skip.

---

## Step 0 — Publish gate (HARD precondition)

Before any push / PR / merge action, verify ONE of:

(a) **Explicit publish keyword** in the most recent user message. Keywords:
   - Korean: `올려`, `푸시`, `배포`, `merge`, `PR 만들어`, `배포해`, `deploy`, `ship`
   - English: `push`, `open PR`, `merge`, `deploy`, `ship`

(b) **Active `.codex/plans/<slug>.md`** in scope that authorizes the publish action explicitly.

If NEITHER condition holds, **STOP** and surface to user:

```
git-publish: PUBLISH GATE NOT OPENED
Commit ready at <sha>. Explicit publish trigger needed before push/PR/merge.
Trigger words: push, 올려, PR, 배포, merge, deploy, ship.
```

Do NOT proceed to Step 1. Reason: prevents premature push (PR #105 / #116 / #117 incident pattern).

---

## Step 1 — Pre-push drift check

```bash
git fetch origin develop
git log --oneline HEAD..origin/develop
```

If the second command returns any commits, the feature branch is behind `develop`. Decision:
- **Light drift** (< 5 commits, no overlap with PR's files): proceed but note in PR body.
- **Heavy drift / overlap**: STOP. Either rebase onto `origin/develop` first (only if branch is unpushed or owned solely by this session) or escalate to `git-publisher` agent.
- **Rebase on a pushed branch**: requires `--force-with-lease`, which means escalate to `git-publisher` agent (it knows how to handle the lease retry safely).

```bash
git log --oneline -3
git status
```

Verify:
- On `feature/<role>-<topic>` branch.
- Working tree clean.
- HEAD has the commits to ship.

---

## Step 2 — Push to remote

```bash
git push -u origin feature/<branch-name>
```

If push fails:
- **Branch protection rejection** (shouldn't happen on `feature/*` but possible if branch name pattern is wrong): check branch name. Rename if needed (`git branch -m <new>`), re-push.
- **Non-fast-forward**: someone else pushed to the same feature branch (rare — usually solo). Escalate to `git-publisher` agent.

---

## Step 3 — Open PR (base=develop)

```bash
gh pr create \
  --base develop \
  --head feature/<branch-name> \
  --title "<caveman conventional-commit-style title>" \
  --body "$(cat <<'EOF'
## Summary
<1-3 caveman bullets — what changed and why>

## Changes
- <file>: <what>
- <file>: <what>

## Test plan
- [x] `cd backend && pytest -x` (or skip note if frontend-only)
- [x] `cd frontend && npm run lint && npm run build`
- [x] code-review PASS
- [x] security PASS
- [ ] Manual smoke (admin)

## Risk zone
- [ ] None (UI logic only / data migration / auth / external API — pick what applies)

EOF
)"
```

Title: caveman conventional-commit style. Body: caveman compressed, technical substance kept. Include codex review fixes (if any) in a `## Codex review fixes` block.

**Forbidden**: `--base main` (Mode 3 territory). If a `main`-base PR is needed (e.g. post-deploy revert), escalate to `git-publisher` agent.

---

## Step 4 — Admin squash-merge

Sole-admin CODEOWNERS = PR author means Code Owner review is structurally unsatisfiable. Admin-bypass squash merge per AGENTS.md `## Branch Model`:

```bash
gh pr merge <PR_NUMBER> --admin --squash --delete-branch
```

This:
- Squashes all commits on the feature branch into a single squash commit on `develop`.
- Deletes the remote feature branch (`--delete-branch`).

Verify the merge:
```bash
git fetch origin develop
git log --oneline -3 origin/develop
```

The top commit should be the squash, with message `<PR title> (#<PR_NUMBER>)`.

---

## Step 5 — Post-merge local cleanup

```bash
git checkout develop
git pull origin develop
git branch -D feature/<branch-name> 2>/dev/null || true
```

Verify final state:
```bash
git branch --show-current   # should be 'develop'
git rev-parse --short HEAD  # should match the squash commit
```

---

## Step 6 — Report

After successful merge + cleanup:

```
GIT-PUBLISH: MERGED
PR: #<NUMBER>
URL: https://github.com/hongikarchi/archi-tinder/pull/<NUMBER>
Squash SHA: <first 7 chars on develop>
Branch deleted: remote ✓ + local ✓
Current local: develop @ <SHA>
```

Then STOP. Do NOT trigger `develop → main` deploy. That's `git-publisher` Mode 3, a separate decision requiring explicit deploy keyword + multi-PR batching.

---

## When to escalate to git-publisher agent

Routine Mode-2 squash merges run in this skill. Escalate to `git-publisher` agent for:

1. **Mode 3 — `develop → main` deploy**: multi-PR batch + admin squash + post-deploy `develop` force-reset to match `main`. Requires explicit deploy keyword AND HARD RULE 4 carve-out citation.

2. **External collaborator PR triage**: a PR from someone other than admin needs review + decision. Different workflow (CODEOWNERS, possibly different merge strategy).

3. **Rebase failure or force-with-lease retries**: complex history surgery beyond this skill's linear flow.

4. **Push rejection with unclear cause**: any push failure that isn't a simple wrong-branch or fast-forward issue.

5. **Mid-merge failure**: if `gh pr merge --admin --squash` fails with a non-trivial error (e.g. CODEOWNERS misconfiguration, status-check pending despite none configured), escalate rather than retry with destructive workarounds.

Dispatch shape:
```json
{
  "agent_type": "git-publisher",
  "message": "Escalation from git-publish skill. <precise problem description + current branch state>."
}
```

---

## Related skills
- `reporter-inline` — runs BEFORE this skill so the audit ships in the same PR.
- `git-commit` — runs to create the commit(s) that this skill then publishes.
