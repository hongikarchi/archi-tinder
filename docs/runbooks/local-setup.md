# Runbook — Local development setup (Windows + macOS)

**Audience**: a new collaborator or agent setting up this repo. Both operating systems are supported; every command below goes through `make`, which picks the right Python for your OS (the Windows `python3` is a Microsoft Store stub that prints "Python" and runs nothing — the Makefile detects and avoids it).

Prerequisites: git, GitHub CLI (`gh auth login`), Node 20, Python 3.12 (3.11 works locally; CI and prod use 3.12 per `backend/.python-version`), `make` (macOS: Xcode CLT; Windows: Git Bash + `make` from Chocolatey/Scoop, or run the commands inside WSL).

---

## 1. Clone and install hooks (once per clone)

```bash
git clone https://github.com/hongikarchi/archi-tinder.git make_web
cd make_web
./tools/onboarding.sh      # installs the pre-push migration-numbering hook (= tools/install-hooks.sh) + CODEOWNERS prompt
```

`tools/install-hooks.sh` alone is enough if you only want the hook. Without it you can push a duplicate-numbered Django migration that breaks the team.

## 2. Environment files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Fill `backend/.env` from the values the admin gives you. Rules:
- `DB_*` must point at a **Neon child branch** of `production`, never at the production endpoint (its hostname contains `broad-hat`). The admin provisions one with `neonctl branches create --name local-dev-N --parent production --project-id holy-pond-45504245`. The app DB (`user_data`) and the buildings DB (`archi_data`) may live on different child branches; copy both host values as given.
- `DB_USER=make_web_app` (runtime role, no DDL). `BUILDINGS_DB_USER=make_web` (SELECT-only). Never put `neondb_owner` in `.env`.
- `REDIS_URL` empty locally (LocMemCache fallback). LLM keys optional until you touch search/report code.
- `frontend/.env`: `VITE_API_BASE_URL=http://localhost:8001`, `VITE_GOOGLE_CLIENT_ID`, and `VITE_DEV_LOGIN_SECRET` matching the backend `DEV_LOGIN_SECRET` (dev-login button only renders in `import.meta.env.DEV`).

## 3. Install dependencies and run

```bash
make setup        # backend venv deps + migrate (needs owner creds for DDL, see §4) + superuser + npm install
make dev          # backend :8001 + frontend :5174 together (fails loudly if a port is already bound)
make backend      # backend only
make frontend     # frontend only
```

Windows note: create the venv as `backend/.venv` so the Makefile finds `.venv/Scripts/python.exe`:

```bash
cd backend && py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```

macOS: `cd backend && python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt`.

## 4. Keep your local DB schema current

Git moves migration *files*; your local DB schema only changes when you migrate. Nothing auto-migrates (local or prod). After every `tools/git-sync-develop.sh` that brought migrations:

```bash
make migrate-local        # prompts for the neondb_owner password (read -s; never written anywhere); DDL hits your child branch only
```

The target keeps `DB_HOST`/`DB_NAME` from your `.env` and injects `DB_USER=neondb_owner` inline for that one command (`settings.py` loads `.env` with `override=False`, so inline env wins). Your `.env` stays on `make_web_app`.

Symptoms of a stale local schema: `column X does not exist` 500s, `app-test` "unapplied migrations" gate, orphan NOT NULL columns on `recommendation_analysissession` (local-only; fix via `neondb_owner`, never on prod — see memory `project_local_orphan_columns`).

## 5. Tests and checks

```bash
make test-local ARGS="-x -k liked_buildings"   # CI-shape pytest on real Postgres+pgvector; creates/drops test_<DB_NAME> as neondb_owner
./tools/back-validate.sh [app_label]           # flake8 → migrate-if-needed → pytest (what back-maker runs)
./tools/front-validate.sh                      # eslint + build
./tools/check-frontend.sh
```

Plain `pytest` fails with `permission denied to create database` because `make_web_app` lacks CREATEDB — use `make test-local`. CI (`.github/workflows/ci.yml`) is the canonical gate: Python 3.12, pgvector/pg16, `makemigrations --check`, pytest, eslint, build.

## 6. Branch workflow (summary — full rules in `AGENTS.md`/`CLAUDE.md` HARD RULES and `CONTRIBUTING.md`)

```bash
tools/git-sync-develop.sh                 # NOT `git pull`: survives the post-deploy develop force-reset
git checkout -b feature/<role>-<topic>    # algo- / sns- / admin- / claude- / codex-
# ... work, commit ...
git push -u origin feature/<role>-<topic>
gh pr create --base develop               # the PR template fills the checklist
```

Never commit on `main`/`develop`; never `--force`, `--no-verify`, `rebase -i`, `reset --hard` on shared branches. If another session or person is active in the same checkout, do not switch branches under them.

## 7. OS differences cheat sheet

| Topic | Windows (Git Bash) | macOS |
|---|---|---|
| Python | `python` or `.venv/Scripts/python` — never `python3` | `python3` / `.venv/bin/python` |
| Shell for `make` | Git Bash (Makefile sets `SHELL := /bin/bash`) or WSL | Terminal |
| Git path conversion | `git show origin/develop:path` may be mangled by MSYS; prefix `MSYS_NO_PATHCONV=1` | n/a |
| Symlinks | need Developer Mode + `git config core.symlinks true`; not relied on in this repo | native |
| Port check in `make dev` | needs `lsof` (Git Bash lacks it → install or skip `make dev`, run `make backend` + `make frontend`) | built in |
| Reduced-motion | Windows "show animations" OFF makes Chromium disable smooth scroll; interaction motion ignores it by design | — |

## 8. Where things are

| Need | Location |
|---|---|
| Deploy to production | `docs/runbooks/deploy.md` |
| Branch / PR / roles / file ownership | `CONTRIBUTING.md` |
| Shared rules for humans + AI tools | `AGENTS.md` (Claude Code adds `CLAUDE.md`) |
| Design system | `DESIGN.md` |
| Algorithm theory | `docs/algorithm.md` |
| Building DB schema and ownership | `docs/database-schema.md` |
| Backlog / done log | `Task.md` (moving to GitHub Issues) |
