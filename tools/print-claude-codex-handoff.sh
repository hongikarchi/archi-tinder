#!/bin/bash
# Print the handoff prompt for Claude-main after Codex prepared the lean
# Claude Architect + Codex Implementer workflow.
#
# Usage:
#   ./tools/print-claude-codex-handoff.sh
#   ./tools/print-claude-codex-handoff.sh --check

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

required_files=(
    "tools/cmux_lean_setup.sh"
    "tools/dispatch-codex-task.sh"
    "tools/codex-task-template.md"
    "tools/print-claude-codex-handoff.sh"
)

check() {
    local failed=0

    for path in "${required_files[@]}"; do
        if [ -f "$path" ]; then
            printf "[ok] %s\n" "$path"
        else
            printf "[fail] missing %s\n" "$path"
            failed=$((failed + 1))
        fi
    done

    for path in tools/cmux_lean_setup.sh tools/dispatch-codex-task.sh tools/print-claude-codex-handoff.sh; do
        if [ -x "$path" ]; then
            printf "[ok] executable %s\n" "$path"
        else
            printf "[fail] not executable %s\n" "$path"
            failed=$((failed + 1))
        fi
    done

    if [ "$failed" = "0" ]; then
        exit 0
    fi
    exit 1
}

if [ "${1:-}" = "--check" ]; then
    check
fi

branch="$(git branch --show-current 2>/dev/null || echo unknown)"
status="$(git status --short 2>/dev/null || true)"

cat <<EOF
Codex handoff for Claude-main
=============================

Paste this into Claude Code main:

Codex started a Claude Architect + Codex Implementer workflow refactor.
Current branch: ${branch}

Codex added these implementation artifacts:
- tools/cmux_lean_setup.sh
- tools/dispatch-codex-task.sh
- tools/codex-task-template.md
- tools/print-claude-codex-handoff.sh

Important context:
- Codex intentionally did not edit CLAUDE.md, AGENTS.md, .claude/*, or docs/*
  because the repo guardrails make those admin/Claude-owned.
- Existing dirty .claude/Task.md changes may predate this Codex work. Inspect
  them before staging; do not overwrite or discard them blindly.
- The goal is not to make Claude and Codex chat freely. The goal is artifact
  protocol: Claude owns decisions, Codex receives bounded task files, review/git
  lanes consume diff/test/PR artifacts.

Please do the following:
1. Review the diff on branch ${branch}.
2. Decide whether to adopt the lean workflow.
3. If adopting, update canonical Claude-owned docs/settings:
   - CLAUDE.md
   - .claude/SESSION_PROTOCOL.md
   - .claude/codex/backend-worker.md and frontend-worker.md if needed
   - any Claude memory or agent setting that conflicts with the new protocol
4. Reconcile the new tools with existing cmux workflow:
   - tools/cmux_setup.sh remains the full 5-tab option.
   - tools/cmux_lean_setup.sh is the default lightweight option for most work.
   - tools/dispatch-codex-task.sh dispatches bounded Codex tasks using task files.
5. Add or adjust tests/checks if you want stronger enforcement.
6. After docs/tools agree, use Claude-main as architect and Codex as bounded
   implementer for future development.

Suggested validation before commit:
- bash -n tools/cmux_lean_setup.sh
- bash -n tools/dispatch-codex-task.sh
- bash -n tools/print-claude-codex-handoff.sh
- ./tools/cmux_lean_setup.sh --check
- ./tools/print-claude-codex-handoff.sh --check

Current git status:
${status:-clean}
EOF
