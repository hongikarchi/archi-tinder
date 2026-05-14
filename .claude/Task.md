# Task Board

> Auto-updated by orchestrator. When you request work, orchestrator reads Goal.md
> + current code, then adds/updates tasks here before executing.
> Categories: Algorithm, Frontend, Backend, Auth, UX/Design, Infrastructure

---

## Handoffs

> Short-lived cross-terminal signals for the **review / push** cycle.
> Each terminal (main / review / git / codex workers) reads this section at session start.
> Oldest entries expire naturally — reporter trims to ~30 most recent on session-end pass.
>
> Lane note (2026-05-13): **lean 3-lane is the default** (WEB-MAIN + 1 Codex worker + WEB-REVIEW + WEB-GIT, set up via `tools/cmux_lean_setup.sh <back|front|both>`). Full 5-tab is opt-in via `tools/cmux_setup.sh` for full-stack concurrent work. Signal vocabulary is identical across both lanes — only the worker baseline path changed (`.claude/codex/<team>-worker.md`, formerly `.claude/agents/team-<team>.md`).
>
> Signal types for this section:
>
> **Review cycle:**
> - `REVIEW-REQUESTED: <sha>` — reporter (main pipeline) → review terminal; run `/review` next (or just say "리뷰해줘" / "review please").
> - `REVIEW-PASSED: <sha>` — review terminal → WEB-GIT; PASS verdict, drift-verified. WEB-GIT runs `git-push-pr.sh`. On `PASS-WITH-MINORS` verdict the signal inlines `<K> MINOR noted (see .claude/reviews/latest.md)`; MINORs are non-blocking.
> - `REVIEW-ABORTED: <sha> — <reason>` — review terminal → main; PASS verdict but drift detected. Re-run after rebase.
> - `REVIEW-FAIL: <sha> — <summary>` — review terminal → main; run fix loop via orchestrator (max 2 cycles).
>
> **Codex team handoffs (WEB-BACK / WEB-FRONT → WEB-MAIN):**
> - `BACK-DONE: <slug>` / `FRONT-DONE: <slug>` — task complete. Append `(claude-review-requested)` for risky-zone work.
> - `BACK-BLOCKED: <reason>` / `FRONT-BLOCKED: <reason>` — codex team escalates after exhausting self-heal (2 cycles).
> - `<TEAM>-NEEDS-CLARIFICATION: <q>` — scope ambiguous; team waits.
>
> **WEB-GIT publish cycle (Internal PR — Mode 1):**
> - `READY-FOR-PUSH: <branch>` — WEB-MAIN → WEB-GIT (alt path for trivial commits skipping `/review`).
> - `BRANCH-CREATED: <branch>` — WEB-GIT created new feature branch from develop (`tools/git-new-feature.sh`).
> - `PR-OPENED: #<N>` — WEB-GIT pushed branch + `gh pr create --base develop`. CI is running.
> - `PR-CI-GREEN: #<N>` / `PR-CI-FAIL: #<N>` — `git-poll-merge.sh` result.
> - `PR-MERGED: #<N>` — squash-merged into develop, branch deleted, local develop synced.
>
> **WEB-GIT external triage (Mode 2 — collaborator PRs):**
> - `PR-READY-FOR-REVIEW: #<N>` — WEB-GIT checked out external PR. Admin manually triggers `/review` per hybrid policy.
> - `PR-CHANGES-REQUESTED: #<N>` — WEB-GIT posted FAIL verdict to PR via `gh pr review --request-changes` (summary + collapsible details body).
> - `PR-CONFLICT: #<N>` — external PR conflicts with develop; WEB-GIT commented asking author to rebase.
>
> **WEB-GIT deploy (Mode 3 — develop → main):**
> - `DEPLOY-PR-OPENED: #<N>` — develop → main PR opened with batch summary.
> - `DEPLOY-MERGED: #<N>` — admin merged; Railway auto-deploy started.
>
> **WEB-GIT refusals / specials:**
> - `GIT-PUBLISH-BLOCKED: <reason>` — refusal (e.g. wrong branch, ruleset violation).
> - `GIT-PUBLISH-RETRY: <branch>` — rebase performed, new sha; re-run `/review` against new sha.
> - `GIT-PUBLISH-NOOP: <reason>` — nothing to do (e.g. develop = main on deploy).
>
> **Session-spanning TODOs:**
> - `SESSION-START-TODO: <action>` — explicit pending action for the *next* session's first move (e.g. "run `./tools/cmux_setup.sh`"). Surfaced automatically by the SESSION_PROTOCOL.md § 2 checklist on next session start.

<!-- Append new handoff entries here. Format: `- [YYYY-MM-DD] <SIGNAL>` -->

