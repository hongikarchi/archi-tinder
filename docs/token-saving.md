# Token-Saving Workflow Rules

Operational rules to keep per-session Claude token spend bounded. Referenced
from `CLAUDE.md`, `.claude/agents/orchestrator.md`, `.claude/agents/reporter.md`,
and `.claude/SESSION_PROTOCOL.md`. Memory: `feedback_token_saving_workflow.md`.

## Rule 1 — Defer reporter to session end

Do NOT spawn `reporter` after every commit. Accumulate `.claude/Report.md` +
`.claude/Task.md` working-tree changes and run reporter ONCE at session end (or
right before `git push`).

User override: "지금 reporter 돌려" → run immediately.

## Rule 2 — Skip reviewer + security on trivial commits

A commit is **trivial** when ALL of:
- `<50 LOC` OR pure docs/policy/agent-file commit (zero source code)
- No migration
- No production code (only test, config, docs, `.claude/` policy/agent files,
  `web-testing/`, or `.claude/commands/review.md`)
- No auth / network / model layer change

The "pure docs/policy" branch handles cases like CLAUDE.md / agent-md /
AGENTS.md cross-cutting policy commits that legitimately exceed 50 LOC (e.g.
the 121-LOC hybrid pre-commit policy commit `756b247`) but introduce zero
runtime risk.

Trivial commits go `back-maker` → `git-manager` directly, bypassing the
in-session `reviewer` + `security-manager` agents.

User override: "리뷰 돌려" or any explicit request → run them anyway.

## Rule 3 — Hybrid pre-commit policy for Codex team output

When work was dispatched to WEB-BACK / WEB-FRONT (Codex teams), the team's
own self-review (per `.claude/agents/team-back.md` § "Self-review checklist
before BACK-DONE" / `team-front.md` § "Self-review checklist before
FRONT-DONE") is the **default pre-commit gate**. WEB-MAIN trusts the
BACK-DONE / FRONT-DONE report and skips the in-session Claude `reviewer` +
`security-manager` agents.

Cross-model verification still happens at `/review` (Claude Opus on
WEB-REVIEW vs Codex gpt-5.5 on the teams).

**Risky-commit override**: Codex teams append `(claude-review-requested)` to
their DONE message when work touches:
- auth flow
- token-handling
- new external API integration
- migrations with data backfill
- cross-cutting refactors ≥ 4 unrelated apps

WEB-MAIN then runs the in-session reviewer/security pass on top of the
self-review. Same rule applies to direct Claude `back-maker`/`front-maker`
work — in-session reviewer/security run when the orchestrator believes the
change is risky.

Rationale: pre-commit Claude reviewer + security on Codex output ate
~150-200 K Claude tokens per BOARD-class deliverable (3-cycle fix loop)
while `/review`'s Part A already covers the 7-axis static analysis. The
hybrid keeps the cross-model verification (which catches genuine bugs — see
BOARD3 cycle 0 `resp.is_reacted` vs `resp.reacted` contract mismatch) at
`/review` time, where Part B browser test ALSO runs.

## Rule 4 — Auto-archive Task.md handoffs

When `## Handoffs` section in `.claude/Task.md` exceeds 30 entries, reporter
trims the oldest to `.claude/handoffs-archive/<YYYY-MM>.md`, keeping the
most recent 30 in Task.md.

(2026-05-10) Task.md `## Resolved` is also split: full history lives in
`.claude/resolved-archive.md`; Task.md only carries a stub. Reporter
appends new resolved entries directly to the archive, not to Task.md.

## Rule 5 — Slim back-maker prompts

Target 1.5-2 K tokens per delegation (vs 3-5 K previously). Use spec section
pointers + minimal scope; back-maker reads the spec directly when needed.

## Rule 6 — Bundle trivial commits, push only on milestone / push-worthy

Don't `/review + push` after every trivial commit. Accumulate locally and
sweep them in with the next push-worthy commit's `/review` (which scans the
whole `origin/main..HEAD` range, so no extra cost).

Empirical from 2026-05-06 session: 8 push events for 16 commits ≈ ~2
commits/push. Bundling could have reduced to 4-5 push events
(~30-40% `/review` token savings = ~450-600 K Claude per session).

### Push-worthy (immediately `/review` + push when committed)

