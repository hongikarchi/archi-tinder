# Task Board

> Authored by the session; updated by the `reporter` agent at session end. The dashboard
> (`project/dashboard.html` ← `project/state.js`) renders this file's three active
> sections (`## Now` / `## Next` / `## Done`). The compact `## Roadmap (Historical)`
> section at the bottom is a phase-level summary, not a task list.

## Workflow Rules

- **Session start** — read `## Now` first. If empty and the user is starting new work, move the matched `## Next` entry (under `### HIGH` / `### MEDIUM` / `### LOW`) into `## Now`. Or write a fresh entry if brand-new. One initiative slice at a time.
- **Mid-session** — if work in `## Now` gets deferred ("미루자"), move it back to `## Next` with a one-line rationale note. If a new sub-task appears, add it under the active Now entry's body or create a new Now entry.
- **Session end (success)** — reporter moves `## Now` → `## Done` with PR ref + SHA. If the Now entry's note mentions a deferred follow-up (`Deferred: ...`), reporter also auto-surfaces a matching `## Next` entry per its sub-step 2a (see `.claude/agents/reporter.md`).

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

_(none — no active initiative slice with a PR in flight.)_

---

## Next

> Backlog grouped by priority bucket (`### HIGH` / `### MEDIUM` / `### LOW`). Each
> item is a `#### <SLUG>` entry one level deeper. Bucket semantics described in
> `## Workflow Rules` above. Phase 16-18 dimensions inlined here (formerly
> `docs/specs/*`, absorbed 2026-05-24). Algorithm theory + production
> hyperparameters still live in `docs/algorithm.md` (admin-owned, reporter syncs
> Production Value column only).

### HIGH

#### BACK-LLM-1 — LLM 채팅이 검색에 필요한 정보를 다 안 모음
`backend/apps/recommendation/services/parse_query.py` already implements a 0-2 turn probe budget where the LLM free-choices an abstract A-vs-B axis. This task **drops persona classification (P1-P4)** and re-scopes the work: (1) define an explicit *required information slate* the chat must collect — filter fields the downstream search needs — and (2) refine LLM probe behaviour so probes deterministically target missing slate fields when the user's first turn is too diffuse, instead of choosing axes freely.

Goal: a diffuse natural-language query ("좋은 거 보여줘", "추천해줘") still ends with a usable filter set, by virtue of the probe loop asking specifically for the gaps.

Open dimensions:
- **Required info slate** — which filter fields are mandatory? Today's 0-turn skip rule = "`program` + at least one of (`style` | `material` | `location_country`)". Keep / expand / contract?
- **Probe priority** — among missing required fields, which is asked first? (e.g., program > material > style > location)
- **Optional slate** — `color_tone` / `year_min-max` / `transparency` etc. — never probed (auto-inferred only) vs allowed to consume probe budget when essentials are already covered?
- **Fallback when 2-turn budget exhausts with slate gap** — best-effort filter / generic default / broad-pool fallback?
- **Conversational shape** — keep current abstract A-vs-B style ("따뜻한 재료감 vs 차가운 기하성") vs allow direct field-asking ("어떤 program이 필요하세요?")? Mix?
- **Cross-language posture** — Korean query → Korean probe (current). No change (Constitution Decision Principle 7).

Acceptance:
- TTFC for Taste-tab chat does not regress beyond the 4000 ms budget (per `docs/algorithm.md`).
- After ≤2 probe turns, `filter_priority` always contains at least one required-slate field.
- A/B run on a fixed 50-query sample comparing slate-completion-rate (current prompt vs refined prompt) — refined prompt must not regress and should improve on diffuse-prior cases.

#### BACK-RECOMMEND-1 — Project 두번째 세션이 이전 taste를 모름
Same Project can host multiple `AnalysisSession` rows (user comes back, "Resume" or new swipe round on the same Project — second session is created fresh while `Project.liked_ids` / `disliked_ids` / `saved_ids` carry forward as the persistent accumulator). Today the new session's algorithm-side state (`like_vectors`, `convergence_history`, `phase`) starts from scratch — exploring phase, empty pool of taste signal — even though the user just liked 12 buildings in Session #1.

