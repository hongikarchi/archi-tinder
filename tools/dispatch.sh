#!/bin/bash
# dispatch.sh — WEB-MAIN sends a task to a team's cmux workspace.
#
# Usage:    ./tools/dispatch.sh <team> "<message>"
# Example:  ./tools/dispatch.sh back "Add /api/v1/foo/ endpoint per BACK1 spec section §2.3"
#
# Wraps `cmux send` + Enter for the named team's workspace. The message
# is typed into the team's prompt as if a user wrote it; the resident
# agent (codex for WEB-BACK / WEB-FRONT, claude for WEB-REVIEW) treats
# it as a task. Newlines in the message are stripped (cmux send types
# literally).
#
# After dispatch, poll the team's screen with tools/poll.sh and watch
# .claude/Task.md § Handoffs for the team's <SIGNAL>: response.

set -euo pipefail

CMUX=/Applications/cmux.app/Contents/Resources/bin/cmux

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <team> \"<message>\"" >&2
    echo "  team ∈ {back, front, review, git}" >&2
    exit 1
fi

TEAM="$1"
MESSAGE="$2"

WS_NAME="WEB-$(echo "$TEAM" | tr '[:lower:]' '[:upper:]')"

ws_ref=$(
    $CMUX list-workspaces 2>/dev/null \
        | awk -v want="$WS_NAME" '
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
    echo "ERROR: no workspace named '$WS_NAME'" >&2
    echo "  run tools/cmux_setup.sh to create it" >&2
    exit 2
fi

# Surface selection — prefer terminal-type panes over Claude Code special views.
#
# Empirical (2026-05-09 dogfood): cmux list-pane-surfaces may return a surface
# like "* surface:4  ✳ DEEP REVIEW  [selected]" when Claude Code is showing a
# special view (agent dropdown, thinking display, /agents picker, etc.) instead
# of the normal terminal prompt. Sending text to that surface returns
# "Surface is not a terminal" and exits non-zero.
#
# Strategy: gather all surfaces; first prefer ones WITHOUT the ✳ marker
# (terminal panes); if all surfaces have ✳, fall back to the first raw
# surface and let the cmux send error message guide the operator.
all_surfs=$(
    $CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
        | awk '{
            ref=""
            for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { ref=$i; break }
            if (ref == "") next
            # Skip surfaces marked with ✳ — those are non-terminal special views.
            if (index($0, "✳") > 0) next
            print ref
        }'
)
if [ -z "$all_surfs" ]; then
    # No clean terminal surface found; fall back to first raw surface.
    all_surfs=$(
        $CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
            | awk '{for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { print $i; exit }}'
    )
fi
surf_ref=$(echo "$all_surfs" | head -1)

if [ -z "$surf_ref" ]; then
    echo "ERROR: no surface in workspace $ws_ref ($WS_NAME)" >&2
    exit 3
fi

# Pre-flight probe: try a no-op send. If the chosen surface is non-terminal,
# fail FAST with a clear message instead of letting the long-message dispatch
# bomb halfway through.
if ! $CMUX send --workspace "$ws_ref" --surface "$surf_ref" "" >/dev/null 2>&1; then
    echo "ERROR: surface $surf_ref in $WS_NAME is not a terminal pane (probably a Claude Code special view: ✳ marker, /agents picker, thinking display, etc.)" >&2
    echo "Fix: in cmux UI, click the $WS_NAME tab and press Esc to return to the terminal prompt, then re-run dispatch." >&2
    exit 4
fi

# WEB-REVIEW context-bloat mitigation: empirical bug — a /review
# session that has accumulated ~400 KB+ tokens stops processing new
# input cleanly (dispatch message stuck in prompt for ~14 minutes
# before manual Enter nudge resolved it). /review is stateless by
# design (re-reads files each invocation) so dropping prior context
# is free. Auto-/clear before EVERY review dispatch. Opt-out:
# DISPATCH_NO_CLEAR=1 ./tools/dispatch.sh review "..."
if [ "$TEAM" = "review" ] && [ "${DISPATCH_NO_CLEAR:-0}" != "1" ]; then
    $CMUX send --workspace "$ws_ref" --surface "$surf_ref" "/clear" >/dev/null
    $CMUX send-key --workspace "$ws_ref" --surface "$surf_ref" "Enter" >/dev/null
    sleep 3
    printf "[dispatch] %s pre-clear sent\n" "$WS_NAME"
fi

# Strip newlines: cmux send types literally and a multi-line message
# would submit the prompt prematurely on the first \n.
flat_msg=$(printf '%s' "$MESSAGE" | tr '\n' ' ')

# Long-message fallback: cmux send silently truncates messages past
# ~1-2 KB. Empirical: a 2.3 KB BOARD3 plan was dropped entirely on
# first try (codex never saw it; WEB-FRONT scrollback showed no
# dispatched line at all). For anything past 1500 chars, write the
# full plan to a temp file and dispatch a short pointer instead.
LIMIT=1500
if [ ${#flat_msg} -gt "$LIMIT" ]; then
    plan_file="/tmp/dispatch-${TEAM}-$(date +%Y%m%d-%H%M%S).md"
    printf '%s\n' "$MESSAGE" > "$plan_file"
    flat_msg="Long plan: read ${plan_file} and execute. Acceptance + handoff signal format are inside. Append handoff line per the file's instructions when done, then stop."
    printf '[dispatch] %s plan → %s (%d chars; sending pointer)\n' "$WS_NAME" "$plan_file" "${#MESSAGE}"
fi

$CMUX send --workspace "$ws_ref" --surface "$surf_ref" "$flat_msg" >/dev/null
$CMUX send-key --workspace "$ws_ref" --surface "$surf_ref" "Enter" >/dev/null

printf "[dispatch] %s ← %.80s%s\n" "$WS_NAME" "$flat_msg" "$( [ ${#flat_msg} -gt 80 ] && echo '…' )"
