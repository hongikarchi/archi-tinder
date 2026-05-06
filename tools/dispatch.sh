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
    echo "  team ∈ {back, front, review}" >&2
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

surf_ref=$(
    $CMUX list-pane-surfaces --workspace "$ws_ref" 2>/dev/null \
        | awk '{for (i=1;i<=NF;i++) if ($i ~ /^surface:/) { print $i; exit }}'
)

if [ -z "$surf_ref" ]; then
    echo "ERROR: no surface in workspace $ws_ref ($WS_NAME)" >&2
    exit 3
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
