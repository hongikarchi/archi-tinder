#!/bin/bash
# git-stage-and-commit.sh — single safe commit, secret-excluded staging.
#
# Usage:    ./tools/git-stage-and-commit.sh "<commit message first line>" ["<body>"]
# Example:  ./tools/git-stage-and-commit.sh "feat: add Office claim API" \
#                                            "Per PROF1 spec §2.3."
#
# What it does:
#   1. Refuses if on main / develop (server-side ruleset would reject anyway).
#   2. Stages all changes EXCLUDING secret/cache files.
#   3. Verifies no .env/.key/.pem snuck in.
#   4. Creates one commit with the supplied message + Claude co-author tag.
#   5. Never pushes. Push is the git-publish skill's job (git-push-pr.sh).
#
# Invoked by the git-commit skill (the git-manager agent was removed 2026-05-31).
# Operator can call it directly for trivial commits.

set -euo pipefail

# --check mode: validate branch state + show what would be staged. No commit.
if [ "${1:-}" = "--check" ]; then
    echo "git-stage-and-commit.sh --check"
    cur=$(git branch --show-current)
    case "$cur" in
        main|develop) echo "  ✗ on protected branch '$cur' — would refuse"; exit 2 ;;
        feature/*)    echo "  ✓ on feature branch: $cur" ;;
        *)            echo "  ⚠ unusual branch '$cur' — would warn but allow" ;;
    esac
    n_changed=$(git status --porcelain | wc -l | tr -d ' ')
    echo "  → $n_changed files would be staged (excluding secrets)"
    git status --short | head -10
    exit 0
fi

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 \"<message-first-line>\" [\"<message-body>\"]" >&2
    echo "       $0 --check                   # branch + would-stage check only" >&2
    echo "Example: $0 \"feat: add /api/v1/foo/\" \"Per spec §2.3.\"" >&2
    exit 1
fi

SUBJECT="$1"
BODY="${2:-}"

# Branch guard — never commit on protected branches
BRANCH=$(git branch --show-current)
case "$BRANCH" in
    main|develop)
        echo "ERROR: refusing to commit on protected branch '$BRANCH'." >&2
        echo "  Switch to a feature branch first:" >&2
        echo "  ./tools/git-new-feature.sh <role> <topic>" >&2
        exit 2
        ;;
    feature/*)
        ;;
    *)
        echo "WARNING: unusual branch '$BRANCH' — proceeding anyway." >&2
        echo "  Conventional names are 'feature/<role>-<topic>'." >&2
        ;;
esac

# Subject sanity
if [ ${#SUBJECT} -gt 72 ]; then
    echo "ERROR: subject line too long (${#SUBJECT} chars; max 72)." >&2
    echo "  Move details to the body." >&2
    exit 3
fi

# Stage (exclude secrets + cache)
git add --all -- \
    ':(exclude).env' \
    ':(exclude).env.*' \
    ':(exclude)__pycache__' \
    ':(exclude)*.pyc' \
    ':(exclude)*.key' \
    ':(exclude)*.pem' \
    ':(exclude)*.p12' \
    ':(exclude)*.pfx' \
    ':(exclude)credentials.*' \
    ':(exclude)secrets'

# Defense-in-depth: scan staged tree for secret patterns
staged=$(git diff --cached --name-only)
if [ -z "$staged" ]; then
    echo "ERROR: no files staged. Working tree clean?" >&2
    exit 4
fi

if echo "$staged" | grep -qE '\.(env|key|pem|p12|pfx)$|credentials\.|^secrets/'; then
    echo "ERROR: secret-like file slipped past exclude list:" >&2
    echo "$staged" | grep -E '\.(env|key|pem|p12|pfx)$|credentials\.|^secrets/' >&2
    echo "Aborting. Fix .gitignore or unstage manually." >&2
    # Best-effort cleanup: unstage each secret-like path, preserving
    # whitespace-safe filenames (avoid word-split via while-read).
    while IFS= read -r leaked; do
        [ -n "$leaked" ] && git reset HEAD -- "$leaked" >/dev/null 2>&1 || true
    done < <(echo "$staged" | grep -E '\.(env|key|pem|p12|pfx)$|credentials\.|^secrets/' || true)
    exit 5
fi

# Show what's about to be committed
echo "─── Staging ─────────────────────────────────"
git diff --cached --stat
echo "─────────────────────────────────────────────"

# Build commit message
COAUTHOR="Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
if [ -n "$BODY" ]; then
    MSG="${SUBJECT}

${BODY}

${COAUTHOR}"
else
    MSG="${SUBJECT}

${COAUTHOR}"
fi

# Commit
git commit -m "$MSG"

# Report — use diff-tree against the just-created commit; falls back to "?"
# on first-commit-ever (no parent) where diff-tree returns zero rows.
SHA=$(git rev-parse --short HEAD)
COUNT=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | wc -l | tr -d ' ')
COUNT=${COUNT:-?}

echo ""
echo "✓ Committed: $SHA on $BRANCH"
echo "  Subject: $SUBJECT"
echo ""
echo "Next steps:"
echo "  • Pre-push gate (recommended): app-test"
echo "  • Push + PR: git-publisher runs ./tools/git-push-pr.sh"