1. **Milestone commit** — closes a Task.md `## Development Roadmap` task
   ID (PROF1, BOARD3, SOC3-back, REC1, etc).
2. **Production code commit** — `backend/apps/*/{models,views,serializers,
   urls,migrations}.py` or `frontend/src/{pages,hooks,api,contexts}/*.{js,jsx}`
   with logic change.
3. **Migration commit** — schema change in any app.
4. **Risky-zone touch** — auth / token-handling / new external API
   integration / cross-cutting refactor ≥ 4 unrelated apps (matches
   Rule 3 risky-commit list).
5. **User explicit request** — "지금 push" / "리뷰 돌려".

### Bundle-worthy (commit locally; push deferred)

1. **Pure docs / policy** — `CLAUDE.md`, `.claude/agents/*.md`, `AGENTS.md`,
   `CONTRIBUTING.md`, `DESIGN.md`, `docs/*.md`, `Goal.md`, `Report.md`,
   `Task.md` (handoff entries, status updates).
2. **Tooling** — `tools/*.sh`, `hooks/*`, `.github/*`, `.gitignore`
   whitelist additions, cmux config (per 2026-05-07: tooling-self-use is
   local-effective from commit time; remote sync waits for next code push).
3. **Sub-MINOR follow-ups** — cosmetic fixes from `/review` reports (typo,
   dead-code branch, etc).
4. **Handoff entries** — single-line additions to `Task.md ## Handoffs`.
5. **Session-end housekeeping** — reporter pass output (Report.md sync,
   Task.md trim, handoffs archive).

### Forced push triggers

1. **Push-worthy commit lands** (automatic — sweeps everything in
   `origin/main..HEAD`).
2. **Session end** (cleanup batch — explicit user "끝내자" or context
   wind-down).
3. **Bundle accumulator > 5 commits** (heuristic — review scope and
   history clarity start to suffer).
4. **24 hours since first bundle commit** (anti-stale; rarely triggers).
5. **User explicit "지금 push"**.

### Drift safety

Each push still triggers `/review` Part C drift check on the entire
`origin/main..HEAD` range, so bundling does NOT lose drift protection.
Larger range simply means slightly larger Part A scope (Part B browser
test cost is fixed-per-session regardless of range size).

## Rule 7 — Post-push session-memory cleanup

After a push completes (origin/main caught up to local HEAD), the WEB-MAIN
operator runs `tools/cleanup-after-push.sh` to send `/clear` to WEB-BACK /
WEB-FRONT / WEB-REVIEW. WEB-GIT is intentionally NOT cleared (small
transcripts; auto-clear cost > benefit per 2026-05-09 empirical). WEB-MAIN
itself runs `/compact` manually (Claude cannot self-`/clear` from inside
the same session).

This bounds each push cycle's accumulated context so the next cycle starts
fresh and avoids the 2026-05-07-class context-bloat bugs (WEB-REVIEW
stuck-prompt at 464K tokens; WEB-REVIEW server-side rate-limit mid-review).

The codex teams' `/clear` is followed by an automatic init prompt re-send
(self-discovery against AGENTS.md + team-{back,front}.md + CLAUDE.md +
Task.md Handoffs).

Estimated savings: ~30-50% Claude tokens per cycle when applied
consistently. Rule applies to push-completion events only — mid-session
`/clear` on a busy tab is destructive and can interrupt running work.

## Rule 8 — Codex model standardization

Both WEB-BACK and WEB-FRONT use `gpt-5.5` with `model_reasoning_effort=high`
(NOT medium/xhigh/etc). The `/fast` mode toggle is left to operator
discretion (currently on for both — empirically 1.5-3 min for 200-400 LOC
mechanical work).

**Critical empirical (2026-05-08)**: codex's `~/.codex/config.toml` setting
`model_reasoning_effort = "xhigh"` is NOT auto-applied on codex restart,
AND the `/model` slash menu resets effort to medium when re-selecting. The
only way to make `high` stick is the `-c model_reasoning_effort=high`
command-line flag at codex launch. `tools/cmux_setup.sh` codifies this:
TEAMS array uses `codex -c model_reasoning_effort=high`.

When a codex tab is restarted manually, also use
`-c model_reasoning_effort=high` (not just `codex`). Operator: do NOT use
`/model` slash inside codex — it triggers the medium-default reset bug.
