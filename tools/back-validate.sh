#!/bin/bash
# back-validate.sh — back-maker's pre-DONE self-check chain.
#
# Usage:    ./tools/back-validate.sh [app_label_for_pytest]
#
# Runs in order:
#   1. flake8 on backend/ (config from backend/.flake8 — no CLI flag overrides)
#   2. unapplied-migration check (report-only: applying needs neondb_owner DDL —
#      INFRA-DB-1 — so the fix is `make migrate-local`, never a bare migrate here)
#   3. pytest <app> if app arg given, else pytest all
#      (DB-backed tests may fail locally: runtime user lacks CREATEDB — INFRA-DB-2.
#       `make test-local` reproduces CI; CI stays the canonical gate.)
#
# Stops on first failure (set -e). Prints a final summary.
#
# PYTHON env var overrides the interpreter (Windows: python3 is a broken
# Store stub — same fix as Makefile #293; default `python`).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-}"
PYTHON="${PYTHON:-python}"

cd "${REPO_ROOT}/backend"

# 1. flake8 — config auto-discovered from backend/.flake8 (no CLI overrides)
echo "─── 1/3: flake8 ─────"
"$PYTHON" -m flake8 . || {
    echo "✗ flake8 found issues"
    exit 1
}
echo "✓ flake8 clean"
echo ""

# 2. unapplied-migration check (report-only — runtime DB user has no DDL)
echo "─── 2/3: migration check ─────"
UNAPPLIED=$("$PYTHON" manage.py showmigrations 2>&1 | grep -E '\[ \]' || true)
if [ -n "$UNAPPLIED" ]; then
    echo "✗ unapplied migrations detected:"
    echo "$UNAPPLIED"
    echo "  → run \`make migrate-local\` (prompts for neondb_owner password), then restart backend"
    exit 2
fi
echo "✓ no unapplied migrations"
echo ""

# 3. pytest
echo "─── 3/3: pytest ─────"
if [ -n "$APP" ]; then
    "$PYTHON" -m pytest "apps/${APP}/" -v 2>&1 | tail -25 || {
        echo "✗ pytest failed for app=${APP} (DB-permission failures? → make test-local)"
        exit 3
    }
else
    "$PYTHON" -m pytest -v 2>&1 | tail -25 || {
        echo "✗ pytest failed (full suite; DB-permission failures? → make test-local)"
        exit 3
    }
fi
echo ""
echo "✓ back-validate ALL GREEN"
