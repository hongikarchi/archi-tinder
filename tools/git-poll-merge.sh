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
#
# `gh pr checks` exit-code reference (verified empirically against gh CLI 2.x
# on PR #6 dogfood, 2026-05-09):
#   0 = all checks pass
#   1 = at least one check FAILED (SilentError)
#   8 = at least one check still PENDING (PendingError)
#   * = unexpected (gh installation issue, auth, etc.)
# Older gh versions (<2.0) overload exit 1 for both fail and pending; if
# that becomes a problem, fall back to keyword-scanning OUTPUT for
# "fail"/"error" on any non-zero exit.

set -euo pipefail

# --check mode: gh auth + PR existence check. No polling.
if [ "${1:-}" = "--check" ]; then
    echo "git-poll-merge.sh --check"
    if ! gh auth status >/dev/null 2>&1; then
        echo "  ✗ gh CLI not authenticated"; exit 5
    fi
    echo "  ✓ gh CLI authenticated"
    if [ -n "${2:-}" ]; then
        if gh pr view "$2" --json number >/dev/null 2>&1; then
            echo "  ✓ PR #$2 exists"
        else
            echo "  ✗ PR #$2 not found"; exit 6
        fi
    else
        echo "  (skip PR existence check — no PR# given)"
    fi
    exit 0
fi

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <PR-number> [timeout_seconds]    # poll CI until green/red/timeout" >&2
    echo "       $0 --check [PR-number]              # gh auth + optional PR existence" >&2
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
    # gh pr checks exit codes: 0=pass, 1=fail, 8=pending (see top-of-file ref)
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
        1)
            # Defense-in-depth: very old gh (<2.0) returned 1 for both fail
            # and pending. If OUTPUT contains only "pending"/"in_progress"
            # markers and no "fail", treat as pending. Otherwise treat as fail.
            FAIL_LINES=$(echo "$OUTPUT" | grep -cE '\bfail\b|\berror\b' || true)
            if [ "$FAIL_LINES" = "0" ] && echo "$OUTPUT" | grep -qE 'pending|in.progress'; then
                PENDING=$(echo "$OUTPUT" | grep -cE 'pending|in.progress' || echo 0)
                echo "[$NOW] +${ELAPSED}s  → still pending (${PENDING} checks; old gh overload)"
            else
                echo "[$NOW] +${ELAPSED}s  → CHECKS FAILED"
                echo "$OUTPUT" | grep -E '(fail|FAIL)' | head -5
                echo ""
                FAILED_RUN=$(gh pr checks "$PR" --json name,state,link 2>/dev/null \
                    | grep -o '"link":"[^"]*"' | head -1 | sed 's/"link":"//;s/"$//' || echo "?")
                echo "Append to .claude/Task.md § Handoffs:"
                echo "  PR-CI-FAIL: #${PR} — checks red after ${ELAPSED}s; logs at ${FAILED_RUN}"
                exit 1
            fi
            ;;
        8)
            PENDING=$(echo "$OUTPUT" | grep -cE 'pending|in.progress' || echo 0)
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
