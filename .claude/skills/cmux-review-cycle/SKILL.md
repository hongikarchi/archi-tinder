---
description: Run a full pre-push /review cycle in WEB-REVIEW. Dispatches "리뷰해줘" (or /review), polls Task.md handoffs until a verdict signal appears for the current HEAD SHA, summarizes the verdict to the operator. Use when committing a push-worthy change per docs/token-saving.md Rule 6.
allowed-tools: Bash
---

# cmux-review-cycle

End-to-end pre-push review automation. Replaces the manual sequence:

1. `./tools/dispatch.sh review "리뷰해줘"`
2. Periodically check Task.md handoffs / WEB-REVIEW transcript
3. Read verdict, summarize, decide next step

with one skill invocation.

## When to invoke

- A **push-worthy commit** just landed (per `docs/token-saving.md` Rule 6 —
  milestone / production-code / migration / risky-zone / explicit user
  request).
- User says "리뷰 돌리자" / "리뷰 시작" / "review now" / "/review 돌려" in
  WEB-MAIN context.
- Bundle accumulator > 5 commits / 24h since first bundle (Rule 6 forced
  push triggers).

## When NOT to invoke

- **Trivial commit** (Rule 2: <50 LOC + no migration + no production
  code + no auth/network/model change). Bundle locally; review at next
  push-worthy.
- **WEB-REVIEW currently busy** — first run `./tools/poll.sh review 5`;
  if you see "Working..." or active output, wait.
- **Branch is `main` / `develop`** — branch protection blocks push
  anyway. /review is for `feature/*` branches against `origin/main..HEAD`.

## Steps

```bash
# 1. Capture current HEAD SHA — this is the "review ticket" anchor
SHA=$(git rev-parse --short HEAD)
echo "[review-cycle] reviewing ${SHA} on $(git branch --show-current)"

# 2. Sanity check — must be on a feature branch
BR=$(git branch --show-current)
case "$BR" in
    feature/*) ;;
    *) echo "ERROR: not on feature/* branch (on '$BR'). Refusing." >&2; exit 2 ;;
esac

# 3. Dispatch the review
./tools/dispatch.sh review "리뷰해줘"

# 4. Poll Task.md handoffs until verdict for this SHA appears.
#    Hard ceiling: 30min (Part B can take 15min for 3-persona × 25-swipe).
START=$SECONDS
TIMEOUT=1800
TODAY=$(date +%F)
until grep -E "^- \[${TODAY}\] (REVIEW-PASSED|REVIEW-FAIL|REVIEW-ABORTED): ${SHA}" .claude/Task.md > /dev/null ; do
    if [ $((SECONDS - START)) -ge $TIMEOUT ]; then
        echo "TIMEOUT after $((TIMEOUT/60))min — check WEB-REVIEW manually" >&2
        ./tools/poll.sh review 80
        exit 3
    fi
    sleep 60
done

# 5. Extract and summarize the verdict line
VERDICT=$(grep -E "^- \[${TODAY}\] (REVIEW-PASSED|REVIEW-FAIL|REVIEW-ABORTED): ${SHA}" .claude/Task.md | tail -1)
echo "─── Verdict for ${SHA} ───"
echo "$VERDICT"
```

## Verdict handling

After Step 5, decide based on the verdict:

- **`REVIEW-PASSED: <sha>` (clean PASS)** → safe to push.
  Hand off to WEB-GIT: `./tools/dispatch.sh git "Push branch + open PR for ${SHA}"`,
  or signal `READY-FOR-PUSH: <branch>` in `.claude/Task.md ## Handoffs`.
- **`REVIEW-PASSED: <sha> — ... PASS-WITH-MINORS, K MINOR noted ...`** →
  push allowed; MINORs are non-blocking. Operator can read `.claude/reviews/latest.md`
  to decide whether to address as bundle-worthy follow-up.
- **`REVIEW-ABORTED: <sha> — HEAD advanced...`** → re-run cycle for new HEAD
  (drift mid-review is normal; no fix needed).
- **`REVIEW-ABORTED: <sha> — origin/main moved...`** →
  `git pull --rebase origin main`, resolve conflicts via Fix Loop, re-run cycle.
- **`REVIEW-FAIL: <sha> — <summary>`** → enter orchestrator Fix Loop (max 2
  cycles per `.claude/agents/orchestrator.md` Step 5b). Read
  `.claude/reviews/latest.md` for findings. After fix + commit, re-run
  this skill (counts toward 2-cycle limit).

## Hard rules

- **Never push from this skill.** Push is WEB-GIT's job (`git-publisher`
  agent, Mode 1). This skill emits the review verdict only.
- **Do NOT read `.claude/reviews/latest.md` by default** — that pulls the
  full 25-30K report into main context (per `docs/token-saving.md` Rule:
  "Don't read full /review reports in main"). Summarize from the handoff
  line; only pull the report on FAIL after the operator asks.
- **Drift safety** — the `<sha>` match in Step 4 is the anchor. If HEAD
  advances locally (you commit something else mid-cycle), the verdict for
  the old SHA may still be valid for that snapshot, but you must re-run
  for the new HEAD before push.

## Estimated tokens

- Dispatch: ~0.1K
- Polling overhead: ~1K (date + grep loop)
- Verdict summary in chat: ~0.5K
- **Total: ~1.5-2K main-session tokens** (vs ~5-10K manual orchestration
  with multiple poll + read + interpret turns)
