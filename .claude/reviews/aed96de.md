# Review: feature/admin-meta-cleanup (origin/develop..HEAD)

- **Date:** 2026-05-09
- **Branch:** feature/admin-meta-cleanup
- **Range:** origin/develop..HEAD  (2 commits, +2076 / -1583 lines, 18 files)
- **Reviewer:** Claude (/review)

## Executive Summary

Two-commit meta-cleanup bundle. `4a60b20` slims CLAUDE.md 506→240 lines
by extracting three sections to dedicated files (`docs/database-schema.md`,
`web-testing/AGENTS.md`, `docs/token-saving.md`), slims Task.md 1201→239
by archiving 89 ## Resolved entries to `.claude/resolved-archive.md`,
narrows reporter.md Step 1 + splits Step 3 + makes Step 4 Mermaid optional,
and introduces three `cmux-*` skills under `.claude/skills/`. `aed96de`
empirically discovers that project-local skills auto-invoke from ALL cmux
workspaces (skills loaded into WEB-REVIEW's context made WEB-REVIEW
self-dispatch on "리뷰해줘"), so it deletes the three skill dirs and
replaces them with a plain `tools/review-cycle.sh` wrapper that has no
auto-invoke surface. End state is coherent, well-justified, and
empirically validated by the second commit's discovery+fix narrative.

Browser test auto-skipped (no UI-affecting paths in scope; all 18 files
are under `.claude/`, `tools/`, `docs/`, `web-testing/`, `CLAUDE.md`,
`.gitignore`).

## Static Review Verdict (Part A)
OVERALL: PASS-WITH-MINORS
- CRITICAL: 0
- MAJOR: 0
- MINOR: 1

## Findings (Part A)

### 1. [MINOR] `web-testing/AGENTS.md` strict-mode swipe-p95 gate is stale
- **File:** `web-testing/AGENTS.md:152`
- **Axis:** 7 — cross-commit drift (cross-doc consistency)
- **Issue:** Strict-mode row table says "per-swipe p95 < 700 ms". The canonical
  spec at `.claude/commands/review.md` Step B5 (lines 604-608) was updated
  post-Investigation 18 to `p95 < 1500 ms` (user-felt outer RTT) AND
  `p95 < 1000 ms` (backend `SessionEvent.swipe.timing_breakdown.total_ms`),
  with the aspirational <500 ms preserved as a goal not a gate. The 700 ms
  figure was the pre-Investigation-18 value. When the Web Testing block was
  extracted from CLAUDE.md into the new `web-testing/AGENTS.md`, this row
  carried the stale number.
- **Why it matters:** Operators consulting `web-testing/AGENTS.md` (per the
  new CLAUDE.md "## Web Testing" pointer) will see a stricter gate than
  /review actually enforces. Could cause confusion when reading review
  reports that PASS at 1100 ms while the doc implies that's a FAIL.
- **Suggested fix:** Replace `per-swipe p95 < 700 ms` with
  `per-swipe p95 < 1500 ms outer / < 1000 ms backend (post-Investigation 18)`,
  keeping the strict mode row aligned with `.claude/commands/review.md` Step B5.

## Sub-MINOR observations (informational; not actionable)

- **`tools/review-cycle.sh` comment typo** (line 7): the inline example in
  the file header reads `'リ뷰해줘'` — the first character is Japanese
  katakana リ, not Korean 리. The actual dispatch call at line 75 uses
  correct Korean 리뷰해줘, so the bug is comment-only and has no runtime
  effect. Cosmetic.
