# make_web Response — Neon Swap 2026-05-24

Response to `make_db/docs/MAKEWEB_DB_SWAP_HANDOFF.md` (1-week archive
following the cleanup).

## Local swap — DONE

- `backend/.env` `BUILDINGS_DB_HOST` / `_USER` / `_PASSWORD` / `_NAME` updated to
  the production endpoint + new `make_web` role + `archi_data` DB.
- `backend/.env` `DB_HOST` also updated — the old `ep-summer-king-a1xldgwi`
  endpoint was the dropped `local-dev` branch, so `user_data` had to follow
  to `ep-broad-hat-a1jaomn7` for local development to function.
  **2026-05-25 follow-up (INFRA-ENV-1)**: pointing local `.env` at the
  production endpoint was a temporary measure — it caused local
  `manage.py runserver` to write straight into the prod `user_data` branch.
  Resolved by re-provisioning a persistent Neon child branch
  `local-dev-2` (`br-shy-thunder-a1p5glmo`, endpoint
  `ep-holy-band-a1w0u5am`, no TTL) off `production`, then repointing
  `backend/.env` `DB_HOST` and `BUILDINGS_DB_HOST` to the new dev
  endpoint. Railway prod env vars (`ep-broad-hat-a1jaomn7`) untouched.
- `backend/.env.example` template refreshed (new role + DB name + comment).
- Verified locally via psql + Django `manage.py check` + ORM smoke through
  `connections['buildings']`:

  | Probe | Result |
  |---|---|
  | `current_database()` on BUILDINGS | `archi_data` ✓ |
  | `current_user` on BUILDINGS | `make_web` ✓ |
  | `COUNT(canonical_v2_buildings)` | 39,478 ✓ |
  | `COUNT(canonical_v2_architects)` | 14,216 ✓ |
  | Foster + Partners smoke | `('arch_000000', 'Foster + Partners', 'United States', 82)` ✓ |
  | `COUNT(auth_user)` on user_data | 2 ✓ |
  | `COUNT(WHERE is_publishable = true)` | 36,864 (93.4%) |

## Railway prod swap — COMPLETED 2026-05-24 (PR #93)

Railway prod env vars swapped on 2026-05-24 as part of PR #93
(`BUILDINGS-DB-SWAP`). Auto-redeploy `04e7633e` came up Online and the
verification SQL block from §4 of the handoff doc was run successfully
against the production endpoint — same probe results as the local table
above. See `.claude/Task.md` `## Done` `#12 BUILDINGS-DB-SWAP` for the
audit trail.

Final prod env values after the swap:
- `BUILDINGS_DB_NAME=archi_data` (was `neondb`)
- `BUILDINGS_DB_USER=make_web` (was `neondb_owner`)
- `BUILDINGS_DB_PASSWORD` rotated
- `BUILDINGS_DB_HOST=ep-broad-hat-a1jaomn7` (unchanged)

## Answers to handoff `Open questions`

### Q1 — Railway redeploy + verification SQL pass
Pending. Will run verification SQL block from §4 of the handoff doc against
the production endpoint immediately after the Railway env swap completes.

### Q2 — `user_data` DB role separation — RESOLVED 2026-05-25 (INFRA-DB-1)
Created `make_web_app` on both `production` and `local-dev-2` branches via
psql (NOT `neonctl roles create`; that grants `neon_superuser` membership by
default, which transitively grants CREATEDB/CREATEROLE/CREATEEXTENSION —
unacceptable for a runtime role). Definition:

```sql
CREATE ROLE make_web_app
  WITH LOGIN PASSWORD '<rotated>'
  NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE user_data TO make_web_app;
GRANT USAGE ON SCHEMA public TO make_web_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO make_web_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO make_web_app;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO make_web_app;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO make_web_app;
```

Smoke verified on `local-dev-2`:

| Probe (as `make_web_app`) | Result |
|---|---|
| `SELECT COUNT(*) FROM auth_user` | 3 ✓ |
| `INSERT/UPDATE/DELETE` round-trip on `auth_user` | ✓ |
| `has_sequence_privilege('auth_user_id_seq')` | t ✓ |
| `CREATE TABLE …` | ERROR: permission denied for schema public ✓ |
| `DROP TABLE auth_user` | ERROR: must be owner of table ✓ |
| `CREATE ROLE …` | ERROR: permission denied to create role ✓ |
| `CREATE EXTENSION hstore` | ERROR: permission denied to create extension ✓ |
| `ALTER TABLE …` | ERROR: must be owner of table ✓ |

