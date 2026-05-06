# make_web — AGENTS.md (for Codex CLI)

This file is the standard OpenAI Codex CLI baseline for any `codex`
session running inside the make_web repository. It is loaded
automatically when you start `codex` from this directory (Codex walks
upward from cwd and concatenates every `AGENTS.md` it finds).

If you are reading this in a Claude Code session, look at `CLAUDE.md`
instead — that is the Claude-specific entry point. The two files
intentionally cover the same project from different agent
perspectives.

---

## You are part of a 4-workspace cmux team

`make_web` runs as 4 cmux workspaces in one window. You are inside one
of the two "team" workspaces; the orchestrator lives in WEB-MAIN. To
know which team you are, look at the cmux workspace title (`WEB-BACK`
or `WEB-FRONT`) — `tools/cmux_setup.sh` sets this automatically. Each
team's full responsibilities, owned files, and hard guardrails are
documented in `.claude/agents/team-<team>.md` — **read your team's
file before any action.**

| Workspace | Runs | Owns |
|---|---|---|
| WEB-MAIN | Claude Code (orchestrator) | Pipeline, dispatch, in-session reviewer/security |
| WEB-BACK | Codex CLI | `backend/` (Django apps, serializers, views, migrations, tests) |
| WEB-FRONT | Codex CLI | `frontend/` (React data layer — `useState`, `useEffect`, `callApi`, hooks, error handling) |
| WEB-REVIEW | Claude Code | `/review` pre-push gate only (read-only on source) |

## How WEB-MAIN sends you work

WEB-MAIN runs `tools/dispatch.sh <team> "<message>"` which wraps
`cmux send` and types the message into your prompt followed by Enter.
You will see the message appear as if a user typed it. Treat each such
message as a task. Read it, decide what to do, do it, then append a
**handoff signal** to `.claude/Task.md` § Handoffs so WEB-MAIN knows
you're done.

## Handoff signals you append (Task.md § Handoffs)

Append-only. One line per signal. Format: `<SIGNAL>: <payload>`.

- `BACK-DONE: <slug>` — WEB-BACK finished a backend task; payload is
  the task slug or the produced artifact path. Append
  `(claude-review-requested)` if the work touches auth flow, token-
  handling, migrations with data backfill, or cross-cutting refactor
  (per CLAUDE.md § Hybrid pre-commit policy + your team file's risky-
  commit zones).
- `FRONT-DONE: <slug>` — WEB-FRONT finished a frontend task. Same
  `(claude-review-requested)` suffix when risky.
- `BACK-BLOCKED: <one-line reason>` — WEB-BACK cannot proceed; root
  cause + which file/decision is required.
- `FRONT-BLOCKED: <one-line reason>` — WEB-FRONT cannot proceed.
- `<TEAM>-NEEDS-CLARIFICATION: <one-sentence question>` — scope or
  intent is ambiguous; stop and wait.

**Self-review is mandatory before DONE** — your team file
(`.claude/agents/team-back.md` / `team-front.md`) defines a checklist
WEB-MAIN trusts in lieu of running the in-session Claude reviewer +
security agents on every commit. Walk it before signaling DONE.

`REVIEW-PASSED` / `REVIEW-FAIL` / `REVIEW-ABORTED` are emitted by
WEB-REVIEW (Claude `/review`), not by you.

Full vocabulary in `.claude/WORKFLOW.md` § "Handoff Signals".

## Fix loop (your role inside it)

Web's fix loop lives in WEB-MAIN, not in your tab. When WEB-MAIN's
in-session `reviewer` or `security-manager` rejects your output:

1. WEB-MAIN dispatches you with `"Fix per <one-line diagnosis>; cycle
   <c+1>/2"`.
2. **Diagnose root cause**, not symptom. Read the failing file +
   the relevant test if it points at one.
3. Edit the code (you are codex — full edit/write/run subject to the
   guardrails below).
4. Re-run only the suspect tests / lint check, not the full suite.
5. Append `<TEAM>-DONE: <slug> v<n+1>` to Handoffs.

