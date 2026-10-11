---
name: orchestrate
description: Codex feature playbook — decompose a task, delegate to back-maker / front-maker sub-agents, run code-review + security-manager, fix loop (max 2), commit, browser-verify, audit, publish gate. Optional per AGENTS.md; use it for multi-file features.
---

# Orchestrate (Codex) — feature playbook

`AGENTS.md` makes agents and skills optional for Codex. Use this playbook when a
task spans backend + frontend or needs review before it lands; for a bounded
one-file fix, work directly and still honor the gates in § Commit → Publish.

Shared rules (branch model, publish keywords, data rules, Constitution) are in
`AGENTS.md`; path conventions in `backend/AGENTS.md` / `frontend/AGENTS.md`. This
file only describes the Codex pipeline mechanics.

## Dispatching sub-agents

"Dispatch `<agent>`" = spawn a Codex sub-agent of that name
(`.codex/agents/<agent>.toml`): `back-maker`, `front-maker`, `code-review`,
`security-manager`, `git-publisher`. Give every dispatch a self-contained brief
(files, acceptance criteria, API contract). Spawn code-review and security-manager
together so they run in parallel. If spawning fails, report it and stop — do not
write the feature code yourself in place of the maker.

## Before a task
1. `git status` + branch (HARD RULE 2); check no other session is active in this
   checkout (HARD RULE 7).
2. Read the GitHub Issue for the item (`gh issue list --label now`, `gh issue view <N>`); read the
   code you will touch — the running code is the source of truth.
3. Algorithm work (`engine*.py`, `services/embeddings.py`, `services/rerank.py`,
   hyperparameters) is owned by the algorithm collaborator — surface and decline
   unless the user assigns it.

## Pipeline
1. **Plan** — backend spec (endpoints, models, migrations) + frontend spec
   (components, API calls) + acceptance criteria. Korean summary to the user.
2. **back-maker** — brief = backend spec. It runs `./tools/back-validate.sh` (flake8 →
   migrate-if-needed → pytest). A new migration must be applied locally
   (`make migrate-local` if the maker could not) before browser verification.
3. **front-maker** — brief = frontend spec + the API contract from step 2 + the
   DESIGN.md sections involved. It runs `./tools/front-validate.sh`.
4. **code-review + security-manager** in parallel — brief = changed files + spec.
5. **Decision** — both PASS → step 6. Any FAIL → translate findings into fix orders
   (code-review Mode B) → re-dispatch the maker(s) → re-review. **Max 2 fix cycles**
   total; then stop and report.
6. **Commit** — `git-commit` skill (local only).
7. **browser-verify** skill — SKIP / SMOKE / FEATURE-SCOPED / FULL-SWIPE per the
   changed surface (FULL-SWIPE for recommendation/swipe path). FAIL → one more fix
   cycle if budget remains; ABORTED (drift) → sync and re-run, not a cycle.
8. **Audit** — `reporter-inline` skill (`Closes #N`, deferred → issues, `node tools/gen-state.js`),
   committed on the same branch.
9. **Publish gate** — default STOP. Open only on a trigger word from `AGENTS.md`
   § Working and publishing or an approved plan that authorizes publishing. Then
   `git-publish` (base=develop). `develop → main` is never done here.
10. **Report** — what shipped, commit/PR, verification verdicts, open follow-ups.

## Rules
- Makers are sandboxed: back-maker edits `backend/` only, front-maker `frontend/` only.
- Never push ad-hoc; never `--force` / `--no-verify`; never commit on `main`/`develop`.
- Trivial changes (< 50 LOC, no migration, no auth/network/model change, or pure
  docs) may skip steps 2–5 and 7: edit → `git-commit`.
- Direct edits by the session are fine for `tools/`, `hooks/`, `.github/`, `.codex/`,
  `.agents/`, docs.
