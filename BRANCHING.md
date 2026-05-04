# Branching & Collaboration

3-person team workflow for Make Web. GitHub Flow with admin review.

## Roles

| Role | Owner | Primary territory |
|---|---|---|
| **A** | Algorithm | `backend/apps/recommendation/engine.py`, `backend/apps/recommendation/services/recommend.py`, `backend/config/settings.py` (RECOMMENDATION dict), algorithm tests |
| **B** | Post-swipe SNS | `backend/apps/social/`, `backend/apps/profiles/`, `frontend/src/pages/PostSwipeLandingPage.jsx`, `FirmProfilePage.jsx`, `UserProfilePage.jsx`, `BoardDetailPage.jsx`, `frontend/src/api/social.js`, `frontend/src/api/profiles.js` |
| **C** (admin) | Everything else | `backend/apps/accounts/`, `backend/apps/recommendation/views/sessions.py`, `views/projects.py`, `views/swipe.py`, `views/search.py`, `views/reports.py`, `views/telemetry.py`, `frontend/src/pages/SwipePage.jsx`, `LLMSearchPage.jsx`, `FavoritesPage.jsx`, `LoginPage.jsx`, `ProjectSetupPage.jsx`, Django admin, deployment config |

## Shared / coordinated edit files

These files are touched by 2+ roles. Default merge strategy is **append-only** where possible (new lines at the bottom rarely conflict). For files where order matters, **announce in chat before parallel edits**.

### Append-only safe (low conflict risk)

| File | Why shared | Merge note |
|---|---|---|
| `backend/apps/recommendation/views/__init__.py` | Re-export barrel | New imports go at the bottom |
| `backend/apps/recommendation/services/__init__.py` | Re-export barrel | New imports go at the bottom |
| `frontend/src/api/client.js` | Re-export barrel | New `export * from './<feature>.js'` at the bottom |

### Order-sensitive (announce before parallel edits)

| File | Why shared | Conflict risk |
|---|---|---|
| `backend/apps/recommendation/serializers.py` | Touchpoint between A's algorithm output and C's API contract | A and C may both add fields — coordinate field names |
| `backend/config/settings.py` | A owns RECOMMENDATION dict + tunable params; B/C add `INSTALLED_APPS`, middleware, throttles | Single file, multiple sections — communicate before editing the same section |
| `backend/config/urls.py` | Root URL include — every new Django app gets a line here | Append at the bottom of the `urlpatterns` list to minimize conflict |
| `frontend/src/App.jsx` | Single React Router setup — every new page registers a `<Route>` here | Add new routes at the bottom of the `<Routes>` block; if two devs add routes simultaneously, second-to-merge rebases |
| `frontend/src/components/profile/InfoCol.jsx` | Tiny shared component (B-extracted, may be reused) | If a non-B role needs to extend it, propose a generalization in PR |
| `frontend/package.json` / `frontend/package-lock.json` | New JS deps | Run `npm install` AFTER pulling main; never hand-edit lock |
| `backend/requirements.txt` | New Python deps | Pin versions; second-to-merge rebases the dep order |
| `backend/.env.example` / `frontend/.env.example` | New env vars | Append to bottom; document what the var does in a comment |

### Migrations (always coordinate)

Django migrations are numbered per app. Two devs creating `<app>/migrations/0042_*.py` simultaneously will produce duplicate numbers and a broken migration graph.

**Per-feature workflow:**
1. `git checkout main && git pull origin main` immediately before `python manage.py makemigrations <app>`.
2. Don't sit on locally-generated migrations for days — merge within ~24h or rebase.
3. If conflict happens at merge time: second-to-merge regenerates the migration on their branch.

## Branch model — GitHub Flow

```
main (protected; admin merges only)
├── feature/algo-<topic>      ← A's branch
├── feature/sns-<topic>       ← B's branch
└── feature/admin-<topic>     ← C's branch
```

**Rules:**

1. `main` is **protected**. Direct pushes blocked. Only merges from approved PRs.
2. Each developer creates `feature/<role>-<short-topic>` per task. Examples:
   - `feature/algo-mmr-lambda-tuning`
   - `feature/sns-board-detail-integration`
   - `feature/admin-search-relevance-tweak`
3. PRs target `main`. **Admin (C) approves all PRs** (or at least one teammate + admin for non-admin PRs).
4. Merge method: **squash merge** (clean history; one commit per PR).

## Workflow per feature

```bash
# 1. Sync from main
git checkout main && git pull origin main

# 2. New branch
git checkout -b feature/algo-mmr-lambda-tuning

# 3. Work + commit (multiple commits OK; squashed at merge time)
git add .
git commit -m "feat: tune mmr_lambda from 0.7 to 0.6 (Investigation 14 §3)"

# 4. Push
git push -u origin feature/algo-mmr-lambda-tuning

# 5. Open PR on GitHub UI (or `gh pr create`)
gh pr create --title "Algo: MMR lambda 0.7 → 0.6" --body "..."

# 6. Admin runs /review in review terminal — verdict in .claude/reviews/
#    or PR comments

# 7. After approval + REVIEW-PASSED → admin clicks "Squash and merge"

# 8. Local cleanup
git checkout main && git pull origin main
git branch -d feature/algo-mmr-lambda-tuning
```

## Commit message convention

Follow Conventional Commits style:

- `feat: ...` — new feature
- `fix: ...` — bug fix
- `refactor: ...` — code restructure, no behavior change
- `chore: ...` — config / docs / tooling
- `test: ...` — test-only changes
- `docs: ...` — documentation only

Body: include context (spec ref, investigation #, decision rationale).

## /review usage

The admin uses `/review` (or natural language "리뷰해줘") in a separate review terminal session for PRs. The verdict (PASS / PASS-WITH-MINORS / FAIL) lands in `.claude/reviews/<sha>.md`.

For non-admin PRs: admin runs `/review` after the author requests review.

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
4. Generate first migration: `python manage.py makemigrations <name>` — see Migration coordination
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
- Reporter is deferred to session end (Rule 1 in CLAUDE.md). Don't spawn after every commit.
- Trivial commits (<50 LOC, no migration, no production logic) skip reviewer/security per Rule 2.

See `.claude/agents/orchestrator.md` and `.claude/agents/reporter.md` for full token-saving policy.