- **`tools/review-cycle.sh` --check not wired to `tools/.smoke.sh`**: the
  script's `--check` mode validates dispatch.sh / poll.sh / Task.md presence
  but isn't aggregated into the canonical smoke harness. The file header
  comments at lines 41-43 explicitly acknowledge and justify this gap
  ("review-cycle is a higher-level wrapper than the git-* group .smoke.sh
  covers"). Acceptable per documented choice.
- **Task.md handoff entries 78/79 out of strict chronological order**: line 78
  is dated `2026-05-10` (SESSION-START-TODO), line 79 is dated `2026-05-09`
  (PR2-IN-FLIGHT). The Handoffs section is append-only and reporter
  `feedback_token_saving_workflow.md` Rule 4 trims by count, not by date,
  so out-of-order is functionally inert. Cosmetic.
- **`.claude/Report.md` "Last Updated" cites dad4eb4 (PR #7) but does not
  yet mention 4a60b20 + aed96de**: this matches `docs/token-saving.md` Rule 1
  (defer reporter to session end). Reporter run at session end will roll
  Last Updated forward to cover both new commits. Acceptable per design.

## Architecture Alignment

The branch is a pure meta-consolidation:

1. **CLAUDE.md extraction** — 3 sections moved to dedicated files. Each
   target file is more focused (DB schema in one place; Web Testing
   self-contained for the agent that owns it; Token-saving rules versioned
   as their own doc). All inbound references updated:
   - `agents/orchestrator.md` token-saving section: 4 long bullets → 1 ref to
     `docs/token-saving.md`.
   - `agents/web-tester.md` Step 0 + `agents/orchestrator.md` Step 5c:
     `CLAUDE.md "Web Testing"` → `web-testing/AGENTS.md`.
   - `agents/team-back.md` + `team-front.md` self-review headers:
     `CLAUDE.md § Token-saving` → `docs/token-saving.md` Rule 3.
   - `agents/reporter.md` Step 1 + Step 3 + Rules: rewritten to use the new
     `.claude/resolved-archive.md` stub-and-archive pattern.

2. **Empirical fix loop in second commit** — `aed96de` is a textbook
   "introduce → discover bug → roll back to a known-good shape" pattern.
   The commit message articulates the discovery (skills auto-invoke from
   ALL cmux workspaces because `.claude/skills/` is shared cwd) and the
   fix rationale (a script has no auto-invoke surface). I personally
   experienced this exact bug in the current review session: the prior
   skill `cmux-review-cycle/SKILL.md` would have made me self-dispatch
   on "리뷰해줘"; the replacement `tools/review-cycle.sh` is invoked
   only by name, no auto-invoke.

3. **No drift from established patterns** — Branch model rules unchanged;
   plan-mode protocol unchanged; cmux 5-tab table unchanged; `building_id`
   canonical-key rule preserved; raw-SQL-only on `architecture_vectors`
   preserved; trailing-slash convention preserved; Django 4.2 LTS
   preservation noted.

End state matches Goal.md / Report.md System Architecture; the only thing
changing is *where* the rules are documented, not the rules themselves.

## Optimization Opportunities

The branch IS the optimization. Estimated savings (per `4a60b20` commit
body):
- CLAUDE.md auto-load per session: ~5 K tokens
- Reporter call: ~50-60 K tokens/run (Task.md slim from 1201→239, Mermaid
  optional, Resolved no longer auto-read)
- Orchestrator agent spawn: ~3 K tokens (token-saving rule consolidation)

Cumulatively this lines up with the broader 2026-04-29 + 2026-05-07
token-saving program (memory `feedback_token_saving_workflow.md`).

No further optimization opportunities surface from the diff itself.

## Security Analysis

Zero auth / token / model / network code in scope. `.gitignore` evolution
correctly tracks the new `.claude/resolved-archive.md` whitelist (added in
`4a60b20`) and removes the `!.claude/skills/` whitelist after the dir is
deleted (in `aed96de`); both moves are net-zero on secret-leak surface
since both are non-secret declarative files. `tools/review-cycle.sh`
dispatches a hardcoded fixed message to a known cmux tab — no user input
flows through, no shell expansion of untrusted strings, no command
injection vector.

## Test Coverage Gaps

Not applicable — no production code in scope. `tools/review-cycle.sh` does
have a `--check` mode that validates dispatch/poll/Task.md presence;
empirical run during this review returned green:
```
review-cycle.sh --check
  ✓ on feature branch: feature/admin-meta-cleanup
  ✓ dispatch.sh executable
  ✓ poll.sh executable
  ✓ .claude/Task.md exists
```

`bash -n` clean across both `tools/review-cycle.sh` and the modified
`tools/cleanup-after-push.sh`.

## Commit-by-Commit Notes

### 4a60b20 feat: meta-cleanup + reporter optim + cmux skills
- Three coherent extractions (CLAUDE.md → docs/token-saving.md +
  web-testing/AGENTS.md + docs/database-schema.md). Each target file is
  self-contained and adds only the prose that was inline in CLAUDE.md, plus
  small framing context. No content lost.
- Task.md 89 ## Resolved entries → `.claude/resolved-archive.md`. Stub
  in Task.md (lines 235-239) explicitly tells reporter where to append.
- reporter.md surgical updates: Step 1 reads Task.md (no longer
  auto-reads Resolved), Step 3 splits (Open/In Progress moved to archive,
  not Task.md ## Resolved), Step 4 Mermaid is now conditional on
  architecture change. Rules section adds the archive-write rule.
- Three new `.claude/skills/cmux-*/SKILL.md` files — well-intentioned, but
  the auto-invoke-from-shared-cwd issue is what `aed96de` discovers.
- `.gitignore` whitelist additions for `.claude/skills/` and
  `.claude/resolved-archive.md` — both correct for the files added in
  this commit.
- Carry-over of `.claude/{Report,Task,reviews/latest,handoffs-archive/2026-05}.md`
  + `.claude/reviews/b93b419.md` + `tools/cleanup-after-push.sh` per Rule 6
  bundling — all match the working-tree state after PR #7's review pass.
  `cleanup-after-push.sh` change (WEB-GIT skip + init_prompt_git removed) is
  consistent with the 2026-05-09 empirical decision in the file header.

### aed96de fix: rollback cmux-* skills + add tools/review-cycle.sh wrapper
- Empirically motivated. Commit body articulates the bug, the root cause
  (project-local skills visible to all workspaces, no per-terminal scope
  in the skills system), and the fix (script with no auto-invoke surface).
- Net diff: -215 LOC (3 skill dirs deleted) + 101 LOC (new
  `tools/review-cycle.sh`) - 1 LOC (`.gitignore` `!.claude/skills/`
  whitelist now stale).
- The replacement script meets the original abstraction goal (single call
  site, consistent polling cadence) without the auto-invoke risk.
- `--check` mode + 30-min ceiling + tail-of-WEB-REVIEW dump on TIMEOUT are
  good operator-affordances. Exit codes (0/1/2/3) clearly documented in
  the file header.
- This commit empirically validates itself: I (WEB-REVIEW, this very
  session) experienced the auto-dispatch loop the commit fixes, then
  switched to following `.claude/commands/review.md` directly — the
  intended post-fix workflow.

## Part B — Browser Verification

Skipped — no UI-affecting paths in scope (all 18 files are under
`.claude/`, `tools/`, `docs/`, `web-testing/`, `CLAUDE.md`, or
`.gitignore`; zero `frontend/`, `recommendation/views.py|engine.py`,
`accounts/`, `urls.py`, recommendation migrations, or RECOMMENDATION
settings).

## References

- Goal.md sections consulted: System Architecture (live state in Report.md
  cited indirectly).
- Report.md sections consulted: Last Updated (Claude) — current entry
  cites dad4eb4 (PR #7); not yet rolled forward to cover this PR's
  HEAD per Rule 1 deferral.
- Spec sections consulted: none (no algorithm or spec touches).
- Other files consulted: `.claude/commands/review.md` (Part B0 path-detection
  gate + Part C drift); `docs/token-saving.md` (canonical 8-rule policy
  the agent files now reference); `.claude/Task.md ## Handoffs` (recent
  PR #7 entries for context on what's already merged); `.claude/agents/{orchestrator,reporter,team-back,team-front,web-tester}.md`
  (agent files with cross-reference updates).
