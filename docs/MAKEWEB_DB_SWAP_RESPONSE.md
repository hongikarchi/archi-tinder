# make_web Response — Neon Swap 2026-05-24

Response to `make_db/docs/MAKEWEB_DB_SWAP_HANDOFF.md` (1-week archive
following the cleanup).

## Local swap — DONE

- `backend/.env` `BUILDINGS_DB_HOST` / `_USER` / `_PASSWORD` / `_NAME` updated to
  the production endpoint + new `make_web` role + `archi_data` DB.
- `backend/.env` `DB_HOST` also updated — the old `ep-summer-king-a1xldgwi`
  endpoint was the dropped `local-dev` branch, so `user_data` had to follow
  to `ep-broad-hat-a1jaomn7` for local development to function.
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

## Railway prod swap — PENDING admin action

Railway prod env vars currently still have stale values for the three
buildings keys. Plan calls for `railway variables --set` of:

- `BUILDINGS_DB_NAME=archi_data` (was `neondb`)
- `BUILDINGS_DB_USER=make_web` (was `neondb_owner`)
- `BUILDINGS_DB_PASSWORD=<new>` (rotated)

`BUILDINGS_DB_HOST` already points at `ep-broad-hat-a1jaomn7` — no host
change. Railway auto-redeploys on env change; ~2-3 min to pick up new vars.

After redeploy, run the verification SQL from the handoff doc against prod.

## Answers to handoff `Open questions`

### Q1 — Railway redeploy + verification SQL pass
Pending. Will run verification SQL block from §4 of the handoff doc against
the production endpoint immediately after the Railway env swap completes.

### Q2 — `user_data` DB role separation
Deferred. `user_data` currently uses `neondb_owner` for read+write (the
Make-DB-managed writer role). Recommendation: separate session to create
a `make_web_user_data_rw` role with grants limited to `user_data.public.*`,
then swap `DB_USER` / `DB_PASSWORD` on Railway. Not urgent — `user_data` is
owned by Make Web and the only writer is the Django app, so role overlap
with Make DB's `neondb_owner` is administrative tidiness rather than a
security gap.

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
