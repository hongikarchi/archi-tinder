# Runbook — Deploy develop → main (production)

**Audience**: the operator (admin) running a production release, and any agent asked to assist.
**Single source**: this file holds the full procedure. `CONTRIBUTING.md`, `CLAUDE.md`/`AGENTS.md`, `.claude/agents/git-publisher.md` and `backend/railway.toml` keep one-paragraph summaries that link here. If this file and another doc disagree, this file wins; fix the other doc.

Production stack: Railway (Django API, `archi-tinder` service) + Vercel (React) + Neon Postgres (`production` branch) + Cloudflare R2 + Redis on Railway. Everything in Singapore.

---

## 0. Preconditions (5 minutes)

| Check | How | Must be |
|---|---|---|
| develop CI green | `gh run list --branch develop --limit 3` | latest run success |
| no in-flight PR targeting develop | `gh pr list --base develop --state open` | empty (or consciously excluded) |
| develop ahead of main | `git fetch origin && git log --oneline origin/main..origin/develop` | non-empty; if empty, nothing to deploy |
| migration delta | `git diff origin/main origin/develop --name-only -- 'backend/**/migrations/*.py'` | note every file; classify each (see §3) |
| pre-launch blockers | `Task.md` ## Next → `DEPLOY-BLOCKER-1` | until public launch these are tolerated per user decision 2026-09-29; re-check they are still non-blocking for this release |
| prod owner creds present | `ls -l backend/.env.prod.owner` (gitignored, `chmod 600`) | exists; template printed by `make migrate-prod` if missing |
| Django 5.2 environment | `backend/.venv/*/python -c "import django; print(django.get_version())"` | 5.2.x — a venv on Django 4.2 cannot run `manage.py` against current code (hit 2026-10-03) |

Authorization: a deploy needs an explicit deploy keyword from the user (`배포`, `deploy`, `ship`, `배포해`). Agents never deploy on their own initiative.

---

## 1. Decide migration ordering BEFORE merging

Railway only deploys code. The runtime DB user `make_web_app` has **no DDL**, so Railway can never auto-migrate (INFRA-DB-1). Migrations are applied by hand with `neondb_owner`. The order relative to the code deploy matters:

| Migration content | Order | Why |
|---|---|---|
| Only ADD (new table, nullable column, index) | **migrate FIRST, then merge** | old code ignores new objects; new code 500s until the column exists (Django SELECTs every model field). Used for `admin_dashboard 0001`, `messaging 0001` |
| Contains DROP / RENAME (`RemoveField`, `DeleteModel`, `RenameField`, `RenameModel`) | **merge FIRST, then migrate** (code-first) | old code still writes the column; dropping it under running old code crashes |
| Both add and drop in one release | split: add-only migrations first, merge, then drops | zero-downtime variant; for pre-launch traffic one `make migrate-prod` right after deploy is acceptable |
| `RunSQL` / `RunPython` | read the file, decide case by case | data migrations may lock tables |
| NOT NULL without default | treat like a drop + expect a short 500 window | seen with `recommendation 0031` (2026-09-29) |

`make migrate-prod` flags destructive ops automatically but does not decide order for you.

---

## 2. Open and merge the deploy PR

```bash
# from a clean checkout (any branch), repo = hongikarchi/archi-tinder
gh pr create --base main --head develop \
  --title "Release: $(date +%F) — <one-line summary>" \
  --body "Included PRs: #... (each already reviewed pre-develop-merge). Migrations: <list or none>. Risk: <notes>."

# CI runs on the merged range. When green and the admin has inspected:
gh pr merge <N> --squash --admin        # Code Owner review is self-unsatisfiable for the sole admin
```

Railway builds and deploys automatically on the `main` push. Watch it:

```bash
cd backend
railway status --service archi-tinder            # service link was lost once; always pass --service
railway deployment list --service archi-tinder   # wait for SUCCESS
railway logs --service archi-tinder | grep -E ' 5[0-9]{2} ' | head   # should be empty
```

Vercel deploys the frontend from `main` on its own; check the Vercel dashboard or `vercel ls`.

