#!/bin/bash
# back-validate.sh — back-maker's pre-DONE self-check chain.
#
# Usage:    ./tools/back-validate.sh [app_label_for_pytest]
#
# Runs in order:
#   1. flake8 on backend/ (max-line=120, ignore=E501,W503)
#   2. migrate (if there are pending migration files in working tree or staged)
#   3. pytest <app> if app arg given, else pytest all
#
# Stops on first failure (set -e). Prints a final summary.
#
# Empirical: encapsulating these 3 steps in one script saves ~150 chars per
# back-maker prompt across many dispatches; the back-maker.md just says
# "run ./tools/back-validate.sh <app>".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-}"

cd "${REPO_ROOT}/backend"

# 1. flake8
echo "─── 1/3: flake8 ─────"
python3 -m flake8 . --max-line-length=120 --ignore=E501,W503 \
    --exclude='__pycache__,.venv,venv,migrations' || {
    echo "✗ flake8 found issues"
    exit 1
}
echo "✓ flake8 clean"
echo ""

# 2. migrate (only if there are migration files in working tree)
echo "─── 2/3: migrate (if needed) ─────"
PENDING_MIGS=$(git -C "${REPO_ROOT}" diff --name-only HEAD -- 'backend/apps/*/migrations/*.py' \
                | grep -v '__init__.py' || true)
PENDING_MIGS_STAGED=$(git -C "${REPO_ROOT}" diff --cached --name-only -- 'backend/apps/*/migrations/*.py' \
                      | grep -v '__init__.py' || true)
if [ -n "$PENDING_MIGS$PENDING_MIGS_STAGED" ]; then
    echo "  (migration files in working tree → applying)"
    python3 manage.py migrate || {
        echo "✗ migrate failed (DB connection? schema conflict?)"
        exit 2
    }
    echo "✓ migrate applied"
else
    echo "  (no migration files in working tree → skipping)"
fi
echo ""

# 3. pytest
echo "─── 3/3: pytest ─────"
if [ -n "$APP" ]; then
    python3 -m pytest "apps/${APP}/" -v 2>&1 | tail -25 || {
        echo "✗ pytest failed for app=${APP}"
        exit 3
    }
else
    python3 -m pytest -v 2>&1 | tail -25 || {
        echo "✗ pytest failed (full suite)"
        exit 3
    }
fi
echo ""
echo "✓ back-validate ALL GREEN"
