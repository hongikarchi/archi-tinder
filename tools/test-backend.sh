#!/bin/bash
# test-backend.sh — pytest wrapper for backend.
#
# Usage:
#   ./tools/test-backend.sh                   # all tests (uses local PG if running)
#   ./tools/test-backend.sh apps/foo/tests    # narrow path
#   ./tools/test-backend.sh -k "test_create"  # pytest -k filter (passed through)
#   ./tools/test-backend.sh --ci-shape        # simulate CI (DB_HOST=invalid)
#
# Prints last 20 lines of pytest output. Exit code = pytest's (0 = green).
#
# pytest config: backend/pytest.ini + backend/conftest.py.
#
# ⚠ Local vs CI gap (see backend/conftest.py docstring for the long form):
#   - `django_db_modify_db_settings` fixture overrides DB to SQLite for
#     `@pytest.mark.django_db`-decorated tests, BUT bypassing tests
#     (backend/tests/test_sessions.py / test_topic*.py) connect direct
#     to `DB_HOST:DB_PORT` — your local dev PG if running.
#   - Result: local pytest can pass while CI fails (empirical: PR #10).
#   - `--ci-shape` forces `DB_HOST=nonexistent.invalid`, which makes
#     bypassing tests fail-fast with "Connection refused" — mirrors the
#     CI surface if no PG were available. Use before pushing CI-changing
#     PRs to catch hidden bypasses without waiting for GHA.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}/backend"

if [ "${1:-}" = "--ci-shape" ]; then
    shift
    echo "─── pytest --ci-shape (DB_HOST=nonexistent.invalid) ─────"
    echo "    Bypassing tests will surface 'Connection refused on 5432' if"
    echo "    your local environment is masking CI breakage."
    export DB_HOST=nonexistent.invalid
else
    echo "─── pytest $* ─────"
fi

# Pass all args through to pytest. Default to -v if no args.
if [ "$#" -eq 0 ]; then
    python3 -m pytest -v 2>&1 | tail -25
else
    python3 -m pytest "$@" -v 2>&1 | tail -25
fi
