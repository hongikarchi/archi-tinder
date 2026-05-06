# Codex Dispatch Protocol — Stateless cmux + `codex exec`

> Empirically validated 2026-05-06 across 3 PASS commits (`27fee9b`, `042bed4`, `59d2af4`). Use this protocol for any Claude-orchestrated dispatch of mechanical code work to Codex CLI.

## Roles

| Pane | Role | Process state |
|---|---|---|
| `workspace:1 MAIN` (Claude main) | Orchestrator: writes plan, dispatches, validates output via reviewer/security agents, runs git-manager | Long-lived Claude session |
| `workspace:2 BACK` (Codex backend) | **Stateless** Codex CLI invocations for backend tasks | Fresh shell prompt; codex exec spawns + exits per task |
| `workspace:3 FRONT` (Codex frontend) | **Stateless** Codex CLI invocations for frontend tasks | Fresh shell prompt; codex exec spawns + exits per task |
| `workspace:4 REVIEW` (Claude review) | `/review` runs (separate model context) for pre-push gate | Long-lived Claude session |

**Rule**: Codex panes are *invocation surfaces*, not session state. Each task starts a fresh `codex exec` process and ends when it exits. The shell prompt is the only persistent thing in BACK/FRONT.

## Why stateless

- Sentinels are output by a **shell wrapper** (`echo WRAP<NNN>FINISHED`), not Codex. That makes them impossible to false-positive from Codex prompt text echoes (the failure mode in test 003 first attempt — see Lessons below).
- Each task gets isolated context — no cross-task contamination.
- Plan-handoff is file-based (stdin pipe `< plan.md`) — explicit and reproducible.
- `codex exec` exits cleanly on success/failure; idle cost is zero.

## The dispatch sequence

### Step 1 — write a plan file

Path: `.claude/codex-tasks/<NNN>-<slug>.md`. Required sections (see existing 001v2/002/003 plans):

- **Why this task** — empirical or codebase need
- **What to do** — file-by-file spec including code blocks where syntax matters
- **Constraints (hard)** — file scope, no-touch territories, dependency rules
- **Spec for each new function/class** — verbatim code blocks for Codex to copy
- **Spec for each new test** — name, inputs, expected status, assertions
- **CRITICAL: Autonomous test-loop requirement** — MUST run pytest/lint/build until green before signaling DONE; max 3 iterations or BLOCKED
- **Acceptance** — exact pytest/lint/build commands and expected exit
- **Output protocol** — sentinel name (the one Codex itself should print, not the wrapper sentinel)
- **Permission scope** — explicit Read/Edit allow-list; explicit Do NOT list

### Step 2 — verify pane state BEFORE dispatch

```bash
cmux read-screen --workspace workspace:2 --surface surface:2 --lines 5
```

Expected: a clean shell prompt like `kms_laptop@... %`. If you see ANY of:
- A `codex` interactive UI box (`╭─...─╮`)
- A `>` or `›` prompt of any non-shell program
- A pending input line

**STOP and reset the pane** (Ctrl+D twice, or ask user). Dispatching into a non-shell prompt is the false-positive scenario.

### Step 3 — dispatch with shell-wrapper sentinel

```bash
cmux send --workspace workspace:2 --surface surface:2 \
  'codex exec --sandbox workspace-write -C /Users/kms_laptop/Documents/archi-tinder/make_web < .claude/codex-tasks/<NNN>-<slug>.md && echo "WRAP<NNN>FINISHED" || echo "WRAP<NNN>NONZERO"\n'
```

Notes:
- Sentinel format: `WRAP<NNN>FINISHED` / `WRAP<NNN>NONZERO`. Avoid words that the plan or task name uses (would echo back into Codex output and cause false matches).
- `--sandbox workspace-write` = read repo + write into cwd; no network, no `sudo`, no destructive ops. Safe default.
- `-C <abs_repo_path>` keeps Codex anchored to the repo even if BACK pane was elsewhere.
- The trailing `\n` is the Enter that runs the command.

### Step 4 — Monitor for sentinel

Use the harness's `Monitor` tool with the wrapper sentinel as the trigger:

