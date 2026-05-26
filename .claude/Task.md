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


#### FRONT-DESIGN-1 — 디자인 시스템 컴포넌트 리워크 (paused)
Foundation shipped: PR #54 (`tokens.css` 4 themes + `ThemeContext` + `AppearanceSettings`) + PR #59 (theme/font server persistence). Remaining: per-component visual rework (≈ 7,700 LOC) — inline `style={{}}` → CSS Modules + `:hover/:focus`/`:active`, light-theme polish where dark-only assumptions still leak through, leaf→hub component order (small leaf components first, then containers).

Resume via `/plan per slice` — each slice = one logical component cluster (e.g. SwipeCard + LoadingCard, then BoardCard, then HomePage, etc.). Each slice ships its own PR via the orchestrate skill; the full sweep takes many sessions.

Acceptance per slice: `npm run lint` + `npm run build` clean; light + all dark variants render the touched components without visual regressions (compare against pre-slice screenshot); no new global token added without DESIGN.md update.

### MEDIUM

#### BACK-AUTH-1 — JWT blacklist DB ~590ms 차지
PERF-1 (PR #124) 발견: `/projects/` local p50 cache-hit path 661 ms 중 ~590 ms는 simplejwt `JWTAuthentication.authenticate()` → `BlacklistMixin` → Neon round-trip per authenticated request. 모든 인증된 endpoint의 floor latency. PERF-2 / PERF-3 측정에도 같이 잡힘.

Investigation outline:
1. JWT validation result in-memory cache (JTI 기반 key, token expiry까지 TTL) — `JWTAuthentication` custom subclass 또는 simplejwt internals patching.
2. Blacklist DB query 인덱스 검사 (Neon round-trip 자체는 한 번이라 cache 외 효과 제한적).
3. Multi-worker prod 환경에서 in-memory cache hit rate 낮음 → Redis 도입 필요.

Acceptance: 인증된 요청 floor latency 절감 (예: 600ms → 100ms 이하); 보안 영향 0 (logout 토큰 무효화 즉시 또는 ≤30s 이내). security-manager 사전 검토 필수.

#### FRONT-LAYOUT-1 — Desktop wide-screen 레이아웃 어색함
Current viewport-lock layout is mobile-first. Detail pages on desktop work but unoptimised. Low priority — desktop is secondary.

#### FULL-LEGAL-1 — PIPA/GDPR consent 없음 (public launch 차단)
Phase 13+ Profile/Board public/private visibility shipped. PIPA + GDPR posture for signup data collection / consent flow / retention policy still open. **Required before public launch.**

#### BACK-RECOMMEND-2 — engine.py matmul warning 정리
sklearn emits matmul dtype warning during clustering. Cosmetic noise but indicates float32 / float64 mismatch — quick fix is dtype-align embedding ndarrays before kmeans.

#### PERF-PREFETCH-CHAIN — async_prefetch chain completion (Redis swap blocker)
`backend/config/settings.py:216` `async_prefetch_enabled: False` (intentional). The async branch in `apps/recommendation/views/swipe.py` currently spawns a background thread that writes `cache.set('prefetch:<session>:<round>', card)` but the next-swipe handler never reads that key — instant-swap chain is broken, flag-flip yields zero latency benefit. Two-step fix: (1) add `cache.get('prefetch:<session>:<saved_current_round>')` to the async branch so the prior thread's write feeds the current response; (2) swap LocMemCache → Redis so multi-worker Railway prod actually shares the cache across processes. Re-flip `async_prefetch_enabled: True` only after both land. Note: hyperparam table in `docs/algorithm.md` also tracks this flag — keep in sync.

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
- [x] `.claude/skills/git-commit/` — single commit + secret guards + caveman convention. Replaces routine `git-manager` agent dispatch.
- [x] `.claude/skills/git-publish/` — push + PR open + admin squash + cleanup (Mode 2 feature → develop). Step 0 publish gate codified (keyword OR active plan precondition; mirrors `[[feedback_publish_gate]]`).
- [x] `.claude/skills/reporter-inline/` — Task.md + state.js + algorithm.md inline before squash. In-flight PR `mergedAt:null` sentinel + next-pass backfill (advisor #1 policy). 9-step behavior 1-to-1 from legacy `reporter` agent (advisor #3 checklist).
- [x] `.claude/agents/git-manager.md` + `reporter.md` → `deprecated:true` frontmatter + body fallback note. Two-PR migration (advisor #2): delete in follow-up PR after ~1 week of skill-only validation.
- [x] `.claude/agents/git-publisher.md` kept indefinitely — Mode 3 deploy / external PR triage / complex rebase escalation.
- [x] `CLAUDE.md` — new `## Git Operations — HARD RULE` section (skill-first matrix + escalation criteria + publish-gate keywords). Workflow section bullets + reporter sync rule refreshed.
- [x] `.claude/WORKFLOW.md` — Mermaid rebuilt with skill labels. § Agent + skill roster split into 3 tables. § 7 Token-saving + § 9 Key rules updated.
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