Smoke probes (anonymous, read-only):

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://archi-tinder.up.railway.app/api/v1/admin/dashboard/overview/   # 401
curl -s -o /dev/null -w '%{http_code}\n' https://archi-tinder.up.railway.app/api/v1/images/batch/              # 400/401, never 5xx
```

---

## 3. Apply production migrations

Interactive (prompts for a typed `deploy-prod` confirmation, lists pending migrations, flags destructive ops):

```bash
make migrate-prod
```

Non-interactive (same checks, confirmation piped — the confirm is a plain stdin `read`):

```bash
echo deploy-prod | make migrate-prod
```

Apply a single migration (add-first ordering):

```bash
cd backend
set -a; . .env.prod.owner; set +a          # exports DB_HOST/PORT/NAME/USER/PASSWORD for THIS shell only
case "$DB_HOST" in *broad-hat*) ;; *) echo "not the prod endpoint — abort"; exit 1;; esac
python manage.py migrate <app> <0001_name>
set +a; unset DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
```

Rules:
- Credentials live only in `backend/.env.prod.owner` (gitignored by `.env.*`, `chmod 600`). Never paste the password into a command line or chat; never copy it into `.env`.
- `settings.py` loads `.env` with `override=False`, so inline/exported env vars win over `.env` without editing it. The runtime `.env` stays on `make_web_app`.
- The prod endpoint hostname contains `broad-hat` (Neon `production` branch). Local child-branch endpoints never do. The guard above is the last line of defense.
- From a scratch clone (when the main checkout is dirty or on another branch): clone, `git checkout origin/main`, copy `backend/.env` + `backend/.env.prod.owner` in, run `echo deploy-prod | make migrate-prod PYTHON=<path to a Django 5.2 python>`, then **delete the clone** (it holds secrets).
- Verify: `make migrate-prod` prints `(none -- prod already current)` on a second run. Or read-only, run by the user: `SELECT app, max(name) FROM django_migrations GROUP BY app;`

Default privileges on the prod DB already grant `make_web_app` SELECT/INSERT/UPDATE/DELETE + sequence USAGE on new tables (verified 2026-10-03 and 2026-10-06), so no GRANT step is needed after a migration.

---

## 4. Post-deploy develop force-reset — MANDATORY (Bug #5)

Squash-merging develop into main leaves identical trees but divergent histories; the next deploy PR then shows `mergeable: CONFLICTING`. Immediately after the merge:

```bash
git fetch origin
# safety: every develop commit must already be in main's tree (no unmerged feature PR targets develop)
git diff --stat origin/main origin/develop        # must be empty
MAIN_SHA=$(git rev-parse origin/main)
gh api -X PATCH repos/hongikarchi/archi-tinder/git/refs/heads/develop \
  --field "sha=$MAIN_SHA" --field "force=true"
tools/git-sync-develop.sh                         # local develop follows; never `git pull` here
```

This is the **only** permitted force on a shared branch (HARD RULE 4 carve-out) and only in this window. Every other clone must run `tools/git-sync-develop.sh` instead of `git pull origin develop` afterwards; the script keeps a local backup branch if a fast-forward is impossible.

---

## 5. Environment variables and one-off operator actions

```bash
cd backend
railway variable list --service archi-tinder
railway variable set KEY=value --service archi-tinder --skip-deploys     # batch several, then one redeploy
railway variable delete KEY --service archi-tinder                       # no --skip-deploys flag → triggers a redeploy
railway redeploy --service archi-tinder
```

Known variables (values live on Railway, never in the repo): `DB_*`, `BUILDINGS_DB_*`, `REDIS_URL`, `LLM_PROVIDER=openai` + `OPENAI_TEXT_MODEL=gpt-5.4-mini` + `OPENAI_STRICT_SCHEMA=true` (B pick 2026-08-05), `GEMINI_*`, `HF_TOKEN`, `R2_*`, `ADMIN_EMAILS`, `OPENAI_ADMIN_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, feature flags (`MESSAGING_ENABLED`, `STAGE_DECOUPLE_ENABLED`, `DB_POOL_ENABLED`, `PREWARM_ENABLED`). Rollback levers that need no deploy: `DB_POOL_ENABLED=false`, `PREWARM_ENABLED=false`, delete `LLM_PROVIDER` (falls back to Gemini).

Run a management command on the production container:

```bash
railway ssh --service archi-tinder -- python manage.py grant_admin <email>
```

Admin access requires the user to have a Google-linked account (plain sign-up creates a `local_` guest; link Google in Settings › 계정 first), `is_staff` via `grant_admin`, and their email in `ADMIN_EMAILS`.

Prod reads for diagnosis (user runs them; agents are blocked from prod access by policy):

```bash
railway run --service archi-tinder python manage.py shell -c "exec(open('script.py').read())"   # multi-line -c breaks in IPython; use a file
```

---

## 6. After the deploy

1. Record the release in `Task.md` (## Done entry via the `reporter-inline` skill) — until S5 of the docs restructure moves tracking to GitHub Issues.
2. If the release changed `backend/config/settings.py` RECOMMENDATION values, run the algorithm-doc sync (reporter-inline).
3. Re-measure performance when the release touched the hot path: `tools/perf/prod_bench.py --warmup 1 --stream` (writes guest rows — needs user approval); compare with `docs/research/perf-baseline-2026-09-30.md`.
4. Neon: `production` compute autoscale 0.25–8 CU with scale-to-zero after 5 min is ON pre-launch (user decision). Expect a cold first request after idle; measure warm.

---

## 7. Rollback

- Code: `git revert` the squash commit on a feature branch → PR → merge to main (Railway redeploys). Never force-push main.
- Schema: write a reverse migration; apply with the same `make migrate-prod` path. Do not hand-edit prod.
- Config: flip the env levers in §5 and `railway redeploy`.

## History (why these rules exist)
- 2026-05-11: every merge path auto-deleted head branches → repo `delete_branch_on_merge=false`.
- 2026-05-25 INFRA-DB-1: runtime role `make_web_app` without DDL; migrations moved to the operator.
- 2026-07-04 #259: deploy left new code live against an unmigrated schema → `make migrate-prod` + code-first rule (INFRA-DEPLOY-1).
- 2026-07-16: Neon pooler reverted; `BUILDINGS_DB_HOST` must stay on the direct endpoint (HNSW `iterative_scan` startup option).
- 2026-09-29 #339: `recommendation 0031` NOT NULL without default → short 500 window; add-first ordering adopted for additive migrations.
- 2026-10-03 #345: Django 4.2 venv could not run prod migrate → Django 5.2 venv requirement.
- 2026-10-06 #349/#351: `railway variable delete` redeploys; `railway ssh` for `grant_admin`.
