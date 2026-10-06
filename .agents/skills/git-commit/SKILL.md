---
name: git-commit
description: Stage + commit one coherent change on a feature branch with secret exclusions and a conventional-commit message. Codex pointer to the shared procedure in .claude/skills/git-commit/SKILL.md.
---

# git-commit (Codex pointer)

The procedure is tool-agnostic and maintained once. **Read and follow
`.claude/skills/git-commit/SKILL.md`** with these translations:

- "the main session" = this Codex session; nothing is dispatched.
- Hard rules it mirrors are `AGENTS.md` § Branch model (HARD RULES 1–4).
- The commit trailer: use the Codex trailer your session is configured with
  (replace the `Co-Authored-By: Claude …` line); keep the conventional-commit
  prefix exact.
- Escalation targets named there (`git-publisher` agent) exist for Codex as
  `.codex/agents/git-publisher.toml` — spawn it only for the edge cases listed.

Never push from this skill. Publishing is `git-publish` and needs the trigger
words in `AGENTS.md` § Working and publishing.
