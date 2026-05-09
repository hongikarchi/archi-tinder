#!/bin/bash
# git-poll-merge.sh — poll PR CI status until green/red/timeout.
#
# Usage:    ./tools/git-poll-merge.sh <PR-number> [timeout_seconds]
# Example:  ./tools/git-poll-merge.sh 12 600
#
# Default timeout: 600 (10 min).
#
# Exits with:
#   0  = all checks GREEN
#   1  = at least one check FAILED
#   2  = timeout reached, still PENDING
#   3  = PR not found / gh error
#
# Stdout: one status line per poll cycle (every 30s).
# Stderr: errors only.
#
# Does NOT merge — that's the caller's choice (operator manual or
# git-publisher.md Mode 1 step 6).

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <PR-number> [timeout_seconds]" >&2
    exit 3
fi

PR="$1"
TIMEOUT="${2:-600}"
INTERVAL=30
ELAPSED=0

# Verify PR exists
if ! gh pr view "$PR" --json number >/dev/null 2>&1; then
    echo "ERROR: PR #$PR not found" >&2
    exit 3
fi

echo "─── Polling PR #$PR (timeout=${TIMEOUT}s, interval=${INTERVAL}s) ───"

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    # gh pr checks exits 0=pass, 8=fail, 1=running
    set +e
    OUTPUT=$(gh pr checks "$PR" 2>&1)
    CODE=$?
    set -e

    NOW=$(date +%H:%M:%S)
    case "$CODE" in
        0)
            echo "[$NOW] +${ELAPSED}s  → ALL CHECKS GREEN"
            echo ""
            echo "Append to .claude/Task.md § Handoffs:"
            echo "  PR-CI-GREEN: #${PR} — passed in ${ELAPSED}s"
            exit 0
            ;;
        8)
            echo "[$NOW] +${ELAPSED}s  → CHECKS FAILED"
            echo "$OUTPUT" | grep -E '(fail|FAIL)' | head -5
            echo ""
            FAILED_RUN=$(gh pr checks "$PR" --json name,state,link 2>/dev/null \
                | grep -o '"link":"[^"]*"' | head -1 | sed 's/"link":"//;s/"$//' || echo "?")
            echo "Append to .claude/Task.md § Handoffs:"
            echo "  PR-CI-FAIL: #${PR} — checks red after ${ELAPSED}s; logs at ${FAILED_RUN}"
            exit 1
            ;;
        1)
            PENDING=$(echo "$OUTPUT" | grep -cE '(pending|in.progress)' || echo 0)
            echo "[$NOW] +${ELAPSED}s  → still pending (${PENDING} checks running)"
            ;;
        *)
            echo "[$NOW] +${ELAPSED}s  → unexpected gh exit code $CODE"
            echo "$OUTPUT" | head -5
            ;;
    esac

    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo ""
echo "TIMEOUT after ${TIMEOUT}s. Re-run later or check manually:"
echo "  gh pr checks ${PR}"
echo ""
echo "Append to .claude/Task.md § Handoffs:"
echo "  PR-CI-TIMEOUT: #${PR} — still pending after ${TIMEOUT}s"
exit 2
