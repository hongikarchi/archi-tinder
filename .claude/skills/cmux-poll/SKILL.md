---
description: Read recent output from a cmux sub-terminal team (back / front / review / git) via tools/poll.sh. Use to check progress, read handoff signals, or detect "Working..." vs idle state.
allowed-tools: Bash
---

# cmux-poll

Wrap `./tools/poll.sh <team> [lines]` for reading a sub-terminal's screen.

## Args (positional)

1. **team** — `back` / `front` / `review` / `git`
2. **lines** — optional, default 60. Lines of recent screen output to fetch.

## Invocation

```bash
./tools/poll.sh <team>           # default 60 lines
./tools/poll.sh <team> 120       # 120 lines for longer transcripts
```

## Common patterns

### After dispatch — wait then check
```bash
./tools/dispatch.sh back "Add /api/v1/foo/ per spec §2.3"
sleep 60
./tools/poll.sh back 80
# Look for: BACK-DONE / BACK-BLOCKED / NEEDS-CLARIFICATION
```

### Active poll for verdict (review)
```bash
sha=$(git rev-parse --short HEAD)
until grep -E "(REVIEW-PASSED|REVIEW-FAIL|REVIEW-ABORTED): ${sha}" .claude/Task.md ; do
    sleep 60
done
./tools/poll.sh review 30   # read the actual verdict context
```
For this exact pattern, prefer the `cmux-review-cycle` skill which bundles
dispatch + verdict-poll into one invocation.

## What to look for

- **Codex teams (back/front)** — `BACK-DONE` / `FRONT-DONE` /
  `BACK-BLOCKED` / `<TEAM>-NEEDS-CLARIFICATION` in transcript or
  `Task.md ## Handoffs`
- **WEB-REVIEW** — `REVIEW-PASSED` / `REVIEW-FAIL` / `REVIEW-ABORTED` in
  `.claude/Task.md ## Handoffs` (Task.md is more reliable than transcript
  scrape since `/review` writes the verdict atomically)
- **WEB-GIT** — `BRANCH-CREATED` / `PR-OPENED` / `PR-MERGED` /
  `GIT-PUBLISH-{BLOCKED,RETRY,NOOP}` in `Task.md ## Handoffs`

## When NOT to invoke

- Mid-render (Claude Code shows "Working..." or partial output) — wait
  for idle state first.
- Right after `tools/cleanup-after-push.sh` /clear — sub-terminal needs
  ~5-10s to re-init before output is meaningful.
