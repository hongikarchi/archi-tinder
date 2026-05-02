# Branching & Collaboration

3-person team workflow for Make Web. GitHub Flow with admin review.

## Roles

| Role | Owner | Primary territory |
|---|---|---|
| **A** | Algorithm | `backend/apps/recommendation/engine.py`, `backend/apps/recommendation/services/recommend.py`, `backend/config/settings.py` (RECOMMENDATION dict), algorithm tests |
| **B** | Post-swipe SNS | `backend/apps/social/`, `backend/apps/profiles/`, `frontend/src/pages/PostSwipeLandingPage.jsx`, `FirmProfilePage.jsx`, `UserProfilePage.jsx`, `BoardDetailPage.jsx`, `frontend/src/api/social.js`, `frontend/src/api/profiles.js` |
| **C** (admin) | Everything else | `backend/apps/accounts/`, `backend/apps/recommendation/views/sessions.py`, `views/projects.py`, `views/swipe.py`, `views/search.py`, `views/reports.py`, `views/telemetry.py`, `frontend/src/pages/SwipePage.jsx`, `LLMSearchPage.jsx`, `FavoritesPage.jsx`, `LoginPage.jsx`, `ProjectSetupPage.jsx`, Django admin, deployment config |

Shared / coordinated edit:
- `backend/apps/recommendation/views/__init__.py` (re-exports — append-only is safe)
- `frontend/src/api/client.js` (re-export barrel — append-only is safe)
- `backend/apps/recommendation/serializers.py` (touchpoint between A's algorithm output and C's API contract)
- Migrations across apps (numbered sequentially per app — coordinate to avoid duplicate numbers)

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
3. **Refactor split** — if conflict happens repeatedly on the same file, split it further into per-feature modules (precedent: `views.py` → `views/` package, `client.js` → `api/*.js`).

## Migration coordination

Django migrations are numbered per app. To avoid duplicate numbers:

1. Before creating a migration, sync `git pull origin main` and check the latest migration number in the affected app.
2. Run `python manage.py makemigrations <app>` immediately before commit (don't generate locally and sit on it for days).
3. If a duplicate-number conflict happens at merge time, the second-to-merge developer regenerates the migration on their branch.

## Token-saving notes (for Claude Code users)

- Use scoped `git -C <subdir>` operations to avoid reading whole repo.
- Pass file:line pointers in agent prompts (e.g., "edit `views/swipe.py:120-150`").
- Reporter is deferred to session end (Rule 1 in CLAUDE.md). Don't spawn after every commit.
- Trivial commits (<50 LOC, no migration, no production logic) skip reviewer/security per Rule 2.

See `.claude/agents/orchestrator.md` and `.claude/agents/reporter.md` for full token-saving policy.