```bash
while true; do
  cur=$(cmux read-screen --workspace workspace:2 --surface surface:2 --lines 30 2>/dev/null | tail -30)
  if echo "$cur" | grep -q "^WRAP<NNN>FINISHED"; then
    echo "DONE codex <NNN> finished cleanly"
    break
  elif echo "$cur" | grep -q "^WRAP<NNN>NONZERO"; then
    echo "FAILED codex <NNN> nonzero exit"
    break
  fi
  sleep 8
done
```

**Anchor with `^`** (start-of-line) so the sentinel matches only when shell echo prints it on its own line — not when the wrapper command itself appears in the user-typed prompt.

Timeout 600-900s typical. For multi-file or test-heavy tasks, 900s+.

### Step 5 — verify the deliverable AFTER sentinel

```bash
git diff --stat <expected_path_glob>
```

If `git diff --stat` shows zero changes, **the sentinel was a false positive** — investigate (was Codex actually running? Did the shell wrapper run inside an interactive prompt?). Do NOT proceed to reviewer.

### Step 6 — reviewer + security in parallel

Spawn both via `Agent` tool with the codex output context, expected files, and verdict format. Use the same agent definitions as for back-maker output — no special "Codex reviewer" needed, the bar is identical.

### Step 7 — fix-loop or commit

- Reviewer + Security both PASS → `git-manager` commit (Co-Authored-By Codex CLI in the message)
- Either FAIL → write Plan v2 with specifics (DRF defaults, ORM gotcha, autonomous-loop reminder, etc.) and re-dispatch (Step 3)
- 2 failed iterations on the same task → stop and use Claude back-maker instead

## Sentinel naming rule

Wrapper sentinel: `WRAP<NNN>FINISHED` / `WRAP<NNN>NONZERO`. Plan-internal sentinel (the one Codex itself prints when its plan-spec is satisfied): `===CODEX-TASK-<NNN>-DONE===` etc.

The **wrapper** sentinel is what the Monitor watches for — it is shell-emitted so it cannot be echoed by Codex prompt text. The **plan-internal** sentinel is a soft contract for Codex (it should also print this if it followed the plan), but Monitor must not rely on it.

## Permission model

`--sandbox workspace-write` allows:
- Read any file in `-C` (repo cwd)
- Write any file in `-C`
- Run subprocesses (pytest, npm, git status etc.)

It does NOT allow:
- Network access
- Writing outside `-C` (cannot touch `~/.config`, `~/.zshrc`, etc.)
- `sudo` or any privilege escalation

Plan must always explicitly deny `git commit`, `git push`, `npm install`, `.env` modification — sandbox doesn't block these on its own.

## Lessons learned (3-PASS empirical cycle)

| Test | Outcome | Lesson |
|---|---|---|
| 001 v1 (single-file) | FAIL — 1 test red | Plan must spec DRF / framework defaults that affect validator reachability. Codex follows plan exactly; missing context = missing code. |
| 001 v2 (retry) | PASS 4/5 | Plan v2 added explicit field declarations + "MUST run pytest before DONE" requirement. Both worked. |
| 002 (mixed-file backend) | PASS 4/5 | Plan-explicit ORM gotcha (`related_name='reactions'` plural) absorbed cleanly. Lazy import pattern absorbed. **Plan-handoff fidelity tax was very low** when plan is fully specified. |
| 003 attempt 1 (frontend) | False positive | BACK pane was inside `codex` interactive (sentinel matched in echoed prompt). **Always read-screen before dispatch.** |
| 003 attempt 2 (FRONT pane, isolated wrapper sentinel) | PASS 4/5 | Designer-territory boundary respected (no JSX). Plan-explicit "STOP — you're out of scope" worked. |

## When NOT to use Codex (use Claude back-maker instead)

- **Open-ended exploration / refactoring** — Codex needs explicit code blocks; back-maker can synthesize from natural language.
- **Cross-cutting changes** spanning >5 files or multiple architectural layers — plan size becomes prohibitive.
- **Bug-fix where root cause is unclear** — back-maker can iterate on diagnosis with full context; Codex starts cold each time.
- **Design-territory work** (frontend UI / inline styles) — owned by `designer` agent, not main pipeline.
- **Algorithm tuning** with subjective output evaluation — back-maker can read research/algorithm.md and reason about trade-offs.

When in doubt: if you can't write a plan with verbatim code blocks for the new functions, you're not ready to dispatch to Codex.
