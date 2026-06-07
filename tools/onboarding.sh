#!/bin/bash
# onboarding.sh — first-time collaborator onboarding helper.
#
# Run this once after cloning. It will:
#   1. Install the migration-conflict pre-push hook (calls install-hooks.sh)
#   2. Ask for your role (A=Algorithm / B=SNS / C=Admin)
#   3. Ask for your GitHub handle (e.g. yourname → no @ prefix)
#   4. Replace the matching @TODO-role-* placeholder in .github/CODEOWNERS
#      with your handle, in the working tree.
#      NOTE: CODEOWNERS is currently pre-filled with @hongikarchi, so this
#      step is a no-op until a real collaborator's @TODO-role-* placeholder
#      is actually added.
#   5. Print next steps (commit + push CODEOWNERS update via PR).
#
# This script does NOT commit or push — by design. You commit the
# CODEOWNERS edit yourself, on your first feature branch, so the
# audit trail is honest ("user X added themselves as Role A on date Y").
#
# Idempotent: safe to re-run. If your handle already replaced your
# placeholder (or CODEOWNERS is already pre-filled with @hongikarchi and
# no placeholder for your role exists), the script reports "no change" and
# exits 0.
#
# Re-running with a different handle: edit CODEOWNERS manually.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEOWNERS_PATH="$REPO_ROOT/.github/CODEOWNERS"

echo ""
echo "===================================================="
echo "  make_web — onboarding helper"
echo "===================================================="
echo ""

# Step 1: install hooks
echo "Step 1/3: installing local pre-push hook..."
if [ -x "$REPO_ROOT/tools/install-hooks.sh" ]; then
    "$REPO_ROOT/tools/install-hooks.sh"
else
    echo "WARNING: tools/install-hooks.sh not found or not executable. Skipping hook install."
fi
echo ""

# Step 2: collect role
echo "Step 2/3: which role are you?"
echo "  A) Algorithm — backend/apps/recommendation/* + algorithm tests"
echo "  B) SNS / profiles / boards — backend/apps/{social,profiles}/ + frontend profile pages"
echo "  C) Admin — everything else (default catch-all)"
echo ""
read -rp "Enter role [A/B/C]: " role
role=$(echo "$role" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')

case "$role" in
    A|B|C) ;;
    *)
        echo "ERROR: role must be A, B, or C. Got: '$role'" >&2
        exit 1
        ;;
esac

# Step 3: collect GitHub handle
echo ""
read -rp "Enter your GitHub handle (without @, e.g. 'yourname'): " handle
handle=$(echo "$handle" | tr -d '[:space:]@')

if [ -z "$handle" ]; then
    echo "ERROR: handle cannot be empty." >&2
    exit 1
fi

if ! echo "$handle" | grep -qE '^[A-Za-z0-9-]+$'; then
    echo "ERROR: handle '$handle' contains invalid chars (allowed: A-Z, a-z, 0-9, -)." >&2
    exit 1
fi

# Determine which placeholder to replace
case "$role" in
    A) placeholder="@TODO-role-A" ;;
    B) placeholder="@TODO-role-B" ;;
    C) placeholder="@TODO-role-C-admin" ;;
esac

# Sanity-check CODEOWNERS exists
if [ ! -f "$CODEOWNERS_PATH" ]; then
    echo "ERROR: $CODEOWNERS_PATH not found. Are you in the make_web repo root?" >&2
    exit 1
fi

# Check whether placeholder is still present
if ! grep -q "$placeholder" "$CODEOWNERS_PATH"; then
    if grep -q "@$handle" "$CODEOWNERS_PATH"; then
        echo ""
        echo "✓ Looks like @$handle is already in CODEOWNERS for role $role. No change needed."
        exit 0
    else
        echo ""
        echo "WARNING: placeholder '$placeholder' is gone from CODEOWNERS but @$handle is not present either."
        echo "Someone may have manually edited CODEOWNERS. Inspect it yourself:"
        echo "  cat $CODEOWNERS_PATH"
        exit 1
    fi
fi

# Replace placeholder with @handle (in-place; backup)
sed -i.bak "s/${placeholder}/@${handle}/g" "$CODEOWNERS_PATH"
rm -f "${CODEOWNERS_PATH}.bak"

echo ""
echo "===================================================="
echo "  ✓ CODEOWNERS updated locally"
echo "===================================================="
echo ""
echo "  Role: $role"
echo "  Handle: @$handle"
echo "  Placeholder '$placeholder' replaced in $CODEOWNERS_PATH"
echo ""
echo "Step 3/3: commit this change on your first feature branch."
echo ""
echo "  git checkout develop && git pull origin develop"
echo "  git checkout -b feature/$(echo "$role" | tr '[:upper:]' '[:lower:]' | sed 's/^./&/' | sed 's/^a$/algo/;s/^b$/sns/;s/^c$/admin/')-onboarding"
echo "  git add .github/CODEOWNERS"
echo "  git commit -m 'chore: register @${handle} as role ${role} owner in CODEOWNERS'"
echo "  git push -u origin <branch-name>"
echo "  gh pr create --base develop"
echo ""
echo "Then admin reviews + merges your PR. After that, all PRs you open"
echo "that touch your role's files will auto-tag you as a Code Owner."
echo ""