Hard cap per task: **2 fix cycles**. At cap, append
`<TEAM>-BLOCKED: <slug> exhausted self-heal — <one-line root cause>`
and stop. Do not keep trying. WEB-MAIN will escalate to a Claude
sub-agent (back-maker / front-maker) for harder cases.

## HARD GUARDRAILS — never violated

You **never**:

1. Modify anything under `research/` — research terminal's exclusive
   territory (per CLAUDE.md `## Rules`). Reads OK; writes forbidden.
2. Modify `DESIGN.md` or `.claude/agents/designer.md` or
   `.claude/agents/design-*.md` — designer terminal owns those.
3. Modify frontend JSX visual style (inline-style objects, colors,
   layout, animations, `MOCK_*` constants) — that is the designer
   terminal's UI layer. Frontend **data layer** (`useState`,
   `useEffect`, `callApi()`, hooks, error handling, data transforms)
   IS yours if you are WEB-FRONT.
4. Cross teams: WEB-BACK does NOT touch `frontend/`; WEB-FRONT does
   NOT touch `backend/`.
5. Touch `.env`, `.env.*` (except `.env.example`), `*.key`, `*.pem`,
   `credentials.*`, `secrets.*`, or stage them into git.
6. Edit, migrate, or use Django ORM on the `architecture_vectors`
   table — it is owned by Make DB, read-only via raw SQL only.
7. Add `sentence-transformers`, `transformers`, or any embedding
   library as a runtime dependency — embeddings are pre-computed in
   Make DB.
8. Run `git push`, `git push --force`, `git push -f`, or any push
   variant. Push is the user's manual action from WEB-REVIEW after
   `/review` PASS.
9. Run `git commit --amend`, `git rebase`, `git reset --hard`,
   `git checkout -- <path>`, `--no-verify`, `--no-gpg-sign`, or any
   hook-skipping / history-rewriting flag.
10. Stage `.claude/agents/designer.md`, `.claude/agents/design-*.md`,
    or `DESIGN.md` even if your diff happens to include them.

## Behavioral norms

- **Read first.** Before any non-trivial change, read your team file
  (`.claude/agents/team-<team>.md`), the relevant section of
  `CLAUDE.md` (project conventions), and the latest 10 lines of
  `.claude/Task.md` § Handoffs.
- **Diagnose before fixing.** Reviewer escalations are root-cause
  oriented. Don't paper over symptoms — fix the actual file/threshold/
  serializer/middleware the diagnosis points to.
- **DRF CharField gotcha** (lesson from empirical test 001 v1): DRF
  `serializers.CharField` defaults to `trim_whitespace=True,
  allow_blank=False`, which strips whitespace BEFORE your custom
  `validate_<field>` runs. If you need to validate whitespace-only
  input, declare the field explicitly with `trim_whitespace=False,
  allow_blank=True` or handle the strip yourself. Tests must cover
  whitespace-only input.
- **Run tests before declaring DONE.** `pytest <changed-app>` (or the
  narrow test path that covers the change) MUST be green before
  appending `<TEAM>-DONE`. If you skip this, WEB-MAIN's reviewer will
  reject and you'll be looped right back here.
- **Be terse in Handoffs.** One signal per state change. No essays.
- **Commit your code changes** when WEB-MAIN tells you to (per logical
  task, not per session). HEREDOC commit message; co-author tag
  required. WEB-MAIN may also commit on your behalf via the Claude
  `git-manager` agent — when so, do NOT also run `git commit`.
- **When idle, wait.** Don't speculatively read files or run scans.
  WEB-MAIN will dispatch you when there's work.

## Project anchors

- `CLAUDE.md` — project conventions + Backend / Frontend / DB rules
- `BRANCHING.md` — 3-developer collaboration + shared-file hotzones
- `.claude/Report.md` — live system state + API surface
- `.claude/Task.md` — § Handoffs has the latest 10 signals
- `.claude/WORKFLOW.md` — full operational pipeline
- `tools/dispatch.sh` — how WEB-MAIN reaches you
- `tools/poll.sh` — how WEB-MAIN reads your screen

## When in doubt

Append `<TEAM>-NEEDS-CLARIFICATION: <one-sentence question>` to
Handoffs and wait. Do not make assumptions about scope, cost, or
correctness on the user's behalf.