- [2026-05-11] PR-OPENED: #15 — feature/admin-git-publisher-deploy-recovery → develop, 1 commits (3ac7622 "docs(git-publisher): Bug #4 — gh pr merge --delete-branch flag regression + safe recovery"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/15. Diff: +38/-2, 2 files. **Bug #4 fix (meta-bug, docs only)**: `.claude/agents/git-publisher.md` Mode 3 step 5 expanded to document the `gh pr merge --delete-branch=false` regression empirically observed during PR #11 deploy (gh CLI ignored the false flag under `--admin`, auto-deleted origin/develop). Two recovery paths now codified: (A) **preferred** — merge via `gh api PUT pulls/N/merge` directly (REST endpoint doesn't touch source branches, sidesteps the gh CLI flag bug entirely); (B) fallback — `gh pr merge --admin` + verify-and-recover via `gh api POST git/refs` if origin/develop vanishes post-merge. Pre-emptive Task.md stash pattern from PR #12-#14 dogfood also captured. Docs only, no tools/scripts changed. /review skipped per CLAUDE.md Rule 2. Polling CI in background (task `bmhepjzz8`). **Meta-note**: when I merge this PR, I get to dogfood the new safer recovery instructions documented in step 5 — using path (A) `gh api PUT pulls/15/merge` would test it on the very PR introducing the doc, but PR #15 targets develop (not main), so develop's branch-protection allows squash via standard `gh pr merge` and the develop-delete scenario doesn't apply here — actual dogfood of the new step 5 recovery will happen at the next develop→main deploy PR.
- [2026-05-11] PR-CI-GREEN: #15 — Backend pytest + migrations 2m4s, Frontend 15s, Vercel + comments all SUCCESS.
- [2026-05-11] PR-MERGED: #15 — squashed into develop (9d52efb) via `gh pr merge 15 --squash --delete-branch --admin` (B+ ruleset bypass). Pre-emptive stash applied → merge → fetch-prune → stash pop, all clean (PR #12-#14 dogfood pattern still load-bearing). Local develop fast-forwarded `c200e23..9d52efb` (2 files, +38/-2: `.claude/agents/git-publisher.md` +35, `.claude/Task.md` +3 handoffs sweep). Remote feature branch + stale ref pruned. **Bug #4 closed.** Net effect: `.claude/agents/git-publisher.md` Mode 3 step 5 now documents the `gh pr merge --delete-branch=false` regression empirically observed at PR #11 deploy + two recovery paths: (A) preferred `gh api PUT pulls/N/merge` (REST endpoint doesn't touch source branches; sidesteps the gh CLI bug); (B) fallback `gh pr merge --admin` + verify-and-recover via `gh api POST git/refs` if origin/develop vanishes. Pre-emptive Task.md stash pattern also codified. **Dogfood deferred** to next develop→main deploy PR (PR #15 targets develop, so develop-auto-delete scenario didn't apply here).
- [2026-05-11] DEPLOY-PR-OPENED: #16 — develop → main, 4 new PRs (#12-#15) since last deploy `78e4548`, Railway will auto-deploy on merge. URL: https://github.com/hongikarchi/archi-tinder/pull/16. Title: "Deploy: PR #12-#15 (workflow bug fixes from dogfood postmortem)". Range: develop@9d52efb vs main@78e4548. GitHub UI will show 12 commits on this PR (develop preserved 8-PR unsquashed history from PR #3-#10 alongside the new 4) — the actual tree diff is only the 4 new PRs since the first 8's tree changes are already in main via 78e4548 squash. All 4 underlying PRs CI was green pre-merge. **Will dogfood new Mode 3 step 5 Option A**: `gh api PUT repos/hongikarchi/archi-tinder/pulls/16/merge --field merge_method=squash` (sidesteps the `gh pr merge --delete-branch=false` regression that ate origin/develop at the prior deploy PR #11). Post-merge will `git ls-remote origin refs/heads/develop` to verify survival; if it vanishes, recover per Option B (`gh api POST git/refs`). Polling deploy CI in background (task `bmhe7eoh5`); on green will dogfood Option A merge.
- [2026-05-11] PR-CI-GREEN: #16 — Backend pytest + migrations 2m13s, Frontend 11s, Vercel + comments all SUCCESS. But:
- [2026-05-11] GIT-PUBLISH-BLOCKED: deploy PR #16 — Option A merge (`gh api PUT pulls/16/merge --field merge_method=squash`) returned `HTTP 405: Pull Request has merge conflicts`. Verified via `gh pr view 16 --json mergeable,mergeStateStatus`: `mergeable=CONFLICTING, mergeStateStatus=DIRTY`. **Root cause** (the unforeseen consequence of the PR #11 deploy's develop-recovery choice): after PR #11 squashed PR #3-#10 into main commit `78e4548` AND admin recreated origin/develop preserving the 8-PR unsquashed history (Option A from the prior GIT-PUBLISH-BLOCKED handoff), develop and main now have divergent histories that BOTH modify the same files. Specifically, `git diff --name-only origin/main origin/develop` shows: `.claude/Task.md`, `.claude/agents/git-publisher.md`, `.claude/postmortems/2026-05-11-workflow-dogfood.md`, `backend/conftest.py`, `tools/dispatch.sh`, `tools/git-new-feature.sh`, `tools/test-backend.sh` — these are touched by BOTH the PR #3-#10 squash on main AND the PR #12-#15 commits on develop. The 3-way merge (merge-base `a1c235c`, head develop@9d52efb, base main@78e4548) can't reconcile the line-arrangements even though the resulting trees would be functionally identical. **Recovery options** (admin decision required — I will NOT force-push develop):
  - **(i) FORWARD-FIX (clean, recommended)**: admin resets origin/develop to origin/main (`git push origin +78e4548:develop` or equivalent force-update by admin via GitHub UI / `gh api PATCH`), then cherry-picks PR #12-#15's 4 commits onto the new develop and force-pushes. This loses the unsquashed PR #3-#10 history on develop but unblocks the deploy + establishes the trunk-based pattern for future deploys (every deploy resets develop = main + replays new work). Going forward this matches the standard GitHub-Flow-with-develop pattern where develop is the integration branch synced to main after each release.
  - **(ii) MANUAL MERGE RESOLUTION**: admin creates `feature/admin-resolve-deploy-16` from main, merges develop in (`git merge --squash origin/develop`), resolves conflicts manually (mostly .claude/Task.md handoff append-order + duplicate handoffs from both deploys), opens a NEW deploy PR. PR #16 closed as superseded. Preserves develop's history but adds one extra PR cycle.
  - **(iii) RULESET ADJUSTMENT**: admin temporarily allows merge-commit on main, retries PR #16 with `--merge` (preserves both histories as a true merge), re-tightens ruleset. Avoids the squash-conflict path entirely. Confirmed earlier that repo only allows squash currently (`mergeCommitAllowed=false, rebaseMergeAllowed=false`).
  - PR #16 stays open until admin chooses; develop is unchanged so future feature work on develop can continue (it just can't deploy until the divergence is resolved).
  - **Lesson for the postmortem follow-up**: my prior recommendation of recovery Option (A) at PR #11 (preserve 8-PR history on develop) was load-bearing-but-wrong — option (B) (reset develop = main) would have prevented this divergence. Adding this to PR #15's Mode 3 step 5 doc would close Bug #5 / the meta-meta-bug.
