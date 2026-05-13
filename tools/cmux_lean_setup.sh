#!/bin/bash
# cmux lean setup for Claude Architect + Codex Implementer workflow.
#
# Usage:
#   ./tools/cmux_lean_setup.sh [back|front|both]
#   ./tools/cmux_lean_setup.sh --check
#
# Default creates one Codex worker selected by argument, plus WEB-REVIEW and
# WEB-GIT. Existing workspaces are left alone. This is an opt-in alternative to
# tools/cmux_setup.sh when the operator wants fewer live agent contexts.

set -euo pipefail

CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux
CWD="/Users/kms_laptop/Documents/archi-tinder/make_web"

usage() {
    cat <<EOF
Usage: $0 [back|front|both]
       $0 --check

Creates a lean cmux layout:
  WEB-MAIN   current Claude Architect session
  WEB-BACK   Codex backend worker, if selected
  WEB-FRONT  Codex frontend worker, if selected
  WEB-REVIEW Claude /review gate
  WEB-GIT    Claude git/deploy lane
EOF
}

check() {
    local failed=0
    for bin in "$CMUX" codex claude; do
        if command -v "$bin" >/dev/null 2>&1 || [ -x "$bin" ]; then
            printf "[ok] %s\n" "$bin"
        else
            printf "[fail] %s not found\n" "$bin"
            failed=$((failed + 1))
        fi
    done

    if [ "$failed" = "0" ]; then
        exit 0
    fi
    exit 1
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

if [ "${1:-}" = "--check" ]; then
    check
fi

worker="${1:-back}"
case "$worker" in
    back)
        TEAMS=("WEB-BACK:codex -c model_reasoning_effort=high" "WEB-REVIEW:claude" "WEB-GIT:claude")
        ;;
    front)
        TEAMS=("WEB-FRONT:codex -c model_reasoning_effort=high" "WEB-REVIEW:claude" "WEB-GIT:claude")
        ;;
    both)
        TEAMS=("WEB-BACK:codex -c model_reasoning_effort=high" "WEB-FRONT:codex -c model_reasoning_effort=high" "WEB-REVIEW:claude" "WEB-GIT:claude")
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

init_prompt_codex() {
    local team_lower="$1"
    local team_upper
    team_upper=$(echo "$team_lower" | tr '[:lower:]' '[:upper:]')
    cat <<EOF
You are WEB-${team_upper}, the Codex implementation worker in the lean Claude Architect + Codex Implementer workflow. Claude-main owns architecture, product decisions, risky-change judgment, and release control. Your job is bounded implementation only. Before work, read: 1) AGENTS.md, 2) .claude/codex/${team_lower}end-worker.md, 3) CLAUDE.md conventions, 4) latest .claude/Task.md Handoffs. Do not touch files outside your team ownership or admin-owned docs. If scope is ambiguous, stop with ${team_upper}-NEEDS-CLARIFICATION. When done, run the requested narrow verification, self-review the diff, append ${team_upper}-DONE or ${team_upper}-BLOCKED per AGENTS.md, then report changed files and verification output.
EOF
}

init_prompt_review() {
    cat <<EOF
You are WEB-REVIEW for the lean Claude Architect workflow. Your only job is /review or natural-language review requests. Read CLAUDE.md Pre-Push Review and .claude/commands/review.md. Source is read-only; write only review artifacts and the review handoff line. Stay idle otherwise.
EOF
}

init_prompt_git() {
    cat <<EOF
You are WEB-GIT for the lean Claude Architect workflow. Read .claude/agents/git-publisher.md and CONTRIBUTING.md. You own push, PR, CI poll, merge, and deploy lanes only. Never commit source, never force-push, never push directly to main or develop, and never auto-approve your own PR. Reply ready after gh auth is confirmed.
EOF
}

existing=$($CMUX list-workspaces 2>/dev/null | awk '{
    for (i=1; i<=NF; i++) if ($i !~ /^\*?$/ && $i !~ /^workspace:/ && $i !~ /^\[/) print $i
}')

for spec in "${TEAMS[@]}"; do
    name="${spec%%:*}"
    cmd="${spec##*:}"
    team_lower=$(echo "${name#WEB-}" | tr '[:upper:]' '[:lower:]')

    if echo "$existing" | grep -qx "$name"; then
        printf "[skip] %s already exists\n" "$name"
        continue
    fi

    printf "[new ] %s cmd=%s\n" "$name" "$cmd"
    ws_ref=$($CMUX new-workspace --name "$name" --cwd "$CWD" --command "$cmd" --focus false 2>&1 \
        | awk '/^OK/ {print $2}')
    if [ -z "$ws_ref" ]; then
        echo "failed to capture workspace ref for $name" >&2
        continue
    fi

    sleep 8
    sref=$($CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
        | awk '{for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { print $i; exit }}')
    if [ -z "$sref" ]; then
        echo "no surface for $name; init prompt skipped" >&2
        continue
    fi

    case "$name" in
        WEB-BACK) msg=$(init_prompt_codex back | tr '\n' ' ') ;;
        WEB-FRONT) msg=$(init_prompt_codex front | tr '\n' ' ') ;;
        WEB-REVIEW) msg=$(init_prompt_review | tr '\n' ' ') ;;
        WEB-GIT) msg=$(init_prompt_git | tr '\n' ' ') ;;
        *) msg="Read AGENTS.md and wait for tasks." ;;
    esac

    $CMUX send --workspace "$ws_ref" --surface "$sref" "$msg" >/dev/null
    $CMUX send-key --workspace "$ws_ref" --surface "$sref" "Enter" >/dev/null
    printf "      init prompt sent\n"
done

if ! echo "$existing" | grep -qx "WEB-MAIN"; then
    cur_ws=$($CMUX identify 2>/dev/null \
        | awk -F'"' '/workspace_ref/ {print $4}' | head -1)
    if [ -n "$cur_ws" ]; then
        $CMUX workspace-action --action rename --workspace "$cur_ws" --title "WEB-MAIN" >/dev/null
        printf "[name] WEB-MAIN current workspace renamed\n"
    fi
fi

echo ""
echo "Lean workspaces ready. Dispatch bounded tasks with:"
echo "  ./tools/dispatch-codex-task.sh <back|front> <slug> <task-file>"
