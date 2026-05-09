#!/bin/bash
# install-hooks.sh — copy repo-tracked hooks into .git/hooks/.
#
# Run this once after cloning. Re-run if hooks/ files change.
# Idempotent: overwrites existing hook with the same name.
#
# Why a manual install step? Git does not version-control .git/hooks/
# (it's local state). The standard pattern is to keep canonical hooks
# under hooks/ in the working tree and copy them on demand.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$REPO_ROOT/hooks"
DST_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$DST_DIR" ]; then
    echo "ERROR: $DST_DIR does not exist. Are you running this from a Git working tree?" >&2
    exit 1
fi

if [ ! -d "$SRC_DIR" ]; then
    echo "ERROR: $SRC_DIR does not exist. Make sure you ran this from the repo root." >&2
    exit 1
fi

installed=0
for hook in "$SRC_DIR"/*; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    cp -f "$hook" "$DST_DIR/$name"
    chmod +x "$DST_DIR/$name"
    echo "[install] $name → .git/hooks/$name"
    installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
    echo "(no hooks found in $SRC_DIR)"
    exit 0
fi

echo ""
echo "✓ Installed $installed hook(s)."
echo "  Test with: git push --dry-run  (the hook will run but no commits transmit)"
