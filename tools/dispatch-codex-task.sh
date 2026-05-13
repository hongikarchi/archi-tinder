#!/bin/bash
# Dispatch a bounded implementation task to a Codex team worker.
#
# Usage:
#   ./tools/dispatch-codex-task.sh <back|front> <slug> <task-file>
#
# The task file is the handoff artifact from Claude Architect to Codex. It
# should include scope, files allowed, acceptance criteria, and verification
# commands. This wrapper adds the worker contract and delegates to dispatch.sh.

set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <back|front> <slug> <task-file>" >&2
    exit 1
fi

team="$1"
slug="$2"
task_file="$3"

case "$team" in
    back|front) ;;
    *)
        echo "ERROR: team must be 'back' or 'front'" >&2
        exit 2
        ;;
esac

if [ ! -f "$task_file" ]; then
    echo "ERROR: task file not found: $task_file" >&2
    exit 3
fi

if [ ! -r "$task_file" ]; then
    echo "ERROR: task file not readable: $task_file" >&2
    exit 4
fi

team_upper=$(echo "$team" | tr '[:lower:]' '[:upper:]')
task_body=$(sed 's/[[:space:]]\+$//' "$task_file")

message=$(cat <<EOF
Task slug: ${slug}
Role: WEB-${team_upper} Codex implementation worker.
Decision owner: Claude-main. Do not make product, architecture, schema, auth, or release decisions beyond this task file.
Scope rule: edit only files explicitly allowed by the task file and your team ownership. If needed files are outside scope, stop with ${team_upper}-NEEDS-CLARIFICATION.
Verification rule: run the exact narrow checks listed in the task file. If they fail twice, stop with ${team_upper}-BLOCKED and the root cause.
Completion rule: self-review diff, report changed files + verification command/output summary, and append ${team_upper}-DONE: ${slug} or ${team_upper}-BLOCKED per AGENTS.md.

--- TASK FILE START ---
${task_body}
--- TASK FILE END ---
EOF
)

"$(dirname "$0")/dispatch.sh" "$team" "$message"
