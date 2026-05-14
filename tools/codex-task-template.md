# Codex Worker Task Template

Use this file as the artifact handoff from Claude-main to a Codex worker.
Dispatch with:

```bash
./tools/dispatch-codex-task.sh <back|front> <slug> <this-file>
```

## Slug
`example-slug`

## Decision Owner
Claude-main owns architecture, product, schema, auth, and release decisions.
Codex implements only the bounded task below.

## Goal
Describe the exact behavior to implement in one or two sentences.

## Allowed Files
- `backend/...` or `frontend/...`

If another file is required, stop and report `<TEAM>-NEEDS-CLARIFICATION`.

## Inputs / Contracts
- API shape, field names, status codes, state shape, or UI behavior locked by Claude-main.
- No new dependency, migration, auth flow, or external service change unless explicitly listed here.

## Implementation Notes
- Follow existing local patterns.
- Keep edits narrow.
- Do not change admin-owned docs or secrets.

## Verification
Run these exact commands:

```bash
# replace with narrow command, for example:
./tools/front-validate.sh
```

## Handoff
After verification and self-review, append one line to `.claude/Task.md`:

```text
FRONT-DONE: example-slug
```

or:

```text
BACK-DONE: example-slug
```

If blocked:

```text
FRONT-BLOCKED: example-slug — <root cause>
```

or:

```text
BACK-BLOCKED: example-slug — <root cause>
```
