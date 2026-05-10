#!/bin/bash
# check-frontend.sh — ESLint + build wrapper for frontend.
#
# Usage:
#   ./tools/check-frontend.sh                  # lint all + build
#   ./tools/check-frontend.sh src/pages/X.jsx  # lint specific files only (skips build)
#
# Default mode (no args) runs both `npm run lint` and `npm run build`.
# Targeted mode (with file args) runs only `npx eslint <files>` for speed
# during edit cycles.
#
# Exit code: non-zero if lint OR build fails.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}/frontend"

if [ "$#" -eq 0 ]; then
    echo "─── npm run lint ─────"
    npm run lint --silent 2>&1 | tail -30 || {
        echo "✗ lint failed"
        exit 1
    }

    echo ""
    echo "─── npm run build ─────"
    npm run build --silent 2>&1 | tail -30 || {
        echo "✗ build failed"
        exit 2
    }

    echo ""
    echo "✓ lint + build green"
else
    echo "─── npx eslint (targeted: $#) ─────"
    npx eslint "$@" --max-warnings=0 2>&1 | tail -30
fi
