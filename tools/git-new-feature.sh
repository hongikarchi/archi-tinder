#!/bin/bash
# git-new-feature.sh — sync develop + create new feature branch.
#
# Usage:    ./tools/git-new-feature.sh <role> <topic>
#   role  ∈ {algo, sns, admin}
#   topic = short slug, kebab-case (e.g. "mmr-lambda-tuning")
#
# Result: local branch `feature/<role>-<topic>` checked out from latest origin/develop.
#
# Refuses if:
#   - working tree has uncommitted changes (would lose work)
#   - branch already exists (re-use existing branch)
#   - role is not in {algo, sns, admin}
#
# Idempotent in spirit: safe to run multiple times if you abort and retry,
# as long as you cleaned up the prior failed attempt.

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <role> <topic>" >&2
    echo "  role  ∈ {algo, sns, admin}" >&2
    echo "  topic = short slug (e.g. 'mmr-lambda-tuning')" >&2
    exit 1
fi

ROLE="$1"
TOPIC="$2"

case "$ROLE" in
    algo|sns|admin) ;;
    *)
        echo "ERROR: role must be one of {algo, sns, admin}. Got: '$ROLE'" >&2
        exit 1
        ;;
esac

if ! echo "$TOPIC" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    echo "ERROR: topic must be kebab-case (a-z, 0-9, hyphen). Got: '$TOPIC'" >&2
    exit 1
fi

BRANCH="feature/${ROLE}-${TOPIC}"

# Working tree must be clean
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree has uncommitted changes. Stash or commit first:" >&2
    git status --short >&2
    exit 2
fi

# Refuse if branch already exists locally
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    echo "ERROR: branch '${BRANCH}' already exists locally." >&2
    echo "  To re-use:  git checkout ${BRANCH}" >&2
    echo "  To restart: git branch -D ${BRANCH}  (only if you don't need its commits)" >&2
    exit 3
fi

# Sync develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b "${BRANCH}"

echo ""
echo "✓ Branch created: ${BRANCH}"
echo "  Base: origin/develop @ $(git rev-parse --short HEAD)"
echo ""
echo "Next steps:"
echo "  1. Make your code changes"
echo "  2. Commit: ./tools/git-stage-and-commit.sh \"<message>\""
echo "  3. Run /review in WEB-REVIEW (or skip for trivial commits)"
echo "  4. Push + PR: WEB-GIT runs ./tools/git-push-pr.sh"
