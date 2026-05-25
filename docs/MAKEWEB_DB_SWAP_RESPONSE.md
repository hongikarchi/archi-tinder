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
