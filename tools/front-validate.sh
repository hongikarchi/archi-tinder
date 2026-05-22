#!/bin/bash
# front-validate.sh — front-maker's pre-DONE self-check chain.
#
# Usage:    ./tools/front-validate.sh
#
# Runs in order:
#   1. npm run lint --quiet (ESLint zero-warnings mode)
#   2. npm run build (Vite production build)
#
# Stops on first failure (set -e). Prints a final summary.
#
# Frontend has no migrate step (no schema), so chain is shorter than back.
# Build is mandatory because lint can pass while a runtime import is broken
# (e.g. moved file without updating consumers).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "${REPO_ROOT}/frontend"

# 1. lint
echo "─── 1/2: npm run lint ─────"
npm run lint --silent 2>&1 | tail -20 || {
    echo "✗ ESLint failed"
    exit 1
}
echo "✓ lint clean"
echo ""

# 2. build
echo "─── 2/2: npm run build ─────"
npm run build --silent 2>&1 | tail -10 || {
    echo "✗ Vite build failed"
    exit 2
}
echo ""
echo "✓ front-validate ALL GREEN"
