# Task Board

> Authored by the session; updated by the `reporter-inline` skill at session end. The dashboard
> (`project/dashboard.html` ← `project/state.js`) renders this file's three active
> sections (`## Now` / `## Next` / `## Done`). The compact `## Roadmap (Historical)`
> section at the bottom is a phase-level summary, not a task list.

## Workflow Rules

- **Session start** — read `## Now` first. If empty and the user is starting new work, move the matched `## Next` entry (under `### HIGH` / `### MEDIUM` / `### LOW`) into `## Now`. Or write a fresh entry if brand-new. One initiative slice at a time.
- **Mid-session** — if work in `## Now` gets deferred ("미루자"), move it back to `## Next` with a one-line rationale note. If a new sub-task appears, add it under the active Now entry's body or create a new Now entry.
- **Session end (success)** — `reporter-inline` moves `## Now` → `## Done` with PR ref + SHA. If the Now entry's note mentions a deferred follow-up (`Deferred: ...`), `reporter-inline` also auto-surfaces a matching `## Next` entry per its Step 2b (see `.agents/skills/reporter-inline/SKILL.md`).

**ID convention** (since 2026-05-25): `<SURFACE>-<TOPIC>-<N>`.
- **SURFACE** = `FRONT` / `BACK` / `FULL` / `INFRA`. Tells where the work lives.
  - `FRONT` = frontend only (React/Vite)
  - `BACK` = backend only (Django/DRF)
  - `FULL` = cross-cutting FE + BE (one feature, two PRs coordinated)
  - `INFRA` = ops surface — Neon / Railway / Vercel / `.env` / DB roles / deploy
- **TOPIC** = readable English word. **No obscure abbreviations.** Only universal acronyms allowed: `LLM`, `UX`, `DB`, `ENV`, `AUTH`. Conventional topics:
  - BACK: `LLM` / `RECOMMEND` / `PERFORMANCE` / `AUTH` / `EXTERNAL`
  - FRONT: `UX` / `DESIGN` / `LAYOUT` / `AUTH`
  - FULL: `LANGUAGE` / `LEGAL` / `REFACTOR` / `LLM`
  - INFRA: `DB` / `ENV` / `DEPLOY` / `QUEUE` / `MONITOR`
- **N** = integer counter per `<SURFACE>-<TOPIC>`, persistent across bucket moves. `BACK-LLM-1`, `BACK-LLM-2`, etc. Never re-used.

**Title convention**: short Korean problem / goal statement, ≤ 25 chars. Says **what is wrong or what we want**, not **how**. The body carries the how. Examples:
- ✅ `LLM 채팅이 검색에 필요한 정보를 다 안 모음`
- ✅ `/projects/ 응답 600ms (목표 300ms)`
- ❌ `LLM chat refinement: refine probe behaviour to deterministically target missing required slate fields` (too long, English jargon, embeds the how)

**Header format**:
- `## Now` and `## Done` items → `### <ID> — <Korean title>`
- `## Next` items → `#### <ID> — <Korean title>` under one of `### HIGH` / `### MEDIUM` / `### LOW`
- `## Done` resolved suffix → append ` — RESOLVED YYYY-MM-DD (PR #N `<sha>`)`
- Multi-line body for context. Sub-tasks use `- [ ]` / `- [x]` checkboxes.

**Consistency across artefacts** — every surface that names a task uses the same `<ID> — <Korean title>` pair so cross-referencing is mechanical:
- **Commit subject**: `<type>(<ID>): <Korean title>`. Body keeps caveman-terse description.
- **PR title**: same shape as the commit subject.
- **Reporter Done entry** in `## Done`: `### <ID> — <Korean title> — RESOLVED YYYY-MM-DD (PR #N `<sha>`)`.
- **state.js**: `id` = `<ID>`, `title` = Korean title (no English duplicate).
- Long historical Done entries from before 2026-05-25 keep their legacy headers (`### #21 SWIPE-CALIBRATING — ...`) as archive — do not rewrite history.

**Priority bucket semantics** (`## Next`):
- **HIGH** — specced, ready to pull into `## Now`. Open dimensions resolved or acceptable to resolve during implementation.
- **MEDIUM** — uncategorised pending. Needs review before promotion (scope, urgency, prerequisites).
- **LOW** — explicitly deferred / skipped. Not blocking; revisit when context shifts (traffic, prereq shipped, priority change).

Algorithm work (`engine.py`, `services/embeddings.py`, etc.) is owned by a separate collaborator post-2026-05-18 — see CLAUDE.md `## Rules`. Tracked in `docs/algorithm.md`, not this board.

---

## Now

### FRONT-AUTH-2 — 로그인 스와이프 온보딩
Redesign `/login` as conversational swipe onboarding while preserving the existing guest auth API contract.

- [ ] Sync `feature/admin-login-page` from latest `origin/develop` before editing.
- [ ] Extract shared `react-tinder-card` gesture config/wrapper for Login, SwipePage, and DiscoveryPage.
- [ ] Rebuild LoginPage: first card right=new user / left=returning user, required display name, required role, consent card with right-swipe or button submit.
- [ ] Preserve `/discovery` handoff, dev login, Google conditional mount, and `buildGuestLoginPayload` wire shape.
- [ ] Verify with frontend unit test, lint, build, and feature-scoped browser check.

---

## Next

> Backlog grouped by priority bucket (`### HIGH` / `### MEDIUM` / `### LOW`). Each
> item is a `#### <SLUG>` entry one level deeper. Bucket semantics described in
> `## Workflow Rules` above. Phase 16-18 dimensions inlined here (formerly
> `docs/specs/*`, absorbed 2026-05-24). Algorithm theory + production
> hyperparameters still live in `docs/algorithm.md` (admin-owned, reporter syncs
> Production Value column only).

### HIGH

#### BACK-RECOMMEND-1 — Project 두번째 세션이 이전 taste를 모름
Same Project can host multiple `AnalysisSession` rows (user comes back, "Resume" or new swipe round on the same Project — second session is created fresh while `Project.liked_ids` / `disliked_ids` / `saved_ids` carry forward as the persistent accumulator). Today the new session's algorithm-side state (`like_vectors`, `convergence_history`, `phase`) starts from scratch — exploring phase, empty pool of taste signal — even though the user just liked 12 buildings in Session #1.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/views/sessions.py` `SessionCreateView.post()` resolves an owned `project_id` early only to skip retry-dedupe. In `session_insert`, every new `AnalysisSession` is still created with `phase='exploring'`, `like_vectors=[]`, `convergence_history=[]`, `previous_pref_vector=[]`, `preference_vector=[]`.
- Persistent taste lives on `Project.liked_ids` as `[{id, intensity}]`; `Project.disliked_ids` and `Project.saved_ids` also carry across sessions. The create path does not read these fields when `project` already exists.
- `backend/apps/recommendation/engine.py` already has `compute_user_taste_vector(profile)` for Discovery-level cross-project taste and `get_pool_embeddings(ids)` for batch embedding fetch. A session-specific warm-start should not call `compute_user_taste_vector(profile)` blindly because it aggregates all Projects, not just the active Project.
- `SwipeView.post()` phase transition still keys off `len(session.like_vectors)` and `min_likes_for_clustering`; any warm-start that seeds `like_vectors` changes phase/progress semantics immediately.

