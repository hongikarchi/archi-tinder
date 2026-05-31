# Plans — active only

This directory holds **active** plans only (work currently in flight). When a
plan's work ships — its tasks marked `RESOLVED` in the root `Task.md` — move the
file into `archive/`.

**Why this matters:** the `orchestrate` skill treats an active plan's `## PR Plan`
section as a **publish-gate authorization**. A stale/resolved plan left here can
be mistaken for a live authorization. So completed plans MUST be archived, and
any `## PR Plan` heading renamed to `## Historical PR Plan` before archiving.

`archive/` = historical record. Never executed; references inside may name
removed agents/files (e.g. `git-manager`, `reporter`, `app-test`, deleted pages).
