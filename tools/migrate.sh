#!/bin/bash
# migrate.sh — apply Django migrations to local dev DB.
#
# Usage:    ./tools/migrate.sh [app_label]
#
# Without arg: applies all pending migrations across all apps.
# With arg:    applies migrations for one app only.
#
# Why this script exists: maker/team agents need to run migrate after
# generating a new migration file; centralizing the cd + manage.py call
# avoids repeating the same shell incantation across agent prompts.
#
# DB connection: relies on backend/.env (DATABASE_URL or DB_* vars).
#
# Run this with full network access — it connects to Neon. A sandboxed
# context that blocks DNS to Neon fails immediately; that is an environment
# signal, not a script bug (the script just runs manage.py).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-}"

cd "${REPO_ROOT}/backend"

if [ -n "$APP" ]; then
    echo "─── migrate (app=${APP}) ─────"
    python3 manage.py migrate "$APP"
else
    echo "─── migrate (all apps) ─────"
    python3 manage.py migrate
fi

echo ""
echo "✓ migrate complete"
