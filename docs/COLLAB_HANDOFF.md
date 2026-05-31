# Collaborator On-Ramp (Make Web)

**Audience**: New team member joining mid-project (e.g. Make DB owner, Role A
algorithm follow-up). Reads in 5 minutes. Points to existing docs rather than
restating them.

If you already cloned the repo and committed at least once, you have everything.
This file exists so the first day is not a scavenger hunt.

---

## 1. First-day checklist

```bash
git clone git@github.com:hongikarchi/archi-tinder.git
cd archi-tinder
./tools/onboarding.sh
```

`onboarding.sh` installs the migration-conflict pre-push hook and registers
your GitHub handle in `.github/CODEOWNERS`. Without the hook you can push a
duplicate-numbered Django migration that breaks the team. **Do not skip.**

Full background: `CONTRIBUTING.md` § Setup (one-time per clone).

---

## 2. Branch model in one paragraph

`main` is production (Railway auto-deploy). `develop` is integration. You work
on `feature/<role>-<topic>` and PR into `develop`. Admin batches `develop →
main`. **Never commit to `main` or `develop` directly** — server-side
protection will reject the push.

Role prefixes: `algo-` (algorithm), `sns-` (social/profile), `admin-`
(everything else). The Make DB owner uses `db-` or `algo-`; pick one and stay
consistent. Local AI agents (Claude Code / Codex) use `claude-` / `codex-` — see
`CONTRIBUTING.md` § Concurrent agents.

Full rules: `CLAUDE.md` § Branch Model + `CONTRIBUTING.md` § Branch model.

---

## 3. File ownership

`CONTRIBUTING.md` § Roles has the full table. Quick summary:

| Role | Owns |
|------|------|
| A — Algorithm | `backend/apps/recommendation/{engine.py,services/*}`, `RECOMMENDATION` dict in `backend/config/settings.py`, algorithm pytest |
| B — SNS / Profiles | `backend/apps/{social,profiles}/`, social/profile frontend pages |
| C — Admin | Accounts, swipe/sessions/projects/reports views, swipe page, deployment, Django admin |

When a PR touches files outside your row, request review from that row's
owner in the PR description.

---

## 4. What is *not* shared (vs. what is)

The repo is whitelist-style: `.gitignore` excludes everything under `.claude/`
*except* the explicitly whitelisted paths. Here's how it shakes out for a
newcomer:

**Shared (in git, you get them on fetch):**
- `tools/*` (CLI scripts)
- `docs/` (specs, algorithm, database schema)
- `.claude/agents/`, `.claude/skills/` (sub-agent definitions + the orchestrate skill)
- `.claude/Task.md`, `.claude/WORKFLOW.md`, `.claude/plans/`
- Root: `CLAUDE.md`, `CONTRIBUTING.md`, `DESIGN.md`, `README.md`

**Not shared (each clone has its own copy or none):**
- `.claude/settings*.json` (personal harness settings)
- `.claude/memory/` (per-machine auto-memory)
- `.env`, `.env.*` (secrets — use `.env.example` as the template)
- `node_modules/`, `.venv/`, `__pycache__/`, build artifacts

If you fetch the repo and run `claude` from the project root, `CLAUDE.md` and
the agent definitions auto-load. Other contributors' Claude instances therefore
share the same workflow guidance once they pull develop.

---

## 5. The Make Web ↔ Make DB seam

`backend/apps/recommendation/engine.py` reads `canonical_v2_buildings` via raw
SQL (read-only). The table is **owned by Make DB** — never run a Django
migration that touches it.

When the schema changes on Make DB side:

1. Make DB owner opens a PR that updates `docs/database-schema.md` only
   (the contract). Pure docs — no code change here.
2. Make Web admin (or Role A) updates `engine.py` raw SQL field references +
   `_row_to_card()` + `frontend/src/api/client.js:normalizeCard` if the API
   response shape changes.
3. The two PRs land in `develop` in either order; the admin coordinates if
   field renames make them sequential.

If you are the Make DB owner and have read access to this repo: bookmark
`docs/database-schema.md` and `backend/apps/recommendation/engine.py`. Those
are the two files your work intersects.

---

## 6. Past replan (delivered 2026-05-14, deployed 2026-05-14 via PR #36)

The 2026-05-14 Tab 3-Structure Replan (S1-S8) shipped: frontend moved
from 4 tabs to 3 (Discovery / Taste / Profile), DB cutover to
`canonical_v2_buildings` happened in Push S2. The replan shipped via PR #36.

---

## 7. When stuck

- Workflow questions → `.claude/WORKFLOW.md`
- Branch / push errors → `CLAUDE.md` § Branch Model + `CONTRIBUTING.md`
- Algorithm theory → `docs/algorithm.md`
- DB schema → `docs/database-schema.md`
- Anything else → ask the admin (Role C) in chat.
