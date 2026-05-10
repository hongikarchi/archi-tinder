#!/bin/bash
# cleanup-after-push.sh — clear sub-terminal session memory after a push completes.
#
# Usage:    ./tools/cleanup-after-push.sh
#
# Sends `/clear` to WEB-BACK / WEB-FRONT / WEB-REVIEW so each starts the next
# task with a fresh agent context. The codex teams pick up AGENTS.md again
# from cwd-walk; the review terminal already re-reads files per /review
# invocation, so the /clear is mainly to drop accumulated transcript bytes
# (empirical: 2026-05-07 WEB-REVIEW hit 464K stuck-prompt bug; 2026-05-07
# WEB-REVIEW second time hit Anthropic server-side rate limit mid-review).
#
# **WEB-GIT is intentionally NOT auto-cleared.** Empirical (2026-05-09):
# git push/PR/merge cycles produce small transcripts (~10 lines per cycle —
# command output + handoff line), so WEB-GIT doesn't accumulate context the
# way /review reports do. Auto-/clear + re-init was costing ~6.5K Claude
# tokens/cycle (file reads of git-publisher.md + CONTRIBUTING.md + Task.md
# handoffs) for negligible benefit. If WEB-GIT *does* feel bloated (long
# external-PR triage chain, etc.), operator can /clear it manually in cmux UI.
# `gh auth status` is OS-level and survives /clear, so no auth re-verify is
# needed even after a manual /clear.
#
# WEB-MAIN (this Claude session) is NOT touched — Claude self-/clear is not
# possible from inside the same session, and the main session's accumulated
# decisions are load-bearing across the push cycle. Run `/compact` manually
# in WEB-MAIN if context bloat is felt (~30-50% token reduction typical).
#
# After /clear, the codex teams need a fresh init prompt for self-discovery
# (AGENTS.md + team-{back,front}.md + CLAUDE.md + Task.md Handoffs). This
# script auto-sends them.
#
# Idempotent: safe to run repeatedly. If a tab is mid-task it will get a
# /clear interrupt — operator should only run this when all tabs are idle
# (typical state after a push completes).

set -euo pipefail

CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Self-discovery prompt for codex teams (mirrors cmux_setup.sh init_prompt_codex).
init_prompt_codex() {
    local team_lower="$1"
    local team_upper
    team_upper=$(echo "$team_lower" | tr '[:lower:]' '[:upper:]')
    cat <<EOF
You are WEB-${team_upper}, one of the 5 cmux workspaces in the make_web stateful multi-team architecture (WEB-MAIN + WEB-BACK + WEB-FRONT + WEB-REVIEW + WEB-GIT). Before doing any work, read these files in order: 1) AGENTS.md (your baseline + hard guardrails — codex should already have auto-loaded this from cwd) 2) .claude/agents/team-${team_lower}.md (your specific role + owned files) 3) CLAUDE.md (project conventions, especially Backend/Frontend Conventions + Rules) 4) the most recent 10 lines of .claude/Task.md § Handoffs (recent state). After reading, reply with one short sentence confirming you understand your role and your hard guardrails. Then wait for WEB-MAIN to dispatch your first real task via tools/dispatch.sh.
EOF
}

# NOTE: init_prompt_git removed (was here, defined alongside init_prompt_codex).
# WEB-GIT is no longer auto-cleared by this script (see file-header comment),
# so the helper is unused. cmux_setup.sh keeps its own init_prompt_git for the
# one-time tab-creation case.

clear_tab() {
    local team="$1"          # back / front / review
    local agent="$2"         # codex / claude
    local team_upper
    team_upper=$(echo "$team" | tr '[:lower:]' '[:upper:]')
    local ws_name="WEB-$team_upper"

    local ws_ref
    ws_ref=$(
        $CMUX list-workspaces 2>/dev/null \
            | awk -v want="$ws_name" '
                {
                    ref=""
                    for (i=1; i<=NF; i++) if ($i ~ /^workspace:/) { ref=$i; break }
                    if (ref == "") next
                    line=$0
                    sub(/^[* ]*/, "", line)
                    sub(/^workspace:[0-9]+[ \t]*/, "", line)
                    sub(/[ \t]*\[selected\][ \t]*$/, "", line)
                    gsub(/^[ \t]+|[ \t]+$/, "", line)
                    if (line == want) print ref
                }
            ' \
            | head -1
    )
    if [ -z "$ws_ref" ]; then
        printf "[skip ] %s — workspace not found\n" "$ws_name"
        return
    fi

    local sref
    sref=$($CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
            | awk '{for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { print $i; exit }}')
    if [ -z "$sref" ]; then
        printf "[skip ] %s — no surface\n" "$ws_name"
        return
    fi

    # Send /clear + Enter
    $CMUX send --workspace "$ws_ref" --surface "$sref" "/clear" >/dev/null
    $CMUX send-key --workspace "$ws_ref" --surface "$sref" "Enter" >/dev/null
    sleep 4
    printf "[clear] %s — /clear sent\n" "$ws_name"

    # Send init prompt:
    #  - codex teams (back/front): always need re-orientation after /clear
    #  - WEB-REVIEW (claude /review): re-reads files per invocation; no
    #    init needed beyond the next /review call
    if [ "$agent" = "codex" ]; then
        local init_msg
        init_msg=$(init_prompt_codex "$team" | tr '\n' ' ')
        $CMUX send --workspace "$ws_ref" --surface "$sref" "$init_msg" >/dev/null
        $CMUX send-key --workspace "$ws_ref" --surface "$sref" "Enter" >/dev/null
        printf "       ↳ codex init prompt sent\n"
    fi
}

clear_tab back   codex
clear_tab front  codex
clear_tab review claude
# WEB-GIT intentionally skipped — see file-header comment.

echo ""
echo "✓ Cleanup complete. WEB-MAIN should run /compact manually if context"
echo "  feels bloated (Claude cannot self-/clear from inside the session)."
