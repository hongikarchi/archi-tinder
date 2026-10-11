# backend/ — conventions (shared: Claude Code, Codex, humans)

Loaded on top of the root `AGENTS.md` when working under `backend/`.

## Runtime
- Django 5.2 LTS, Python 3.12 (`backend/.python-version`, CI, prod). Local dev may
  run 3.11. Run via `make backend` / `make dev`; never hand-type `python3`.
- Every URL pattern ends with `/` — `APPEND_SLASH` redirects only GET, not POST.
- JWT: access 1 h, refresh 30 d, rotate + blacklist (`TokenBlacklist` app installed).
- Cache: Django cache abstraction only (`from django.core.cache import cache`).
  Redis in prod via `REDIS_URL`; LocMemCache locally when unset. No direct redis-py.
- Gunicorn `gthread 3x4`, pre-warm on worker init (`gunicorn.conf.py`); env levers
  `PREWARM_ENABLED`, `DB_POOL_ENABLED` — see `backend/railway.toml` comments.

## Databases
- Two aliases. `'default'` = app DB `user_data` (`DB_*`): ORM + migrations.
  `'buildings'` = Make-DB-owned `archi_data` (`BUILDINGS_DB_*`): read-only raw SQL
  via `connections['buildings']`; never ORM, never migrate (`config/db_router.py`).
- Neon Postgres, `sslmode=require`, psycopg 3 (`psycopg[binary,pool]`) with Django's
  built-in pool (`OPTIONS['pool']`, `CONN_MAX_AGE=0`). Raw SQL: `= ANY(%s)` with a
  Python list, never tuple `IN %s`; literal `%` → `%%`; no `psycopg2` imports.
- Any thread you spawn that touches a DB must call `connections.close_all()` in a
  `finally` (returns the pooled connection; a missed call leaks a pool slot).
- `BUILDINGS_DB_HOST` stays on the direct Neon endpoint (not the pooler): the
  HNSW `iterative_scan=strict_order` startup option needs it.
- Roles: runtime `make_web_app` (no DDL, no role mgmt), buildings `make_web`
  (SELECT-only). Migrations run as `neondb_owner` through `make migrate-local`
  (local child branch) and `make migrate-prod` (production, post-deploy). Nothing
  auto-migrates anywhere. Never put `neondb_owner` in `.env`. Create roles with
  psql `CREATE ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION
  NOBYPASSRLS`, not `neonctl roles create`.
- Local `.env` points at a Neon child branch; production hostname contains
  `broad-hat` — never use it locally. Setup: `docs/runbooks/local-setup.md`.

## Building data
- `canonical_bld_id` only; `is_publishable = true` on every building query;
  `canonical_v2_buildings` is read-only (schema + ownership: `docs/database-schema.md`).
- `images/batch/` POST returns building cards for a `canonical_bld_ids` list.
- Embeddings are pre-computed (HuggingFace API for query embeddings); no
  SentenceTransformers.

## LLM providers
- Parse + board-name: `LLM_PROVIDER=openai` / `gpt-5.4-mini` strict schema in prod
  (env flip, 2026-08-05); code default Gemini (rollback = delete the env var).
  Persona text + images: Gemini, pinned in code. Report prose rules:
  `docs/report-writing.md`.

## Tests and checks
- `./tools/back-validate.sh [app]` = flake8 → migration check → pytest (what the
  maker agents run). `make test-local ARGS="-x -k foo"` = CI-shape pytest on real
  Postgres+pgvector as `neondb_owner` (plain `pytest` fails: runtime role has no
  CREATEDB). CI (`.github/workflows/ci.yml`) is the canonical gate.
- A model change needs a migration file in the same PR (`makemigrations --check`
  runs in CI). Migration numbering is guarded by the pre-push hook.
