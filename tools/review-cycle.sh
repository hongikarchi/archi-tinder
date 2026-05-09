#!/bin/bash
# review-cycle.sh — dispatch /review to WEB-REVIEW + poll Task.md handoffs
# until a verdict signal appears for the current HEAD SHA.
#
# Usage:    ./tools/review-cycle.sh
#
# Replaces the per-cycle pattern of "dispatch.sh review 'リ뷰해줘' + custom
# polling loop" that WEB-MAIN's Claude was repeatedly authoring per
# push-worthy commit (per docs/token-saving.md Rule 6). One wrapper, one
# call site, consistent polling cadence + grep pattern.
#
# Behavior:
#   1. Capture current HEAD SHA + verify on feature/* branch
#   2. Dispatch "리뷰해줘" to WEB-REVIEW via tools/dispatch.sh
#   3. Poll .claude/Task.md ## Handoffs every 30s for a verdict line
#      matching today's date AND the captured SHA
#   4. Print the verdict line and exit:
#         0 = REVIEW-PASSED
#         1 = REVIEW-FAIL or REVIEW-ABORTED
#         2 = branch / argument refusal
#         3 = TIMEOUT (30min ceiling — `tools/poll.sh review 80` dumped to stderr for triage)
#
# Why a script and not a Claude Code skill: project-local skills under
# .claude/skills/ are visible to ALL cmux workspaces (same cwd), so
# cmux-review-cycle.md auto-invoked from WEB-REVIEW itself, dispatching
# to itself in an infinite loop. Skills don't have a "from terminal X
# only" enforcement mechanism. A plain script invoked by name has no
# auto-invoke surface.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    sed -n '1,28p' "$0" | sed 's/^# \?//'
    exit 0
fi

# --check mode: validate environment without dispatching. For tools/.smoke.sh
# parity, but no smoke entry yet (review-cycle is a higher-level wrapper than
# the git-* group .smoke.sh covers).
if [ "${1:-}" = "--check" ]; then
    echo "review-cycle.sh --check"
    BR=$(git branch --show-current)
    case "$BR" in
        feature/*) echo "  ✓ on feature branch: $BR" ;;
        main|develop) echo "  ✗ on protected branch '$BR' — would refuse"; exit 2 ;;
        *) echo "  ⚠ unusual branch '$BR' — would warn but allow" ;;
    esac
    [ -x "$SCRIPT_DIR/dispatch.sh" ] && echo "  ✓ dispatch.sh executable" || { echo "  ✗ dispatch.sh missing"; exit 4; }
    [ -x "$SCRIPT_DIR/poll.sh" ] && echo "  ✓ poll.sh executable" || { echo "  ✗ poll.sh missing"; exit 4; }
    [ -f .claude/Task.md ] && echo "  ✓ .claude/Task.md exists" || { echo "  ✗ Task.md missing"; exit 4; }
    exit 0
fi

SHA=$(git rev-parse --short HEAD)
BR=$(git branch --show-current)

case "$BR" in
    feature/*) ;;
    main|develop)
        echo "ERROR: not on feature/* branch (on '$BR'). /review is for unpushed feature branches." >&2
        exit 2
        ;;
    *)
        echo "WARNING: unusual branch '$BR' — proceeding anyway." >&2
        ;;
esac

echo "[review-cycle] reviewing ${SHA} on ${BR}"

# Step 1 — dispatch
"$SCRIPT_DIR/dispatch.sh" review "리뷰해줘"

# Step 2 — poll Task.md ## Handoffs for verdict on this SHA
TODAY=$(date +%F)
START=$SECONDS
TIMEOUT=1800   # 30min ceiling (Part B 3-persona × 25-swipe ~15min worst case)
PATTERN="^- \[${TODAY}\] (REVIEW-PASSED|REVIEW-FAIL|REVIEW-ABORTED): ${SHA}"

until grep -E "$PATTERN" .claude/Task.md > /dev/null 2>&1; do
    if [ $((SECONDS - START)) -ge $TIMEOUT ]; then
        echo "TIMEOUT after $((TIMEOUT/60))min — last 80 lines of WEB-REVIEW:" >&2
        "$SCRIPT_DIR/poll.sh" review 80 >&2
        exit 3
    fi
    sleep 30
done

# Step 3 — extract + print verdict
VERDICT=$(grep -E "$PATTERN" .claude/Task.md | tail -1)
echo "─── Verdict for ${SHA} ───"
echo "$VERDICT"

if echo "$VERDICT" | grep -q "REVIEW-PASSED"; then
    exit 0
else
    exit 1
fi
