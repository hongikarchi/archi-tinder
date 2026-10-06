---
paths:
  - "backend/**"
  - "frontend/**"
---

# Claude-only: feature code is delegated, not written by the session

Loads when the session touches a file under `backend/` or `frontend/`.

- The orchestrator session does not write production feature code here. Route the
  change: full feature / unclear-root-cause bug / cross-cutting refactor → the
  `orchestrate` skill (launches the `feature` Workflow); bounded mechanical change
  → `back-maker` (backend) or `front-maker` (frontend) sub-agent, `model: sonnet`.
- Direct edits by the session are fine only for: a comment or path-string fix, a
  single-line policy fix, a sub-MINOR follow-up to a reviewed change, or when the
  user explicitly asks for a direct edit. Say so in the commit body.
- After any backend model change: a migration file in the same PR, applied locally
  with `make migrate-local` before browser verification (the maker agents'
  `tools/back-validate.sh` does this; a 500 "column does not exist" is a stale
  local schema, not a code bug).
- Frontend changes consult `DESIGN.md` first (shared rule in `frontend/AGENTS.md`);
  the `front-maker` agent is briefed with the relevant DESIGN.md section numbers.
