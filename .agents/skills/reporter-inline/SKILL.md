---
name: reporter-inline
description: Record a just-shipped change in Task.md and regenerate the dashboard before publishing, in the same PR as the work. Codex pointer to .claude/skills/reporter-inline/SKILL.md.
---

# reporter-inline (Codex pointer)

**Read and follow `.claude/skills/reporter-inline/SKILL.md`.** Everything in it is
file editing plus one script; nothing is Claude-specific. Key facts so you do not
fall back to the retired procedure:

- `project/state.js` is **generated**: run `node tools/gen-state.js` after editing
  `Task.md`. Never hand-author `state.js` (the pre-2026-06-07 manual procedure is
  retired; it caused `*/` comment-termination corruption).
- `docs/algorithm.md`: only the narrow writes listed in `AGENTS.md` § Data rules
  (dated `_(Updated …)_` one-liners + the "Last verified" line). Values are never
  copied: run `make hyperparams` to regenerate `docs/algorithm-hyperparameters.md`.
- Commit the audit with `git-commit` on the same feature branch so it squashes into
  the same PR; then the publish gate applies (`git-publish`).
- Task tracking is migrating to GitHub Issues; when an Issue exists for the work,
  put `Closes #N` in the PR body instead of (or in addition to) the Task.md entry.
