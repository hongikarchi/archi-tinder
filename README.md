# Make Web (archi-tinder)

React + Django web app for the archi-tinder project. Reads from a PostgreSQL DB
built by a sibling repo (Make DB).

For the full picture see:
- `AGENTS.md` — the shared rulebook for humans, Claude Code and Codex (branch rules, publish gate, data rules, Product Constitution). `backend/AGENTS.md`, `frontend/AGENTS.md`, `web-testing/AGENTS.md` add path-scoped conventions.
- `CLAUDE.md` — Claude Code–only additions (workflow, skills, agents, gates); it imports `AGENTS.md`
- `CONTRIBUTING.md` — branch model, PR workflow, role / file ownership
- `docs/runbooks/` — local setup (Windows + macOS) and production deploy
- `DESIGN.md` — visual design system (consult for any UI work)
- `docs/README.md` — map of every doc folder; `docs/algorithm.md` — algorithm design intent; `docs/decisions/` — design decision records
- GitHub Issues — the backlog (`gh issue list`); `Task.md` keeps the `<SURFACE>-<TOPIC>-<N>` ID + label conventions and the migration map

---

## ⚠️ First-time setup (do this once after cloning)

> If you skip this step you will not have the migration-conflict pre-push hook,
> and CODEOWNERS will not auto-assign you for review on PRs you open.

```bash
git clone https://github.com/<org>/<repo>.git
cd make_web
./tools/onboarding.sh           # interactive: hooks + CODEOWNERS handle registration
```

The script installs the hooks and asks for your role + GitHub handle.
`.github/CODEOWNERS` is currently pre-filled with `@hongikarchi` (sole admin) —
no `@TODO-role-*` placeholders remain, so onboarding just flags this. When a real
Role A/B collaborator joins, replace the relevant `@hongikarchi` entries with
their handle on the first feature branch.

Then set up your environment — **Windows and macOS are both supported; use the
`make` targets, which pick the right Python per OS** (on Windows `python3` is a
Store stub that runs nothing). Step-by-step, including Neon child-branch rules,
`.env` fields and the local-migrate / local-test commands:
[`docs/runbooks/local-setup.md`](docs/runbooks/local-setup.md).

```bash
cp backend/.env.example backend/.env     # fill in DB / LLM keys from the admin
cp frontend/.env.example frontend/.env
make setup                               # deps + migrate + superuser + npm install
make dev                                 # backend http://localhost:8001 + frontend http://localhost:5174
```

---

## ⚠️ Branch rules — read this before your first commit

Even if your AI assistant (Claude Code, Cursor, etc.) is doing the
typing, **YOU are responsible for these rules**. Server-side branch protection
will reject violations, but the AI may still try and waste time.

1. **Never commit to `main` or `develop`**. Always work on a `feature/<role>-<topic>` branch:
   - Role A (algorithm) → `feature/algo-<topic>`, e.g. `feature/algo-mmr-tuning`
   - Role B (SNS / profiles / boards) → `feature/sns-<topic>`
   - Role C (admin / everything else) → `feature/admin-<topic>`
   - Local AI agents (Claude Code / Codex) → `feature/claude-<topic>` / `feature/codex-<topic>` (see `CONTRIBUTING.md` § Concurrent agents)
2. **Always sync from `develop` before starting**:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/<role>-<topic>
   ```
3. **PRs target `develop`, not `main`**. The admin batches several develop PRs
   into a `develop → main` PR when ready to deploy to production.
4. **Squash merge** is the merge button to use on GitHub UI (not "Create a merge commit").

If your AI assistant tries to commit directly to `main` or `develop`, **stop it
and tell it to switch to a feature branch first**.

---

## ⚠️ When working with an AI assistant (Claude Code)

If you are a git novice, paste this verbatim into your AI assistant's first
message of a new session:

> Before any work, please:
> 1. Run `git status` and tell me what branch I'm on. If I'm on `main` or
>    `develop`, refuse to commit anything until I'm on a `feature/*` branch.
> 2. Read `CLAUDE.md`, then read the relevant section of `CONTRIBUTING.md`
>    (root) for branch rules.
> 3. Confirm in one sentence what you're about to do and which files you'll
>    touch before you start writing code.

This prompt forces the AI to respect the branch rules and read the project
conventions before touching anything.

---

## Workflow per task (with AI assistant)

```bash
# 1. Sync develop and create your branch
git checkout develop && git pull origin develop
git checkout -b feature/algo-mmr-tuning

# 2. Tell your AI what you want to do
# 3. Review the diff yourself (git diff) — even if AI ran the tests
# 4. Commit (your AI will help with the message)
# 5. Push your branch
git push -u origin feature/algo-mmr-tuning

# 6. Open a PR on GitHub targeting develop (the PR template will guide you)
gh pr create --base develop

# 7. Admin reviews the PR
# 8. After CI green + admin review → admin squash-merges
#    (`gh pr merge --admin --squash`; Code Owner gate self-unsatisfiable for the
#    sole admin, bypassed until collaborators join)

# 9. Local cleanup
git checkout develop && git pull origin develop
git branch -d feature/algo-mmr-tuning
```

---

## Common pitfalls

| Symptom | Cause | Fix |
|--------|------|-----|
| `git push` rejected with "protected branch" | Tried to push to `main` or `develop` | Create a feature branch: `git checkout -b feature/<role>-<topic>` and push that |
| `pre-push` hook says "migration order conflict" | Someone else merged a migration with the same number | `git checkout develop && git pull && git checkout - && git rebase develop`, then `python manage.py makemigrations <app>` to renumber |
| PR shows "1 file is unreviewed" forever | CODEOWNERS is pre-filled with `@hongikarchi`; no `@TODO-role-*` placeholders remain | Add the real collaborator's handle to `.github/CODEOWNERS` and merge via PR |
| CI fails on `makemigrations --check` | Model change without migration file | `cd backend && python manage.py makemigrations <app>` and commit the file |

---

## Architecture (one-liner)

`frontend/` (React 18 + Vite) ↔ `backend/` (Django 4.2 + DRF + pgvector + Gemini)
↔ Neon PostgreSQL (`canonical_v2_buildings` table owned by Make DB, read-only here).

DB schema: `docs/database-schema.md`. Claude Code workflow + agents: `.claude/WORKFLOW.md`. Codex: `AGENTS.md` + `.agents/skills/` + `.codex/` (agents, hooks, rules).
