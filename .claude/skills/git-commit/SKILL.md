---
name: git-commit
description: Stage + commit a single coherent change on a feature branch. Caveman-style conventional commit, secrets excluded, no force/amend/no-verify. Main session runs this directly (no Agent dispatch); supersedes the `git-manager` agent for routine commits. Edge cases (rebase conflicts, multi-commit reorganization) still escalate to git-publisher agent.
---

# git-commit — single commit, main-session-direct

Use this skill when a coherent change is ready to commit on a feature branch. The main session executes the steps below itself. (The `git-manager` agent was removed 2026-05-31 — this skill replaces it.)

## Hard rules (mirror CLAUDE.md HARD RULE 4)

1. **Never commit on `main` or `develop`.** Run `git status` first. If on a protected branch, abort and tell the user to switch to `feature/<role>-<topic>`.
2. **Never push.** No `git push`, no `gh pr create`. That's `git-publish` skill's job.
3. **One commit per invocation.** Never split into multiple commits. If the change is too large for one commit, ask the user to scope down (or invoke this skill twice for two coherent slices).
4. **Never use `--no-verify`, `--amend`, `--force`, or any history-rewriting flag.** Pre-commit hooks must run. If a hook fails, fix the root cause; never bypass.

## Steps

### Step 1 — Branch verification

```bash
git status
git branch --show-current
```

Decision tree:
- On `feature/*` branch → proceed to Step 2.
- On `main` or `develop` → **ABORT**. Report `GIT-COMMIT-BLOCKED: on <branch> — switch to feature/* first`. Do NOT proceed.
- On any other branch name → ABORT. Same reason.

### Step 2 — Stage with secret exclusions

```bash
git add --all -- \
  ':(exclude).env' \
  ':(exclude).env.*' \
  ':(exclude)__pycache__/*' \
  ':(exclude)*.pyc' \
  ':(exclude)*.key' \
  ':(exclude)*.pem' \
  ':(exclude)credentials.*' \
  ':(exclude)secrets/*'
```

### Step 3 — Verify staging

```bash
git diff --cached --stat
```

If any of `.env*`, `*.key`, `*.pem`, `credentials.*`, `secrets/*` appears in the staged set, **ABORT**. Report the leak path and ask the user to clean it up (`git restore --staged <path>` + add to `.gitignore`).

### Step 4 — Compose conventional-commit message (caveman style)

**Subject line** (max 72 chars):
- Format: `<type>(<scope>?): <what changed>`
- Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `security`, `perf`
- Caveman style: drop articles (a/an/the), filler (just/really/basically), pleasantries (Add support for / Implement). Fragments OK. Short synonyms.
- The `<type>(<scope>?):` prefix stays exact — structural for git tooling, not prose.

**Body** (optional, also caveman-terse):
- Why + spec/issue ref. Drop articles. Fragments OK.
- Reference task ID (e.g. `FRONT-UX-4`, `INFRA-DB-1`) if the change closes one.

**Trailer** (required boilerplate, NEVER drop or compress):
```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Adjust the model name to match the actual model the main session is using.

**Examples** (good caveman):
- `feat: add Office.claim_token + claim API per PROF1 §2.3`
- `fix: card title clip — flexShrink:0 on H2, detail panel 72%`
- `chore(INFRA-DOC-7): session-end reporter housekeeping — PR #121 FRONT-UX-2`

**Bad** (too verbose):
- `feat: I added the new Office claim token feature so that users can...` ❌
- `Fixed a bug where the card title was being clipped` ❌

### Step 5 — Commit with HEREDOC

```bash
git commit -m "$(cat <<'EOF'
<subject line>

<body lines, optional>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If the commit fails due to a pre-commit hook:
1. Read the hook output. Identify the root cause (lint error, type error, formatting, migration mismatch, etc.).
2. Fix the root cause in the source file.
3. Re-stage (Step 2).
4. Create a **new** commit (NOT `--amend`). The hook failure means the previous commit didn't happen, so there's nothing to amend.
5. NEVER use `--no-verify` to bypass.

### Step 6 — Report

After successful commit:

```
GIT-COMMIT: COMMITTED
Hash: <first 7 chars>
Message: <subject line>
Files: <count> changed (+<additions> / -<deletions>)
Branch: feature/<...>
```

Then STOP. Do NOT push, do NOT open PR. That's the `git-publish` skill's job (or `git-publisher` agent for edge cases), triggered by an explicit user publish keyword.

## When to escalate to git-publisher agent

If you encounter:
- A failed commit you can't diagnose after one fix attempt.
- A staged set with secrets that you can't cleanly unstage.
- A pre-existing dirty state on a protected branch that needs untangling.

Dispatch `git-publisher` agent with a precise problem description. **Do NOT improvise destructive recovery** (`git reset --hard`, `git checkout .`).

## Related skills
- `reporter-inline` — produces the audit; per the canonical order it runs AFTER `git-publish` opens the PR (so the PR number is known), then THIS skill commits the audit as a separate commit that squashes into the same PR.
- `git-publish` — fires after this skill, on explicit user publish trigger.