Local `backend/.env` swapped to `DB_USER=make_web_app` + rotated password;
Django `manage.py check` clean; ORM + raw SQL smoke unchanged. Migration
DDL (`CREATE TABLE migrate_probe …`) correctly rejected — operator must
temporarily swap to `DB_USER=neondb_owner` when running `manage.py
migrate`, then swap back.

**Railway prod cutover — COMPLETED 2026-05-25**. Sequence executed:

1. Railway dashboard → service env vars rotated:
   - `DB_USER`: `neondb_owner` → `make_web_app`
   - `DB_PASSWORD`: rotated to the `make_web_app` prod password
     (out-of-band hand-off via `/tmp/.makewebapp_pw_prod`; never committed).
2. First Railway redeploy attempt (deployment `d203e2bf`, 07:28:53Z) FAILED
   at the `manage.py migrate --noinput` build step with
   `OperationalError: password authentication failed for user 'make_web_app'`
   — the rotated `DB_PASSWORD` was mis-pasted in the dashboard. Old
   deployment (`9e5d4a69`, 2026-05-24 18:50, still serving with the prior
   `neondb_owner` env) stayed online — no prod outage.
3. `DB_PASSWORD` re-pasted exactly from `/tmp/.makewebapp_pw_prod`. Second
   redeploy (`820de476`, 07:43:29Z) build phase:
   - `pip install` clean.
   - `manage.py migrate --noinput`: `No migrations to apply` ✓
     (SELECT-only on `django_migrations` — `make_web_app` allowed).
   - `collectstatic --noinput`: 152 static files copied ✓.
   - Image push ✓.
4. Deploy phase SUCCESS; `820de476` swapped in as the active deployment.
5. Post-cutover smoke (HTTPS against `archi-tinder.up.railway.app`):
   `/api/v1/auth/me/` → 401 (auth required, container reachable),
   `/api/v1/users/me/` → 401, POST `/api/v1/auth/token/refresh/` with bogus
   token → 401 `{"detail":"Invalid or expired token"}` (Django Simple JWT
   queried `token_blacklist` as `make_web_app` ✓). DDL endpoint surfaces
   would 5xx if the role were over-restricted — none observed.

Rollback path (if needed later): Railway dashboard → flip `DB_USER` back
to `neondb_owner` + restore the prior `DB_PASSWORD`. Both roles coexist on
the production branch; no DDL needed to revert.

`neondb_owner` is now used **only** from the operator machine for
`manage.py migrate` (with a temporary `backend/.env` `DB_USER=neondb_owner`
swap, then revert). The Make-DB-managed `make_web` role on `archi_data`
(PR #93) is unaffected.

**Action item — BUILDINGS_DB_PASSWORD rotation**: `make_web` (buildings)
password was accidentally surfaced in this session's transcript by a
`railway variables` grep that matched too broadly. Rotate via
`neonctl roles reset-password make_web --branch production --project-id
holy-pond-45504245` then update Railway `BUILDINGS_DB_PASSWORD` + redeploy.
Tracked outside this doc.

### Q3 — Cache invalidation
No additional work required.

- Django `LocMemCache` (the taste-vector + pool caches) is per-process and
  resets automatically on Railway redeploy.
- Vercel CDN caches static frontend assets only; backend API responses are
  not CDN-cached.
- Frontend in-memory state resets on user reload.
- JWT tokens are signed by `DJANGO_SECRET_KEY` (unchanged); not affected by
  DB role rotation.

### Q4 — Drop `pre-cleanup-2026-05-24` snapshot branch after 1 week
Approved. Once `prod` smoke + codex Stage 3 audit pass on the new endpoint,
the snapshot is safe to drop. No expected need to roll back to it.

## Observations to flag

- Publishable ratio shifted from C8's "~99.9%" (39 / 39,776 non-publishable)
  to C23's 93.4% (2,614 / 39,478 non-publishable). Already accommodated by
  the existing `is_publishable = true` gate in `engine._build_filter_sql`;
  no Make Web code change. Flagging for Make DB awareness — the tighter
  flagging may affect candidate-pool sizes in low-frequency programs.
- The `local-dev` branch drop also wiped `user_data` data that had been
  written by local dev sessions in that branch (Make Web's local dev had
  been writing to the wrong endpoint). Prod `user_data` is unaffected.
  Acceptable loss — only dev fixtures.

## What make_web will do next

1. Railway env var set (3 keys) + redeploy wait.
2. Prod smoke via psql + production endpoint pings.
3. Codex Stage 3 audit (5-flow: Login / Profile / Discovery / Swipe / AI
   Search) on the new endpoint with `is_publishable=true` gate verified.
4. Reporter session-end housekeeping: `Task.md` entry + dashboard +
   `docs/algorithm.md` `Last Synced` bump.