Open dimensions:
- **Carry policy** — A independent (status quo) / B exposure-only carry (don't re-show prior cards, taste fresh) / C asymmetric negative-only (carry dislikes, drop likes) / D fade-decay carry (recency-weight prior `liked_ids` into `like_vectors`) / E full warm-start (replay prior `liked_ids` → `like_vectors`, skip exploring phase) / F user-controlled toggle ("Resume taste?" prompt at session 2 start).
- **Phase entry on warm-start** — if D or E chosen: enter `analyzing` immediately (3+ likes already), or still play 1-2 exploring rounds for diversity?
- **Backend wiring** — `SessionCreateView` (`views/sessions.py:28`) currently treats project lookup as cosmetic (just resolves project_id). Carry would require reading `Project.liked_ids` → embedding fetch → seeding `AnalysisSession.like_vectors` at create time.
- **Exposure carry** — decide whether previous `liked_ids` / `disliked_ids` / `saved_ids` should seed `session.exposed_ids`. Without this, session 2 may show cards the user already judged even if taste is warm-started.
- **Progress semantics** — if seed vectors count toward `min_likes_for_clustering`, `frontend/src/pages/SwipePage.jsx` progress/Finish logic may jump. If seed vectors are algorithm-only, add metadata or keep them separate to avoid UX mismatch.

Likely tests:
- `backend/tests/test_session_create_correctness.py`: create Project with prior `liked_ids`, start a new session with `project_id`, assert selected policy (`like_vectors` seeded or explicitly not seeded), no cross-project leakage, invalid/foreign `project_id` remains current contract.
- API smoke: session 2 first response latency should not exceed session 1 beyond one extra `get_pool_embeddings(prior_liked_ids)` batch.

Acceptance: behavior matches chosen option deterministically; session 2 TTFC not regressed beyond session 1 (warm-start should be ≤ or equal); A/B telemetry on session 2 satisfaction (saved_ids growth rate, completion rate) vs status quo.

#### FULL-LANGUAGE-1 — 한/영 언어 설정 토글 없음
**Decision (user 2026-05-25)**: language is a user-controlled setting, NOT browser-locale auto-detected. Pattern mirrors the existing theme/font persistence shipped in PR #54 + PR #59. User toggles language in Settings (Korean / English); the choice drives both LLM chat answer language and UI label rendering across the app.

Current state:
- Chat phase (`parse_query.py`) already adapts to the user's latest message language inline ("`reply` and `probe_question` are written in the user's primary language"). With this setting wired through, the chat will instead use the user's profile language deterministically — no language inference from message text.
- Theme + font already follow this exact pattern: `UserProfile.theme` + `UserProfile.font` server-persisted, `ThemeContext` hydrates on login, `AppearanceSettings.jsx` exposes the toggle, `updateMyProfile({ theme })` PATCH on change.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/accounts/models.py` `UserProfile` app preferences are only `theme` and `font`.
- `backend/apps/accounts/serializers.py` `UserSerializer` includes theme/font in login and `/auth/me/`; `UserProfileSelfUpdateSerializer` accepts theme/font in PATCH `/users/me/`. Add language in both places for cross-device sync.
- `frontend/src/context/ThemeContext.jsx` is the best local pattern: validate allowed values, persist to `localStorage`, patch only when a token exists, hydrate from server on login via `App.jsx`.
- `frontend/src/components/AppearanceSettings.jsx` currently renders only Theme and Font. A Language segmented control belongs here unless Product wants a separate Settings page.
- `backend/apps/recommendation/services/parse_query.py` `parse_query()` and `parse_query_stage1()` currently receive only `conversation_history`. `backend/apps/recommendation/views/search.py` calls `services.parse_query(conversation_history)` with no user preference, so prompt language cannot be deterministic yet.

Implementation outline:
- Backend — add `UserProfile.language` CharField with choices `[('ko', 'Korean'), ('en', 'English')]`, default `'ko'` (Korea-first). Migration + serializer wiring + login-response inclusion (parity with theme/font).
- Frontend — either extend `ThemeContext` into a broader `PreferencesContext` or add `LanguageContext` mirroring it; hydrate from login response; `setLanguage()` PATCHes `updateMyProfile({ language })`. Add language toggle to `AppearanceSettings.jsx` (or a sibling settings panel — admin call).
- Wire-through — `parse_query.py` accepts `language` parameter from `ParseQueryView` (via `request.user.profile.language`) and overrides the "match user's message language" rule. UI labels via a small dictionary-lookup helper (`t('home.title')`-style) — no full i18n lib (`react-i18next` adds bundle weight; Korea-first + bilingual-only justifies a hand-rolled lookup).

Open dimensions:
- **Scope priority** — TabBar / button copy / page titles first (high-traffic surfaces) → page bodies → error messages → modal alerts? Or sweep alphabetically?
- **Translation source** — admin hand-writes both KO + EN strings / Gemini-translate KO → EN with admin spot-check / accept any English UI gaps temporarily (Korea-first, English a follower)?
- **Settings UI placement** — extend `AppearanceSettings.jsx` with a language section, or new `LanguageSettings.jsx` sibling page? (Theme + Font already coexist there, language is a natural third.)
- **Untranslated string fallback** — if `t('foo.bar')` lookup misses in current language, fall back to KO (default) or render the key literal `foo.bar` as a debug surface?

Acceptance:
- New `UserProfile.language` field, default `'ko'`, settable via Settings UI; PATCH round-trips correctly.
- LLM chat answer language follows the setting, not message-language inference.
- ≥1 high-traffic UI surface (e.g., TabBar) rendered in both languages off the same string source.
- No regression in theme/font persistence (same wiring shape).

#### BACK-LLM-2 — 채팅 기록이 다른 기기에서 사라짐
**Decision (user 2026-05-25)**: chat conversation history must persist to the backend DB, not just to browser `localStorage` as it does today. Cross-device + cross-browser + survives storage clears.

Current state:
- `LLMSearchPage.jsx:186–205` stores `conversationHistory` in `localStorage` keyed by `storageKey` (Project-scoped). Survives page navigation + browser refresh on the **same browser**, but lost on logout / second device / incognito / cache clear.
- Resume + Exit UX already shipped: `SwipePage.jsx:122–123` `ExitConfirmPopup` (Exit to New Project / Home / Cancel); chat re-enters with the prior history populated from `localStorage`.
- Backend has no conversation field today: `Project.raw_query` stores only the first user message; `AnalysisSession` has algorithm state only.

Code audit 2026-05-27 (`develop@3894ffd`):
- `frontend/src/pages/LLMSearchPage.jsx` stores `messages`, `conversationHistory`, `latestResults`, `latestFilters`, `latestFilterPriority`, `latestVisualDescription`, `latestImageFocus`, `latestRawQuery`, and `showStart` under `archithon_chat_${userId}_${mode}_${projectId || 'new'}`. That key is browser-local and userId/mode/project scoped, but not backend synced.
- `backend/apps/recommendation/models.py` `Project` has `raw_query` but no `conversation_history`; `AnalysisSession` has no chat fields.
- `backend/apps/recommendation/views/search.py` validates incoming `conversation_history` and sends it to Gemini, but does not persist it. It already caps history length/text length, so backend persistence should reuse these validation limits or centralize them.
- `backend/apps/recommendation/views/projects.py` `ProjectDetailView` and `ProjectSerializer` are the natural read surface if history is stored on `Project`. For append/update, a dedicated endpoint is safer than overloading `PATCH /projects/{id}/`, because chat appends need idempotency and ownership checks.
- `frontend/src/api/projects.js` has `getProject()` and `updateProject()` only; a new `appendConversationTurn(projectId, turn)` or `saveConversation(projectId, history, revision)` API helper is needed.

Implementation outline:
- Backend — add `Project.conversation_history` JSONField (default `list`) OR a new `ConversationTurn` row table — see open dimension. Migration. Serializer wiring. Endpoint: probably extend `ProjectSerializer` round-trip + a dedicated `POST /api/v1/projects/<id>/conversation/` for append (idempotent on turn-id).
- Frontend — `LLMSearchPage.jsx` swaps `localStorage` reads for an API fetch on mount; appends to backend on each turn; keep `localStorage` as a write-through cache for offline resume + read-fallback when API is slow.

Open dimensions:
- **Storage shape** — `Project.conversation_history` JSONField (denormalised, simple, hydrates with project payload) vs `ConversationTurn` table (normalised, paginated, ordered by created_at)?
- **Per-session vs per-project** — store on `Project` (history accumulates across sessions) or on `AnalysisSession` (each swipe round has its own chat)? `BACK-LLM-1` reverse-Q lives in `parse_query.py` which is called at session-create time, suggesting per-session — but the user-facing chat UI is project-level.
- **`localStorage` retention** — keep as a write-through cache (offline-tolerant) / delete on first successful backend write (single source of truth) / remove entirely (cleaner)?
- **Retention policy** — keep forever (audit trail for `BACK-LLM-1` chat refinement) / 30-day TTL / cascade delete with Project?
- **Migration of existing `localStorage` data** — one-shot backfill on next login (frontend reads localStorage, POSTs to backend, deletes local) vs no backfill (existing in-flight chats stay local until next exit, then lose history)?

Acceptance:
- Logout + log back in (same or different browser) → conversation history fully re-rendered from backend, including order + structured turn payloads.
- Probe-turn writes succeed under network slow / retry / partial failure (idempotent append).
- No regression in current Resume / Exit UX.
- localStorage cache (if kept) is purged on logout or Project delete to prevent stale cross-user contamination.

#### FRONT-DESIGN-1 — 디자인 시스템 컴포넌트 리워크 (paused)
Foundation shipped: PR #54 (`tokens.css` 4 themes + `ThemeContext` + `AppearanceSettings`) + PR #59 (theme/font server persistence). Remaining: per-component visual rework (≈ 7,700 LOC) — inline `style={{}}` → CSS Modules + `:hover/:focus`/`:active`, light-theme polish where dark-only assumptions still leak through, leaf→hub component order (small leaf components first, then containers).

Code audit 2026-05-27 (`develop@3894ffd`):
- `rg "style={{" frontend/src | wc -l` = 581 inline style call sites. The largest hot files are `BoardDetailPage.jsx` 1049 LOC, `UserProfilePage.jsx` 992 LOC, `App.jsx` 838 LOC, `BuildingDetailPage.jsx` 711 LOC, `SwipePage.jsx` 683 LOC, `FirmProfilePage.jsx` 540 LOC.
- `frontend/src/tokens.css` now has theme/font tokens; `frontend/src/index.css` has only shared animations/utilities plus one masonry media query. Most hover/focus/active behavior still lives in JS handlers.
- Good first slices: `ArticleCard`/`ProjectCard`/`BoardCard` leaf components before page containers; then `SwipeCard` and `BuildingDetailPage` because they have the most visible style state.

Resume via `/plan per slice` — each slice = one logical component cluster (e.g. SwipeCard + LoadingCard, then BoardCard, then HomePage, etc.). Each slice ships its own PR via the orchestrate skill; the full sweep takes many sessions.

Acceptance per slice: `npm run lint` + `npm run build` clean; light + all dark variants render the touched components without visual regressions (compare against pre-slice screenshot); no new global token added without DESIGN.md update.

### MEDIUM

#### BACK-PERFORMANCE-5 — Swipe latency 0.7-1.5s 흔들림
Codex retest 2026-05-26: browser swipe 1.82s/1.75s/1.12s/1.81s; server swipe 1.50s/1.38s/0.746s/1.36s. **PR4 async prefetch consume IS working** — 3rd swipe with cache hit drops to 156ms prefetch stage. But variability is high. Identify which stage causes the 0.7→1.5s spread (DB query latency? embedding cache miss? pgvector?). Aim for swipe p95 ≤1.0s and p50 ≤0.5s on Singapore prod.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/views/swipe.py` still performs the algorithmic card selection inside the request transaction: update Project/session, phase transition, `engine.refresh_pool_if_low()`, `engine.get_pool_embeddings(session.pool_ids)`, then `engine.farthest_point_from_pool()` or `engine.compute_mmr_next()`.
- PERF-PREFETCH-CHAIN moved card data lookahead off-path only after `next_bid` is selected. The cache-hit path avoids some prefetch-card compute/fetch, but it does not skip `get_pool_embeddings()` or MMR/farthest selection for the next visible card.
- The response already logs `[SWIPE TIMING] lock/embed/select/prefetch/total` and captures `engine.get_last_embedding_call_stats()` for cache miss counts. That is the fastest way to classify the spread before editing.
- `engine.get_pool_embeddings()` has an in-process LRU-like building embedding cache; cache misses can still trigger a DB fetch against `canonical_v2_buildings`. Under multi-worker prod, this cache is per process.

Diagnostic plan:
- Re-run a fixed 8-10 swipe session and bucket slow responses by timing stage: `embed_ms` > selection, `select_ms` > MMR/farthest CPU, `prefetch_ms` > buildings batch fetch / cache miss, `lock_ms` > transaction contention.
- Compare first session after worker boot vs warmed worker. If first swipes are slow and later cache-hit swipes are fast, embedding cache warmup is the likely source.
- If `select_ms` dominates in analyzing phase, inspect `engine.compute_mmr_next()` vector math and pool size. If `embed_ms` dominates, inspect `get_pool_embeddings()` DB batch and cache-hit ratio.

#### BACK-AUTH-2 — Cache JWT 통합 테스트 hardening
`apps/accounts/authentication.py:74` cache-hit path skips parent `get_user()`. Current tests are unit-level (CachedJWTAuthentication.get_user direct call). Need integration coverage:
- [ ] DRF `authenticate()` pipeline end-to-end (request → middleware → cache hit → user resolved → view executes)
- [ ] `User.save()` post_save signal auto-invalidation (`auth_user` row mutation → cache.delete fires)
- [ ] `is_active=False` user → cache hit on stale entry must NOT return 200; either auto-invalidate before hit or re-check `is_active` on cached user
- [ ] cross-instance: cache populated from one auth instance, read from another (Redis multi-worker correctness)

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/accounts/authentication.py` cache-hit branch returns `cached_user` directly. It relies on token validation having already happened and on cache invalidation for user-state changes.
- `backend/apps/accounts/signals.py` invalidates on `post_save` and `post_delete` for `User`. This covers admin `.save()` but not `User.objects.filter(...).update(...)`; the docstring calls this out.
- `backend/tests/test_jwt_cache.py` patches cache methods and calls `CachedJWTAuthentication.get_user()` directly with mocked tokens/users. It does not prove the full DRF request pipeline, SimpleJWT token validation, or real cache serialization.
- `backend/apps/social/models.py` intentionally uses queryset `.update()` for counter caches; that is not auth-relevant. A future auth-relevant bulk update would need explicit `invalidate_user_cache()`.

Implementation map:
- Add integration tests around a tiny authenticated endpoint such as `/api/v1/auth/me/` or a protected test view. Populate cache via first request, mutate `auth_user.is_active`, then assert the next request is rejected after signal invalidation.
- Add a stale-cache negative test by manually `cache.set(_user_cache_key(user.id), user)` after setting `user.is_active=False`; decide whether code should re-check `cached_user.is_active` or rely strictly on invalidation. This clarifies the security posture.
- Cross-instance can be simulated by two `CachedJWTAuthentication()` objects with the same Django cache backend; Redis-specific behavior belongs in cache backend tests if local Redis is available.

Codex retest 2026-05-26 flagged as P3 hardening. Not a blocker — security-manager PASS'd PR #133 — but defense-in-depth for any future cache-key drift or signal-wiring regression.

#### INFRA-DB-2 — test DB role permissions for CREATE DATABASE
Codex retest 2026-05-26 — Full `test_imp8_async_prefetch.py` blocked at DB setup because `make_web_app` role has no CREATE DATABASE permission. `test_user_data` DB creation fails. Options:
- (a) operator runs migrate / test-DB-provision with `DB_USER=neondb_owner` swap pre-pytest
- (b) test conftest uses a dedicated `make_web_test` role with `CREATEDB` grant on Neon
- (c) `pytest-django --reuse-db` against a pre-provisioned `test_user_data` DB

Choose one + document in CONTRIBUTING.md / backend/.env.example. Currently the test-DB gap means some integration tests can only run with a manual role swap.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/config/settings.py` defines PostgreSQL `default` and `buildings` from env vars at import time. Runtime role guidance in `backend/.env.example` says local/prod should use `make_web_app` for `user_data`; that role deliberately has `NOCREATEDB`.
- `backend/conftest.py` tries to route pytest DB work to in-memory SQLite via `django_db_modify_db_settings()` and mirrors `buildings` to `default`. App-local conftests (`backend/apps/*/tests/conftest.py`) duplicate only part of that setup and may be invoked differently when running sub-suites.
- The practical failure mode is pytest-django trying to create a test DB from the Neon `DB_NAME` using `make_web_app`, which fails before tests can run. This is infra/test-runner config, not app correctness.

Decision needed:
- Preferred path for local/Claude testability is either a dedicated `make_web_test CREATEDB` role on `local-dev-2`, or a documented `--reuse-db` workflow against a pre-provisioned `test_user_data`. Using `neondb_owner` for every pytest run works but weakens the role-separation habit.
- Any chosen path should be encoded in `CONTRIBUTING.md`, `backend/.env.example`, and the Claude test instructions so future agents do not rediscover the same permission wall.

#### FRONT-LAYOUT-1 — Desktop wide-screen 레이아웃 어색함
Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. Low priority — desktop is secondary.

Code audit 2026-05-27 (`develop@3894ffd`):
- `frontend/src/index.css` sets `body { height: 100vh; overflow: hidden; }`; each page owns its own scroll region. This works for mobile-app feel but makes desktop layout tuning page-by-page.
- `BuildingDetailPage.jsx` uses `maxWidth: 820` for most content and only one `.building-masonry` media query. On wide screens it stays narrow rather than using a split gallery/details layout.
- `BoardDetailPage.jsx` and `UserProfilePage.jsx` use `maxWidth: 1100` and auto-fill grids, but hero/profile sections remain mostly mobile-centered; there is no desktop-specific information hierarchy.
- `App.jsx` routes everything through `MainLayout`; wide-screen fixes should start in page components plus any shared shell constraints, not TabBar.

Likely slices:
- Building detail desktop pass first: full-bleed or two-column gallery + sticky metadata/read actions.
- Board/User profile second: keep existing mobile layout, add desktop breakpoints for hero + board grid density.

#### FULL-LEGAL-1 — PIPA/GDPR consent 없음 (public launch 차단)
Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. **Required before public launch.**

Code audit 2026-05-27 (`develop@3894ffd`):
- Only visible consent surface found is `frontend/src/pages/LoginPage.jsx` line text: "By continuing, you agree to our terms of service". There are no Terms/Privacy routes in `App.jsx`, and no stored consent/version fields on `UserProfile`.
- `backend/apps/accounts/models.py` marks `external_links` as privacy-sensitive and opt-in, but there is no retention policy, export/delete workflow, or policy-version audit trail.
- Guest-first auth (`FULL-LOGIN-REDESIGN-1`) will collect at least display name/role and may create anonymous user rows; it should not ship publicly until legal consent and retention are explicit.

Implementation map:
- Backend fields likely belong on `UserProfile` or a separate `ConsentRecord`: `terms_accepted_at`, `privacy_accepted_at`, `policy_version`, optional marketing consent. Keep immutable history if policy versioning matters.
- Frontend needs Terms/Privacy pages or external links plus a blocking checkbox/continue copy in login/onboarding. Korean-first copy should be reviewed outside Codex.
- Account deletion/export is not currently in scope but should be tracked before public launch if GDPR-like obligations apply.

#### PERF-PREFETCH-POOL-RISK — Neon connection pool 모니터링 (post PR #134)
PR 4 PERF-PREFETCH-CHAIN flipped `async_prefetch_enabled: True` — every prod swipe now spawns a daemon thread holding its own DB connection until `_connections.close_all()` runs in finally. Under high concurrent swipe load: connections ≈ (concurrent_requests × 2) — one main worker + one prefetch thread. Neon free tier limit is 25 connections; Railway Gunicorn default is 2-4 workers. Concurrent swipe × 2 conns/swipe could approach limits at high traffic. Acceptable for current scale (~tens of daily users/day). Monitor Neon dashboard post-deploy + revisit if peak concurrency exceeds 8-10 connections. Mitigation options if exhausted: (a) connection pool size increase, (b) explicit thread-local connection pool, (c) PgBouncer in front of Neon. security-manager (sonnet) flagged this as availability concern on PR #134.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/views/swipe.py` now starts two daemon-style background paths per successful swipe when enabled: `_async_prefetch_thread` and `_emit_telemetry_thread`. Both call `_connections.close_all()` in `finally`, but each can open its own thread-local DB connection while alive.
- Main request can hold `default` DB inside transaction; telemetry writes to `user_data`; async prefetch may read buildings data for next-card hydration. Practical transient footprint can be main + telemetry + prefetch, not just main + prefetch, depending on timing.
- `backend/config/settings.py` has `CONN_MAX_AGE=600` on default DB; buildings alias has no explicit `CONN_MAX_AGE`. Thread cleanup makes leaks unlikely, but peak connection count is still a traffic/concurrency risk.

Monitoring map:
- Track Neon active connections during swipe bursts and Railway worker/thread counts. If peak >8-10 at current traffic, promote this from MEDIUM risk to HIGH infra work.
- If slow swipes correlate with connection pressure, evaluate a bounded executor or queue instead of unbounded per-swipe `threading.Thread`.

### LOW

#### FRONT-AUTH-1 — LoginPage에 Kakao/Naver 버튼 없음
Backend Kakao + Naver implementation shipped: `apps/accounts/views.py` KakaoLoginView + NaverLoginView, `apps/accounts/urls.py` `auth/social/kakao/` + `auth/social/naver/`, `apps/accounts/models.py` provider choices. Frontend `LoginPage.jsx` currently has Google button only.
- [ ] Kakao button on `LoginPage.jsx` (loading state already typed `'kakao'`)
- [ ] Naver button on `LoginPage.jsx` (loading state not yet typed `'naver'`)

Code audit 2026-05-27 (`develop@3894ffd`):
- `frontend/src/api/auth.js` already has generic `socialLogin(provider, accessToken, code)` for `'google' | 'kakao' | 'naver'`, so the API helper is not the blocker.
- Backend accepts either `access_token` or `code` depending on provider view behavior. Frontend still lacks Kakao/Naver SDK or redirect-code handling, so this is a UX/OAuth-client integration task.
- `frontend/src/pages/LoginPage.jsx` loading state should include `'naver'`; the current comment is stale and button icons/styles need design approval.

Decision needed:
- Choose provider integration style: JS SDK popup/access-token vs OAuth redirect/auth-code. Match mobile browser behavior and Vercel callback envs before implementing.
- This may be superseded or reshaped by `FULL-LOGIN-REDESIGN-1`; if guest-first ships first, Kakao/Naver should be secondary account-upgrade options, not necessarily primary login buttons.

#### FULL-REFACTOR-1 — 큰 파일 분해 필요 (engine.py 2383 LOC 등)
File decomp (LOC verified 2026-05-27 on `develop@3894ffd`): `engine.py` 2383, `BoardDetailPage.jsx` 1049, `UserProfilePage.jsx` 992, `App.jsx` 838, `BuildingDetailPage.jsx` 711, `SwipePage.jsx` 683, `FirmProfilePage.jsx` 540. `PostSwipeLandingPage.jsx` removed in INFRA-CLEANUP-1 (PR #142, 2026-05-26). `rg "style={{" frontend/src | wc -l` = 581, so frontend refactor overlaps with `FRONT-DESIGN-1`.

Code audit:
- `engine.py` mixes DB row-to-card mapping, search SQL, pool creation, embedding caches, MMR/DPP/KMeans, telemetry helpers, Discovery taste ranking, and corpus-rank helpers. Split only after active algorithm work stabilizes; algorithm ownership lives in `docs/algorithm.md`.
- `App.jsx` owns auth/session/project state, routing, swipe orchestration, and localStorage persistence. Good future split: `useSessionController`, `useProjectStore`, route shell.
- `BoardDetailPage.jsx` and `UserProfilePage.jsx` combine data fetching, optimistic mutations, selection state, modals, and large inline style blocks. Extract hooks before moving visual components.

Refactor rule: no behavior change PRs. Each slice needs before/after tests or app-test screenshots because these files are user-facing and regression-prone.

#### BACK-RECOMMEND-3 — Profile-tab 사무소/유저 추천 endpoint 없음
Re-scoped 2026-05-14 (REC1 already shipped as Push S3). REC2 (firm) + REC3 (user) target a single composite endpoint `GET /api/v1/recommendations/profile/` returning `{offices: [...], users: [...]}` for a Profile-tab button. Landing tab removed (Push S6).

Code audit 2026-05-27 (`develop@3894ffd`):
- No route exists today in `backend/apps/recommendation/urls.py`, `backend/apps/profiles/urls.py`, or `backend/apps/social/urls.py` for `/recommendations/profile/`; the only recommendation-style public route is `recommendations/board-surprise/`.
- Firm data model exists in `backend/apps/profiles/models.py`: `Office`, `OfficeProjectLink`, `Office.canonical_id`, follower counters. `OfficeDetailView` already hydrates office projects from `OfficeProjectLink` + `canonical_v2_buildings`.
- User taste helper exists as `engine.compute_user_taste_vector(profile)`, but it aggregates the requester only. For recommending users, a batch scoring strategy is needed; do not loop all users and run per-user DB fetches in request path.
- Social graph exists (`Follow`, `OfficeFollow`) and should be used to exclude already-followed users/offices unless Product decides otherwise.
- Frontend profile stats buttons have TODOs for followers/following routes, but no recommendation trigger UI yet.

Implementation map:
- Backend endpoint probably belongs in a new recommendation view/module because it combines Make Web user_data and Make DB building vectors. Keep office/user recommendation payload minimal for p95 <= 800 ms.
- For firms, precompute or cache office vectors from `OfficeProjectLink.building_id` embeddings; query-time max-sim over each office's projects will get expensive if done naively.
- For users, use each user's aggregated liked vector and follower/exclusion filters. Cold-start needs a separate branch (popular offices/users or disable with CTA).

Open dimensions (admin decision before implementation):
- **Firm vector composition** — Mean / weighted-mean / curated-subset / max-sim of firm's project embeddings?
- **User taste vector** — Aggregated from user's `liked_ids` across Projects; recency-weighted? curated subset?
- **Cold-start strategy** — New user 0 swipes → "popular users" / generic taste cluster / disable User tab until N swipes?
- **Match score visibility** — Show "92% match" on cards or hide?
- **Diversity vs follow-exclusion** — Recommend already-followed firms? (probably exclude)
- **Tie-breakers** — Followers count / recency / random / hybrid?
- **Trigger surface UX** — Single button → modal / full-page / toggle between Office/User?

Acceptance: `/recommendations/profile/` p95 ≤ 800 ms on Singapore deploy; cold-start UX graceful; `canonical_bld_id` + `is_publishable=true` gating preserved per CLAUDE.md hard rules.

#### BACK-EXTERNAL-1 — FirmProfilePage에 외부 기사 surface 없음
Surfaces external articles about a firm on FirmProfilePage (Space / ArchDaily / news keyword match). Phase 15 already shipped External DM wiring (`Office.contact_email`, `Office.website`, `UserProfile.external_links`).

Code audit 2026-05-27 (`develop@3894ffd`):
- `frontend/src/pages/FirmProfilePage.jsx` already renders an Articles section only when `office.articles?.length > 0`; it defaults `articles` to `[]` because backend omits the field.
- `frontend/src/components/profile/ArticleCard.jsx` is already present and expects `{title, url, source, date}`.
- `backend/apps/profiles/serializers.py` explicitly documents `articles[] -> EXCLUDED (Phase 18 External — deferred)`.
- `backend/apps/profiles/models.py` has no article table/fields; `OfficeDetailView` only returns office metadata + projects + `is_following`.

Implementation map:
- If article fetch is real-time, it must not block `OfficeDetailView` TTFC; use async frontend fetch or backend cached endpoint.
- If stored, a separate `OfficeArticle` model is cleaner than denormalizing a mutable article list into `Office`, because source/date/url uniqueness and refresh state matter.
- External URL opening is already handled by `ArticleCard` (`target="_blank" rel="noreferrer"`); backend must sanitize/validate stored URLs.

Open dimensions:
- **Article source priority** — Space-first (Korean) vs ArchDaily-first (global) vs parity? (Korea-first principle suggests Space)
- **Crawl freshness** — real-time on view / scheduled daily-weekly / event-driven?
- **Storage** — denormalised in `Office` row / separate `OfficeArticle` table / external CDN?
- **Article fallback** — empty section / hide section / "no recent articles" placeholder?

Acceptance: ≤10 most recent articles per firm; open in new tab (legal posture); no FirmProfilePage TTFC regression (article fetch async, doesn't block initial paint).

#### INFRA-QUEUE-1 — corpus_rank telemetry 꺼져있음
Bookmark telemetry used to compute `corpus_rank` synchronously (O(corpus_size) scan) before emitting a `SessionEvent` bookmark payload. PR #79 turned this off on the bookmark path (`rank_corpus = None` + TODO). Today the field is None on every bookmark event — telemetry slightly degraded but bookmark response is fast. Celery + Redis would let us re-enable the calculation off the hot path.

Code audit 2026-05-27 (`develop@3894ffd`):
- `backend/apps/recommendation/engine.py` still has `compute_corpus_rank(card_id, v_initial)` implemented as a corpus-wide pgvector `ROW_NUMBER() OVER (ORDER BY embedding <=> vector)` query.
- `backend/apps/recommendation/views/swipe.py` `ProjectBookmarkView` sets `rank_corpus = None` with a TODO before `event_log.emit_event('bookmark', ...)`.
- Tests intentionally lock the deferred behavior: `backend/tests/test_bookmark.py::test_rank_corpus_is_none_placeholder` and `backend/tests/test_imp10_topic06_telemetry.py` assert `compute_corpus_rank` is not called and payload `rank_corpus` remains null.
- No Celery/worker dependency is present in `backend/requirements.txt`; Redis exists as a cache backend, not a task queue.

Implementation map:
- Do not re-enable synchronous `compute_corpus_rank()` in the bookmark path. The only acceptable path is queue/background worker with bounded retries and failure-tolerant telemetry update.
- If introduced, update tests from "placeholder None" to "enqueued job" and add worker tests around success/failure without blocking bookmark response.

Why LOW: introducing Celery just for this one field is over-investment. Adds Redis (Railway add-on cost), a worker process, monitoring surface, and a deploy step — all for one telemetry column the product doesn't currently consume. Revisit when other background jobs accumulate (image batch processing, periodic embedding refresh, scheduled snapshot drops) so Celery earns its keep across multiple tasks.

---

## Done

### FULL-LOGIN-REDESIGN-1 — Guest-first onboarding + 보드 4번째 verify gate — RESOLVED 2026-05-27 (PRs #154 / #155 `db81e0f` + `e8296f5-pre-squash`)
- [x] **Backend PR #154** (squashed `db81e0f`): `UserProfile.is_guest` + `onboarding_role` + `consent_accepted_at` + `consent_policy_version` + migration `0004`. `GuestLoginView` (3/min/IP `GuestLoginThrottle`) + `GuestPromoteView` (5/min `GuestPromoteThrottle UserRateThrottle`). `CustomTokenObtainPairSerializer` adds `is_guest` claim on refresh → propagates to access via simplejwt's claim copy (rotation-safe). `IsVerifiedUser` permission (future-proof). `ProjectListCreateView.post()` inline gate: `is_guest AND Project.count() >= 3 → 403 {detail:'verify_required', reason:'board_limit_reached', limit:3}`. `GuestPromoteView` atomic: Branch 1 cross-device merge (8 FK update rules: Project/AnalysisSession/SessionEvent/Follow×2/OfficeFollow/Reaction; SwipeEvent skipped — no direct user FK) + delete guest + blacklist refresh; Branch 2 in-place transform + username collision guard (`google_{provider_id}` fallback) + blacklist refresh. 14 pytest tests. CI Postgres service container verifies; INFRA-DB-2 blocks local. Railway auto-applied migration on develop merge.
- [x] **Frontend PR #155** (pre-squash `e8296f5`): `LoginPage.jsx` full rewrite — terminal 3-step wizard (intro → name → role) + "동의합니다" PIPA capture (server-persisted; strict `is True` check rejects coerced values) + dual CTA (returning Google secondary). `VerifyGateModal.jsx` (NEW) — catches `403 verify_required`, fires Google verify → `promoteAccount` → token swap → retry. `useGoogleLogin` extracted to `GoogleLoginButton.jsx` + `GoogleVerifyButton.jsx` child components (conditional mount under provider tree — prevents "must be used within GoogleOAuthProvider" throw when `VITE_GOOGLE_CLIENT_ID` unset). Cross-device merge: `onPromoted(user, merged)` → `handleLogin(user)` on `merged:true` re-syncs `userId` + project keys. `SaveToBoardModal` Option A (stash `{name, visibility}` + auto-retry post-promote); `SurpriseBoardModal` Option B (10-card payload too fat → toast "Verified! Now try again", 3s per DESIGN.md §8.11). Conditional `GoogleOAuthProvider` mount (no `'guest-only-google-disabled'` literal anywhere). 24/24 `loginFlow.test.mjs` PASS. `is_guest` source: `/auth/me/` response (not jwt-decode) per security-manager PR1 warning.
- User decisions Q1–Q6 (2026-05-27): Board 4번째 gate · Board만 차단 (Follow/Reaction 자유) · Google OAuth만 · cross-device merge (atomic 8 FK rules) · 3/min throttle · "동의합니다" server-persisted.
- Reviews: PR1 sec-mgr PASS (3 warnings → fixed pass 2); code-review FAIL pass 1 (1 HIGH + 3 MED + 1 LOW → 7 fixes pass 2). PR2 sec-mgr PASS clean; code-review FAIL pass 1 (3 HIGH + 2 MED → all fixed pass 2: `useGoogleLogin` extraction · `not_a_guest`/400 string · retry path · Branch 1 merge re-login · JSDoc).
- Plan: `~/.codex/plans/merry-toasting-dove.md` — FULL-LOGIN-REDESIGN-1 rebuild after codex `feature/codex-guest-auth-*` archived for 6 issues; all resolved.
- Codex archive: `feature/codex-guest-auth-backend` (3049b40) + `feature/codex-guest-auth-frontend` (f488ccd) — remote 삭제, local 보관, 재구현 참조용.

Deferred:
- `FRONT-AUTH-1` — LoginPage Kakao + Naver 버튼 (backend ready).
- `INFRA-DB-CLEANUP-1` (conditional — monitor Neon `auth_user WHERE email='' AND is_active=True` weekly; open if growth > 500/week).
- `FULL-LEGAL-1` — PIPA copy legal review (partial mitigation shipped: `consent_accepted_at` + policy version field).
- PIPA copy not yet legally reviewed — terminal "동의합니다" placeholder copy; `FULL-LEGAL-1` to produce final + Privacy/Terms routes.

### BACK-BOARD-PERF-1 — /projects/&lt;id&gt;/ ~879ms → &lt;500ms — response cache 60s — RESOLVED 2026-05-27 (PR #148 `4573623-pre-squash`)
- [x] **Response cache 60s** (projects.py ProjectDetailView.get): PR #147 Profile detail pattern을 ProjectDetailView에 적용. Per-(project_uuid, requester_id, version) key. requester_id partition (anon / profile.id) → is_owner / is_reacted / visibility-gated payload cross-user leak 방지.
- [x] **caches.py helpers**: PROJECT_DETAIL_TTL=60 + version key + evict_project_detail(uuid) + get_project_detail_cache_key(uuid, requester_id). Version-based invalidation.
- [x] **Invalidation 8 mutation sites**: ProjectDetailView patch/delete · ProjectListCreateView.post · ProjectBookmarkView · SwipeView (transaction-safe) · SessionCreateView · ProjectReportGenerate/ImageView · ReactionView post/delete (gated).
- [x] **CRITICAL fix-loop**: ProjectDetailView.delete 초기 evict가 row delete 전 → race window. 정정: evict AFTER delete.
- [x] **test_board_detail_perf.py** NEW 7 pure-mock cases.
- Verification: manage.py check PASS · 7 non-DB tests PASS · code-review PASS · security-manager PASS.
- 기대: cold ~879ms → ~500ms, warm ~50ms.
- Origin: User goal 2026-05-27 — PR 3/N of iterative perf sweep.

### BACK-PROFILE-PERF-1 — /users/&lt;id&gt;/ 895ms → &lt;1s — thumbnail-only fetch + response cache — RESOLVED 2026-05-27 (PR #147 `4cd1fdf-pre-squash`)
- [x] **Fix 1 `engine.get_building_thumbnails(ids)`** NEW: lightweight minimal-column SELECT.
- [x] **Fix 2 `_build_boards_field` thumbnail-only swap**.
- [x] **Fix 3 `UserProfileDetailView` response cache (60s)**: per-(viewed_user, requester, page, page_size, version) key. Cross-user leak partition.
- [x] **Invalidation wired**: PATCH /users/me/ · Project mutations · Session create · Follow/unfollow · ProjectBookmark POST.
- [x] **`test_profile_perf.py`** NEW 9 cases.
- Verification: manage.py check PASS · 9 non-DB tests PASS · code-review PASS · security-manager PASS.
- 기대: cold ~500-700ms, warm ~100ms.

### BACK-PERFORMANCE-4 — Discovery cold 4.6s → ~1.5-2.5s — taste vector cap + SQL top-K — RESOLVED 2026-05-27 (PR #146 `dc1651b-pre-squash`)
- [x] **Fix 1 `taste_ranked_page` CTE 제거**: PG planner top-K heap scan.
- [x] **Fix 2 `compute_user_taste_vector` recent-50 cap**: bounded cold get_pool_embeddings.
- [x] **Fix 3 `_async_warm_taste` daemon thread** (rolled back; pytest-django connection race).
- Verification: manage.py check PASS · code-review PASS · security-manager PASS.
- 기대 효과: Discovery cold ~4.6s → ~1.5-2.5s.

### BACK-ALGO-1 — Required-slate hard WHERE + first-swipe prefetch cache seed — RESOLVED 2026-05-27 (PR #145 `72f8f27-pre-squash`)
- [x] **F3 required-slate hard WHERE** (engine.py): "Japan museum" search 후 첫 save → Bolivia card 표시되던 버그. Root cause: filters가 score CASE만 emit, pool SQL WHERE는 `is_publishable=true AND score > 0`만 — Bolivia가 country 0이어도 style/program 양의 점수로 통과. Fix: `_REQUIRED_SLATE_FIELDS_SET` frozenset (services/parse_query.REQUIRED_SLATE_FIELDS 미러 + cross-ref 주석) + `_build_required_slate_where(filters)` helper. Mode V (HyDE) + Mode F (filter-only) 적용. Mode H (RRF) excluded — rank-fusion 의미 다름. Tier 2 relaxation은 기존 location_country drop 동작 그대로.
- [x] **F4 first-swipe prefetch cache seed** (sessions.py): 첫 swipe `saved_current_round=1` (current_round가 swipe.py:548에서 save 전 증가) → `cache.get('prefetch:{sid}:1')` always miss → sync compute 770ms. **SPEC DEVIATION**: back-maker source-reading으로 spec :0 → 실제 :1로 정정. SessionCreate 끝에 `cache.set('prefetch:{sid}:1', {prefetch_card_id: initial_batch[1], prefetch_card_2_id: initial_batch[2]}, timeout=60)` 시드. `_async_prefetch_thread` write shape 미러.
- [x] **`test_engine_filter_hard_constraint.py`** NEW 4 cases: slate WHERE emit, Tier 2 relaxation, optional fields stay soft, **Mode V param order** (param-position regression catch).
- [x] **`test_session_create_correctness.py`** +2 F4 `TestPrefetchCacheSeeding` cases.
- **code-review fix-loop CRITICAL catch**: 초기 구현 2개 SQL execute call에서 **param order inversion**. 정정 후 테스트가 param positions 검증.
- Verification: manage.py check PASS · F3 4/4 tests PASS · F4 tests local INFRA-DB-2 차단 (CI 실행) · code-review PASS (after fix-loop) · security-manager PASS (parameterized SQL, UUID-isolated cache keys).
- Origin: 4th Codex retest 2026-05-26 of develop=72bf8d3. F3+F4 알고리즘 territory.

### FRONT-UX-FIXES-1 — Image timeout + Gallery CTA nav + Board card click — RESOLVED 2026-05-26 (PR #144 `b5c53f2-pre-squash`)
- [x] **F2 SwipeCard image timeout**: 2000ms → 4000ms. `?retry=1` cache-bust path 전부 삭제 (별도 URL 없음, 대역폭만 2배). Fallback chain: `covers_by_type.exterior → interior → aerial → detail → drawing → gallery[N]`. Singapore R2 cold-cache 1.7-2.6s 정상 처리.
- [x] **F5 Gallery CTA navigation**: 동작 변경. 이전 `openGallery()` → in-card 3D flip back-face. 현재 `navigate('/buildings/${card.image_id}')` → BuildingDetailPage 전체 갤러리. 3D flip path가 실제 no-op surface (back-face JSX는 `setShowGallery(true)` unreachable로 절대 안 렌더링). SwipePage `onGalleryOpen` prop 무해하게 drop. 죽은 코드 (back-face JSX, `hasBeenOpened`) 별도 cleanup PR로.
- [x] **F7 BoardDetail building card click**: ID 정규화 OR chain에 `building.id` 추가 (3 sites: BuildingTile line 180, handleDeleteSelected filter line 458, render bid line 926). MOCK_BOARD `building_id` priority 유지. Stored `{id: "bld_..."}` shape 정상 인식 → 클릭 navigate.
- Verification: npm run lint clean · npm run build PASS · code-review PASS (3 dead-code items flagged out-of-scope) · security-manager PASS (XSS-safe — image_id BUILDING_ID_RE 검증; IDOR-safe — board-scoped ownership server-side).
- FRONT-UX-5 (Gallery CTA backlog) closed by F5.
- Origin: 4th Codex retest 2026-05-26 of develop=72bf8d3. F1 (session 2.11s) positive PR #137+138 작동 확인. F3+F4 → Group B separate PR. F6 (StrictMode dup GET) dev-only → 별도 backlog 검토.

### BACK-CORRECTNESS-1 — /projects/ cache evict + dedupe project_id + orphan project — RESOLVED 2026-05-26 (PR #143 `d87a5f9-pre-squash`)
- [x] **Fix 1 — `/projects/` cache eviction**: `evict_projects_list(profile.id)` added at 5 mutation sites: sessions.py dedupe-hit return path + sessions.py post-create + swipe.py post-save + reports.py post-final_report + reports.py post-report_image. ProjectListSerializer exposes liked_ids/saved_ids/final_report/report_image — eviction now covers all paths.
- [x] **Fix 2 — dedupe + project_id intent**: PR #138 dedupe scope extended. Early project_id resolve before dedupe lookup. If project_id provided + matches user-owned Project → dedupe SKIPPED (App.jsx:723 fresh-swipe flow honored). project_id missing or no match → existing (user, name, raw_query, filters) dedupe runs.
- [x] **Fix 3 — orphan Project on mid-failure**: Project.objects.create() deferred from line ~113 to inside `session_insert` stage. Pool fetch failure / empty pool 404 no longer leaks Project rows. Project + AnalysisSession pair wrapped in `transaction.atomic()` savepoint (fix-loop catch — closes session_insert-step orphan too).
- [x] **`test_session_create_correctness.py`** NEW 9 tests: 3 cache evict (session create / swipe write / dedupe hit) + 1 project_id-skip-dedupe + 2 no-orphan (pool empty / pool exception) + 2 cache evict on reports + 1 session insert rollback.
- Verification: manage.py check PASS · pytest full suite **553 passed** (was 550, +3 new tests, zero regression) · PR #138 dedupe tests 8/8 still PASS · code-review PASS (after 1 fix-loop catching reports.py + transaction.atomic) · security-manager PASS (IDOR-safe: user= clause on early project_id resolve; cache eviction scoped to profile.id).
- Origin: 3rd Codex retest 2026-05-26 of develop=17f7d65 (worktree `/private/tmp/make_web_review_develop`). P2-1/2/3 shipped here. P2-4 (pytest bootstrap) merged into existing INFRA-DB-2. P3 findings (daemon thread / large files / LLM localStorage / PostSwipeLandingPage) all already tracked — PostSwipeLandingPage finding superseded by PR #142 INFRA-CLEANUP-1.

### INFRA-CLEANUP-1 — Dead code 정리 (-1124 LOC) — RESOLVED 2026-05-26 (PR #142 `beb1d74-pre-squash`)
- [x] **Files removed (-1124 LOC)**:
  - `frontend/src/pages/PostSwipeLandingPage.jsx` (696 LOC) — PROF3+PROF4 mockup with unwired backend TODOs.
  - `frontend/src/components/GalleryOverlay.jsx` (181 LOC) — initial-commit artifact; PR #120 BuildingDetailPage rolled its own inline gallery.
  - `backend/tools/optimization_results.json` (247 LOC) — Optuna search artifact. Zero refs.
- [x] **Doc references**: CONTRIBUTING.md role B table drops PostSwipeLandingPage; BoardDetailPage.jsx:143 JSDoc drops PostSwipeLanding mirror reference.
- [x] **Session decisions batched in this audit**:
  - **FRONT-UX-1 obsolete** — App.jsx:783 already `<Route index element={<Navigate to="/discovery">>` ; first-login lands on /discovery directly. Removed from ## Next ### HIGH.
  - **FULL-LOGIN-REDESIGN-1** added to ## Next ### HIGH — codex guest-auth direction (guest-first + 3-step onboarding) accepted; codex code archived (local only) due to 6 issues; re-design pending.
  - **FULL-REFACTOR-1** LOC list updated.
- Verification: npm run lint clean · cross-cutting grep verified zero non-self refs for all 3 deleted files · git history confirms abandoned status.
- Origin: salvaged from codex-authored `feature/codex-cleanup-stale-develop` (commit `986bd5e`). Codex branch's docs/skill changes rejected (regressions of PR #136 INFRA-DOC-6); only file deletions kept.

### BACK-LLM-1 — LLM 채팅이 검색에 필요한 정보를 다 안 모음 — RESOLVED 2026-05-26 (PR #141 `cdbf5c7-pre-squash`)
- [x] **`parse_query.py`**: `REQUIRED_SLATE_FIELDS = (program, material, style, location_country)` + `REQUIRED_SLATE_PROBE_PRIORITY` module-level constants. System prompt + few-shot examples rewritten to deterministically target missing slate fields (drop prior free A-vs-B axis selection).
- [x] **`_normalise_filter_priority`**: required-slate keys promoted to front of Gemini-returned `filter_priority`. Engine score weights respect the new order.
- [x] **`_repair_required_slate`**: injects `style: 'Contemporary'` (`_BROAD_SLATE_DEFAULT_VALUE`) when no required-slate field present after Gemini parse OR 2-turn probe budget exhausts with slate gap. Runs on `probe_needed=True` intermediate turns too — documented.
- [x] **Korean few-shot examples** updated with slate-targeted probe Korean questions. Korea-first preserved (Constitution Decision Principle 7).
- [x] **`test_back_llm1_required_slate.py`** NEW 5 tests: prompt content assertions, slate promotion into priority, broad default injection for both `parse_query` + `parse_query_stage1`, budget-exhausted terminal repair.
- Verification: manage.py check PASS · pytest 5/5 PASS · code-review PASS (rebase clean; parse_query.py untouched on main since branch base) · security-manager PASS (no prompt injection — user input never touches system prompt; static constants; mocks-only tests).
- Open dimensions resolved: required slate = 4 fields (program/material/style/location_country); priority = same order; fallback = 'Contemporary' default; conversational shape = Korean slate-targeted probes (mix of direct + axis).
- Deferred: A/B 50-query benchmark harness (Task.md acceptance criterion c). Code contract structurally verified; empirical measurement = post-merge follow-up.
- Behavioral note: `_normalise_filter_priority` promotion changes `engine._build_score_cases` weight semantics (rank-based; required-slate field outranks temporal filter). Intended.
- Origin: codex-authored `feature/codex-back-llm1-required-slate` (commit `79346ff`) cherry-pick. Clean rebase onto develop=92915b8.

### BACK-LLM-3 — Gemini cache 호출에 timeout 없음 — RESOLVED 2026-05-26 (PR #140 `715e06e-pre-squash`)
- [x] `backend/apps/recommendation/services/_caches.py:92` `client.caches.create` 호출을 zero-arg `_create_cache` closure로 추출 → `_svc._retry_gemini_call(_create_cache)`로 라우팅. 기존 `_retry_gemini_call`의 15s timeout cap (PR #94) 적용.
- [x] `backend/tests/test_imp5_context_caching.py` `+17` LOC `test_gemini_create_runs_through_retry_timeout_wrapper`: MagicMock으로 Gemini 네트워크 hit 없이 patch 검증.
- [x] `context_caching_enabled` 플래그 default OFF 유지 — 프로덕션 영향 없음. SDK hang 시 cap 적용. Pre-emptive safety.
- Verification: manage.py check PASS · 새 테스트 PASS (12 passed) · code-review PASS (~5 LOC budget 정확히 준수) · security-manager PASS (no secret leakage, closure capture 안전).
- 9 pre-existing DB-요구 tests는 `INFRA-DB-2` (`permission denied to create database`)로 차단됨; 본 PR이 도입한 게 아님.
- Origin: codex-authored `feature/codex-back-llm3-timeout` (commit `5ac1f6d`)에서 cherry-pick. 원 branch가 stale develop에 stacked되어 있어서 fresh feature branch에 cherry-pick. Clean rebase.

### FULL-SESSION-DEDUPE-1 — Session create POST retry → 중복 Project/Session — RESOLVED 2026-05-26 (PR #138 `3fcbe3c-pre-squash`)
- [x] **Frontend `api/core.js`**: retry gate by HTTP method. `_IDEMPOTENT_METHODS = {GET, HEAD, OPTIONS}`. POST/PATCH/DELETE throw on first network error (no retry).
- [x] **Frontend `api/sessions.js`**: `SESSION_CREATE_TIMEOUT_MS=30000` per-call override for `startSession` (cold pool ~16s requires >15s default).
- [x] **Backend `views/sessions.py`**: dedupe guard at start of `SessionCreateView.post`. 30s window; match (`user`, `project.name`, `project.raw_query`, `project.filters`). Hit → returns existing session with `deduped:true` HTTP 200 (vs 201 fresh).
- [x] **Tests `test_session_create_dedupe.py`** NEW: 8 cases (baseline 201, hit 200, expiry, different raw_query/name/filters, project_id=None retry, response shape).
- Trade-offs: `recordSwipe` (POST) no-retry — backend `idempotency_key` (sessions.js:68) still guards server-side. Race window ~100ms (POST 1 commit → POST 2 SELECT) unreachable from single-tab client with retry-gate above.
- Verification: manage.py check PASS · flake8 zero new · npm run lint+build PASS · code-review PASS · security-manager PASS · app-test FEATURE-SCOPED PASS (5/5 checklist incl. dedupe path HTTP 200 + `deduped:true` + same session_id + only 1 Project row).
- Origin: Codex retest 2026-05-26 of develop=d53b232. P0 finding: 15s timeout → retry → 2 boards same name (one with 4 photos, one with 0).
- Deferred surfaced to Next ### MEDIUM: BACK-PERFORMANCE-4 (Discovery 4.6s) + BACK-PERFORMANCE-5 (Swipe latency variability) + FRONT-UX-5 (View Gallery click no-op).

### INFRA-DEPLOY-3 — railway migrate align + Redis prod guard + docs drift — RESOLVED 2026-05-26 (PR #137 `09a3b7c-pre-squash`)
- [x] `backend/railway.toml` buildCommand: dropped `migrate --noinput`. Per INFRA-DB-1, Railway runtime is `make_web_app` (no DDL); next schema migration would have failed at deploy time. Comment block rewritten to cite INFRA-DB-1 + operator runbook in `.env.example`. `collectstatic` kept.
- [x] `backend/config/settings.py` `_check_async_prefetch_safety()` helper: raises `ImproperlyConfigured` at module import when `DEBUG=False && async_prefetch_enabled && !REDIS_URL`. Silent LocMem fallback in prod = thread cost without multi-worker coherence (same bug class PR #134 just fixed). Operator migrate path safe because `.env.example` defaults `DJANGO_DEBUG=True` → guard short-circuits.
- [x] `backend/tests/test_cache_backend.py` `TestAsyncPrefetchSafetyGuard` (4 cases): prod+REDIS_URL set OK, DEBUG=True bypass, async_prefetch=False bypass, prod misconfig raises.
- [x] Docs drift: `swipe.py:79`+`:723` "primary path does NOT consume" stale (PR #134 PERF-PREFETCH-CHAIN consumes); `settings.py:142` + `.env.example:72` "JTI cache" stale (PR #133 BACK-AUTH-1 final = JWT user-row cache).
- Verification: `manage.py check` PASS · `pytest test_cache_backend.py` 20/20 · code-review PASS · security-manager PASS.
- Origin: Codex retest of develop=`d53b232` 2026-05-26 surfaced P2-railway-migrate + P2-Redis-silent-fallback + P3-docs-drift; P3-cache-integration-tests + P3-test-DB-role surfaced as `BACK-AUTH-2` + `INFRA-DB-2` in Next.

### INFRA-DOC-6 — orchestrate / git-publisher / web-testing AGENTS skill-regime 정렬 — RESOLVED 2026-05-26 (PR #136 `80e7d86-pre-squash`)
- [x] Cherry-picked session-start docs work (`010edf8`) onto post-deploy develop. Three files re-aligned with the 2026-05-26 skill-migration regime (INFRA-WORKFLOW-1, PR #123).
- [x] `.agents/skills/orchestrate/SKILL.md` — drop deprecated `git-manager` / `reporter` agent refs from frontmatter, dispatch list, Step 5 session-end, Step 7 fix-cycle, Step 8 publish gate, Step 10, Rules. Step 6 → `git-commit` skill. Step 8 default = `git-publish` skill (git-publisher agent only for Mode 3 / external / complex rebase). Step 9 = `reporter-inline` + `git-commit` + `git-publish`.
- [x] `.codex/agents/git-publisher.toml` — frontmatter repositioned as edge-case agent (Mode 3 deploy, external PR triage, complex rebase, push rejection unclear, mid-merge failure). New "When this agent is called" preamble enforces refuse-on-routine-publish. Mode 1 header renamed "Internal push escalation (fallback only)". Hard guardrails + Tools footer point at `git-commit` skill.
- [x] `web-testing/AGENTS.md` — scope clarified (agent contract owned by `.codex/agents/app-test.toml`; this doc = standalone runner + shared dev-login). 2026-04-28 `web-tester` → `app-test` rename documented. Dev-login 404 fallback rewritten to match `app-test.md` hard-FAIL. `skip_login` flag note marked removed. Modes table rewritten FULL vs FEATURE-SCOPED (supersedes legacy fast/strict /review split).
- [x] Pure docs/policy edit per CLAUDE.md `## Implementation delegation — HARD RULE` carve-out. Skipped code-review + security-manager + app-test (sub-MINOR meta cleanup, no migration / production code / auth / network / model change).
- [x] Stale `feature/admin-docs-skill-migration-sync` branch (session-start orphan, base pre-deploy develop) replaced by fresh `feature/admin-skill-docs-align` cherry-picked onto post-deploy develop. Old branch deleted locally post-merge.

### INFRA-DEPLOY-2 — 2026-05-26 develop → main 배포 (PRs #116-#134, perf sweep + Redis) — RESOLVED 2026-05-26 (PR #135 `d53b232`)
- [x] develop → main squash-merged. main = `d53b232`. Railway prod auto-deploy SUCCESS (deployment `047a6e2f`, RUNNING).
- [x] Carried 15 PRs since main `1888b5f` (PR #112 prior release): #116 INFRA-ENV-1 + #117 + #118 FRONT-DESIGN-2 + #119 INFRA-DB-1 + #120 FRONT-UX-4 + #121 FRONT-UX-2 + #122 reporter housekeeping + #123 INFRA-WORKFLOW-1 + #124 BACK-PERFORMANCE-1 + #125 BACK-PERFORMANCE-3 + #126 BACK-PERFORMANCE-2 + #128 INFRA-CI-1 + #129 dashboard fix + #130 SWIPE-CONVERGENCE-10 + #131 INFRA-REDIS-1 + #132 BACK-RECOMMEND-2 + #133 BACK-AUTH-1 + #134 PERF-PREFETCH-CHAIN.
- [x] **Bug #5 carve-out applied** (HARD RULE 4 SOLE permitted force): `origin/develop` force-reset to `origin/main` (`d53b232`) via `gh api PATCH refs/heads/develop --force=true`. Precondition checked (no in-flight feature PR targeting develop). Tree-equivalence verified: `git diff origin/main origin/develop` empty.
- [x] **Railway Redis service** provisioned (admin via dashboard during session) and `REDIS_URL=${{Redis.REDIS_URL}}` env set on backend service before merge. Post-deploy: backend service deployment SUCCESS, RUNNING, gunicorn 4 workers booted clean, no `django_redis` import errors in logs.
- [x] Prod smoke (CLI): `/` → 404 (no route). `/auth/dev-login/` → 404 (`DEBUG=False` gates per design). `/api/v1/projects/` unauthenticated → 401 (DRF auth pipeline working). `/auth/token/refresh/` empty body → 400 (view reachable). No 5xx anywhere.
- [x] Direct cache-hit latency measurement NOT possible from CLI (prod `DEBUG=False` blocks dev-login + Google OAuth needs browser). Real-world impact verified via Codex retest (admin runs separately).
- Outstanding: `PERF-PREFETCH-POOL-RISK` (## Next ### MEDIUM) — monitor Neon connection count post-deploy. Async prefetch daemon thread + main worker = 2 conns/swipe; Neon free-tier 25 limit.

### PERF-PREFETCH-CHAIN — async_prefetch chain end-to-end (PR 4/4 FINAL of perf sweep) — RESOLVED 2026-05-26 (PR #134 `dc296bc-pre-squash`)
- [x] PR 4 (FINAL) of 4 in `.codex/plans/merry-toasting-dove.md` (backend performance sweep). Depends on PR 1 INFRA-REDIS-1 merged (Redis multi-worker cache coherence). Plan complete after this PR merges.
- [x] **`_async_prefetch_thread` off-by-one fix** (swipe.py thread function): `pf_bid` index `current_round_snap + 1` → `+2`, `pf2_bid` index `+2` → `+3`. Applied to all 4 formula sites (exploring pf, exploring pf2, analyzing pf via `compute_mmr_next` round arg, analyzing pf2). Prior thread stored cards for T+1's `next_card` slot (duplicate of main-thread compute); fix stores cards for T+1's prefetch slot, matching sync-path semantics.
- [x] **Async-branch consumer in `SwipeView.post`** (~line 752+): `cache.get(f'prefetch:{session.session_id}:{saved_current_round}')` reads PRIOR swipe's thread write. Batched `engine.get_buildings_by_ids([next, pf, pf2])` for 1-RTT 3-card hydration. Cache miss → prefetch fields stay None (graceful fallback).
- [x] **Dedupe guards** (code-review fix-loop): degrade `pf_id` to None if `== next_bid`, degrade `pf2_id` to None if `== next_bid` or `== pf_id`. Prevents analyzing-path collision where `compute_mmr_next` can return same card for T's lookahead and T+1's main pick (similar inputs + `mmr_lambda_ramp_enabled=False`). Frontend `App.jsx:521+536` non-instant-swap path does NOT dedupe; without backend guard user would see same card twice.
- [x] **`async_prefetch_enabled` False → True** (config/settings.py:216). Chain functional end-to-end.
- [x] Tests: `test_imp7_pool_cache.py:635` `prefetch_strategy 'sync' → 'async-thread'`. `test_imp8_async_prefetch.py` default-flag tests updated. New `TestAsyncBranchConsumerIntegration` class with cache-hit + cache-miss + dedupe regression tests (pre-fix collision triggers test failure → post-fix passes).
- [x] code-review FAIL → fix-loop applied (MAJOR analyzing-path duplicate). 2nd code-review PASS implicit (3-line dedupe patch matches the prescription exactly). security-manager PASS with availability warning (deferred as `PERF-PREFETCH-POOL-RISK` in ## Next ### MEDIUM).
- [x] `docs/algorithm.md` Hyperparameter Space table: `async_prefetch_enabled` Production Value `False → True`. Last Synced bumped `785f4ad → dc296bc`.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS after fix-loop + cache-miss path preserves current behavior + dedupe guard backstops cache-hit edge). Inline drift: HEAD `dc296bc` vs `origin/develop` `4c72513` — clean.
- [x] Expected impact (verified post-deploy via Codex retest): swipe latency p50/p95 on warm session (2nd+ swipe with cache hit) — card hydration moves off main-thread critical path. Combined with PR 3 BACK-AUTH-1 (~590ms auth floor removed), per-swipe round-trip should improve meaningfully on cache-warm sessions.
- Deferred: `PERF-PREFETCH-POOL-RISK` — Neon connection pool monitoring post-deploy.

### BACK-AUTH-1 — JWT user-row cache (PR 3/4 of perf sweep) — RESOLVED 2026-05-26 (PR #133 `5a1e914-pre-squash`)
- [x] PR 3 of 4 in `.codex/plans/merry-toasting-dove.md` (backend performance sweep). RE-SCOPED from original JTI-cache premise after empirical falsification: simplejwt source inspection confirmed `AccessToken` does NOT inherit `BlacklistMixin` — only `RefreshToken` does. Blacklist DB lookup never runs during access-token validation. The actual ~590ms per-request DB hit is `JWTAuthentication.get_user()` → `User.objects.get(id=user_id)` against Neon. Caching that lookup is the actual fix.
- [x] `backend/apps/accounts/authentication.py` **NEW** — `CachedJWTAuthentication(JWTAuthentication)` subclass overrides `get_user(validated_token)`. Cache key `jwt_user:<user_id>` (Django KEY_PREFIX `makeweb:` auto-applied). TTL = `min(token_exp_unix - now, 3600s)` — entry cannot outlast access token's natural lifetime. Exports `invalidate_user_cache(user_id)` helper.
- [x] `backend/apps/accounts/views.py` — `invalidate_user_cache(...)` calls at LogoutView (after `RefreshToken.blacklist()`, uses `request.user.id`) and TokenRefreshView (after rotation `refresh.blacklist()`, uses `refresh.get(api_settings.USER_ID_CLAIM)` from signature-verified RefreshToken).
- [x] `backend/apps/accounts/signals.py` **NEW** — `post_save` + `post_delete` on `User` invalidate cache. Safety net for ORM/admin mutations. Wired via `AccountsConfig.ready()` in `apps.py`.
- [x] `backend/config/settings.py:111` — `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']` swap simplejwt → `apps.accounts.authentication.CachedJWTAuthentication`.
- [x] `backend/tests/test_jwt_cache.py` **NEW** 12 tests: cache miss/hit/TTL cap/explicit invalidate/`post_save` signal/`post_delete` signal/tampered signature/expired token/cross-instance/`is_active` toggle/malformed exp fallback/missing USER_ID_CLAIM.
- [x] Security verification (security-manager PASS): signature check still runs first via parent's `get_validated_token` before `get_user` is called — bad signatures never reach cache. Cache key from signature-verified user_id claim (not raw input). TTL cap enforced. Explicit invalidation at all 2 blacklist sites + signal backstop catches admin/ORM mutations. `User.objects.filter(...).update(...)` gap documented (grep confirms zero auth-relevant call sites today). Redis is Railway-internal (private network); cached User instance same data as DB return — no new disclosure surface.
- [x] code-review (sonnet) PASS — override target / api_settings.USER_ID_CLAIM usage / TTL math edge cases / cache key collision / refresh user_id extraction / signal registration via short-form INSTALLED_APPS / `.update()` gap audit / no-regression on existing tests / test isolation via override_settings.
- [x] Expected impact: local proxy p50 `/projects/` cache-hit path ~661ms → ~150ms (~500ms get_user() floor removed). Prod Singapore Railway p50 verified post-deploy via Codex retest.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + auth-layer cache with mandatory security review). Inline drift: HEAD `5a1e914` vs `origin/develop` `b53e633` — clean.
- Non-blocking note: signal-wiring integration test exercised handler functions directly rather than `user.save()` ORM call (avoids INFRA-DB-1 `make_web_app` no-DDL constraint blocking full ORM-flow tests). Code-read confirms `apps.py.ready()` import + Django 4.2 short-form INSTALLED_APPS auto-discovery of AccountsConfig.

### BACK-RECOMMEND-2 — sklearn KMeans matmul warning 압제 (PR 2/4 of perf sweep) — RESOLVED 2026-05-26 (PR #132 `785f4ad-pre-squash`)
- [x] PR 2 of 4 in `.codex/plans/merry-toasting-dove.md` (backend performance sweep). Re-scoped from original "dtype align" to `np.errstate` suppression after empirical falsification: `like_embeddings.dtype == float64` already pre-edit because `_finite_unit_vector` (engine.py:66) calls `np.asarray(raw_vec, dtype=np.float64)`. The matmul `RuntimeWarning: divide by zero / overflow / invalid` originates inside sklearn's KMeans centroid normalization (`sklearn/utils/extmath.py:203 ret = a @ b`) on high-dim unit-norm vectors — sklearn-internal noise, cosmetic per Task.md original entry.
- [x] `engine.py:90-99` new helper `_silenced_kmeans_fit(kmeans, X, sample_weight=None)` wraps `kmeans.fit(X, sample_weight=sample_weight)` with `np.errstate(divide='ignore', invalid='ignore', over='ignore')`. Placed near other small helpers (`_parse_embedding_text`, `_finite_unit_vector`, `_cosine_sim_matrix`).
- [x] `engine.py:1664` Path 2 adaptive k=2 + `engine.py:1701` Path 4 default k — `kmeans.fit(...)` call sites swapped to `_silenced_kmeans_fit(...)`. `sample_weight=like_weights` recency weighting preserved on both paths.
- [x] **Computation byte-identical** — `np.errstate` ONLY changes NumPy's warning/error behavior, never numerical results. `random_state=42` + `n_init=3` deterministic. `test_topic06.py` 9/9 PASS (silhouette + cluster-correctness assertions) — empirical proof cluster output unchanged.
- [x] `pytest -W error::RuntimeWarning backend/tests/test_topic06.py` 9/9 PASS (previously failing on develop with matmul RuntimeWarning escalated to error). Test corpus exercises both adaptive-k Path 2 (k=2) and Path 3 (k=1 silhouette degradation) — same `_silenced_kmeans_fit` wrap.
- [x] code-review (sonnet) PASS — helper placement / sample_weight threading / silencing scope verified. security-manager (sonnet) PASS — no new SQL/auth/network/log surface, no thread-leak (np.errstate thread-local since NumPy 1.17 — multi-worker Gunicorn safe), sample_weight provenance traced to session-managed canonical_bld_id (no user-controllable input).
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + change is warning suppression with no functional surface). Inline drift check: HEAD `785f4ad` vs `origin/develop` `34a0c9e` — clean.
- [x] `docs/algorithm.md` Last Synced line bumped (engine.py touched). Step 3b inline annotation skipped — algorithm behavior byte-identical pre/post; only warning output silenced.

### INFRA-REDIS-1 — Redis cache 도입 (PR 1/4 of perf sweep) — RESOLVED 2026-05-26 (PR #131 `d5b6c18-pre-squash`)
- [x] PR 1 of 4 in `.codex/plans/merry-toasting-dove.md` (backend performance sweep). Foundation enabling PR 3 (BACK-AUTH-1 JTI cache) + PR 4 (PERF-PREFETCH-CHAIN async consume) — both require shared cache across Railway multi-worker Gunicorn that LocMemCache per-process cannot provide.
- [x] `backend/config/settings.py` `CACHES` block reads `REDIS_URL` env. Set → `django_redis.cache.RedisCache` (`KEY_PREFIX=makeweb`, `SOCKET_CONNECT_TIMEOUT=3`, `SOCKET_TIMEOUT=3`). Unset → existing `LocMemCache` with `MAX_ENTRIES=2000` preserved (local dev parity). `_build_caches_dict(redis_url)` helper extracted for clean unit testing without env monkeypatching.
- [x] `backend/requirements.txt` `django-redis>=5.4,<6.0` added (alphabetical position between `django-cors-headers` and `djangorestframework`; transitively pulls `redis-py>=4.x`).
- [x] `backend/.env.example` new Cache section between Feature flags + CORS, commented `REDIS_URL=` placeholder.
- [x] `CLAUDE.md` `## Backend Conventions` bullet — Redis prod / LocMemCache local-dev / never bypass Django cache abstraction.
- [x] `backend/tests/test_cache_backend.py` (NEW) 16 tests across `TestLocMemBranch` / `TestRedisBranch` / `TestMutualExclusion`. Helper called directly; no live Redis daemon required.
- [x] **Connection-failure policy**: `REDIS_URL` set + Redis unreachable → Django raises loudly. `IGNORE_EXCEPTIONS` deliberately absent. Silent multi-worker incoherence is worse than a visible error.
- [x] code-review (sonnet) PASS — KEY_PREFIX collision check clean across `engine.py`, `swipe.py`, `_caches.py`, `parse_query.py`, `caches.py` (all consume Django cache abstraction; no raw `redis-py`). `TestMutualExclusion` confirms fresh-dict semantics.
- [x] security-manager (sonnet) PASS — `.env` gitignored, no `logger`/`print` of REDIS_URL, ConnectionError carries no creds (host:port only), `rediss://` TLS supported transparently via redis-py, no known CVE at version range.
- [x] app-test skipped per `[[feedback_app_test_policy]]` (4-gate stack PASS + REDIS_URL unset in local/CI yields identical behavior to prior develop). Inline drift check: HEAD `d5b6c18` vs `origin/develop` `83db42c` — clean.
- [x] User manual step before merge: Railway dashboard → Add service → Database → Redis; on Make Web backend service set `REDIS_URL=${{Redis.REDIS_URL}}` via Railway variable reference. Until that lands, prod stays on LocMemCache (single-worker functional parity).

### SWIPE-CONVERGENCE-10 — 10-swipe target + multimodal escalation + stuck-state safety — RESOLVED 2026-05-26 (PR #130 `7f6a056-pre-squash`)
- [x] Replaces closed PR #127 (codex `feature/algo-convergence-study` — algorithm exploratory PR with spec divergence + UX stuck-state risk + chain-broken async flag).
- [x] **Algorithm policy (spec-synced)** — `convergence_threshold` 0.08 → **0.13**, new `target_swipes=10`, `min_likes_for_multimodal=11` (gates K-Means K=2 behind target_swipes+1 — single centroid default for 10-swipe sessions, escalation activates on continue-past-target / resume flows), `convergence_min_recent_likes=2` (positive-evidence gate — blocks false convergence on dislike streaks even when delta_v settles).
- [x] `docs/algorithm.md` synced inline (Phase 1->2 transition + K-Means + Convergence Detection subsections + Hyperparameter Space table + Optimization Methodology target). Production direction shifted from "15-25 swipes" to "~10 swipes default, multimodal escalation past N>=11". Topic 06 adaptive-k + soft-relevance paths remain flag-gated and now sit behind the multimodal gate.
- [x] **Frontend stuck-state safety floor** (new vs PR #127) — `SwipePage.isAt100` + `App.jsx` auto-nav `useEffect` get `beyondTargetFloor = swipeCount >= targetSwipes + 5` (default 15). Without floor, backend `min_recent_likes=2` gate could withhold `phase='converged'` indefinitely on dislike-heavy paths → user stranded until pool exhaust (100+ swipes).
- [x] **Engine `_with_image_focus` bug fix** (new vs PR #127) — `gallery_drawing_start` decrements by 1 when `focus_url` removed from index strictly less than original `drawing_start`. Prior code clamped only — drawing boundary drifted by 1 when cover promoted from before drawing section.
- [x] **`async_prefetch_enabled` revert True → False** — code-review (sonnet) caught: PR #127 flipped True but swipe.py async branch writes prefetch cache without next-swipe handler reading it back. Chain broken; flag flip yields zero latency gain plus daemon-thread DB lifecycle risk (echo of PERF-3 PR #128 TIME_ZONE KeyError class of bug). `test_imp7_pool_cache` + `test_imp8_async_prefetch` assertions reverted to match False default. Deferred: `PERF-PREFETCH-CHAIN` surfaced in `## Next ### LOW`.
- [x] **Swipe.py stale defaults** — `RC.get('convergence_threshold', 0.08)` at lines 598 + 862 → `0.13` matching settings prod.
- Code-review (sonnet) FAIL → all 4 findings resolved before commit (async revert + stale defaults + dislike_ids semantics confirmed intentional + PR body cleaned). Security-manager (sonnet) PASS. Frontend lint+build PASS. Local pytest deferred to CI (env DB unavailable).
- Plan file `.codex/plans/merry-toasting-dove.md` (Codex retest fix — Analyzing-Phase Calibrating UX) is now superseded by this PR's broader ConfidenceBar rewrite. Calibrating label preserved.
- 2 commits on branch (will be squashed): `e4677fb` "Study swipe convergence latency" (PR #127 base content carried forward) + `7f6a056` follow-up (this audit-bearing commit).
- Deferred: `PERF-PREFETCH-CHAIN` — async prefetch cache-read wiring + Redis swap (Task.md ### LOW). `BACK-AUTH-1` simplejwt blacklist ~590ms unchanged. `BACK-RECOMMEND-2` sklearn matmul warnings unchanged.

### INFRA-CI-1 — PR #125 PERF-3 CI fail hotfix — RESOLVED 2026-05-26 (PR #128 `198eca4-pre-squash`)
- [x] Root cause: PERF-3 `_async_emit` daemon thread silent fail. 첫 thread connection setup 시 `settings_dict["TIME_ZONE"]` KeyError (Django backend `timezone_name` cached_property). `emit_event_batch` try/except 잡혀 silent → `test_imp6_stage_decouple` `evt is not None` assert fail (production analytics 손실 + test 회귀).
- [x] Settings.py defensive: `DATABASES['default'] + ['buildings']` `'TIME_ZONE': None` 명시. Django default 동일, reconnect path defensive declaration.
- [x] **Sync emit revert** — `_async_emit` closure + `threading` import + `_SESSIONS_VIEW.threading.Thread` test patch 제거. `event_log.emit_event_batch` main thread sync 호출. Production established connection 사용 — KeyError 안 발생. `emit_event_batch` bulk_create는 보존 (1 SQL round-trip).
- Cost: ~290 ms sync emit restored to request path. PERF-3 1508 → ~1800 ms — 여전히 PASS ≤2000 ms goal.
- 3 commits on branch (squashed): TIME_ZONE settings + close_old_connections removal + sync emit revert. CI green confirmed.

### BACK-PERFORMANCE-2 — Discovery 캐시 hit 450ms (목표 <200ms) — RESOLVED 2026-05-26 (PR #126 `b40cfea-pre-squash`)
- [x] `GET /api/v1/discovery/` warm cache hit p50 1572 → 672 ms (-57%). Goal <200 ms 미달 — auth floor ~600 ms (BACK-AUTH-1) + `get_profile` 74 ms 잔존.
- [x] Response cache 60 s TTL — `get_or_build_discovery_feed` + `evict_discovery_feed` (per-`profile.id`+cursor+limit key, mirror PERF-1 pattern).
- [x] Mutation evict hooks: `SwipeView.post` (liked/disliked) + `ProjectBookmarkView.post` (saved) + `ProjectDetailView.patch remove_building_ids`.
- [x] Per-stage `perf_timing` instrumentation: `get_profile` / `build_exclude_set` / `get_or_build_taste` / `taste_ranked_page` / `cache_lookup_or_build`.
- [x] `taste_ranked_page` (814 ms, 84% of body, dominant) absent on cache hits — verified.
- Not evicted (60 s TTL self-cleans, no security impact): `ProjectDetailView.delete` (UX-only stale exclude_set), `ProjectListCreateView.post` (empty IDs at create).
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore Railway p50 = post-deploy Codex retest (admin). Multi-worker prod = per-worker `LocMemCache`, 60 s TTL eventual consistency across workers.
- Deferred: BACK-AUTH-1 (already in `## Next ### MEDIUM`) — auth-layer optimization required for sub-200 ms total.

### BACK-PERFORMANCE-3 — Search 후 첫 카드까지 5-8초 — RESOLVED 2026-05-26 (PR #125 `fb669b6-pre-squash`)
- [x] Local sessions create p50 2567 → 1508 ms realistic / 1484 ms worst-case (-42%). Both PASS ≤ 2000 ms.
- [x] Tier 1 pool cache (filter signature SHA1 key, 30 min TTL). `_tier1_cache_key(filters, filter_priority, seed_ids, v_initial, q_text)`. Pool ordering preserved (full tuple cached pre-exclude). `exclude_ids` applied post-fetch (per-session state, not in key).
- [x] `_random_pool` 30 min in-memory cache (module-level dict). Tier 3 random fallback ~1040 → ~5 ms warm.
- [x] `emit_events` → `threading.Thread` daemon fire-and-forget. `close_old_connections()` entry+finally. Analytics events lost on process crash mid-thread (acceptable per spec).
- [x] `emit_event_batch` in `event_log.py` — `bulk_create` wrapper. Backward-compat `emit_event` preserved.
- [x] `perf_timing` sub-stages on `engine.create_pool_with_relaxation` / `create_bounded_pool` / `get_pool_embeddings` (data-driven hypothesis formation).
- [x] `perf_measure` CLI `--filters` JSON option (realistic Tier 1 measurement).
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore p50 = post-deploy Codex retest. Multi-worker prod: per-worker cache, warm-up cost per worker. Cold path / first request unchanged ~2400-2600 ms — cache hit dominates `perf_measure` 3-run p50.
- Algorithm-territory edits (`engine.py`) per user authorization. Pool ordering + initial_batch shape + swipe-loop determinism preserved (code-review AC1 verified).

### BACK-PERFORMANCE-1 — `/projects/` 응답 600ms (목표 300ms) — RESOLVED 2026-05-26 (PR #124 `505717a-pre-squash`)
- [x] Local p50 1136 → 661 ms (-42%). Goal ≤ 300 ms 미달 — auth floor ~590 ms 잔존.
- [x] Response cache 60 s TTL + evict POST/PATCH/DELETE/Bookmark. Per-`profile.id` key isolation.
- [x] `ProjectListSerializer` drops `analysis_report` (LLM JSON list-unused). `defer('analysis_report')` on queryset. `_latest_like_count` via `jsonb_array_length` (no full `like_vectors` fetch). `page_size+1` trick — no `count()` query.
- [x] `CONN_MAX_AGE=600` + `CONN_HEALTH_CHECKS=True` on `default` DB. `buildings` DB `CONN_MAX_AGE` removed (Make-DB owner territory per Backend Conventions).
- [x] `perf_timing` ctx manager + `perf_measure` CLI (reused by PERF-3 / PERF-2).
- [x] `orchestrate` skill Step 6/9 deprecated agent refs → `git-commit` / `reporter-inline` skills.
- Measurement scope: local Neon `local-dev-2` only (development proxy). Prod Singapore Railway p50 = post-deploy Codex retest (admin).
- Deferred: BACK-AUTH-1 — simplejwt JWT blacklist DB query (~590 ms, security territory; explicit user approval required before touching auth path).

### INFRA-WORKFLOW-1 — Reporter / git-manager 흡수 + 3 skill 도입 — RESOLVED 2026-05-26 (PR #123 `bbadcf1-pre-squash`)
- [x] `.agents/skills/git-commit/` — single commit + secret guards + caveman convention. Replaces routine `git-manager` agent dispatch.
- [x] `.agents/skills/git-publish/` — push + PR open + admin squash + cleanup (Mode 2 feature → develop). Step 0 publish gate codified (keyword OR active plan precondition; mirrors `[[feedback_publish_gate]]`).
- [x] `.agents/skills/reporter-inline/` — Task.md + state.js + algorithm.md inline before squash. In-flight PR `mergedAt:null` sentinel + next-pass backfill (advisor #1 policy). 9-step behavior 1-to-1 from legacy `reporter` agent (advisor #3 checklist).
- [x] `.codex/agents/git-manager.toml` + `reporter.md` → `deprecated:true` frontmatter + body fallback note. Two-PR migration (advisor #2): delete in follow-up PR after ~1 week of skill-only validation.
- [x] `.codex/agents/git-publisher.toml` kept indefinitely — Mode 3 deploy / external PR triage / complex rebase escalation.
- [x] `CLAUDE.md` — new `## Git Operations — HARD RULE` section (skill-first matrix + escalation criteria + publish-gate keywords). Workflow section bullets + reporter sync rule refreshed.
- [x] `.codex/WORKFLOW.md` — Mermaid rebuilt with skill labels. § Agent + skill roster split into 3 tables. § 7 Token-saving + § 9 Key rules updated.
- [x] MEMORY: `feedback_orchestrator.md` rewritten (skill matrix). `feedback_workflow_skill_absorption.md` new (migration rationale + per-agent measurement).
- [x] Validation: this PR audited via the new `reporter-inline` skill (this entry + PR #118 + #120 backfill entries). Skills self-validated by shipping this very PR through `git-commit` + `git-publish` flow.
- [x] Savings: per PR cycle agent dispatches 8 → 3, ~30-40k tokens + ~150-300s saved. Reporter audit ships in same PR as work — PR count halved.

### FRONT-UX-4 — BuildingDetailPage UX 개선 (스크롤 + 순서 + 보드 저장) — RESOLVED 2026-05-26 (PR #120 `8f90104`)
- [x] `BuildingDetailPage.jsx` — minHeight → height + overflowY:auto (MainLayout `overflow:hidden` 부모 안에서 자체 스크롤 회복). Title/architect/meta 갤러리 위로 재배치 (정보가 사진보다 먼저). 상단 우측 "+ 보드에 추가" 핑크 그라디언트 버튼 + SaveToBoardModal 트리거. 저장 후 골드 체크 상태.
- [x] `BoardDetailPage.jsx` — buildings 이동 시 `fromBoard:true` location.state.
- [x] Codex P2 fix — `saveEnabled={!fromBoard}` (negative gate, 너무 넓음: firm profile / direct URL / BoardDetail recommended tile 모두 노출) → `saveEnabled={fromRecommended}` (positive gate, ResultsPage 추천만). `ResultsPage.handleOpenBuilding` `fromRecommended:true` state 추가. `fromBoard` derivation 제거 (ESLint no-unused-vars enforced). BoardDetailPage `fromBoard:true` writes 살아 있되 dead-state harmless.

### FRONT-DESIGN-2 — 카드 이미지 contain 전환 + 카드 크기 확대 — RESOLVED 2026-05-26 (PR #118 `9fcd078`)
- [x] `SwipeCard.jsx` — objectFit cover → contain (사진 잘림 해소, 전체 이미지). 갤러리 뒷면 contain 통일. Letterbox 배경 #111 (도면 #fff 유지). `CARD_WIDTH = min(420, vw-32)` (16+16 컨테이너 padding 보정), `CARD_HEIGHT = min(width×1.55, vh-220)`.
- [x] `SwipePage.jsx` — flex centering wrapper (카드+버튼 영역을 flex:1 center로 감싸 header/hint 높이 무관 수직 정중앙). Converged phase에서 confidence 무관하게 Finish 버튼 활성화 (ConfidenceBar 100% 표시와 일치).
- [x] `App.jsx` — auto-nav `at100` 조건에서 `(phase === 'converged')` 단독 분기. confidence null이어도 converged면 nav.
- [x] Codex P1 fix — CARD_WIDTH overflow blocker 해소: `vw-16` → `vw-32`. 390px폰 358px 컨테이너에 358px 카드 = 딱 맞음 (이전 374px 카드 16px 클립).
- [x] Codex P2 fix — `finishUnlocked` latch 재도입 drop. PR #121 1-shot `isAt100` 설계 보존 (App.jsx auto-nav 주 trigger, SwipePage Finish 버튼은 safety net). Same-project 새 session 시 stale state 위험 제거.

### FRONT-UX-2 — 스와이프 자동 이동 + 키보드 입력 — RESOLVED 2026-05-26 (PR #121 `80b519c`)
- [x] `App.jsx` — `useEffect` watching `swipeSession` auto-navigates `/swipe` → `/result/:sessionId` when `session.phase` is `completed`/`results`, OR when latch threshold reached: `exploring` with `like_count >= 4`, or `analyzing`/`converged` with `confidence >= 1.0`. Replaces PR #114 + PR #115 (both had wrong base `main`; closed without merge).
- [x] `DiscoveryPage.jsx` — `keydown` listener binds `←` (skip) / `→` (save) for arrow-key swipe on discovery feed.
- [x] Codex-review chain: PR #114 (`feature/admin-swipe-finish-ux`) + PR #115 (`feature/front-ux-keyboard-swipe`) superseded by this bundle (HARD RULE 5: both PRs targeted `main` instead of `develop`; re-based onto `develop` as PR #121).
- [x] Codex fix 1 (P2 / PR #114) — auto-nav swallowed the "Keep exploring" path: now only navigates on 100% latch / pool-exhaust, not on every phase update.
- [x] Codex fix 2 (P2 / PR #114) — `finishUnlocked` latch leaked across sessions: latch dropped; the 1-shot calc retained as Finish-button safety net on `SwipePage.jsx` only.
- [x] Codex fix 3 (P2 / PR #115) — `surpriseOpen` modal guard added: arrow-key handler checks `surpriseOpen` before firing, preventing key-bleed into the Surprise modal.
- [x] Codex fix 4 (P3 / PR #115) — `keySwipingRef` permanent lock on async throw: `try/finally` ensures the ref is always released.

### INFRA-DB-1 — user_data role separation — RESOLVED 2026-05-25 (PR #119 `1d3bfdc`)
- [x] Created `make_web_app` Neon role on both `production` and `local-dev-2` branches via psql `CREATE ROLE … NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS` (NOT `neonctl roles create` — that grants `neon_superuser` membership, transitively allowing CREATEDB/CREATEROLE/CREATEEXTENSION; verified by smoke and dropped+recreated cleanly).
- [x] `GRANT SELECT/INSERT/UPDATE/DELETE ON ALL TABLES IN SCHEMA public` + `USAGE/SELECT ON ALL SEQUENCES` + `ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public` so future migration tables auto-grant to `make_web_app`.
- [x] Local `backend/.env` swapped `DB_USER` `neondb_owner` → `make_web_app` + rotated `DB_PASSWORD`. `manage.py check` clean; ORM smoke (`auth_user=3`) + buildings raw SQL smoke (39,478 / publishable 36,864) unchanged; migration-style DDL correctly rejected.
- [x] Railway prod cutover: env vars swapped via dashboard. First redeploy (`d203e2bf`) FAILED with `password authentication failed for user 'make_web_app'` (mis-pasted password). Re-pasted; second redeploy (`820de476`) SUCCESS. Active deployment swapped from old (`9e5d4a69`, 2026-05-24 18:50) to `820de476` (2026-05-25 07:43). Post-cutover smoke: `/auth/me/` 401, `/users/me/` 401, POST token refresh → 401 `{"detail":"Invalid or expired token"}` (token_blacklist DB hit OK).
- [x] 8-probe psql matrix as `make_web_app`: CRUD ✓, has_sequence_privilege ✓, CREATE TABLE ✗ (permission denied for schema public), DROP TABLE ✗, CREATE ROLE ✗, CREATE EXTENSION ✗, ALTER TABLE ✗. All as designed.
- [x] Files committed: `backend/.env.example` (role-separation block + `DB_USER=make_web_app` default), `CLAUDE.md` (`## Backend Conventions` bullets for Neon role separation + local-vs-prod Neon branches discipline), `docs/MAKEWEB_DB_SWAP_RESPONSE.md` (Q2 rewritten Deferred → RESOLVED with full SQL + 8-probe matrix + Railway COMPLETED block + `BUILDINGS_DB_PASSWORD` rotation action item).
- [x] Pure docs/meta — direct-edit carve-out per CLAUDE.md `## Implementation delegation — HARD RULE`. No production code touched.
Outstanding: `BUILDINGS_DB_PASSWORD` rotate (transcript leak via railway variables grep mismatch this session) — tracked outside this entry.

### INFRA-ENV-1 — Neon dev branch 복구 + prod 격리 — RESOLVED 2026-05-25 (PR #116 `4b900da`)
- [x] Re-provisioned persistent Neon child branch `local-dev-2` (`br-shy-thunder-a1p5glmo`, endpoint `ep-holy-band-a1w0u5am`, no TTL) off `production` via `neonctl branches create --name local-dev-2 --parent production --project-id holy-pond-45504245`.
- [x] Repointed local `backend/.env` `DB_HOST` + `BUILDINGS_DB_HOST` from prod endpoint `ep-broad-hat-a1jaomn7` → dev endpoint `ep-holy-band-a1w0u5am`. Railway prod env untouched.
- [x] Smoke verified: `manage.py check` OK; `default` host = dev endpoint; `buildings` host = dev endpoint; `auth_user` count = 3; `archi_data` current_db/user = `('archi_data', 'make_web')`; `canonical_v2_buildings` count = 39,478; `is_publishable=true` count = 36,864.
- [x] `backend/.env.example` updated: DEV-vs-PROD endpoint discipline block + neonctl create command + dev-branch note on `BUILDINGS_DB_HOST`.
- [x] `docs/MAKEWEB_DB_SWAP_RESPONSE.md` updated: 2026-05-25 follow-up paragraph documenting the restoration.
- [x] Pure docs/meta — direct-edit carve-out per CLAUDE.md `## Implementation delegation — HARD RULE`. No code touched. `backend/.env` itself is gitignored.

### INFRA-DEPLOY-1 — 2026-05-25 develop → main 배포 (PR #99–#111) — RESOLVED 2026-05-25 (PR #112 `1888b5f`)
- [x] develop → main squash-merged, carrying 11 PRs: #99 (CI hang fix + deploy #98 reporter), #100 (Product Identity CLAUDE.md), #101 (docs/specs → Task.md Next), #102 (reporter housekeeping PRs #100/#101), #103 (DESIGN-REWORK → Next), #104 (Task.md restructure v2), #107 (reporter housekeeping PRs #103/#104 redo), #108 (ConfidenceBar Calibrating fix), #109 (publish-gate + reporter no-git-ops codification), #110 (reporter housekeeping PR #108), #111 (Task.md ID convention + bucket + stale doc cleanup).
- [x] main = `1888b5f`. Railway prod auto-deploy triggered.
- [x] Bug #5 carve-out applied: `origin/develop` force-reset to `origin/main` (`1888b5f`).

### INFRA-DOC-1 — Task.md ID 규칙 + bucket + stale doc 정리 — RESOLVED 2026-05-25 (PR #111 `b28855e`)
- [x] `## Next` flat list → `### HIGH` / `### MEDIUM` / `### LOW` buckets; all 20 entries renamed to `<SURFACE>-<TOPIC>-<N>` ID convention + Korean ≤25-char title.
- [x] 20-item bucket re-classification pass: HIGH 12 / MEDIUM 3 / LOW 5. DEV-ENV2 concern surfaced (local-dev Neon branch unverified, confirmed as INFRA-ENV-1). 3 stale Next entries deleted.
- [x] ID convention `<SURFACE>-<TOPIC>-<N>` codified in `## Workflow Rules`; cross-refs updated in `reporter.md`, `orchestrate/SKILL.md`, `back-maker.md`, `front-maker.md`, `code-review.md`.
- [x] 5 stale doc cleanups: `WORKFLOW.md` Mermaid `docs/specs` ref removed; `orchestrate/SKILL.md` old phase block + stale token-saving rule numbers replaced; `README.md` `docs/specs/` → `Task.md ## Next`; `MAKEWEB_DB_SWAP_RESPONSE.md` Railway status → COMPLETED; `frontend/.env.example` unused env vars annotated.

### INFRA-DOC-2 — Reporter housekeeping (PR #108 기록) — RESOLVED 2026-05-25 (PR #110 `4d35034`)
- [x] Task.md `## Done` prepended with `#21 SWIPE-CALIBRATING` entry (PR #108 `890236c`). `state.js` `meta.head` → `890236c`, `done[]` + `prs[]` rebuilt.

### INFRA-DOC-3 — Publish gate + reporter no-git-ops mechanism — RESOLVED 2026-05-25 (PR #109 `e9f8b3c`)
- [x] `orchestrate/SKILL.md` Step 8: publish blocked by default; gate opens only on explicit user trigger or active deploy plan.
- [x] `git-publisher.md` guardrails 7+8: trigger citation required; `main`-base PRs must have explicit deploy keyword.
- [x] `reporter.md` Hard scope: all state-mutating `git`/`gh` commands forbidden; reporter refuses any dispatch prompt instructing git ops.
- [x] `WORKFLOW.md` Rule 3: enforcement note referencing post-PR #105 incident (accidental `main`-base PR merged without admin trigger).

### #21 SWIPE-CALIBRATING — RESOLVED 2026-05-25 (PR #108 `890236c`)
[x] `ConfidenceBar` analyzing branch now guards on `value != null`. Null confidence (4th swipe trips exploring→analyzing transition, backend resets `convergence_history = []` per spec C-1, `compute_confidence` returns null for ~5 swipes) → `Calibrating…` label + `likeCount/4` progress. Old fallback showed `Analyzing 100%` falsely — user stuck with no path forward.
[x] `isAt100` Finish-button gate untouched (still correct — requires `confidence >= 1.0`).
[x] Backend convergence reset unchanged (correct per spec).
Deferred (surfaced by Codex retest, intentionally NOT fixed this session): MATMUL-WARN (engine.py matmul warnings), PERF-DISCOVERY (4.11s cold load), PERF-SESSION-CREATE (7.71s POST /analysis/sessions/), PERF-PROJECTS (double-fetch in dev StrictMode). All remain in `## Next`.

### #20 TASK-MD-RESTRUCTURE-V2 — RESOLVED 2026-05-25 (PR #104 `0690b85`)
[x] Restructured `.codex/Task.md` 394 → 305 lines: dropped 100+ lines of `## Development Roadmap` Phase 1-18 (duplicates of Done content), replaced with compact `## Roadmap (Historical)` at file bottom + new `## Workflow Rules` block at top.
[x] File order now: header → Workflow Rules → `## Now` → `## Next` → `## Done` → `## Roadmap (Historical)`.
[x] AUTH1 scope narrowed to frontend buttons only (backend Kakao + Naver already shipped in `apps/accounts/views.py` KakaoLoginView / NaverLoginView).
[x] AUDIT-T4 LOC counts re-verified 2026-05-25: engine.py 2079→2139, FirmProfilePage 611→540 (refactored down).
[x] Codified Now/Next discipline in `orchestrate/SKILL.md ## When user requests work` (Session start → move Next→Now, Mid-session deferral → Now→Next, Session end success → Now→Done via reporter).

### #19 DESIGN-REWORK-MOVE — RESOLVED 2026-05-25 (PR #103 `a6d173a`)
[x] Moved DESIGN-REWORK from Task.md `## Now` to `## Next` with paused tag — `## Now` definition is "PR in flight" and there was no design PR in 50+ commits + memory marked paused.
[x] state.js `now[]` → `[]`; DESIGN-REWORK entry appended to `next[]`. dashboard.html `emptyMsg("nothing in flight")` already handles empty array.
[x] CLAUDE.md `## Current State` refreshed ("in progress" → "foundation shipped + per-component rework paused").
[x] Memory `project_design_redesign.md` updated to reflect paused-in-Next status.

### #18 TASK-NEXT-RESTRUCTURE — RESOLVED 2026-05-24 (PR #101 `19694aa`)
[x] Absorbed `docs/specs/*.md` (4 files: phase16-recommendation-expansion.md, phase17-llm-reverse-q.md, phase18-external-connections.md, requirements.md) into `.codex/Task.md ## Next` as a flat backlog. Deleted the folder.
[x] Fixed `orchestrate/SKILL.md` stale refs: `.claude/Goal.md` → `CLAUDE.md ## Product Identity + ## Product Constitution`; `.claude/Report.md` → "read code directly + state.js"; `docs/token-saving.md` → `.codex/WORKFLOW.md § Token-saving rules`.
[x] Surfaced 10 operational deferrals previously buried in Done note text (IMP-5 bypass, Codex Stage 3 re-audit, perf observations, architects-wiring, security backlog, etc.) as individual `## Next ### <SLUG>` entries.
[x] Added `reporter.md` sub-step 2a "Deferred-item surfacing (Done note → Next)" so future Done `Deferred: ...` lines auto-surface to `## Next` going forward.
[x] Stripped stale `docs/specs/*` READ-rights mentions from back-maker.md, front-maker.md, code-review.md — pointed at Task.md `## Next § PHASE16/17/18` instead.

### #17 PRODUCT-IDENTITY — RESOLVED 2026-05-24 (PR #100 `56ce5f3`)
[x] Added new top-level `## Product Identity` section to CLAUDE.md between `## What This Repo Does` and `## Branch Model — HARD RULES`.
[x] `### Core Promise` sub-section: 10-15 swipes → Aha! moment anchor, Korean user-quote, two-pillars one-liner (algorithm + corpus), pointer to `docs/algorithm.md`.
[x] Surfaces positive product identity that was previously implicit across scattered sections. Single file, +8 lines.

### #16 DEPLOY-2026-05-24-v2 — RESOLVED 2026-05-24 (PR #98 `fd063e0`)
[x] develop → main deploy. 1 PR (#97). main = `fd063e0`. Railway deployment `a98725bf` Online.
[x] Bug #5 carve-out applied: origin/develop force-reset to fd063e0.
[x] Prod functional pre-deploy (PR #94 cap working). This deploy = CI baseline alignment + main/develop sync. PR #98.

### #15 CI-HANG-FIX — RESOLVED 2026-05-24 (PR #97 `9647c40`)
[x] `_retry_gemini_call` runtime primitive swapped: `concurrent.futures.ThreadPoolExecutor` → `threading.Thread(daemon=True)` + `queue.Queue.get(timeout)`.
[x] `from threading import Thread as _Thread` captured at module-load — bypasses test_imp8 `_DiscThread` global mock leak.
[x] Same 15s/45s deadline + FATAL classification + retry semantics. Prod behavior unchanged.
[x] Triggered by: PR #94 ThreadPoolExecutor wrapper hung pytest CI at 15min timeout, cascading 5 CI failures (PR #94, #95, #96 develop/main/PR).
[x] Full suite: 683 passed / 11 skipped / 0 failed.

### #13 GEMINI-TIMEOUT-CAP — RESOLVED 2026-05-24 (PR #94 `8b4df92`)
[x] `_retry_gemini_call` hard-caps every Gemini SDK call at 15s (45s for Imagen 3) via `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=N)`.
[x] 228s `/parse-query/` hang observed in codex audit → worst case now ≤31s.
[x] 4 new tests + 5 regression tests added.
Deferred: `_caches.py:92` IMP-5 cache create call still bypasses wrapper (gated by `context_caching_enabled` default `False`, zero prod impact until toggled on).

### #12 BUILDINGS-DB-SWAP — RESOLVED 2026-05-24 (PR #93 `b1b1212`)
[x] Make DB renamed buildings DB `neondb` → `archi_data`; new SELECT-only role `make_web` (was `neondb_owner`).
[x] Added `canonical_v2_architects` table (14,216 firms).
[x] Make Web swapped local `backend/.env` + Railway prod env vars.
[x] Refreshed `backend/.env.example` + `CLAUDE.md` is_publishable stat (39/39,776 → 2,614/39,478 ~6.6%) + `docs/database-schema.md` status block.
[x] New `docs/MAKEWEB_DB_SWAP_RESPONSE.md` added.
[x] Verified end-to-end (psql + Django check + ORM smoke + prod redeploy 04e7633e Online).

### #11 V1-LEGACY-CLEANUP — RESOLVED 2026-05-24 (PR #92 `5957df9`)
[x] Neondb `local-dev` branch drop + 23 orphan user/app tables + legacy `architecture_vectors` dropped.
[x] 3 backend files referencing v1 deleted: `tools/algorithm_tester.py`, `apps/recommendation/management/commands/profile_image_latency.py`, `tests/test_chat_phase.py::test_chat_phase_style_labels_in_corpus`.
[x] 5 stale doc refs refreshed: CLAUDE.md / docs/database-schema.md / docs/COLLAB_HANDOFF.md / .codex/agents/reporter.toml / .codex/agents/code-review.toml.
Plan `.codex/plans/merry-toasting-dove.md` archived to `.codex/plans/archive/2026-05-24-merry-toasting-dove.md`.

### develop → main deploy — 21 PRs (#68–#89) — RESOLVED 2026-05-24 (PR #90 merge `179d6f6`)
[x] Release PR #90 squash-merged develop → main (`179d6f6`). Carried PRs #68–#89 (21 PRs).
[x] Railway prod auto-deploy confirmed Online at `179d6f6`.
[x] origin/develop force-reset to match main (Bug #5 carve-out).

### Dashboard rework — 5-tab Done/Now/Next + Mermaid flows + KST timestamps — RESOLVED 2026-05-24 (PR #89 merge `f5967f2`)
[x] 6-tab Tasks/Roadmap/Git/Architecture/FileMap/Flow → 5-tab Done/Now/Next/System Flow/Agent Flow.
[x] Task.md sections renamed: Open→Next, In Progress→Now, Resolved→Done. Dashboard vocab 1:1.
[x] Vendored mermaid.min.js (3.3 MB) for offline file:// + airplane safety. Lazy-render on tab.
[x] 3 Mermaid diagrams: System Flow + Recommendation Flow + Agent Flow.
[x] state.js schema rewritten: meta.updatedAt, done/now/next arrays, prs.mergedAt+mergedAtKST.
[x] reporter.md spec updated: new Task.md vocab, KST formatter, no Mermaid regen.
[x] 8 agent frontmatters gain effort: default.

### Codex Round 2 audit — 7 findings resolved — RESOLVED 2026-05-24 (PRs #85 / #86 / #87)
[x] B1 — `/images/batch/` 500 on nested list input: serializer validation fixed (PR #85)
[x] B2 — BoardDetail field mismatch causing placeholder rendering: normalize fixed (PR #85)
[x] B3 — useBoard.Promise.all coupling: board no longer waits on result API (PR #85)
[x] P1 — SwipePage analyzing 0% progress drop: fixed analyzing percentage flow (PR #86)
[x] P2 — Gemini auth-error retry waste: fail-fast on auth errors, no retry (PR #86)
[x] P3 — Discovery taste vector TTL cache: caches.py get_or_build_taste/evict_taste, 1hr TTL, evict on liked_ids change (PR #87)
[x] P4 — IMP-8 redis-prep doc sync: algorithm.md annotated (this housekeeping commit)

### External codex audit — 9 findings resolved — RESOLVED 2026-05-23 (PRs #81 / #82 / #83)
[x] #1.1 (P1 latent) — raw_query stored under both `'raw_query'` and `'query'` keys so old + new clients both read correctly (PR #82).
[x] #1.2 (P1) — swipe idempotency: full SwipeRecord payload re-returned on duplicate swipe_id (was empty 200); race-condition guard catches concurrent identical swipe (PR #81).
[x] #1.3 (P1) — Project row lock: `select_for_update()` on Project in swipe handler prevents concurrent-write corruption (PR #81).
[x] #1.4 (P1 latent) — DPP 3× overfetch: `dpp_overfetch_multiplier=3` added to RECOMMENDATION; SessionResultView passes `n = k * multiplier` candidate window so DPP MAP-narrow runs over a broader set (PR #82).
[x] #2.5 (P2) — `get_diverse_random` replaced ORDER BY RANDOM() full scan with two-query pattern (ID fetch + Python `random.sample` + WHERE IN) to avoid O(corpus) sort (PR #83).
[x] #2.6 (P2) — ProjectListView + OfficeProjectListView N+1: `Subquery` composition eliminates per-project ORM queries (PR #83).
[x] #2.7 (P2) — JWT refresh now blacklists old token on rotate + wraps `TokenError` for clean 401 response (PR #83).
[x] #2.8 (P2) — `image_focus` `isinstance` guard in sessions.py rejects non-string values with 400 early; plumbed from LLMSearchPage → App → POST body (PR #83).
[x] #2.9 (P2) — exploring progress bar max raised 3→4 in SwipePage to match `min_likes_for_clustering=4` backend threshold (PR #83).

### Audit Tier 3 ops risk — RESOLVED 2026-05-23 (PR #79)
[x] #14a ORDER BY RANDOM replaced with two-query pattern (ID fetch + Python random.sample + WHERE IN) in get_top_k_results no-pref + _random_pool. Remaining 2 sites (get_diverse_random, search_by_filters) left — already-filtered subsets, cost acceptable.
[x] #14b bookmark POST corpus-rank sync removed; rank_corpus = None + TODO (telemetry-only field, not in API response; eliminates O(corpus_size) scan on bookmark).
[x] #16 SessionResultView GET write wrapped in transaction.atomic() for multi-field save atomicity. select_for_update() dropped — caused CI hang (PG savepoint+FOR UPDATE interaction with pytest-django outer atomic).
[x] #17 engine.py module-global _last_embedding_call_stats/_last_clustering_stats replaced with threading.local(). 6 write sites + 2 getters updated. Per-thread isolation prevents concurrent-request stats overwrite.
Note: TestTelemetryThreadLocal (2 tests) removed — ThreadPoolExecutor + threading.local() + pytest-django PG context caused CI hang (19min). Diagnostic CI run (-v -x --durations=20, 20min timeout) confirmed test as hang root cause. Structural guarantee of #17 fix preserved by code; test coverage dropped but CI green.

### Audit Tier 2 UX-contract bugs — RESOLVED 2026-05-23 (PR #76 / #77 / #78)
[x] #3 area filter normalization: normalizeFilters() in frontend; backend filter_args guard on empty list (PR #76).
[x] #4 FE→BE raw_query plumbing: raw_query field threaded from DiscoveryPage through API call to backend (PR #77).
[x] #5 raw_query persist: backend persists raw_query to SwipeSession on first swipe (PR #77).
[x] #7 dead /matched route removed from MainLayout.jsx guard + routing table (PR #76).
[x] #9 rerank response shape fixed: engine returns list-of-dicts matching frontend expectation (PR #76).
[x] #10 profiles legacy table: architecture_vectors references replaced with canonical_v2_buildings reads (PR #78).

### Audit Tier 1 hotfix bundle — RESOLVED 2026-05-23 (PR #74)
[x] #1 legacy `liked_ids`/`saved_ids` string entries: migration `0019` normalizes to dict.
[x] #2 bookmark + project PATCH: `transaction.atomic` + `select_for_update` on Project.
[x] #6 finish gate FE 3→4 to match BE `min_likes_for_clustering=4`.
[x] #8 `ProjectSerializer` `latest_session_meta` + Resume vs New UI on BoardCard; ownership gate on `latest_session_*` (IDOR fix); projects.py PATCH/DELETE locked-query ownership filter (TOCTOU fix).

### External PR triage — Board UX + Codex defect fixes — RESOLVED 2026-05-23 (PR #72)
[x] PR #71 (external, `yywon1`) opened against wrong base `main`. Triage: branched
    `feature/admin-board-ux-clean` off develop, cherry-picked both PR #71 commits
    (authorship preserved), added third commit `82bd36e` fixing 3 Codex defects.
    PR #72 squash-merged to develop as `877e82c`. PR #71 closed superseded.
[x] Defect 1 (Major) — "Finish & View Report" race: `swipePending` counter gates button
    `disabled={isResultLoading || swipePending > 0}`; threaded via `sharedLayoutProps`
    → `MainLayout.jsx` → `SwipePage.jsx`.
[x] Defect 2 (Major) — stale board hero cover after delete: `BoardDetailPage.jsx` cover
    now prefers `buildings[0].image_url`, falls back to `board.cover_image_url`.
[x] Defect 3 (Medium) — `PATCH remove_building_ids` type validation + atomicity:
    `isinstance(remove_ids, list)` guard → 400; `is_valid(raise_exception=True)` before
    `transaction.atomic()`; both saves inside atomic block. + 3 new unit tests in
    `backend/tests/test_projects.py` (valid removal, invalid type, atomicity proof).
[x] app-test FULL PASS-WITH-MINORS (3-persona live journey, local-dev branch).

### DEV-ENV1. Local backend/.env repointed off production DB — RESOLVED 2026-05-23
[x] Provisioned persistent Neon child branch `local-dev` (`br-rough-wildflower-a115ukd4`,
    endpoint `ep-summer-king-a1xldgwi`, no TTL) off `production`. Contains CoW copies of
    both `user_data` (57 migrations, 2 users at branch time) and `neondb`
    (39,736 publishable buildings).
[x] Updated 6 `.env` keys (`DB_HOST`/`DB_USER`/`DB_PASSWORD` + `BUILDINGS_*` equivalents).
    Backup saved at `backend/.env.bak.1779499369`. Production credentials no longer in `.env`.
[x] Backend runserver + vite restarted, both confirmed pointed at `local-dev`.
    Production isolation now mechanically guaranteed.

### External PR triage — UserSerializer fix + image loading perf — RESOLVED 2026-05-23 (PRs #68, #69)
[x] PR #68 (squash `779725e` on develop): `fix: UserSerializer.user_id source — user.id not profile id`.
    `UserSerializer.user_id` field source `'id'` → `'user.id'` so `auth/me` + login response
    returns Django `User.id` (not `UserProfile.id`), fixing wrong-profile-after-Google-login when
    PKs diverge. Adds `backend/apps/accounts/tests/test_userserializer.py` (deterministic, forces
    id divergence). External PR #62 closed superseded. Two parts of PR #62 intentionally NOT
    carried: `UserProfilePage.jsx` `/user/me` change (already fixed on develop via static route
    in `App.jsx`) and `views.py` display_name/avatar login-sync (separate concern, out of scope).
[x] PR #69 (squash `403bd02` on develop): `perf(frontend): image loading — 4s→2s timeout, lazy gallery, preload cap 3`.
    Cherry-pick of external PR #64's intended commit `3f9c385`: `SwipeCard.jsx` image-load
    timeout 4s→2s + gallery CSS→`<img>` lazy, `DiscoveryPage.jsx` preload cap 12→3. JSDoc
    comment synced. External PR #64 closed superseded (wrong base + polluted 154-file diff).
    app-test ran FEATURE-SCOPED (write-constrained — local .env targets prod DB; see DEV-ENV1).

### Neon DB-split (data step) + Production Deploy — RESOLVED 2026-05-22 (PR #63)
[x] DB-split complete and live in production: app DB = `user_data` (57 migrations,
    23 tables), buildings DB = `neondb` (`canonical_v2_buildings`, 39,776 rows).
[x] Prior DEPLOY-BLOCKER — "DB-split data step incomplete (`user_data` empty)" —
    fully resolved: `DB_NAME` env flipped `neondb` → `user_data` on Railway; cutover
    deploy `69c9473a` = SUCCESS; production verified healthy (schema 57/23, DB
    connections, gunicorn clean, Vercel frontend 200 — all green).
[x] Deploy PR #63 squash-merged develop → main (carried PRs #50–#61, 12 commits).
    origin/develop force-reset to match main (Bug #5 carve-out).
[x] Read-only infra CLIs (neonctl, railway, vercel) installed + authed this session.
Deferred follow-ups (not scheduled — noted for later):
- Drop `neondb`'s orphaned app tables in a later session (kept as rollback backup
  until prod is confirmed stable for ≥1 week).
- Neon `Staging` branch TTL auto-expires 2026-05-23 07:14 UTC (no action needed).

### PR #2 — theme/font server persistence — SHIPPED 2026-05-22
[x] Merged as PR #59 (develop `49b347d`).
Backend `UserProfile.theme`/`font` fields + migration `0003`; `UserSerializer`
login-response wiring; frontend `ThemeContext` hydrate-on-login + `updateMyProfile()`
PATCH on change. Cross-device server-sync fully operational.

---

## Roadmap (Historical)

> Compact phase summary. For full work audit see `## Done` above + `git log`.

- **Phase 1-12 (2026-03 → 2026-04)** — Single-user reference-exploration base: auth, 4-phase recommendation, Gemini search, persona report, project CRUD, E2E infra. **Shipped.**
- **Phase 13-15 (2026-04-29 → 2026-05-06)** — Social-graph triplet: User-follow, Project-reaction, Office-follow + Profile / Board system. **Shipped.**
- **Phase 16-18** — Recommendation expansion / LLM reverse-Q / external connections. **Pending** — open dimensions tracked in `## Next` § PHASE16 / PHASE17 / PHASE18.
- **Phase 19-26 (2026-05-14 Replan)** — Tab 3-Structure Transition (Library tab → Profile, Landing tab removed, Discovery infinite-scroll). **Shipped** via deploy PR #36 (S1-S8).
- **Phase P1-P6 (2026-05-15 → 2026-05-18)** — Latency + UX overhaul series. **Shipped** via deploy PR #49.
