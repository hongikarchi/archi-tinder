# Make Web (archi-tinder)

React + Django web app for the archi-tinder project. Reads from a PostgreSQL DB
built by a sibling repo (Make DB).

For the full picture see:
- `CLAUDE.md` — project conventions, agent rules, DB schema (auto-loaded by Claude Code)
- `AGENTS.md` — codex CLI baseline (auto-loaded by codex CLI)
- `CONTRIBUTING.md` — branch model, PR workflow, role / file ownership
- `DESIGN.md` — visual design system (consult for any UI work)
- `docs/algorithm.md` — recommendation algorithm theory
- `docs/specs/` — pending-feature specs (Phase 16 / 17 / 18)

---

## ⚠️ First-time setup (do this once after cloning)

> If you skip this step you will not have the migration-conflict pre-push hook,
> and CODEOWNERS will not auto-assign you for review on PRs you open.

```bash
git clone https://github.com/<org>/<repo>.git
cd make_web
./tools/onboarding.sh           # interactive: hooks + CODEOWNERS handle registration
```

The script asks for your role (A=Algorithm / B=SNS / C=Admin) and your GitHub
handle, then replaces the matching `@TODO-role-*` placeholder in `.github/CODEOWNERS`.
Commit the CODEOWNERS edit on your first feature branch — see "Common pitfalls"
below.

Then set up your environment:

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then fill in DB / GEMINI / etc.
python3 manage.py runserver 8001 # http://localhost:8001

# Frontend (separate terminal)
cd frontend
npm ci
cp .env.example .env             # if needed
npm run dev                       # http://localhost:5174
```

---

## ⚠️ Branch rules — read this before your first commit

Even if your AI assistant (Claude Code, Codex CLI, Cursor, etc.) is doing the
typing, **YOU are responsible for these rules**. Server-side branch protection
will reject violations, but the AI may still try and waste time.

1. **Never commit to `main` or `develop`**. Always work on a `feature/<role>-<topic>` branch:
   - Role A (algorithm) → `feature/algo-<topic>`, e.g. `feature/algo-mmr-tuning`
   - Role B (SNS / profiles / boards) → `feature/sns-<topic>`
   - Role C (admin / everything else) → `feature/admin-<topic>`
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

## ⚠️ When working with an AI assistant (Claude Code / Codex CLI)

If you are a git novice, paste this verbatim into your AI assistant's first
message of a new session:

> Before any work, please:
> 1. Run `git status` and tell me what branch I'm on. If I'm on `main` or
>    `develop`, refuse to commit anything until I'm on a `feature/*` branch.
> 2. Read `CLAUDE.md` (or `AGENTS.md` if you are codex), then read the
>    relevant section of `CONTRIBUTING.md` (root) for branch rules.
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

# 7. Admin reviews via the WEB-REVIEW terminal /review command
# 8. After CI green + admin approval → admin clicks "Squash and merge"

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
| PR shows "1 file is unreviewed" forever | CODEOWNERS placeholder still has `@TODO-role-*` | Admin replaces placeholders with real GitHub handles |
| CI fails on `makemigrations --check` | Model change without migration file | `cd backend && python manage.py makemigrations <app>` and commit the file |

---

## Architecture (one-liner)

`frontend/` (React 18 + Vite) ↔ `backend/` (Django 4.2 + DRF + pgvector + Gemini)
↔ Neon PostgreSQL (architecture_vectors table owned by Make DB, read-only here).

Full system docs: `.claude/Report.md`.
