#!/bin/bash
# cmux 4-workspace setup for make_web (Phase 15 stateful multi-team).
#
# Each team gets its OWN workspace (sidebar entry), mirroring make_db's
# DB-MAIN/CRAWLER/MATCHER/ENRICHER/REVIEWER layout.
#
#   WEB-MAIN     — Claude Code (Opus orchestrator, this session)
#   WEB-BACK     — Codex CLI (writes/fixes backend/*)
#   WEB-FRONT    — Codex CLI (writes/fixes frontend/* data layer)
#   WEB-REVIEW   — Claude Code (Opus, /review pre-push gate)
#
# Each new workspace's first agent message is a self-discovery prompt
# that anchors it to AGENTS.md (codex auto-loads from cwd) + its team
# file (.claude/agents/team-<team>.md). Without this, codex sessions
# would start blank and act inconsistently across reboots / first-runs.
#
# Idempotent: re-running adds missing workspaces only; existing ones
# are left alone (won't kill running agents or re-send init prompts).

set -euo pipefail

CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux
CWD="/Users/kms_laptop/Documents/archi-tinder/make_web"

# team : start_command  (WEB-MAIN excluded — it's the current session)
TEAMS=("WEB-BACK:codex" "WEB-FRONT:codex" "WEB-REVIEW:claude")

# Self-discovery prompt sent on first start. Same template for codex
# teams (WEB-BACK / WEB-FRONT). WEB-REVIEW uses a different prompt
# because it runs Claude Code with the /review slash command.
init_prompt_codex() {
    local team_lower="$1"          # e.g. "back"
    local team_upper
    team_upper=$(echo "$team_lower" | tr '[:lower:]' '[:upper:]')
    cat <<EOF
You are WEB-${team_upper}, one of the 4 cmux workspaces in the make_web stateful multi-team architecture. Before doing any work, read these files in order: 1) AGENTS.md (your baseline + hard guardrails — codex should already have auto-loaded this from cwd) 2) .claude/agents/team-${team_lower}.md (your specific role + owned files) 3) CLAUDE.md (project conventions, especially Backend/Frontend Conventions + Rules) 4) the most recent 10 lines of .claude/Task.md § Handoffs (recent state). After reading, reply with one short sentence confirming you understand your role and your hard guardrails. Then wait for WEB-MAIN to dispatch your first real task via tools/dispatch.sh.
EOF
}

init_prompt_review() {
    cat <<EOF
You are WEB-REVIEW, the pre-push review terminal for make_web. Your only job is the /review slash command (per .claude/commands/review.md and CLAUDE.md § Pre-Push Review). When the user types "리뷰해줘" or "review" or invokes /review, run the gate. Otherwise stay idle. You are READ-ONLY on backend/, frontend/, research/. You write only to .claude/reviews/<sha>.md, .claude/reviews/latest.md, and a one-line REVIEW-PASSED/REVIEW-FAIL/REVIEW-ABORTED signal in .claude/Task.md § Handoffs. Reply with "ready" once you've read CLAUDE.md § Pre-Push Review and .claude/commands/review.md.
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
        printf "[skip ] %-12s — workspace already exists\n" "$name"
        continue
    fi

    printf "[ new ] %-12s — creating with cmd=%s + init prompt\n" "$name" "$cmd"
    ws_ref=$($CMUX new-workspace --name "$name" --cwd "$CWD" --command "$cmd" --focus false 2>&1 \
              | awk '/^OK/ {print $2}')
    if [ -z "$ws_ref" ]; then
        echo "  failed to capture workspace ref — init prompt skipped" >&2
        continue
    fi

    # Wait for the agent (codex/claude) to finish its own startup splash
    # before typing into its prompt. 8s is empirically enough for either.
    sleep 8

    # Find the first surface of the new workspace
    sref=$($CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
            | awk '{for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { print $i; exit }}')
    if [ -z "$sref" ]; then
        echo "  no surface in new workspace $ws_ref — init prompt skipped" >&2
        continue
    fi

    # Send the self-discovery prompt + Enter. Newlines are stripped by
    # cmux send (it types literally), so the heredoc collapses to one
    # long line — perfect for an agent prompt.
    if [ "$cmd" = "claude" ]; then
        msg=$(init_prompt_review | tr '\n' ' ')
    else
        msg=$(init_prompt_codex "$team_lower" | tr '\n' ' ')
    fi
    $CMUX send --workspace "$ws_ref" --surface "$sref" "$msg" >/dev/null
    $CMUX send-key --workspace "$ws_ref" --surface "$sref" "Enter" >/dev/null
    printf "         ↳ init prompt sent to %s (%s)\n" "$name" "$sref"
done

# Ensure WEB-MAIN exists with the right name (this script may run from
# anywhere; if the current workspace is unnamed or named MAIN, rename it).
if ! echo "$existing" | grep -qx "WEB-MAIN"; then
    cur_ws=$($CMUX identify 2>/dev/null \
        | awk -F'"' '/workspace_ref/ {print $4}' | head -1)
    if [ -n "$cur_ws" ]; then
        printf "[name ] WEB-MAIN     — renaming current workspace %s\n" "$cur_ws"
        $CMUX workspace-action --action rename --workspace "$cur_ws" --title "WEB-MAIN" >/dev/null
    fi
fi

echo ""
echo "✓ WEB workspaces ready"
$CMUX list-workspaces | grep -E "WEB-(MAIN|BACK|FRONT|REVIEW)" || true
echo ""
echo "  dispatch:  ./tools/dispatch.sh <team> \"<message>\""
echo "  team ∈ {back, front, review}"
