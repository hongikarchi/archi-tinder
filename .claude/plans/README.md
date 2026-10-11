# .claude/plans — execution plans (active only)

Two kinds of plan documents exist in this repo; keep them apart:

| | `.claude/plans/*.md` (this folder) | `docs/decisions/*.md` |
|---|---|---|
| What | **Execution plans**: branches, PR sequence, delegation, acceptance checks | **Design decision records**: problem, options, decision, open items |
| Language | English (Korean summary block) | Korean |
| Lifecycle | active while the work is in flight → `archive/` when every task is RESOLVED in `Task.md` / closed in Issues | permanent; a superseded record says so in its status line |
| Publish-gate meaning | an active plan that explicitly authorizes publishing opens the `git-publish` gate (`AGENTS.md` § Working and publishing) | none |

Rules for this folder:

1. **Active only.** When a plan's work ships, move the file into `archive/` in the same PR
   as the audit. A resolved plan left here can be mistaken for a live publish authorization.
2. Before archiving, rename any `## PR Plan` heading to `## Historical PR Plan` and add a
   one-line `**Status:** SHIPPED (PR #…)` at the top.
3. **Code comments may cite a plan** (`.claude/plans/<name>.md §N`). Section numbers are
   frozen once cited. When you archive the plan, retarget those comments to
   `.claude/plans/archive/<name>.md` in the same commit (`git grep` the old path = 0).
4. Session plan-mode drafts live in `~/.claude/plans/` (outside the repo) until approved;
   copy an approved plan here only if other sessions must read it.

`archive/` = historical record, never executed; references inside may name removed
agents, files or branches.
