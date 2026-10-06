---
name: git-publish
description: Push a feature branch, open a PR against develop, admin-squash-merge, clean up. Codex pointer to the shared procedure in .claude/skills/git-publish/SKILL.md; publish gate per AGENTS.md.
---

# git-publish (Codex pointer)

**Read and follow `.claude/skills/git-publish/SKILL.md`** — steps 0–6 are plain
`git` / `gh` commands and apply unchanged. Translations:

- Step 0 publish gate: the trigger words are in `AGENTS.md` § Working and
  publishing (the only list). An approved plan file that explicitly authorizes
  publishing also opens the gate. No trigger → STOP and report the ready commit.
- PR base is `develop` only. A `develop → main` deploy PR needs a deploy keyword and
  goes through the `git-publisher` agent (`.codex/agents/git-publisher.toml`) with
  the operator runbook `docs/runbooks/deploy.md`.
- "Escalate to the `git-publisher` agent" = spawn `git-publisher` with a precise
  problem description (edge cases only: deploy PR, external collaborator PR triage,
  complex rebase, push rejection with unclear cause, mid-merge failure).
- PR body trailer: use the Codex attribution line your session is configured with.

The Codex hook `.codex/hooks.json` + `.codex/rules/git.rules` block direct or
forced pushes to `develop`/`main` and `gh pr create --base main` at the tool layer.