Open dimensions:
- **Carry policy** — A independent (status quo) / B exposure-only carry (don't re-show prior cards, taste fresh) / C asymmetric negative-only (carry dislikes, drop likes) / D fade-decay carry (recency-weight prior `liked_ids` into `like_vectors`) / E full warm-start (replay prior `liked_ids` → `like_vectors`, skip exploring phase) / F user-controlled toggle ("Resume taste?" prompt at session 2 start).
- **Phase entry on warm-start** — if D or E chosen: enter `analyzing` immediately (3+ likes already), or still play 1-2 exploring rounds for diversity?
- **Backend wiring** — `SessionCreateView` (`views/sessions.py:28`) currently treats project lookup as cosmetic (just resolves project_id). Carry would require reading `Project.liked_ids` → embedding fetch → seeding `AnalysisSession.like_vectors` at create time.

Acceptance: behavior matches chosen option deterministically; session 2 TTFC not regressed beyond session 1 (warm-start should be ≤ or equal); A/B telemetry on session 2 satisfaction (saved_ids growth rate, completion rate) vs status quo.

#### FRONT-UX-1 — 신규 사용자에게 홈이 빈 화면
First-time user with 0 projects sees Home → project picker. Need explicit empty-state path so new sign-ups don't bounce off a blank Home. Frontend-only (HomePage / ProjectListPage).

Open dimensions:
- **Onboarding shape** — guided flow (single CTA "Start your first taste analysis" → jump straight to AI Search) / empty-state placeholder + create button / demo query (pre-baked example, zero-friction swipe immediately) / hybrid (placeholder + demo CTA together).
- **Copy + voice** — direct ("아직 프로젝트가 없어요") vs product-voice ("취향 첫 발견을 시작해볼까요?").
- **Visual** — illustration / icon-only / none?

Acceptance: 0-project user sees a deliberate empty state on Home (no broken-looking blank); CTA path to first swipe ≤2 clicks; no regression on existing-projects rendering.

#### FULL-LANGUAGE-1 — 한/영 언어 설정 토글 없음
**Decision (user 2026-05-25)**: language is a user-controlled setting, NOT browser-locale auto-detected. Pattern mirrors the existing theme/font persistence shipped in PR #54 + PR #59. User toggles language in Settings (Korean / English); the choice drives both LLM chat answer language and UI label rendering across the app.

Current state:
- Chat phase (`parse_query.py`) already adapts to the user's latest message language inline ("`reply` and `probe_question` are written in the user's primary language"). With this setting wired through, the chat will instead use the user's profile language deterministically — no language inference from message text.
- Theme + font already follow this exact pattern: `UserProfile.theme` + `UserProfile.font` server-persisted, `ThemeContext` hydrates on login, `AppearanceSettings.jsx` exposes the toggle, `updateMyProfile({ theme })` PATCH on change.

Implementation outline:
- Backend — add `UserProfile.language` CharField with choices `[('ko', 'Korean'), ('en', 'English')]`, default `'ko'` (Korea-first). Migration + serializer wiring + login-response inclusion (parity with theme/font).
- Frontend — `LanguageContext` mirroring `ThemeContext`; hydrate from login response; `setLanguage()` PATCHes `updateMyProfile({ language })`. Add language toggle to `AppearanceSettings.jsx` (or a sibling settings panel — admin call).
- Wire-through — `parse_query.py` accepts `language` parameter from `SessionCreateView`/`SwipeView`/etc., overrides the "match user's message language" rule. UI labels via a small dictionary-lookup helper (`t('home.title')`-style) — no full i18n lib (`react-i18next` adds bundle weight; Korea-first + bilingual-only justifies a hand-rolled lookup).

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

#### BACK-LLM-3 — Gemini cache 호출에 timeout 없음
`backend/apps/recommendation/services/_caches.py:92` IMP-5 Gemini context-cache create call bypasses the `_retry_gemini_call` timeout wrapper that every other Gemini SDK call goes through (PR #94 hard-cap 15s, 45s for Imagen). Gated by `context_caching_enabled` flag (default OFF) — zero prod impact until the flag is toggled on, at which point an SDK hang would have no cap.

Fix: wrap the create call in `_retry_gemini_call(...)` so it inherits the same 15s deadline. ~5 LOC backend edit. Pre-emptive safety — easier to do now than to discover the gap when toggling the flag under load.

Acceptance: `_caches.py:92` flows through the wrapper; existing IMP-5 unit tests still pass; flag toggle behaviour unchanged.

#### BACK-PERFORMANCE-1 — `/projects/` 응답 600ms (목표 300ms)
Codex Round 2 (2026-05-24) measured `GET /api/v1/projects/` at p50 = 600 ms, spec budget = 300 ms. Codex retest (2026-05-25) also observed double-fetch in dev (React StrictMode artefact + real prefetch — both contribute). User-visible: Projects list is the post-login first paint surface; >300 ms reads as sluggish.

Investigation outline:
1. Measure SQL count via `connection.queries` or Django Debug Toolbar against `ProjectListView`.
2. If N+1 → port the `Subquery` / `prefetch_related` pattern shipped in PR #83 (`ProjectListView` + `OfficeProjectListView` already use this; new offenders likely live in serializer relations).
3. If serializer-heavy → trim fields, introduce a `ProjectListSerializer` (lightweight) distinct from `ProjectDetailSerializer`.
4. If neither → add a Django cache-framework layer (taste cache at `caches.py` is the existing template).

Acceptance: p50 ≤ 300 ms on Singapore-deploy `/projects/`; no regression on serializer field shape consumed by HomePage / BoardCard.

#### BACK-PERFORMANCE-2 — Discovery 캐시 hit 450ms (목표 <200ms)
Codex Round 2: `GET /api/v1/discovery/` cache-hit p50 = 450 ms vs spec budget < 200 ms. Codex retest 2026-05-25 observed cache-cold path 4.11 s with external image retries — cache-hit re-measure pending. Taste cache shipped in PR #87 (`get_or_build_taste` / `evict_taste`, 1 h TTL, evict on `liked_ids` change).

Suspect work on the hit path:
- response serialization on 12 cards (image URL resolution + program normalisation per row)
- buildings-DB raw SQL lookup still executing on cache hit (cache may only hold the candidate id list, not the card payloads)
- cache-key fragmentation lowering true hit rate

Investigation outline:
1. Discovery view (`views/discovery.py`) — log per-stage timing on a single request (cache lookup / SQL fan-out / serialization).
2. If serialization is the floor → trim card payload, batch-resolve image URLs.
3. If raw SQL still fires on hit → extend the cache to hold full card payloads, not just ids.
4. If hit rate is low → audit cache key shape (taste fingerprint vs raw filter signature).

Acceptance: cache-hit p50 < 200 ms on Singapore deploy; cache-cold path improvement opportunistic; no SwipePage UX regression (card payload shape preserved).

#### BACK-PERFORMANCE-3 — Search 후 첫 카드까지 5-8초
Codex Round 2 baseline = 5.2 s; Codex retest (2026-05-25) measured browser-side 7.71 s — slipping further. No explicit spec budget yet for session create itself (the 4000 ms TTFC budget covers chat parse, not the swipe-session bootstrap that follows). UX impact: 5–8 s wait between "Search" click and first swipe card is the heaviest single delay in the funnel.

Pipeline steps (`views/sessions.py:28–160`):
1. Project resolve / create
2. `v_initial` embedding (HyDE sync or IMP-6 late-bind cache lookup)
3. `engine.create_pool_with_relaxation` — 3-tier `canonical_v2_buildings` raw-SQL fan-out
4. `engine.get_pool_embeddings` — pool 150 × 384-dim
5. Tier-ordered `initial_batch` build — repeated `farthest_point_from_pool` matmul (≈10 iterations, also where Codex flagged the divide/overflow/invalid warnings)
6. `AnalysisSession.objects.create` + response serialization

Suspect bottlenecks: (a) pool SQL fan-out + 3-tier relaxation worst-case; (b) embedding batch fetch (≈ 150 vectors); (c) matmul repetition in initial batch.

Investigation outline:
1. Per-step timing log on one create request (Singapore deploy) to identify the dominant step.
2. If pool creation dominates → cache by `(filter_signature, tier)` key; the same filter shape recurs across users.
3. If embedding fetch dominates → batch-prefetch via single SQL, drop per-id round-trips.
4. If initial-batch matmul dominates → vectorise the 10-call farthest-point loop into one batched matmul (cousin of MMR vectorisation already done in `compute_mmr_next`).

Acceptance: session-create p50 ≤ 2 s Singapore deploy (≈ 3 × improvement); pool shape + initial_batch ordering unchanged (swipe loop deterministic with prior tests); no regression on filter relaxation behaviour.

#### INFRA-DB-1 — Django app이 owner 권한으로 DB 접근
**Decision (user 2026-05-25)**: split into two roles. Today the Django runtime logs into the `user_data` DB as `neondb_owner` — full DDL + DML + role + extension privileges. The app only needs DML on app tables.

Plan:
- Create a new Neon role `make_web_app` with `LOGIN` + `SELECT, INSERT, UPDATE, DELETE` on `ALL TABLES IN SCHEMA public` + `USAGE, SELECT ON ALL SEQUENCES`. No DDL, no role mgmt, no extension privileges.
- Switch `DB_USER` in `backend/.env`, `backend/.env.example`, and Railway prod env from `neondb_owner` → `make_web_app`.
- Keep `neondb_owner` alive as the **admin-only** login the operator uses when running `python manage.py migrate` (DDL needs the strong role; migrations run from the operator's machine, not from the prod app).
- Mirrors the buildings-DB pattern shipped in PR #93 (`make_web` SELECT-only on `archi_data`), but with write privileges added since `user_data` is the app's read+write DB.

Open dimensions:
- **Default-privilege carry-over** — after the GRANT, future tables created by migration default to `neondb_owner`-only. Add `ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO make_web_app;` so future migrations don't require manual GRANT each time?
- **Cutover order** — create role + GRANT → verify with a manual `psql -U make_web_app` smoke (CRUD + reject DDL) → flip Railway env vars → restart prod gunicorn → confirm app green. Rollback = flip env back to `neondb_owner`.

Acceptance:
- Django runtime (Railway prod + local) connects as `make_web_app`; full app suite passes (login → swipe → save).
- `make_web_app` cannot `DROP TABLE` or `CREATE ROLE` (verified via psql).
- `manage.py migrate` still works under `neondb_owner` from operator machine.

#### INFRA-ENV-1 — local-dev Neon branch 사라짐 — prod 직격 위험
**Discovered during 2026-05-25 SNAPSHOT-BRANCH-DROP review.** The `local-dev` Neon branch provisioned by DEV-ENV1 (2026-05-23) is no longer listed in `neonctl branches list` for project `holy-pond-45504245`. Current branches: `production` + `pre-cleanup-2026-05-24` snapshot — that is all. The local `backend/.env` `DB_HOST` is `ep-broad-hat-a1jaomn7.ap-southeast-1.aws.neon.tech`, which is unverified (Claude session was blocked from inspecting Neon endpoint→branch mapping for credential-leak reasons).

Risk: if `ep-broad-hat-a1jaomn7` belongs to the `production` branch, then **local `manage.py runserver` writes directly to prod user_data** — the exact failure mode DEV-ENV1 fixed. No mechanical guarantee of isolation right now.

Architecture context (the answer to the user's recurring question):
- `.env` is `.gitignored`; values exist only on the local machine. Loaded into `os.environ` by `python-dotenv` when Django boots.
- Railway prod injects its own env vars into the gunicorn container; `.env` file is never deployed.
- → Local and prod can point at different Neon branches via the same `settings.py` code reading `os.environ.get('DB_HOST')`.
- This separation is the mechanism that makes DEV-ENV1 work — but only if local `.env` actually points at a dev branch and Railway env points at production.

Tasks:
1. **Verify current state** — user opens Neon dashboard, looks up endpoint `ep-broad-hat-a1jaomn7` and confirms which branch it belongs to. (Two possibilities: dev branch survived under a different name → no fix needed; or it points at `production` → DEV-ENV1 broken.)
2. **Restore isolation if broken** — re-provision a persistent child Neon branch off `production` (no TTL), point `backend/.env` `DB_HOST` + `BUILDINGS_DB_HOST` at the new branch endpoint, leave Railway env vars untouched.
3. **Document the separation** in `CLAUDE.md` `## Backend Conventions` (currently this convention exists only in DEV-ENV1 Done note + this entry). Make explicit:
   - Local `.env` → dev branch
   - Railway env → production branch
   - Migrations run from operator machine using the admin role on production branch only when the deploy demands it
4. **(Stretch)** add a startup-time sanity check (Django `apps.py` `ready()` or a runserver wrapper) that logs which branch the runtime resolved — so future drift is visible.

Acceptance: known mapping between every env (local + Railway + any future preview) and its Neon branch; CLAUDE.md documents the separation; mechanical isolation between local writes and prod data restored if broken.

#### FRONT-DESIGN-1 — 디자인 시스템 컴포넌트 리워크 (paused)
Foundation shipped: PR #54 (`tokens.css` 4 themes + `ThemeContext` + `AppearanceSettings`) + PR #59 (theme/font server persistence). Remaining: per-component visual rework (≈ 7,700 LOC) — inline `style={{}}` → CSS Modules + `:hover/:focus`/`:active`, light-theme polish where dark-only assumptions still leak through, leaf→hub component order (small leaf components first, then containers).

Resume via `/plan per slice` — each slice = one logical component cluster (e.g. SwipeCard + LoadingCard, then BoardCard, then HomePage, etc.). Each slice ships its own PR via the orchestrate skill; the full sweep takes many sessions.

Acceptance per slice: `npm run lint` + `npm run build` clean; light + all dark variants render the touched components without visual regressions (compare against pre-slice screenshot); no new global token added without DESIGN.md update.

### MEDIUM

#### FRONT-LAYOUT-1 — Desktop wide-screen 레이아웃 어색함
Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. Low priority — desktop is secondary.

#### FULL-LEGAL-1 — PIPA/GDPR consent 없음 (public launch 차단)
Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. **Required before public launch.**

#### BACK-RECOMMEND-2 — engine.py matmul warning 정리
sklearn emits matmul dtype warning during clustering. Cosmetic noise but indicates float32 / float64 mismatch — quick fix is dtype-align embedding ndarrays before kmeans.

### LOW

#### FRONT-AUTH-1 — LoginPage에 Kakao/Naver 버튼 없음
Backend Kakao + Naver implementation shipped: `apps/accounts/views.py` KakaoLoginView + NaverLoginView, `apps/accounts/urls.py` `auth/social/kakao/` + `auth/social/naver/`, `apps/accounts/models.py` provider choices. Frontend `LoginPage.jsx` currently has Google button only.
- [ ] Kakao button on `LoginPage.jsx` (loading state already typed `'kakao'`)
- [ ] Naver button on `LoginPage.jsx` (loading state not yet typed `'naver'`)

#### FULL-REFACTOR-1 — 큰 파일 분해 필요 (engine.py 2139 LOC 등)
File decomp (LOC verified 2026-05-25): engine.py 2139 (+60 since first flagged), App.jsx 817, BoardDetailPage 1045, UserProfilePage 992, PostSwipeLandingPage 696, SwipePage 666, FirmProfilePage 540 (recently refactored down from 611).

#### BACK-RECOMMEND-3 — Profile-tab 사무소/유저 추천 endpoint 없음
Re-scoped 2026-05-14 (REC1 already shipped as Push S3). REC2 (firm) + REC3 (user) target a single composite endpoint `GET /api/v1/recommendations/profile/` returning `{offices: [...], users: [...]}` for a Profile-tab button. Landing tab removed (Push S6).

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

Open dimensions:
- **Article source priority** — Space-first (Korean) vs ArchDaily-first (global) vs parity? (Korea-first principle suggests Space)
- **Crawl freshness** — real-time on view / scheduled daily-weekly / event-driven?
- **Storage** — denormalised in `Office` row / separate `OfficeArticle` table / external CDN?
- **Article fallback** — empty section / hide section / "no recent articles" placeholder?

Acceptance: ≤10 most recent articles per firm; open in new tab (legal posture); no FirmProfilePage TTFC regression (article fetch async, doesn't block initial paint).

#### INFRA-QUEUE-1 — corpus_rank telemetry 꺼져있음
`recommendation_swipeevent` row inserts used to compute `corpus_rank` synchronously (O(corpus_size) scan on every swipe). PR #79 turned this off on the bookmark path (`rank_corpus = None` + TODO). Today the field is None on every write — telemetry slightly degraded but swipe response is fast. Celery + Redis would let us re-enable the calculation off the hot path.

Why LOW: introducing Celery just for this one field is over-investment. Adds Redis (Railway add-on cost), a worker process, monitoring surface, and a deploy step — all for one telemetry column the product doesn't currently consume. Revisit when other background jobs accumulate (image batch processing, periodic embedding refresh, scheduled snapshot drops) so Celery earns its keep across multiple tasks.

---

## Done

### #21 SWIPE-CALIBRATING — RESOLVED 2026-05-25 (PR #108 `890236c`)
[x] `ConfidenceBar` analyzing branch now guards on `value != null`. Null confidence (4th swipe trips exploring→analyzing transition, backend resets `convergence_history = []` per spec C-1, `compute_confidence` returns null for ~5 swipes) → `Calibrating…` label + `likeCount/4` progress. Old fallback showed `Analyzing 100%` falsely — user stuck with no path forward.
[x] `isAt100` Finish-button gate untouched (still correct — requires `confidence >= 1.0`).
[x] Backend convergence reset unchanged (correct per spec).
Deferred (surfaced by Codex retest, intentionally NOT fixed this session): MATMUL-WARN (engine.py matmul warnings), PERF-DISCOVERY (4.11s cold load), PERF-SESSION-CREATE (7.71s POST /analysis/sessions/), PERF-PROJECTS (double-fetch in dev StrictMode). All remain in `## Next`.

### #20 TASK-MD-RESTRUCTURE-V2 — RESOLVED 2026-05-25 (PR #104 `0690b85`)
[x] Restructured `.claude/Task.md` 394 → 305 lines: dropped 100+ lines of `## Development Roadmap` Phase 1-18 (duplicates of Done content), replaced with compact `## Roadmap (Historical)` at file bottom + new `## Workflow Rules` block at top.
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
[x] Absorbed `docs/specs/*.md` (4 files: phase16-recommendation-expansion.md, phase17-llm-reverse-q.md, phase18-external-connections.md, requirements.md) into `.claude/Task.md ## Next` as a flat backlog. Deleted the folder.
[x] Fixed `orchestrate/SKILL.md` stale refs: `.claude/Goal.md` → `CLAUDE.md ## Product Identity + ## Product Constitution`; `.claude/Report.md` → "read code directly + state.js"; `docs/token-saving.md` → `.claude/WORKFLOW.md § Token-saving rules`.
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
[x] 5 stale doc refs refreshed: CLAUDE.md / docs/database-schema.md / docs/COLLAB_HANDOFF.md / .claude/agents/reporter.md / .claude/agents/code-review.md.
Plan `.claude/plans/merry-toasting-dove.md` archived to `.claude/plans/archive/2026-05-24-merry-toasting-dove.md`.

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
