#!/bin/bash
# test-backend.sh — pytest wrapper for backend.
#
# Usage:
#   ./tools/test-backend.sh                   # all tests
#   ./tools/test-backend.sh apps/foo/tests    # narrow path
#   ./tools/test-backend.sh -k "test_create"  # pytest -k filter (passed through)
#
# Prints last 20 lines of pytest output (full results in stderr if needed).
# Exit code = pytest's exit code (0 = green, non-0 = at least one failure).
#
# pytest config lives in backend/pytest.ini + backend/conftest.py (sets
# DJANGO_SETTINGS_MODULE + SQLite override for fast tests).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}/backend"

echo "─── pytest $* ─────"

# Pass all args through to pytest. Default to -v if no args.
if [ "$#" -eq 0 ]; then
    python3 -m pytest -v 2>&1 | tail -25
else
    python3 -m pytest "$@" -v 2>&1 | tail -25
fi
