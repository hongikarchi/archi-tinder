# docs/ — what lives where

| Folder / file | Type | Who writes | Notes |
|---|---|---|---|
| `algorithm.md` | Reference — recommendation **design intent** (phases, formulas, edge cases) | admin + algorithm collaborator via PR; sessions append dated `_(Updated …)_` notes | Product Constitution 6: intent lives here, values live in code |
| `algorithm-hyperparameters.md` | **Generated** table of `RECOMMENDATION` values | `tools/gen-hyperparams.py` (`make hyperparams`); CI fails when stale | never edit by hand; comment keys in `backend/config/settings.py` |
| `database-schema.md` | Reference — Make-DB-owned building tables, ownership rules, `is_publishable` semantics | admin via PR | |
| `report-writing.md` | Reference — persona report prose rules (BACK-LLM-5) | admin via PR; mirrors `services/_report_prompts.py` | |
| `runbooks/` | Operator procedures: `deploy.md`, `local-setup.md` | admin via PR | single source for deploy / setup; other docs link here |
| `decisions/` | Design decision records (ADR-style, Korean): problem → options → decision → open items, with a status line near the top | admin + session via PR | durable; never archived — a superseded record says so in its status line |
| `research/` | Dated research outputs (perf baselines, audits, image-latency findings, one-off reviews) | the session | read-only history; conclusions are recorded in Task.md / decisions |
| `prd/` | Product requirement material (`archibe-business-model.html`) | admin | |
| `design-preview/` | **Generated** HTML bundle for the Claude Design canvas sync | `tools/gen-design-preview.py` after `tokens.css` changes | not a source of truth; regenerate, do not edit |
| `archive/` | Completed hand-offs, point-in-time incident records, and `task-done-2026-04-to-10.md` (the frozen Task.md history) | — | history only; nothing here is a live instruction |
| `db-index-handoff.md` | Open ask to the Make DB owner (HNSW / GIN indexes, 2026-07-07) | admin | partially answered (HNSW exists per `research/perf-baseline-2026-09-30.md`); close or archive once the rest is settled |

Not under `docs/`: shared rules `AGENTS.md` (+ `backend/AGENTS.md`, `frontend/AGENTS.md`,
`web-testing/AGENTS.md`), Claude-only `CLAUDE.md` + `.claude/`, Codex `.codex/` + `.agents/`,
visual design system `DESIGN.md`, branch/PR process `CONTRIBUTING.md`, tracking conventions
`Task.md` (the backlog itself lives in GitHub Issues), execution plans `.claude/plans/` (archived on ship).

Conventions:
- New decision record: `docs/decisions/YYYY-MM-DD-<topic>.md`; first lines = title and a
  status line (proposed / accepted / implemented with PR # / partial / superseded by …),
  then context, options, decision, open items.
- Code that implements a decision cites it by path in a header comment; when a record moves,
  retarget every citation in the same commit (`git grep` the old path = 0).
- Reference docs stay at the `docs/` root so existing citations (skills, agents, code) keep working.