- [2026-05-11] PR-OPENED: #17 — feature/admin-bug-5-post-deploy-sync → develop, 1 commits (4fcc100 "docs(git-publisher): Bug #5 — post-deploy develop=main reset (squash deploy divergence fix)"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/17. Diff: +64/-0, 3 files (pure docs additions). **Bug #5 fix (meta-meta-bug, docs only)**: `.claude/agents/git-publisher.md` Mode 3 step 5 augmented with mandatory post-deploy `gh api PATCH refs/heads/develop --field force=true` to force-reset origin/develop to match origin/main after every squash deploy. Without this step, every squash deploy after the first hits the graph-divergence merge conflict observed at PR #16. Postmortem (`.claude/postmortems/2026-05-11-workflow-dogfood.md`) updated with Bug #5 entry + the specific recovery procedure for the currently-blocked PR #12-#15 deploy (option (i) forward-fix from prior GIT-PUBLISH-BLOCKED handoff). Docs only — zero tool/script/runtime changes. /review skipped per CLAUDE.md Rule 2. Polling CI in background (task `buf0udm1t`); on green, will pre-emptively stash Task.md + merge via standard `gh pr merge 17 --squash --delete-branch --admin` (pattern from PR #12-#14). **Note**: PR #17 targets develop (not main), so Bug #4 / Bug #5 scenarios don't apply on this merge itself — develop accepts squash merges normally regardless of main-develop divergence (the divergence only blocks develop→main deploy PRs, not feature→develop PRs). The blocked deploy PR #16 stays separately open; admin will resolve via (i)/(ii)/(iii) after this PR documents Bug #5.
- [2026-05-11] PR-CI-GREEN: #17 — Backend pytest + migrations 2m6s, Frontend 10s, Vercel + comments all SUCCESS.
- [2026-05-11] PR-MERGED: #17 — squashed into develop (b597b30) via `gh pr merge 17 --squash --delete-branch --admin` (B+ ruleset bypass). Standard stash+squash pattern (validated PR #12-#15). Local develop fast-forwarded `9d52efb..b597b30` (3 files, +64/-0: git-publisher.md +18, workflow-dogfood postmortem +35, Task.md +11). Remote feature branch + stale ref pruned; stash popped cleanly. **Bug #5 closed.** Net effect: Mode 3 step 5 now mandates post-deploy `gh api PATCH refs/heads/develop --field force=true` to force-reset origin/develop = origin/main, preventing the graph-divergence merge conflict observed at PR #16. **Note**: PR #16 (the blocked deploy of PR #12-#15) remains separately open; admin must still resolve via (i)/(ii)/(iii) from the prior GIT-PUBLISH-BLOCKED entry. The new doc in PR #17 prescribes (i) "forward-fix" as the canonical recovery + makes "develop = main after each deploy" the standing rule going forward. PR #17 itself merged successfully because it targets develop (not main), so the divergence didn't block it.


