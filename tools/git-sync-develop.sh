#!/usr/bin/env bash
# Sync LOCAL develop to origin/develop, surviving the post-deploy force-reset.
#
# Why: develop->main deploys are squash merges, after which origin/develop is
# force-reset to origin/main (CLAUDE.md HARD RULE 4 carve-out). Any clone that
# did not run the deploy keeps the pre-squash commits on its LOCAL develop, so a
# plain `git pull origin develop` then fails ("not possible to fast-forward") or
# produces a conflict-ridden merge. Local develop must never carry unique work
# (HARD RULE 1: no commits on develop), so when fast-forward is impossible the
# local branch is reset to origin/develop. The old tip is kept as a local backup
# branch so nothing is ever lost.
#
# Usage: tools/git-sync-develop.sh   (leaves you checked out on develop)
set -euo pipefail

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "ERROR: working tree has uncommitted changes to tracked files — commit or stash first." >&2
    exit 1
fi

git fetch origin develop
git checkout develop

if git merge-base --is-ancestor develop origin/develop; then
    git merge --ff-only origin/develop
    echo "✓ develop fast-forwarded to origin/develop @ $(git rev-parse --short HEAD)"
    exit 0
fi

OLD=$(git rev-parse --short develop)
AHEAD=$(git rev-list --count origin/develop..develop)
BACKUP="backup/develop-${OLD}"
git branch -f "${BACKUP}" develop
git reset --hard origin/develop
echo "✓ local develop had diverged (${AHEAD} local-only commits — pre-squash leftovers from a deploy)."
echo "  Reset to origin/develop @ $(git rev-parse --short HEAD). Old tip kept as local branch '${BACKUP}'."
echo "  Delete it once you're sure: git branch -D ${BACKUP}"
