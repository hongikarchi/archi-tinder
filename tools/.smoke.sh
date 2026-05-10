#!/bin/bash
# .smoke.sh — environment sanity check for tools/git-*.sh scripts.
#
# Usage:    ./tools/.smoke.sh
#
# Calls --check on every git-* script. Used:
#   - by operators after `git pull` to verify environment
#   - by CI (future, FOLLOWUP-CI-PYTEST follow-up) for early failure detection
#   - by reviewer agents before recommending a script chain
#
# Each --check mode:
#   - validates required environment (branch state, gh auth, network reachability)
#   - prints ✓/✗/⚠ summary
#   - exits 0 on PASS, non-0 on FAIL (script-specific exit codes)
#
# Does NOT take any side-effecting action. Safe to run repeatedly.
#
# Exit code: 0 if all scripts pass --check; non-0 if any script fails.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

scripts=(
    "tools/git-new-feature.sh"
    "tools/git-stage-and-commit.sh"
    "tools/git-push-pr.sh"
    "tools/git-poll-merge.sh"
)

failed=0
total=${#scripts[@]}

echo "─── Smoke test: ${total} git-* script(s) ─────"

for script in "${scripts[@]}"; do
    if [ ! -x "$REPO_ROOT/$script" ]; then
        echo ""
        echo "[FAIL] $script — not found or not executable"
        failed=$((failed + 1))
        continue
    fi
    echo ""
    set +e
    "$REPO_ROOT/$script" --check
    code=$?
    set -e
    if [ "$code" != "0" ]; then
        failed=$((failed + 1))
    fi
done

echo ""
echo "─── Result ─────"
echo "  Total: $total"
echo "  Failed: $failed"

if [ "$failed" = "0" ]; then
    echo "  ✓ ALL CHECKS GREEN"
    exit 0
else
    echo "  ✗ $failed script(s) reported issues"
    exit 1
fi
