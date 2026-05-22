#!/bin/bash
# git-push-pr.sh — push current feature branch + open PR against develop.
#
# Usage:    ./tools/git-push-pr.sh ["<PR title override>"]
#
# What it does:
#   1. Refuses if on main / develop.
#   2. Verifies feature branch has commits ahead of origin/develop.
#   3. Pushes branch to origin (-u for tracking).
#   4. Opens PR against develop with auto-generated title (or override).
#   5. Echoes PR number for downstream tools (git-poll-merge.sh).
#
# Called by:
#   - git-publisher.md Mode 1
#   - operator directly when trivial PR

set -euo pipefail

# --check mode: branch + AHEAD + gh auth check. No push, no PR open.
if [ "${1:-}" = "--check" ]; then
    echo "git-push-pr.sh --check"
    cur=$(git branch --show-current)
    case "$cur" in
        main|develop) echo "  ✗ on protected branch '$cur' — would refuse"; exit 2 ;;
        feature/*)    echo "  ✓ on feature branch: $cur" ;;
        *)            echo "  ⚠ unusual branch '$cur' — would proceed with warning" ;;
    esac
    if ! git fetch origin develop --quiet 2>/dev/null; then
        echo "  ✗ git fetch origin develop failed"; exit 3
    fi
    ahead=$(git rev-list --count "origin/develop..HEAD" 2>/dev/null || echo 0)
    if [ "$ahead" = "0" ]; then
        echo "  ✗ branch not ahead of origin/develop — nothing to PR"; exit 4
    fi
    echo "  ✓ $ahead commits ahead of origin/develop"
    if ! gh auth status >/dev/null 2>&1; then
        echo "  ✗ gh CLI not authenticated (run 'gh auth login')"; exit 5
    fi
    echo "  ✓ gh CLI authenticated"
    exit 0
fi

TITLE_OVERRIDE="${1:-}"

BRANCH=$(git branch --show-current)
case "$BRANCH" in
    main|develop)
        echo "ERROR: refusing to push from protected branch '$BRANCH'." >&2
        exit 2
        ;;
    feature/*)
        ;;
    *)
        echo "WARNING: unusual branch '$BRANCH' — pushing anyway." >&2
        ;;
esac

# Verify there's something to push
git fetch origin develop --quiet
AHEAD=$(git rev-list --count "origin/develop..HEAD")
if [ "$AHEAD" = "0" ]; then
    echo "ERROR: branch '$BRANCH' is not ahead of origin/develop. Nothing to PR." >&2
    exit 3
fi

# Build PR title from latest commit subject if not overridden
if [ -z "$TITLE_OVERRIDE" ]; then
    TITLE=$(git log -1 --pretty=%s)
else
    TITLE="$TITLE_OVERRIDE"
fi

# Push (sets upstream)
echo "─── Pushing $BRANCH → origin/$BRANCH ($AHEAD commits) ─────"
git push -u origin "$BRANCH"

# Build PR body — auto-fill from PR template if possible
COMMITS=$(git log --reverse --pretty="- %s" "origin/develop..HEAD")
TEMPLATE_PATH=".github/PULL_REQUEST_TEMPLATE.md"

if [ -f "$TEMPLATE_PATH" ]; then
    BODY="$(cat "$TEMPLATE_PATH")

---

## Auto-generated commit list

${COMMITS}"
else
    BODY="## Commits

${COMMITS}"
fi

# Open PR
echo "─── Opening PR (target=develop) ───────────────────────────"
PR_URL=$(gh pr create --base develop --head "$BRANCH" \
    --title "$TITLE" \
    --body "$BODY" 2>&1 | tail -1)

# Extract PR number
PR_NUM=$(echo "$PR_URL" | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+$' || echo "?")

echo ""
echo "✓ PR #${PR_NUM} opened: $PR_URL"
echo ""
echo "Next steps:"
echo "  • Poll CI:        ./tools/git-poll-merge.sh ${PR_NUM}"
echo "  • Manual merge:   gh pr merge ${PR_NUM} --squash --delete-branch"
echo ""
echo "Append to .claude/Task.md § Handoffs:"
echo "  PR-OPENED: #${PR_NUM} — ${BRANCH} → develop, ${AHEAD} commits, CI running"
