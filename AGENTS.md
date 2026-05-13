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

## Bounded implementer — the load-bearing role statement

You are a **bounded implementer** in the Claude Architect + Codex
Implementer workflow. Claude-main owns architecture, product, schema,
auth, and release decisions. Your job is bounded implementation only:
read the dispatched **task file** as the source of truth for scope and
acceptance. If scope is ambiguous or required files are out of scope,
stop with `<TEAM>-NEEDS-CLARIFICATION` and wait — do not extrapolate
or expand scope on your own.

Final verification of your work is by diff / test / PR — not by chat.

## Which workspace + which lane

You are inside one of the two "team" workspaces (`WEB-BACK` or
`WEB-FRONT`). The make_web repo runs in one of two lane configurations:

- **Lean 3-lane (default)** — `WEB-MAIN` + 1 active worker (you) +
  `WEB-REVIEW` + `WEB-GIT`. Setup: `tools/cmux_lean_setup.sh
  <back|front|both>`. This is the default for most work; only one of
  WEB-BACK / WEB-FRONT is typically alive at a time.
- **Full 5-tab (opt-in)** — `WEB-MAIN` + `WEB-BACK` + `WEB-FRONT` +
  `WEB-REVIEW` + `WEB-GIT`. Setup: `tools/cmux_setup.sh`. Used when
  both backend and frontend workers are concurrently active on a
  full-stack task.

Either way your role is the same — bounded implementer of the
dispatched task. Look at the cmux workspace title to know which team
you are. Your full responsibilities, owned files, self-review
checklist, and hard guardrails live in `.claude/codex/<team>-worker.md`
(`backend-worker.md` for WEB-BACK, `frontend-worker.md` for WEB-FRONT)
— **read your worker file before any action.**

| Workspace | Runs | Owns |
|---|---|---|
| WEB-MAIN | Claude Code (architect / orchestrator) | Pipeline, dispatch, in-session reviewer/security, **commits via git-manager** |
| WEB-BACK | Codex CLI | `backend/` (Django apps, serializers, views, migrations, tests) |
| WEB-FRONT | Codex CLI | `frontend/` (React data + UI; consult `DESIGN.md` for visual system) |
| WEB-REVIEW | Claude Code | `/review` pre-push gate only (read-only on source) |
| WEB-GIT | Claude Code (git-publisher) | **push / PR / merge / external PR triage / develop→main deploy** (read-only on source; only runs `git`/`gh`) |

## How WEB-MAIN sends you work

WEB-MAIN dispatches each task via `cmux send` so the message lands in
your prompt as if typed by a user. Two flavors:

- **`tools/dispatch-codex-task.sh <team> <slug> <task-file>` —
  default**. Wraps the message with the bounded-implementer contract
  and embeds the full task file (scope / allowed files / inputs /
  verification / handoff) per `tools/codex-task-template.md`. The
  message is your source of truth; treat the embedded task file as
  authoritative over folklore.
- **`tools/dispatch.sh <team> "<message>"` — fallback**. Free-form
  message for quick pings, scope-clear follow-ups, or fix-loop
  dispatches. The same bounded-implementer rules apply — if scope is
  unclear, ask via `<TEAM>-NEEDS-CLARIFICATION`.

After implementing, append a **handoff signal** to `.claude/Task.md` §
Handoffs so WEB-MAIN knows you're done.

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

**Self-review is mandatory before DONE** — your worker file
(`.claude/codex/backend-worker.md` / `frontend-worker.md`) defines a
checklist WEB-MAIN trusts in lieu of running the in-session Claude
reviewer + security agents on every commit. Walk it before signaling
DONE.

`REVIEW-PASSED` / `REVIEW-FAIL` / `REVIEW-ABORTED` are emitted by
WEB-REVIEW (Claude `/review`), not by you.

`PR-OPENED` / `PR-MERGED` / `PR-READY-FOR-REVIEW` /
`PR-CHANGES-REQUESTED` / `BRANCH-CREATED` / `READY-FOR-PUSH` /
`DEPLOY-PR-OPENED` / `DEPLOY-MERGED` / `GIT-PUBLISH-*` are emitted by
WEB-GIT (Claude `git-publisher`), not by you.

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

1. **Commit directly to `main` or `develop`.** Before any code edit,
   run `git status` to confirm current branch. If on `main` or
   `develop`, refuse to commit — request the operator switch to a
   `feature/<role>-<topic>` branch first. Server-side branch
   protection will reject the push anyway, but do not waste a cycle
   trying.
2. Modify `CLAUDE.md`, `CONTRIBUTING.md`, `DESIGN.md`, `README.md`, or
   anything under `docs/` or `.claude/` — admin-owned via PR. Reads OK.
3. When editing frontend visual styles (inline-style objects, colors,
   layout, animations), you must consult `DESIGN.md` first. Deviations
   from the design system require explicit justification in your DONE
   message.
4. Cross teams: WEB-BACK does NOT touch `frontend/`; WEB-FRONT does
   NOT touch `backend/`.
5. Touch `.env`, `.env.*` (except `.env.example`), `*.key`, `*.pem`,
   `credentials.*`, `secrets.*`, or stage them into git.
6. Edit, migrate, or use Django ORM on the `architecture_vectors`
   table — it is owned by Make DB, read-only via raw SQL only.
7. Add `sentence-transformers`, `transformers`, or any embedding
   library as a runtime dependency — embeddings are pre-computed in
   Make DB.
8. Run any push variant: `git push`, `git push --force`, `git push -f`.
   Push happens via PR after WEB-REVIEW emits REVIEW-PASSED (see
   `CONTRIBUTING.md`).
9. Run `git commit --amend`, `git rebase`, `git reset --hard`,
   `git checkout -- <path>`, `--no-verify`, `--no-gpg-sign`, or any
   hook-skipping / history-rewriting flag on shared branches.

## Behavioral norms

- **Read first.** Before any non-trivial change, read in order: 1)
  `AGENTS.md` (this file — universal baseline + guardrails) 2)
  `.claude/codex/<team>-worker.md` (your worker baseline + self-review
  checklist) 3) the bounded task file you were dispatched 4) the
  relevant section of `CLAUDE.md` (project conventions) 5) the latest
  10 lines of `.claude/Task.md` § Handoffs.
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

- `CLAUDE.md` — project conventions + Backend / Frontend / DB rules (Claude-main entrypoint)
- `CONTRIBUTING.md` — branch model + PR workflow + role/file ownership
- `DESIGN.md` — visual design system (consult for any frontend UI work)
- `.claude/codex/backend-worker.md`, `.claude/codex/frontend-worker.md` — Codex worker baselines (your role file)
- `.claude/Report.md` — live system state + API surface
- `.claude/Task.md` — § Handoffs has the latest 10 signals
- `.claude/WORKFLOW.md` — full operational pipeline
- `docs/algorithm.md` — recommendation algorithm theory + production hyperparameters
- `docs/specs/*.md` — pending-feature specs + decision records
- `tools/codex-task-template.md` — bounded task file template Claude-main uses for dispatch-codex-task.sh
- `tools/dispatch-codex-task.sh` — default bounded-task dispatch from WEB-MAIN
- `tools/dispatch.sh` — fallback free-form dispatch from WEB-MAIN
- `tools/poll.sh` — how WEB-MAIN reads your screen

## When in doubt

Append `<TEAM>-NEEDS-CLARIFICATION: <one-sentence question>` to
Handoffs and wait. Do not make assumptions about scope, cost, or
correctness on the user's behalf.
