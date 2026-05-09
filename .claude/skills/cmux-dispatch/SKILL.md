---
description: Send a task message to a cmux sub-terminal team (back / front / review / git) via tools/dispatch.sh. Use when WEB-MAIN needs to delegate work to WEB-BACK / WEB-FRONT, trigger /review on WEB-REVIEW, or hand a push to WEB-GIT.
allowed-tools: Bash
---

# cmux-dispatch

Wrap `./tools/dispatch.sh <team> "<message>"` for sending tasks to a stateful
sub-terminal.

## Args (positional)

1. **team** — `back` / `front` / `review` / `git`
2. **message** — the prompt to deliver (newlines auto-stripped; >1500 chars
   auto-saved to `/tmp/dispatch-<team>-<ts>.md` and a pointer is sent
   instead — `dispatch.sh` handles this, no caller action needed)

## Invocation

```bash
./tools/dispatch.sh <team> "<message>"
```

The script handles:
- ESC-force (drops any stuck dropdown / picker / agent menu before send;
  empirically validated 2026-05-09 across two cycles)
- Long-message file fallback (>1500 chars)
- WEB-REVIEW pre-clear (auto-`/clear` before each review dispatch — opt
  out with `DISPATCH_NO_CLEAR=1 ./tools/dispatch.sh review "..."`)

## After dispatch

Poll with `tools/poll.sh <team>` to read the team's screen output, OR use
the `cmux-review-cycle` skill for the dispatch + verdict-poll
combination on review.

## Hard rules

- Never dispatch directly to `WEB-MAIN` (this terminal). dispatch.sh has
  no `main` team and would error out.
- WEB-GIT dispatch is for handing a `READY-FOR-PUSH` instruction; do not
  dispatch source-code edits to it (it commits nothing).
- Codex teams (back / front) auto-load `AGENTS.md` + `team-{back,front}.md`
  on startup; the dispatch should be a task-spec, not an
  agent-orientation.