- [2026-05-11] DEPLOY-RECOVERY-COMPLETE: develop force-reset to main (c231c59) via gh api PATCH. Bug #5 recovery executed. All 5 bug fixes from workflow dogfood (postmortem 2026-05-11) are live on main. No divergence remaining.
- [2026-05-11] REVIEW-REQUESTED: c231c59 — docs(reporter): post-PR#18 sync — 5 bug fixes live (dispatch.sh, git-new-feature.sh, conftest.py, test-backend.sh, git-publisher.md) + Bug #5 recovery complete (develop=main reset codified in git-publisher.md Mode 3 step 5)
- [2026-05-11] PR-OPENED: #19 — feature/admin-reporter-sync → develop, 1 commits (a351d52 "docs(reporter): post-PR#18 sync — 5 bug fixes live + Bug #5 recovery complete"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/19. Diff: +58/-60, 3 files (pure reporter-sync doc updates). /review skipped per CLAUDE.md Rule 2 (docs only). Polling CI in background (task `buzzwu78w`); on green, will dogfood **Option A merge** (`gh api -X PUT pulls/19/merge --field merge_method=squash`) per user instruction + Bug #4 codified rule, even though Mode 1 (feature→develop) doesn't strictly need it (Bug #4 regression manifests only on Mode 3 deploys where develop is the SOURCE). Post-merge manual cleanup needed: delete remote feature branch via `gh api -X DELETE`, sync local develop, delete local feature branch, prune. PR targets develop (not main) → Bug #5 develop=main reset NOT needed after this merge. NOTE: PR numbering jumped #17 → #19, indicating PR #18 was the admin's out-of-band Bug #5 recovery deploy (which landed PR #12-#15 + Bug #5 doc onto main as `c231c59`) — no longer pending here.
- [2026-05-11] PR-CI-GREEN: #19 — Backend pytest + migrations 2m9s, Frontend 14s, Vercel + comments all SUCCESS.
- [2026-05-11] PR-MERGED: #19 — squashed into develop (cc18fb9) via **`gh api -X PUT pulls/19/merge --field merge_method=squash`** (Option A dogfood per Bug #4 codified rule). REST endpoint returned `{"sha":"cc18fb9...","merged":true,"message":"Pull Request successfully merged"}` in one HTTP call. **Empirical findings vs documentation**: (1) ✓ origin/develop SURVIVED (verified via `git ls-remote origin refs/heads/develop` = cc18fb9) — Option A's main promise holds. (2) ⚠️ remote feature branch was AUTO-DELETED anyway — the repo's "Automatically delete head branches" GitHub setting fires on every merge regardless of API path (gh api PUT vs gh pr merge --delete-branch). My anticipated `gh api -X DELETE refs/heads/feature/admin-reporter-sync` returned `422 Reference does not exist`. **Doc-update candidate for git-publisher.md Mode 1/Mode 3**: note that the repo's auto-delete-head-branches setting means manual `gh api DELETE` after Option A is unnecessary in practice; just sync local. (3) Option A requires manual local sync since REST endpoint doesn't touch local filesystem: stash → checkout develop → pull → branch -D feature → fetch --prune → stash pop. Total ~5 commands vs `gh pr merge`'s 1, but no checkout-abort risk on dirty Task.md (the irony — Option A actually MORE tolerant of dirty working tree than `gh pr merge --admin`). Local develop fast-forwarded `b597b30..cc18fb9` (3 files, +58/-60: reporter trimmed Task.md handoffs 86→~30, archived 33 entries to handoffs-archive/2026-05.md). Bug #4 Option A path empirically validated; all 6 workflow-dogfood bugs (incl. Bug #5 + the auto-delete-branch annotation candidate) now in main's tree. Standing by.
- [2026-05-11] PR-OPENED: #20 — feature/admin-bug-4-root-cause-fix → develop, 1 commits (5d15840 "docs(bug-4): root cause fix — disable repo delete_branch_on_merge"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/20. Diff: +60/-33, 3 files. **Bug #4 ROOT-CAUSE fix (per PR #19 dogfood discovery)**: PR #19 empirically proved that `gh api PUT pulls/N/merge` (Option A) ALSO auto-deletes the head branch — the root cause was never the gh CLI `--delete-branch=false` flag, it was the repo-level setting `delete_branch_on_merge: true` firing on every merge regardless of API path. Permanent fix already applied to repo settings (verified via `gh api repos/hongikarchi/archi-tinder --jq .delete_branch_on_merge` → false). PR #20 documents the fix in `.claude/agents/git-publisher.md` Mode 1 steps 6-8 (drop `--delete-branch` flag, add explicit `gh api -X DELETE refs/heads/<branch>` step for remote cleanup) + Bug #4 section rewrite. /review skipped per CLAUDE.md Rule 2 (docs only). Polling CI in background (task `bnftsc85i`). **Empirical verification plan after merge**: (a) confirm head branch SURVIVES on origin via `gh api repos/.../branches/feature/admin-bug-4-root-cause-fix --jq .name` (should return branch name, not 404 — empirical proof Bug #4 ROOT cause is fixed); (b) explicit `gh api -X DELETE refs/heads/...` to clean up the surviving branch per new Mode 1 step 7; (c) local sync. PR targets develop (not main) → Bug #5 develop=main reset NOT applicable post-merge.
- [2026-05-11] BUG-4-ROOT-CAUSE-FIXED: PR #19 empirical finding (`gh api PUT` also auto-deletes head branch) revealed that Bug #4's original diagnosis ("`gh pr merge --delete-branch=false` flag ignored") was the symptom, not the cause. Real root cause: GitHub repo-level setting `delete_branch_on_merge: true` which fires on EVERY merge regardless of API path (`gh pr merge`, `gh api PUT`, web UI). Permanent fix applied: `gh api -X PATCH repos/hongikarchi/archi-tinder --field delete_branch_on_merge=false`. Verified `delete_branch_on_merge: False`. Trade-off: feature branches no longer auto-delete on origin → explicit `gh api -X DELETE refs/heads/<branch>` added to git-publisher.md Mode 1 step 7 as canonical cleanup. Deploy PRs (develop→main) now safe with any merge API — `origin/develop` preserved by repo-setting guarantee, no verify-and-recover dance. Bug #4 fully resolved at root cause. git-publisher.md Bug #4 section rewritten + postmortem updated. Working on feature/admin-bug-4-root-cause-fix; will push + PR + merge in this session for end-to-end empirical validation (head branch should survive after merge — this is the dogfood that closes Bug #4).
- [2026-05-11] PR-CI-GREEN: #20 — Backend pytest + migrations 2m9s, Frontend 15s, Vercel + comments all SUCCESS.
- [2026-05-11] PR-MERGED: #20 — squashed into develop (249a8d5) via `gh pr merge 20 --squash --admin` (NO `--delete-branch` flag per new Mode 1 doc — repo setting now handles branch retention). 🎯 **EMPIRICAL PROOF Bug #4 ROOT CAUSE FIX**: immediately after squash merge, `gh api repos/hongikarchi/archi-tinder/branches/feature/admin-bug-4-root-cause-fix --jq .name` returned `"feature/admin-bug-4-root-cause-fix"` (NOT 404) — head branch SURVIVED on origin. This is dispositive proof that the root cause was the repo-level `delete_branch_on_merge: true` setting (now `false`), NOT the gh CLI `--delete-branch=false` flag behavior. Prior Bug #4 diagnosis ("flag ignored under --admin") and Bug #4 codified Option A (gh api PUT) were both addressing the SYMPTOM not the cause; the surviving head branch via standard `gh pr merge --admin` (no flag) confirms this. Explicit Mode 1 step 7 cleanup executed end-to-end: (a) `gh api -X DELETE repos/.../git/refs/heads/feature/admin-bug-4-root-cause-fix` → HTTP 204 OK; (b) local sync: stash → checkout develop → pull → branch -D → fetch --prune → stash pop, all clean; (c) post-cleanup verify: same `gh api branches/...` now returns `404 Branch not found` ✓. Local develop fast-forwarded `cc18fb9..249a8d5` (3 files, +60/-33: .claude/agents/git-publisher.md Mode 1 steps 6-8 rewrite + Bug #4 section, postmortem Bug #4 root-cause entry, Task.md handoff sweep). **Bug #4 ROOT cause now closed empirically and dispositively** — the Mode 1 step 7 cleanup pattern (no `--delete-branch` flag + explicit `gh api DELETE` + local sync) is the new canonical post-merge sequence; Option A (`gh api PUT`) remains documented as the safer-for-Mode-3 path but is no longer needed in Mode 1 just to preserve the source branch.
- [2026-05-11] PR-OPENED: #21 — feature/admin-task-md-cleanup → develop, 1 commits (5b669f5 "chore(task.md): sweep PR#20 handoffs + drop 2 stale entries"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/21. Diff: +4/-4, 1 file (.claude/Task.md only — removes MINOR-3-PACK from Carryover, drops stale Bug #5 SESSION-START-TODO from Resolved, sweeps WIP PR#20 lifecycle handoffs). /review skipped per CLAUDE.md Rule 2 (docs only, zero source code). Polling CI in background (task `bz5tvpy79`); on green, will merge via Mode 1 step 7 canonical sequence: `gh pr merge 21 --squash --admin` (NO --delete-branch flag) + `gh api -X DELETE refs/heads/feature/admin-task-md-cleanup` + local sync (stash → checkout develop → pull → branch -D → fetch --prune → stash pop). PR targets develop → Bug #5 reset N/A.
- [2026-05-11] PR-CI-GREEN: #21 — Backend pytest + migrations 2m14s, Frontend 12s, Vercel + comments all SUCCESS.
- [2026-05-11] PR-MERGED: #21 — squashed into develop (f08dc7a) via `gh pr merge 21 --squash --admin` (no --delete-branch). Canonical Mode 1 step 7 sequence executed cleanly: stash → merge → `gh api -X DELETE refs/heads/feature/admin-task-md-cleanup` (HTTP 204) → checkout develop → pull (fast-forward `249a8d5..f08dc7a`, 1 file +4/-4) → branch -D → fetch --prune (origin/feature/admin-task-md-cleanup deleted) → stash pop. Zero issues. PR #20's Mode 1 step 7 pattern continues to work as documented; this is the second consecutive empirical validation of the post-root-cause-fix workflow.
- [2026-05-14] REVIEW-REQUESTED: a65b75a — chore(workflow): finalize lean Claude Architect + Codex Implementer rename. Companion to 9e95615 (lean tools). 17 files, docs+tools+`.claude/codex/` only — no source-code paths touched. Part B browser strict mode auto-skip expected (no UI-affecting paths). WEB-REVIEW: please run `/review` Part A 7-axis + Part C drift.
- [2026-05-14] REVIEW-PASSED: a65b75a — drift checks passed, 1 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal. **2-commit range (origin/develop..HEAD), +633/-121, 18 files** — pure meta-cleanup, zero source code. `9e95615` adds 4 net-new lean-workflow tools (cmux_lean_setup.sh +149, dispatch-codex-task.sh +57, codex-task-template.md +65, print-claude-codex-handoff.sh +104; 375 LOC all-new). `a65b75a` finalizes the rename: `.claude/agents/team-{back,front}.md` → `.claude/codex/{backend,frontend}-worker.md` (90-93% content similarity; YAML frontmatter stripped — correct, since they're no longer Claude sub-agents) + propagates new paths + "bounded implementer" language across AGENTS.md / CLAUDE.md / WORKFLOW.md / SESSION_PROTOCOL.md / Goal.md / 8 tool scripts / `.gitignore` whitelist (`!.claude/codex/`). **Part A: PASS-WITH-MINORS 0/0/1** — single MINOR: `.claude/Report.md:135-136` Structure-table rows still cite the pre-rename ``.claude/agents/team-back.md`` / ``team-front.md`` paths (reporter-owned per CLAUDE.md, deferred to session-end per Token-saving Rule 1; non-blocking). **Architecture wins**: this rename RESOLVES the prior `.claude/reviews/3ef52b2.md:45` MINOR which flagged that `team-{back,front}.md` lived alongside `.claude/agents/` and could be mis-invoked as Claude `subagent_type` — the move to `.claude/codex/` eliminates that surface. `git grep` confirms zero live `subagent_type: team-{back,front}` callers in source (only historical mention inside the prior review file itself). **Integrity verifications**: `bash -n` PASS on all 7 changed shell scripts; executable bits PASS on all 8 tool scripts; `tools/cmux_lean_setup.sh --check` → 3/3 OK (cmux + codex + claude detected); `tools/print-claude-codex-handoff.sh --check` → 7/7 OK (4 required files + 3 executable bits); all 24 cross-referenced files exist; bash string concat `${team}end-worker.md` produces correct names for back→backend-worker.md and front→frontend-worker.md. Stale-ref residue in `.claude/handoffs-archive/`, `.claude/resolved-archive.md`, `.claude/reviews/*.md` is correctly preserved (archive artifacts reference paths at time of past commit; rewriting them would be wrong). Sub-MINOR observation (not actionable): `init_prompt_codex` heredoc duplicated across `cmux_setup.sh` / `cmux_lean_setup.sh` / `cleanup-after-push.sh` (3 copies, drift independently) — predates this commit, not a new issue; future cleanup candidate to source from `tools/_init-prompts.sh`. **Part B: skipped** per Step B0 — no UI-affecting paths (all 18 files under `.claude/`, `tools/`, `docs/`, root `AGENTS.md` / `CLAUDE.md` / `.gitignore`; zero `frontend/`, `recommendation/views.py|engine.py`, `accounts/`, `urls.py`, recommendation migrations, RECOMMENDATION settings). **Part C: drift PASS** — HEAD `a65b75ae70679072cd60ba517a3caf04a0005736` (no advance), origin/main `c231c5972c72af1a373bac50af7c38c3788aea46` (no remote drift). Static review at `.claude/reviews/a65b75a.md`. Governance-clean (zero `research/` writes, zero source code, zero design-pipeline writes; only `.claude/reviews/` + this Task.md handoff line).
- [2026-05-14] READY-FOR-PUSH: feature/admin-lean-agent-workflow — REVIEW-PASSED at a65b75a. WEB-GIT Mode 1 internal push+PR: `gh pr create --base develop` with title "chore(workflow): finalize lean Claude Architect + Codex Implementer rename", poll CI, on green `gh pr merge <N> --squash --admin` (NO `--delete-branch` flag per Bug #4 root-cause fix) + explicit `gh api -X DELETE refs/heads/feature/admin-lean-agent-workflow` + local sync (stash → checkout develop → pull → branch -D → fetch --prune → stash pop). 2-commit range (9e95615 lean tools + a65b75a rename), pure meta-cleanup.
- [2026-05-14] PR-OPENED: #24 — feature/admin-lean-agent-workflow → develop, 2 commits (9e95615 "chore: add lean Claude Codex workflow tools" + a65b75a "chore(workflow): finalize lean Claude Architect + Codex Implementer rename"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/24. Diff: 18 files +633/-121, pure meta-cleanup zero source code. /review = REVIEW-PASSED at a65b75a with 1 non-blocking MINOR (Report.md:135-136 stale pre-rename paths, deferred to reporter at session-end). Polling CI in background (task `bflnfzvuw`). On green: canonical Mode 1 step 7 sequence.
- [2026-05-14] PR-CI-GREEN: #24 — Backend 2m5s, Frontend 11s, Vercel + comments all SUCCESS.
- [2026-05-14] PR-MERGED: #24 — squashed into develop (c8a5bc7) via `gh pr merge 24 --squash --admin` (no --delete-branch). Canonical Mode 1 step 7 sequence clean: stash review-artifacts → merge → `gh api -X DELETE refs/heads/feature/admin-lean-agent-workflow` (HTTP 204) → checkout develop → pull (fast-forward f08dc7a..c8a5bc7, 18 files +633/-121) → branch -D → fetch --prune → stash pop. Third consecutive empirical validation of post-Bug#4-root-cause workflow. Lean Claude Architect + Codex Implementer rename now live on develop.
- [2026-05-14] PR-CHANGES-REQUESTED: #23 — base-ref violation (target main, must be develop). CLAUDE.md branch model hard rule 5. No /review needed (base-ref is the blocker, content review premature). `gh pr review 23 --request-changes --body-file ...` posted with retarget instructions (`gh pr edit 23 --base develop`). Verified `reviewDecision=CHANGES_REQUESTED`. Author: ksangjo (권상조), branch `feat/sj-0513-errorfix`.
- [2026-05-14] PR-READY-FOR-REVIEW: #22 — ksangjo/feat/sj-0512-dbspeed → develop, "refactor: optimize full-stack data flow and caching architecture". +641/-190, 9 files. CI=all green (Backend pytest+migrations SUCCESS, Frontend lint+build SUCCESS, Vercel + comments SUCCESS). Mergeable=UNKNOWN (GitHub still computing). 2 commits (5fd4bb7 main refactor + 4db3e4a backend pytest fix). Local checkout via `gh pr checkout 22` done; HEAD will return to `feat/sj-0512-dbspeed` after this handoff stashed so WEB-REVIEW's `/review` defaults to `origin/develop..HEAD` = PR diff. Admin: trigger `/review` in WEB-REVIEW per hybrid policy; on PASS → Mode 2 step 4 (approve + squash merge + `gh api -X DELETE refs/heads/feat/sj-0512-dbspeed` + local sync); on FAIL → Mode 2 step 5 (request-changes with collapsible report body). Working-tree handoff edits will be stashed on develop pending /review verdict.
- [2026-05-14] PR-CHANGES-REQUESTED: #22 — 0 CRIT / 1 MAJ / 4 MIN per .claude/reviews/4db3e4a.md. `gh pr review 22 --request-changes --body-file /tmp/pr22-fail-comment.md` posted using canonical git-publisher.md:158-178 format (header verdict + counts + top-3 + collapsible <details> with full review body). Verified `reviewDecision=CHANGES_REQUESTED`. Top 3 surfaced: (MAJOR) `.env.example` deletion vs README/CONTRIBUTING references — onboarding break; (MINOR) `card_cache_ttl` not declared in RECOMMENDATION dict; (MINOR) `views/swipe.py:619-628` narrows action-card fallback for MMR-returns-ID-but-DB-missing. 2 additional MINOR folded into body: LocMemCache MAX_ENTRIES=300 vs ~150-per-session footprint thrash; `bcard:<id>` cache key missing schema version for future Redis swap. Part B browser verification SKIPPED per review.md Step A6 (MAJOR ≥ 1 short-circuits to FAIL). Mode 2 step 6 cleanup executed: checkout develop + delete LOCAL `feat/sj-0512-dbspeed` (NOT remote — author still owns it). Remote `origin/feat/sj-0512-dbspeed` preserved for author's next push after addressing findings.
- [2026-05-14] REPORTER-DONE: c8a5bc7 — Report.md Last Updated synced (PR #24: lean workflow rename — `.claude/agents/team-{back,front}.md` → `.claude/codex/{backend,frontend}-worker.md`, 4 new lean tools cmux_lean_setup/dispatch-codex-task/codex-task-template/print-claude-codex-handoff); fixed stale `.claude/agents/team-back.md`/`team-front.md` paths in Report.md structure table (rows 135-136) + Phase 13-15 bullet (line 476); 2 external PRs triaged (PR #23 base-ref violation → request-changes; PR #22 REVIEW-FAIL 0/1/4 → request-changes); Task.md handoffs trimmed 51→30 (oldest 21 archived to `.claude/handoffs-archive/2026-05.md`); algorithm.md skipped (no RECOMMENDATION dict changes this session).
- [2026-05-14] PR-OPENED: #25 — feature/admin-reporter-sync → develop, 1 commits (4998ccf "docs(reporter): post-PR#24 sync — lean workflow rename live + 2 external PRs triaged"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/25. Diff: 6 files +334/-140 (Report.md sync + Task.md handoff archive + 2 review artifacts). /review skipped per CLAUDE.md Rule 2 (pure docs sweep). Canonical Mode 1 step 7 on green.
- [2026-05-14] PR-CI-GREEN: #25 — Backend 2m7s, Frontend 13s, Vercel + comments all SUCCESS (initial poll exited early due to checks-registered-later race; re-polled with `length(map(select(.bucket=="pending")))==0` predicate which waited correctly).
- [2026-05-14] PR-MERGED: #25 — squashed into develop (25c14bb) via `gh pr merge 25 --squash --admin` (no --delete-branch). Mode 1 step 7 sequence clean: no stash needed (working tree clean) → merge → `gh api -X DELETE refs/heads/feature/admin-reporter-sync` HTTP 204 → checkout develop → pull (fast-forward c8a5bc7..25c14bb, 6 files +334/-140) → branch -D → fetch --prune → no stash to pop. Reporter sync of PR #24 + 2 external PR triages now live on develop.
- [2026-05-14] BACK-DONE: s3-swipe-end-flow-back
- [2026-05-14] BACK-DONE: s3-swipe-end-flow-back-fix1
- [2026-05-14] REPLAN-LANDED: S1 of 2026-05-14 tab 3-structure replan committed on feature/admin-replan-tab3. Files: `.claude/plans/replan-2026-05-14-tab3-restructure.md` (new, full push roadmap S1-S8 + /compact boundaries + decisions Q1-Q6), `docs/COLLAB_HANDOFF.md` (new, collaborator on-ramp pointing to CLAUDE.md/CONTRIBUTING.md/database-schema.md), `.claude/Task.md` Roadmap Phase 19-26 entries added + Phase 16-18 marked as superseded/scope-revised + B3v2 entry routed to S3. /review skipped per CLAUDE.md Rule 2 (pure docs). Ready for git-publisher Mode 1 push+PR.
- [2026-05-14] FRONT-DONE: s3-swipe-end-flow-front
- [2026-05-14] BACK-BLOCKED: s3-swipe-end-flow-back-fix2 — required verification failed twice (`cd backend && python3 -m pytest tests/test_confidence.py tests/test_imp7_pool_cache.py tests/test_imp8_async_prefetch.py tests/test_sessions.py 2>&1 | tail -3` reports 62 errors and failing tests in `tests/test_sessions.py`), and backend-wide `__action_card__` grep still returns residual matches outside edited test files (`backend/tests/test_sessions.py`, `backend/apps/recommendation/views/swipe.py`).
- [2026-05-14] REVIEW-PASSED: fd871d3 — drift checks passed, 6 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-05-14] REVIEW-PASSED: 2936fc2 — drift checks passed, 6 MINOR noted (see .claude/reviews/latest.md); run `git push` manually from this terminal
- [2026-05-14] PR-OPENED: #29 — feature/admin-s5-library-to-profile → develop, 1 commits (7143588 "feat(s5): absorb /library into Profile (replan Issue 3)"), CI running. URL: https://github.com/hongikarchi/archi-tinder/pull/29. /review skipped per Rule 2 (frontend dead-code removal + route redirects; front-validate.sh PASS in WEB-MAIN; no algorithm/contract change).
- [2026-05-14] PR-CI-GREEN: #29 — Backend 2m8s, Frontend 11s, Vercel + comments all SUCCESS.
- [2026-05-14] PR-MERGED: #29 — squashed into develop (7f225c2) via `gh pr merge 29 --squash --admin` (no --delete-branch). Mode 1 step 7 clean: stash → merge → `gh api -X DELETE refs/heads/feature/admin-s5-library-to-profile` HTTP 204 → checkout develop → pull (fast-forward a5edff5..7f225c2, 7 files +220/-191) → branch -D → fetch --prune → stash pop. S5 (absorb /library into Profile per replan Issue 3) live on develop.
- [2026-05-14] READY-FOR-PUSH: feature/admin-s6-tab-cutover — REVIEW-SKIPPED (trivial cutover, token-saving Rule 2). 1-commit S6 (14510ae "feat(s6): 4-tab → 3-tab TabBar cutover"). WEB-GIT Mode 1 internal push+PR: `gh pr create --base develop` with title "feat(s6): 4-tab → 3-tab TabBar cutover", poll CI, on green canonical Mode 1 step 7 sequence. Frontend-only, 6 files -930 LOC (dead-code removal).

## Development Roadmap

> Orchestrator: follow this order. Each Phase's tasks are referenced by ID.

### Phase 1: Critical Bug Fix -- COMPLETED 2026-04-03
1. **B4** -- Mobile Google login (auth-code flow)
2. **B1** -- "View Result" button timing
3. **B2** -- Card repetition (exposed_ids)
4. **B3** -- "No buildings match" fallback

### Phase 2: Stability -- COMPLETED 2026-04-03
5. **F1** -- Swipe error handling + state sync
6. **A3** -- Recency weight math protection
7. **BE1** -- API timeout/retry

### Phase 3: Performance -- A1 COMPLETED, A2 VALIDATED
8. **A1** -- Pool caching + KMeans caching + prefetch -- COMPLETED 2026-04-03
9. **A2** -- Algo-tester 100 personas -- validated (smoke test passed, full run pending)

### Phase 4: UX Enhancement -- COMPLETED 2026-04-03
10. **UX1** -- Tutorial popup -- COMPLETED 2026-04-03
11. **UX3** -- Action card message improvement -- COMPLETED 2026-04-03
12. **F2** -- Image load failure handling -- COMPLETED 2026-04-03

### Phase 4.5: Swipe Bug Fix -- B5, B6, B2v2 COMPLETED 2026-04-04 (B3v2 skipped)
13. **B5** -- Fast swipe race condition (no swipe lock, concurrent requests)
14. **B6** -- Card suddenly changes (prefetch response overwrites current card)
15. **B2v2** -- Same cards still repeating (prefetch uses stale exposed_ids)
16. **B3v2** -- Pool exhaustion during exploring phase returns null (SKIPPED -- low priority)

### Phase 5: New Features -- UX2, F3 COMPLETED 2026-04-04 (AUTH1 deferred)
17. **UX2** -- Persona Report AI image generation -- COMPLETED 2026-04-04
18. **AUTH1** -- Kakao / Naver OAuth (deferred -- future)
19. **F3** -- Mobile optimization -- COMPLETED 2026-04-04

### Phase 6: Cleanup -- COMPLETED 2026-04-04
20. **INFRA1** -- Backend integration tests -- COMPLETED 2026-04-04
21. **INFRA2~4** -- Idempotency, total_rounds, console.error -- COMPLETED 2026-04-04
22. **BE2** -- Gemini error handling improvement -- COMPLETED 2026-04-04

### Phase 7: Codebase Audit Fixes -- COMPLETED 2026-04-04
23. **AUDIT1** -- Remove unused deps, dead code, consolidate tests, fix deprecations -- COMPLETED 2026-04-04

### Phase 8: E2E Testing Infrastructure -- COMPLETED 2026-04-05
24. **TEST1** -- E2E visual test runner module -- COMPLETED 2026-04-05

### Phase 9: E2E Runner Fix -- COMPLETED 2026-04-07
25. **TEST2** -- Rewrite runner.py to match actual frontend UI flow -- COMPLETED 2026-04-06
26. **TEST3** -- Fix screenshots, card visibility, timing breakdown -- COMPLETED 2026-04-07

### Phase 10: Swipe API Latency Fix -- COMPLETED 2026-04-05
27. **PERF1** -- Non-algorithm swipe latency optimizations -- COMPLETED 2026-04-05

### Phase 11: Frontend Bug Fix -- COMPLETED 2026-04-05
28. **B7** -- Keyboard swiping blocked in gallery mode (SwipePage.jsx) -- COMPLETED 2026-04-05
29. **B8** -- Card disappears after swipe race condition (App.jsx) -- COMPLETED 2026-04-05

### Phase 12: Critical Swipe Bug Fixes -- COMPLETED 2026-04-05
30. **B9** -- Cards stop loading after ~N swipes (never set currentCard null) -- COMPLETED 2026-04-05
31. **B10** -- Refresh creates new session instead of resuming (SessionStateView + currentHint) -- COMPLETED 2026-04-05
32. **B11** -- Same card appears twice (client_buffer_ids in exposed_ids) -- COMPLETED 2026-04-05

### Phase 13: Profile System -- COMPLETED 2026-05-06
33. **PROF1** -- OfficeProfile model + Make DB integration (blue-mark, project list, external links, basic info) -- COMPLETED 2026-04-29
34. **PROF2** -- UserProfile extension (MBTI, avatar, bio, external DM links) -- COMPLETED 2026-04-29
35. **PROF3** -- Firm profile page UI (project card grid + website/email links) -- COMPLETED 2026-05-02
36. **PROF4** -- User profile page UI (feed style, board list) -- COMPLETED 2026-05-02

### Phase 14: Board System -- COMPLETED 2026-05-06
37. **BOARD1** -- Board model (public/private visibility, owner FK) -- COMPLETED 2026-04-30
38. **BOARD2** -- Project creation: visibility selection UI -- COMPLETED 2026-05-06
39. **BOARD3** -- Profile page: board browse/manage UI -- COMPLETED 2026-05-06

### Phase 15: Social Foundation -- COMPLETED 2026-05-06
40. **SOC1** -- Follow model + API (follow/unfollow, follower list) -- COMPLETED 2026-05-02
41. **SOC2** -- "Love this!" reaction model + API -- COMPLETED 2026-05-02
42. **SOC3** -- Profile/board: follow button + reaction button UI -- COMPLETED 2026-05-06

### Phase 16: Recommendation Expansion -- PENDING (revised under 2026-05-14 replan)
> Spec: `docs/specs/phase16-recommendation-expansion.md`. REC1 supersedes the
> swipe end-flow rework now scoped under **Push S3** (see plan
> `.claude/plans/replan-2026-05-14-tab3-restructure.md`).
> REC2/REC3/REC4 retargeted to the Profile tab "사무소 추천" button (Q3 decision)
> rather than a dedicated Landing tab. Spec body needs S8 sweep.
43. **REC1** -- Post-swipe end screen consolidation (now executed in **S3**)
44. **REC2** -- Firm recommendation logic (Profile-button-triggered)
45. **REC3** -- User recommendation logic (Profile-button-triggered)
46. **REC4** -- ~~Landing tab~~ → folded into S6 (Profile tab integration)

### Phase 17: LLM Reverse-Questioning -- PENDING
> Spec: `docs/specs/phase17-llm-reverse-q.md`. Replan Q6 confirms Option A —
> reverse-question in first 0-2 turns of Taste-tab LLM chat. Spec needs S8 sweep.
47. **LLM1** -- Chat reverse-question prompt design (identify user needs)
48. **LLM2** -- Persona classification logic (P1-P4 differentiation; populates `UserProfile.persona_summary`)
49. **LLM3** -- Per-persona UI branching (recommendation card type switching)

### Phase 18: External Connections -- PENDING
> Spec: `docs/specs/phase18-external-connections.md`. Lower priority than Phase 16-17.
50. **EXT1** -- Firm article crawler (Space, ArchDaily, news — keyword-based)
51. **EXT2** -- Article list UI (inside firm profile)
52. **EXT3** -- External DM link UI (Instagram, email — on profile)

### Phase 19-26: 2026-05-14 Replan (Tab 3-Structure Transition) -- PENDING
> Full plan: `.claude/plans/replan-2026-05-14-tab3-restructure.md`.
> Pre-empts Phase 16-18 ordering — execute S1-S8 sequentially before reopening Phase 16-18 dimensions.
53. **S1** -- Plan + collaborator on-ramp doc (this push)
54. **S2** -- DB new-schema integration *(triggers Make DB owner fetch)*
55. **S3** -- Swipe end-flow consolidation (Issue 2: ActionCard removal + end-screen rewrite)
56. **S4** -- Progress UI single source (Issue 1: ConfidenceBar/round-counter merge)
57. **S5** -- Library → Profile absorb (Issue 3: real data + redirect)
58. **S6** -- 4-tab → 3-tab cutover (Discovery / Taste / Profile)
59. **S7** -- Discovery Swipe tab (new infinite-scroll page + save flow + surprise board)
60. **S8** -- Roadmap / spec sweep (Phase 16-18 reconciliation, stale docs cleanup)

### Carryover (deferred non-blocking from prior reviews)
61. **SOC3-back-blocked** -- Original blocker was Neon DB DNS in codex sandbox. Revisit when next Office model migration is needed; resolution path documented in `.claude/codex/backend-worker.md` § "DB-touch handoff".

---

## Specs

> Pending-feature specs and decision records live in `docs/specs/` (admin-owned via PR).
> Algorithm theory + production hyperparameters live in `docs/algorithm.md` (reporter
> syncs production values; admin owns theory edits).
>
> Current pending specs:
> - `docs/specs/phase16-recommendation-expansion.md` — Phase 16 dimensions
> - `docs/specs/phase17-llm-reverse-q.md` — Phase 17 dimensions
> - `docs/specs/phase18-external-connections.md` — Phase 18 dimensions
> - `docs/specs/requirements.md` — still-open cross-cutting questions

---

## Open

#### B3v2. Exploring phase pool exhaustion returns null (superseded by S3)
`views.py:436-437` farthest_point_from_pool returns None when pool exhausted.
The 2026-05-14 replan **S3** push rewrites end-of-session handling and
deprecates `build_action_card`; pool-exhaustion now routes to the new
end-screen via `can_continue: false` + `is_analysis_completed: true`.
Close this entry when S3 lands.
- [ ] exploring phase pool exhaustion -> handled by S3 end-screen rewrite

### Algorithm

#### A2. Hyperparameter optimization -- validated, full run pending
Smoke test (3 personas x 5 trials) passed. No code changes needed.
- [x] Smoke test passed (--personas 3 --trials 5)
- [ ] Run algo-tester: 100 personas x 200 trials
- [ ] Evaluate results vs baseline
- [ ] Apply optimized params if improvement found

### Auth
#### AUTH1. Kakao / Naver OAuth not implemented
Google OAuth only. Korean users need domestic login.
- [ ] Kakao social auth backend + frontend button
- [ ] Naver social auth backend + frontend button

---

## In Progress

(none)

---

## Resolved

Historical resolved tasks moved to `.claude/resolved-archive.md` (frees
~30-50K tokens per reporter call; git log is the authoritative history).
Append new resolved entries to the archive, not here.
