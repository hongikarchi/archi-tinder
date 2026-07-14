# Contributing to Make Web

3-person team workflow. main + develop + feature/* branches with PR-only landing
and admin review. Read this once before your first commit. Local AI agents
(Claude Code, Codex) are workers too — same model, each in its **own clone** (see
§ Concurrent agents).

## Setup (one-time per clone)

```bash
git clone <repo>
cd make_web
./tools/onboarding.sh    # interactive: installs hooks + registers your CODEOWNERS handle
```

`onboarding.sh` walks you through 3 steps:
1. Installs the migration-conflict pre-push hook (calls `install-hooks.sh`)
2. Asks your role (A=Algorithm / B=SNS / C=Admin)
3. Asks your GitHub handle. `.github/CODEOWNERS` is currently pre-filled with
   `@hongikarchi` (sole admin) — no `@TODO-role-*` placeholders remain, so
   onboarding just flags this. When a real Role A/B collaborator joins, replace
   the relevant `@hongikarchi` entries with their handle (per the CODEOWNERS
   header) on the first feature branch.

If you only want to install hooks (e.g. CODEOWNERS already has your handle),
run `./tools/install-hooks.sh` directly instead.

## Roles

| Role | Owner | Primary territory |
|---|---|---|
| **A** | Algorithm | `backend/apps/recommendation/engine.py`, `backend/apps/recommendation/services/{embeddings,rerank,generation,parse_query,_caches,_gemini}.py`, `backend/config/settings.py` (RECOMMENDATION dict only), `backend/tests/` (algorithm tests: `test_topic*`, `test_hyde`, `test_hybrid_retrieval`, `test_imp*`, `test_chat_phase`, `test_confidence`, etc.) |
| **B** | Post-swipe SNS | `backend/apps/social/`, `backend/apps/profiles/`, `frontend/src/pages/FirmProfilePage.jsx`, `UserProfilePage.jsx`, `BoardDetailPage.jsx`, `frontend/src/api/social.js`, `frontend/src/api/profiles.js`, `frontend/src/components/profile/` (BoardCard, BioPersonaFlipCard, DescriptionAboutFlipCard, ProjectCard, ArticleCard, InfoCol) |
| **C** (admin) | Everything else | `backend/apps/accounts/`, `backend/apps/recommendation/views/sessions.py`, `views/projects.py`, `views/swipe.py`, `views/search.py`, `views/reports.py`, `views/telemetry.py`, `frontend/src/pages/SwipePage.jsx`, `LLMSearchPage.jsx`, `FavoritesPage.jsx`, `LoginPage.jsx`, `ProjectSetupPage.jsx`, Django admin, deployment config |

## Shared / coordinated edit files

These files are touched by 2+ roles. Default merge strategy is **append-only** where possible (new lines at the bottom rarely conflict). For files where order matters, **announce in chat before parallel edits**.

### Append-only safe (low conflict risk)

| File | Why shared | Merge note |
|---|---|---|
| `backend/apps/recommendation/views/__init__.py` | Re-export barrel | New imports go at the bottom |
| `backend/apps/recommendation/services/__init__.py` | Re-export barrel | New imports go at the bottom |
| `frontend/src/api/client.js` | Re-export barrel | New `export * from './<feature>.js'` at the bottom |
| `backend/config/urls.py` | Root URL include — every new Django app gets a line here | Append at the bottom of the `urlpatterns` list |
| `frontend/src/App.jsx` `<Routes>` block | Every new page registers a `<Route>` here | Append new routes at the bottom of `<Routes>` (the surrounding component logic is order-sensitive — see below) |
| `backend/.env.example` / `frontend/.env.example` | New env vars | Append to the bottom; comment what the var does |
| `backend/requirements.txt` | New Python deps | Append; pin versions |

### Order-sensitive (announce before parallel edits)

| File | Why shared | Conflict risk |
|---|---|---|
| `backend/apps/recommendation/serializers.py` | Touchpoint between A's algorithm output and C's API contract | A and C may both add fields — coordinate field names |
| `backend/config/settings.py` | A owns RECOMMENDATION dict + tunable params; B/C add `INSTALLED_APPS`, middleware, throttles | Single file, multiple sections — announce which section you'll edit |
| `frontend/src/App.jsx` (non-`<Routes>` body) | Shared `useEffect`/handlers/imports section | Touch only if a new feature genuinely needs cross-page state plumbing; otherwise stay inside your page |
| `frontend/src/components/profile/InfoCol.jsx` | Tiny shared component (B-extracted, may be reused) | If a non-B role needs to extend it, propose a generalization in PR |
| `frontend/package.json` / `frontend/package-lock.json` | New JS deps | Run `npm install` AFTER pulling main; never hand-edit the lock file; commit both files together |

### Migrations (always coordinate)

Django migrations are numbered per app. Two devs creating `<app>/migrations/0042_*.py` simultaneously will produce duplicate numbers and a broken migration graph.

**Per-feature workflow:**
1. `git checkout develop && git pull origin develop` immediately before `python manage.py makemigrations <app>`.
2. Don't sit on locally-generated migrations for days — merge within ~24h or rebase.
3. The local `hooks/pre-push` (installed via `./tools/install-hooks.sh`) catches duplicate-number conflicts before push. GHA CI also runs `makemigrations --check` as backup.
4. If conflict happens at merge time anyway: second-to-merge regenerates the migration on their branch.

## Branch model — main + develop + feature/*

```
main (production — Railway auto-deploy on push)
 ↑ squash merge from develop (admin manual, after batched verification)
develop (integration — PR target for all feature work)
 ↑ squash merge from feature/<role>-<topic>
feature/algo-<topic>      ← Role A's work branch
feature/sns-<topic>       ← Role B's work branch
feature/admin-<topic>     ← Role C's (admin) work branch
feature/claude-<topic>    ← local Claude Code  (§ Concurrent agents)
feature/codex-<topic>     ← local Codex        (§ Concurrent agents)
```

**Rules:**

1. `main` is **protected** — PR + status check + Code Owner approval required.
2. `develop` is **protected** — PR + status check required. Code Owner review is
   nominally required too, but sole-admin CODEOWNERS = PR author makes it
   structurally unsatisfiable → **admin-bypass squash-merge** (`gh pr merge
   --admin --squash`) is the current workflow until collaborators join (mirrors
   `CLAUDE.md`). The PR + status-check requirement still holds — never direct-push.
3. Each developer creates `feature/<role>-<short-topic>` per task. Examples:
   - `feature/algo-mmr-lambda-tuning`
   - `feature/sns-board-detail-integration`
   - `feature/admin-search-relevance-tweak`
   - `feature/claude-<topic>` / `feature/codex-<topic>` — local AI agents (§ Concurrent agents)
4. PRs target **`develop`**, not `main`.
5. Periodically (when develop has accumulated enough vetted features), admin opens
   a `develop → main` PR and squash-merges to deploy.
6. Merge method: **squash merge** (clean history; one commit per PR).

## Workflow per feature

```bash
# 1. Sync from develop
git checkout develop && git pull origin develop

# 2. New branch
git checkout -b feature/algo-mmr-lambda-tuning

# 3. Work + commit (multiple commits OK; squashed at merge time)
git add .
git commit -m "feat: tune mmr_lambda from 0.7 to 0.6"

# 4. Push (the local pre-push hook checks migration numbering)
git push -u origin feature/algo-mmr-lambda-tuning

# 5. Open PR targeting develop
gh pr create --base develop --title "Algo: MMR lambda 0.7 → 0.6" \
             --body "$(cat <<'EOF'
See PR template (auto-rendered).
EOF
)"

# 6. CI runs (.github/workflows/ci.yml — pytest + lint + makemigrations check).
#    Admin reviews the PR for deeper analysis.

# 7. After admin review + CI green → admin squash-merges with
#    `gh pr merge <N> --admin --squash` (Code Owner review is self-unsatisfiable
#    for the sole admin → bypassed until collaborators join; see Branch model).

# 8. Local cleanup
git checkout develop && git pull origin develop
git branch -d feature/algo-mmr-lambda-tuning
```

## Concurrent agents — one clone per worker (Claude Code + Codex)

This repo is often worked by more than one agent at once. Locally the maintainer
runs **Claude Code** (in a cmux terminal) and **Codex** (in a web browser, for
visual UI/UX) at the same time — on top of the distributed human team above. One
rule keeps all of them from colliding:

> **Every worker — a remote human teammate OR a local AI tool — owns ONE working
> directory with its OWN `.git`, works on its own `feature/*` branch, and opens
> its own PR to `develop`. No worker ever checks out or commits in another
> worker's directory.**

The human team already lives by this: each teammate has their own **clone**, so
their `HEAD`s can never touch. Local AI tools get the same treatment — **each its
own clone** — which makes them first-class workers, indistinguishable from a
remote teammate. There is no special "local multi-agent" model; it is the same
clone-per-worker model.

Two **independent** failure modes — you need both fixes:

| Failure | Cause | Fix |
|---|---|---|
| **HEAD collision** | two sessions share ONE working dir → one `HEAD`; one's `checkout`/`pull` drags the other's | **separate `.git`** (own clone) |
| **Merge conflict** | two workers edit the same files on different branches | **scope split** (assign files per task) |

Scope-naming alone does NOT prevent the HEAD collision; isolation alone does NOT
prevent merge conflicts.

### Mechanism: a separate clone (NOT a worktree)

```bash
# Give a second local agent (e.g. Codex) its OWN clone — its own .git:
git clone <repo-url> ../make_web-codex
cd ../make_web-codex
./tools/install-hooks.sh                     # own clone → own hooks (one-time; a clone's .git is a real dir, so this works)
cp ../make_web/backend/.env backend/.env     # working files are NOT shared between clones
cd frontend && npm install                   # own node_modules
# then launch the agent with ../make_web-codex as its working directory
```

A clone has its **own `.git`** → another tool literally cannot reach in to move a
`HEAD`. We deliberately do **NOT** use `git worktree` for session isolation:
worktrees **share one `.git`**, and on **2026-05-31** that shared `.git` was
exactly how a Codex session moved the main checkout's `HEAD` onto its own branch
(`feature/codex-loginpage`) — the collision recurred *despite* the worktree docs.
The disk cost of a clone over a worktree is only the `.git` objects;
`node_modules`/venv/`.env` are per-directory either way.

### Who works where

| Agent | Launch | Clone | Tendency (a default, NOT a hard wall) |
|---|---|---|---|
| **Claude Code** | cmux terminal | the main clone `make_web/` | backend / API / recommendation-algorithm / DB |
| **Codex** | web browser (visual UI/UX) | a separate clone `make_web-codex/` | frontend / UI / UX (`frontend/src/**`) |

- Scope is assigned **per task** — the back/front split is just the usual
  tendency. At task start, name which files/area each tool owns and keep them
  non-overlapping so the two branches don't merge-conflict. If a task genuinely
  needs both to touch the same files: sequence it, or use one tool.
- **API contract = a named hand-off**, not free concurrency: when a backend change
  alters a request/response shape the frontend consumes, coordinate it explicitly.
- **Branch naming**: local AI agents use `feature/claude-<topic>` /
  `feature/codex-<topic>` (the prefix tells the admin which clone a PR came from).
  The human team's `feature/<role>-<topic>` (algo/sns/admin) is unchanged.
- Both clones push to the same remote and PR to `develop` exactly like a human.

### Sub-agent isolation is a different thing

Claude Code's Agent tool `isolation:"worktree"` (and Codex's worktree/sandbox
mode) isolate parallel file-mutating *sub-agents* within ONE session. That is
unrelated to the per-session clone above and does NOT prevent two top-level
sessions from colliding.

The **reliable layer is launch placement**: each tool is started in its own clone
(Claude in `make_web/`, Codex in `make_web-codex/`). The session-start check in
`CLAUDE.md` / `AGENTS.md` (confirm you are in your own clone on your own branch)
is a backstop, not the guarantee.

## First PR sanity check (recommended after onboarding)

After cloning + running `./tools/install-hooks.sh`, do one tiny verification PR
to confirm your local + GitHub setup works end-to-end:

1. `git checkout develop && git pull origin develop`
2. `git checkout -b feature/<role>-onboarding-check`
3. Make a trivial edit (e.g., a typo fix or a comment in a file your role owns)
4. `git add . && git commit -m "chore: <role> onboarding check"`
5. `git push -u origin feature/<role>-onboarding-check`
6. `gh pr create --base develop`
7. Confirm visually on GitHub: CI runs (status checks `backend` + `frontend`),
   CODEOWNERS auto-assigns admin as reviewer.
8. After CI green → admin squash-merges via `gh pr merge --admin --squash`
   (sole-admin Code Owner gate is self-unsatisfiable — see Branch model).

If any step fails, surface the error to the admin — usually a setup detail to
fix (e.g., status check name mismatch, missing CODEOWNERS handle, hook not
installed).

## Deploy flow (develop → main)

When `develop` has accumulated enough vetted features (admin's call):

```bash
# 1. Open PR develop → main
gh pr create --base main --head develop --title "Release: <date> — <summary>"

# 2. CI runs again on the merged range. A fresh review can be run if there's any
#    concern (typically not needed since each feature was already reviewed).

# 3. Admin self-approves + squash-merge. Railway auto-deploys on main push.

# 4. MANDATORY post-deploy step (Bug #5 — squash deploy creates commit-graph
#    divergence): force-reset origin/develop to match origin/main, otherwise
#    the next deploy PR fails with mergeable: CONFLICTING.
MAIN_SHA=$(git rev-parse origin/main)
gh api -X PATCH repos/hongikarchi/archi-tinder/git/refs/heads/develop \
  --field "sha=$MAIN_SHA" --field "force=true"
git checkout develop && git fetch origin develop && git reset --hard origin/develop

# 5. Prod DB migrate — required whenever the deploy range contains new
#    migration files. Railway can NOT auto-migrate (the runtime user
#    make_web_app has no DDL — INFRA-DB-1), so this is a manual operator step:
make migrate-prod
```

**This is the only permitted force on a shared branch.** It is codified as a
carve-out in `CLAUDE.md` / `AGENTS.md` § HARD RULE 4 and in `.claude/agents/git-publisher.md`
§ Mode 3 step 5. Precondition: every commit on `origin/develop` must be
content-equal to `origin/main` (no in-flight feature PR targets `develop`).
The `git-publisher` agent runs this automatically after a deploy merge.

### Prod migrate runbook (`make migrate-prod`)

Railway deploys code only; schema changes ship separately because the prod
runtime role has no DDL. `make migrate-prod` is the one-command wrapper:

- Reads credentials from **`backend/.env.prod.owner`** (gitignored, `chmod 600`;
  holds `DB_HOST` = the production Neon endpoint + `DB_USER=neondb_owner` +
  password). If the file is missing the target prints the template to create it.
  The runtime `backend/.env` (local branch, `make_web_app`) is never touched.
- Shows the pending migration list on prod, **flags destructive/data operations**
  (`RemoveField` / `DeleteModel` / `RenameField` / `RunSQL` / `RunPython`), and
  requires typing `deploy-prod` to proceed.
- **Ordering rule (code-first):** run it only AFTER the Railway deploy for the
  release is live.
  - Column **drops** (e.g. `RemoveField`) crash the OLD code if applied while it
    is still running (old ORM still writes the column).
  - Column **adds** crash the NEW code until applied (Django SELECTs every model
    field, so reads 500 too — keep the merge→migrate gap short).
  - If a release carries BOTH an add and a drop and zero-downtime matters,
    split: apply the add before/during the Railway build
    (`python3 manage.py migrate <app> <add_migration>` with the same env
    mechanism), then the drop after the new code is live. For pre-launch /
    low-traffic, one `make migrate-prod` right after the deploy is fine.

### Buildings-DB connection pooling (Neon pooler) — recommended, user-applied

Context: `DATABASES['buildings']` deliberately carries **no `CONN_MAX_AGE`**
(ownership decision, Task.md 2026-06: don't hold persistent app-level
connections on the Make-DB-owned project). Django therefore opens a fresh
TLS connection to Neon on every request that touches the buildings DB —
the swipe/session hot path pays that handshake 1-4x per request. The <1s
page-load mandate postdates that decision.

**Ownership-safe alternative — Neon's server-side pooler** (PgBouncer,
transaction mode): the app still "connects per request", but the handshake
terminates at Neon's pooler which reuses real DB connections. No app-level
persistent connection, no connection-slot squatting on the Make-DB project.

- **How:** change the `BUILDINGS_DB_HOST` env value from
  `ep-<endpoint>.<region>.aws.neon.tech` to
  `ep-<endpoint>-pooler.<region>.aws.neon.tech` (insert `-pooler` after the
  endpoint ID). Railway: edit the service env var; local: `backend/.env`.
- **Compatibility:** transaction-mode pooling forbids session state
  (LISTEN/NOTIFY, advisory locks, temp tables, session-level prepared
  statements). Make Web's buildings usage is stateless read-only SELECTs —
  compatible. The app-DB alias (`default`) keeps `CONN_MAX_AGE=600` and is
  NOT part of this change.
- **Measured 2026-07-07 (local dev box in KR → Neon SG, 10 fresh
  connect+query cycles each):** connect p50 450ms (direct) ≈ 457ms (pooler),
  but tail max **2059ms → 517ms** — the pooler flattens the handshake tail.
  Same-region prod (Railway SG → Neon SG) has far smaller absolute connect
  cost; re-measure there before/after flipping the Railway var.

## Commit message convention

Follow Conventional Commits style:

- `feat: ...` — new feature
- `fix: ...` — bug fix
- `refactor: ...` — code restructure, no behavior change
- `chore: ...` — config / docs / tooling
- `test: ...` — test-only changes
- `docs: ...` — documentation only

Body: include context (spec ref, investigation #, decision rationale).

## Review

The `orchestrate` skill runs the `code-review` and `security-manager` sub-agents
on a feature branch before push. The pre-push browser + drift gate is the
`app-test` sub-agent on Claude Code and the `browser-verify` skill on Codex. Each
returns a PASS / FAIL verdict; FAIL feeds the fix loop. Review scope is the
unmerged commits that would land in develop on PR merge (`origin/develop..HEAD`).

`develop → main` PRs typically don't need a fresh review since each underlying
feature was already reviewed; admin self-merges based on CI green.

## File ownership conflict resolution

If two roles need to edit the same file, coordinate via:

1. **Sequencing** — one merges first, the other rebases.
2. **Pre-discussion** — quick async note in PR or chat before parallel work.
3. **Refactor split** — if conflict happens repeatedly on the same file, split it further into per-feature modules (precedent: `views.py` → `views/` package, `services.py` → `services/` package, `client.js` → `api/*.js`, `UserProfilePage.jsx` + `FirmProfilePage.jsx` → `components/profile/`).

## Common scenarios

### Adding a new Django app (B or C)

1. `python manage.py startapp <name>` under `backend/apps/`
2. Add `'apps.<name>'` to **`backend/config/settings.py`** `INSTALLED_APPS` (announce in chat)
3. Add `path('api/v1/<name>/', include('apps.<name>.urls'))` to **`backend/config/urls.py`** (announce in chat)
4. Generate first migration: `python manage.py makemigrations <name>` — follow the **Migrations (always coordinate)** subsection above
5. If app exposes models referenced by other roles' code: discuss the public surface with admin (C) before merging

### Adding a new frontend page

1. Create the page under `frontend/src/pages/<name>.jsx`
2. Add `<Route>` in **`frontend/src/App.jsx`** at the bottom of the `<Routes>` block (announce in chat)
3. If the page uses a new API endpoint, add a function to the appropriate `frontend/src/api/<feature>.js` module (or create a new feature file + `export * from` line in `client.js`)
4. If the page needs a tab on `TabBar`: that's a B/C coordination point — discuss before editing `frontend/src/components/TabBar.jsx`

### Adding a backend dependency (any role)

1. `pip install <pkg>` in the venv
2. Append `<pkg>==<version>` to **`backend/requirements.txt`** (always pin)
3. If the dep needs an API key or env var, append to **`backend/.env.example`** with a comment

### Adding a frontend dependency

1. `cd frontend && npm install <pkg>` (NEVER hand-edit `package-lock.json`)
2. Commit both `package.json` and `package-lock.json` together
3. After pulling main, always run `npm install` to sync the lock file

## Token-saving notes (for Claude Code users)

- Use scoped `git -C <subdir>` operations to avoid reading whole repo.
- Pass file:line pointers in agent prompts (e.g., "edit `views/swipe.py:120-150`").
- Reporter is deferred to session end. Don't spawn after every commit.
- Trivial commits (<50 LOC, no migration, no production logic) skip code-review/security.

See `.claude/WORKFLOW.md` (Claude) / `.codex/WORKFLOW.md` (Codex) for the full token-saving policy.
