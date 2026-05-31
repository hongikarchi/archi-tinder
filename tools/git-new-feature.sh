#!/bin/bash
# git-new-feature.sh — sync develop + create new feature branch.
#
# Usage:    ./tools/git-new-feature.sh <role> <topic>
#   role  ∈ {algo, sns, admin, claude, codex}
#   topic = short slug, kebab-case (e.g. "mmr-lambda-tuning")
#
# Result: local branch `feature/<role>-<topic>` checked out from latest origin/develop.
#
# Refuses if:
#   - working tree has uncommitted SOURCE-CODE changes (would lose work)
#   - branch already exists (re-use existing branch)
#   - role is not in {algo, sns, admin, claude, codex}
#
# Auto-stashes (and restores after branch creation):
#   - `Task.md` — task-ledger edits
#   - `.claude/resolved-archive.md` — historical resolved entries
#   These are bookkeeping that the next feature commit needs to sweep in.
#
# Idempotent in spirit: safe to run multiple times if you abort and retry,
# as long as you cleaned up the prior failed attempt.

set -euo pipefail

# Path pattern for review-terminal artifacts that are safe to auto-stash.
# Matches against `git status --porcelain` second-field paths.
SAFE_PATHS_REGEX='^Task\.md'

# Helper: list dirty paths (modified + staged + untracked); return only those
# NOT matching SAFE_PATHS_REGEX.
unsafe_dirty_paths() {
    git status --porcelain | sed 's/^...//' | grep -vE "$SAFE_PATHS_REGEX" || true
}

# Helper: list dirty paths matching SAFE_PATHS_REGEX (review artifacts).
safe_dirty_paths() {
    git status --porcelain | sed 's/^...//' | grep -E "$SAFE_PATHS_REGEX" || true
}

# --check mode: validate environment without taking action. Used by tools/.smoke.sh
# and by operators who want to verify branch state before committing.
if [ "${1:-}" = "--check" ]; then
    echo "git-new-feature.sh --check"
    UNSAFE=$(unsafe_dirty_paths)
    SAFE=$(safe_dirty_paths)
    if [ -n "$UNSAFE" ]; then
        echo "  ✗ working tree has uncommitted SOURCE changes (would refuse):"
        echo "$UNSAFE" | sed 's/^/      /'
        exit 2
    fi
    if [ -n "$SAFE" ]; then
        echo "  ⚠ review-terminal artifacts dirty (would auto-stash):"
        echo "$SAFE" | sed 's/^/      /'
    fi
    cur=$(git branch --show-current)
    echo "  ✓ no blocking dirty paths; current branch: $cur"
    if ! git fetch origin develop --quiet 2>/dev/null; then
        echo "  ✗ git fetch origin develop failed (network or remote issue)"
        exit 3
    fi
    echo "  ✓ origin/develop reachable"
    exit 0
fi

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <role> <topic>          # create new feature branch" >&2
    echo "       $0 --check                 # environment sanity check only" >&2
    echo "  role  ∈ {algo, sns, admin, claude, codex}" >&2
    echo "  topic = short slug (e.g. 'mmr-lambda-tuning')" >&2
    exit 1
fi

ROLE="$1"
TOPIC="$2"

case "$ROLE" in
    algo|sns|admin|claude|codex) ;;
    *)
        echo "ERROR: role must be one of {algo, sns, admin, claude, codex}. Got: '$ROLE'" >&2
        exit 1
        ;;
esac

if ! echo "$TOPIC" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    echo "ERROR: topic must be kebab-case (a-z, 0-9, hyphen). Got: '$TOPIC'" >&2
    exit 1
fi

BRANCH="feature/${ROLE}-${TOPIC}"

# Refuse only on SOURCE-CODE dirty. Review artifacts auto-stash below.
UNSAFE=$(unsafe_dirty_paths)
if [ -n "$UNSAFE" ]; then
    echo "ERROR: working tree has uncommitted source-code changes. Stash or commit first:" >&2
    echo "$UNSAFE" | sed 's/^/    /' >&2
    exit 2
fi

# Refuse if branch already exists locally
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    echo "ERROR: branch '${BRANCH}' already exists locally." >&2
    echo "  To re-use:  git checkout ${BRANCH}" >&2
    echo "  To restart: git branch -D ${BRANCH}  (only if you don't need its commits)" >&2
    exit 3
fi

# Auto-stash review-terminal artifacts (handoffs / reviews / postmortems).
# These need to be carried into the new feature branch and bundled with the
# next commit (per the long-standing "review terminal is read-only on source
# code but writes Task.md handoffs" pattern — see CONTRIBUTING.md § Review).
SAFE=$(safe_dirty_paths)
STASHED=0
if [ -n "$SAFE" ]; then
    echo "Auto-stashing review-terminal artifacts:"
    echo "$SAFE" | sed 's/^/    /'
    # shellcheck disable=SC2086
    git stash push -u -m "auto-stash-for-${BRANCH}" -- $(echo "$SAFE" | tr '\n' ' ')
    STASHED=1
fi

# Sync develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b "${BRANCH}"

# Restore stash on the new branch
if [ "$STASHED" = "1" ]; then
    git stash pop
    echo "✓ Review-terminal artifacts restored to ${BRANCH}"
fi

echo ""
echo "✓ Branch created: ${BRANCH}"
echo "  Base: origin/develop @ $(git rev-parse --short HEAD)"
echo ""
echo "Next steps:"
echo "  1. Make your code changes"
echo "  2. Commit: ./tools/git-stage-and-commit.sh \"<message>\""
echo "  3. Pre-push gate: app-test (or skip for trivial commits)"
echo "  4. Push + PR: git-publish skill (git-publisher agent only for Mode 3 / edge cases)"
