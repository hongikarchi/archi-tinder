# Contributing to Make Web

3-person team workflow. main + develop + feature/* branches with PR-only landing
and admin review. Read this once before your first commit.

## Setup (one-time per clone)

```bash
git clone <repo>
cd make_web
./tools/onboarding.sh    # interactive: installs hooks + registers your CODEOWNERS handle
```

`onboarding.sh` walks you through 3 steps:
1. Installs the migration-conflict pre-push hook (calls `install-hooks.sh`)
2. Asks your role (A=Algorithm / B=SNS / C=Admin)
3. Asks your GitHub handle and replaces the matching `@TODO-role-*` placeholder
   in `.github/CODEOWNERS` with `@yourhandle`. You commit the CODEOWNERS edit
   yourself on your first feature branch — see "First PR sanity check" below.

If you only want to install hooks (e.g. CODEOWNERS already has your handle),
run `./tools/install-hooks.sh` directly instead.

## Roles

| Role | Owner | Primary territory |
|---|---|---|
| **A** | Algorithm | `backend/apps/recommendation/engine.py`, `backend/apps/recommendation/services/{embeddings,rerank,generation,parse_query,_caches,_gemini}.py`, `backend/config/settings.py` (RECOMMENDATION dict only), `backend/tests/` (algorithm tests: `test_topic*`, `test_hyde`, `test_hybrid_retrieval`, `test_imp*`, `test_chat_phase`, `test_confidence`, etc.) |
| **B** | Post-swipe SNS | `backend/apps/social/`, `backend/apps/profiles/`, `frontend/src/pages/PostSwipeLandingPage.jsx`, `FirmProfilePage.jsx`, `UserProfilePage.jsx`, `BoardDetailPage.jsx`, `frontend/src/api/social.js`, `frontend/src/api/profiles.js`, `frontend/src/components/profile/` (BoardCard, BioPersonaFlipCard, DescriptionAboutFlipCard, ProjectCard, ArticleCard, InfoCol) |
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
```

**Rules:**

1. `main` is **protected** — PR + status check + Code Owner approval required.
2. `develop` is **protected** — PR + status check required (admin bypass disabled;
   admin's PRs go through the same gate).
3. Each developer creates `feature/<role>-<short-topic>` per task. Examples:
   - `feature/algo-mmr-lambda-tuning`
   - `feature/sns-board-detail-integration`
   - `feature/admin-search-relevance-tweak`
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

# 7. After review pass + Code Owner approval + CI green → admin clicks
#    "Squash and merge" on GitHub.

# 8. Local cleanup
git checkout develop && git pull origin develop
git branch -d feature/algo-mmr-lambda-tuning
```

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
8. After admin approves + CI green: Squash and merge.

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
```

**This is the only permitted force on a shared branch.** It is codified as a
carve-out in `CLAUDE.md` § HARD RULE 4 and in `.claude/agents/git-publisher.md`
§ Mode 3 step 5. Precondition: every commit on `origin/develop` must be
content-equal to `origin/main` (no in-flight feature PR targets `develop`).
The `git-publisher` agent runs this automatically after a deploy merge.

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
on a feature branch before push (the `app-test` sub-agent runs the pre-push
browser + drift gate). Each returns a PASS / FAIL verdict; FAIL feeds the fix
loop. Review scope is the unmerged commits that would land in develop on PR
merge (`origin/develop..HEAD`).

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

See `.claude/WORKFLOW.md` for the full token-saving policy.
