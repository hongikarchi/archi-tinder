# Task Board

> Auto-updated by the orchestrator. When you request work, the orchestrator reads
> the current code, then adds/updates tasks here before executing.
> Categories: Frontend, Backend, Auth, UX/Design, Infrastructure
> (Algorithm work is owned by a separate collaborator post-2026-05-18.)

---

## Development Roadmap

> Orchestrator: follow this order. Each Phase's tasks are referenced by ID.

### Phase 1: Critical Bug Fix -- COMPLETED 2026-04-03
1. **B4** -- Mobile Google login (auth-code flow)
2. **B1** -- "View Result" button timing
3. **B2** -- Card repetition (exposed_ids)
4. **B3** -- "No buildings match" fallback

### Phase 2: Stability -- COMPLETED 2026-04-03
5. **F1** -- Swipe error handling + state sync
6. **A3** -- Recency weight math protection
7. **BE1** -- API timeout/retry

### Phase 3: Performance -- A1 COMPLETED, A2 VALIDATED
8. **A1** -- Pool caching + KMeans caching + prefetch -- COMPLETED 2026-04-03
9. **A2** -- Algo-tester 100 personas -- validated (smoke test passed, full run pending)

### Phase 4: UX Enhancement -- COMPLETED 2026-04-03
10. **UX1** -- Tutorial popup -- COMPLETED 2026-04-03
11. **UX3** -- Action card message improvement -- COMPLETED 2026-04-03
12. **F2** -- Image load failure handling -- COMPLETED 2026-04-03

### Phase 4.5: Swipe Bug Fix -- B5, B6, B2v2 COMPLETED 2026-04-04 (B3v2 skipped)
13. **B5** -- Fast swipe race condition (no swipe lock, concurrent requests)
14. **B6** -- Card suddenly changes (prefetch response overwrites current card)
15. **B2v2** -- Same cards still repeating (prefetch uses stale exposed_ids)
16. **B3v2** -- Pool exhaustion during exploring phase returns null (SKIPPED -- low priority)

### Phase 5: New Features -- UX2, F3 COMPLETED 2026-04-04 (AUTH1 deferred)
17. **UX2** -- Persona Report AI image generation -- COMPLETED 2026-04-04
18. **AUTH1** -- Kakao / Naver OAuth (deferred -- future)
19. **F3** -- Mobile optimization -- COMPLETED 2026-04-04

### Phase 6: Cleanup -- COMPLETED 2026-04-04
20. **INFRA1** -- Backend integration tests -- COMPLETED 2026-04-04
21. **INFRA2~4** -- Idempotency, total_rounds, console.error -- COMPLETED 2026-04-04
22. **BE2** -- Gemini error handling improvement -- COMPLETED 2026-04-04

### Phase 7: Codebase Audit Fixes -- COMPLETED 2026-04-04
23. **AUDIT1** -- Remove unused deps, dead code, consolidate tests, fix deprecations -- COMPLETED 2026-04-04

### Phase 8: E2E Testing Infrastructure -- COMPLETED 2026-04-05
24. **TEST1** -- E2E visual test runner module -- COMPLETED 2026-04-05

### Phase 9: E2E Runner Fix -- COMPLETED 2026-04-07
25. **TEST2** -- Rewrite runner.py to match actual frontend UI flow -- COMPLETED 2026-04-06
26. **TEST3** -- Fix screenshots, card visibility, timing breakdown -- COMPLETED 2026-04-07

### Phase 10: Swipe API Latency Fix -- COMPLETED 2026-04-05
27. **PERF1** -- Non-algorithm swipe latency optimizations -- COMPLETED 2026-04-05

### Phase 11: Frontend Bug Fix -- COMPLETED 2026-04-05
28. **B7** -- Keyboard swiping blocked in gallery mode (SwipePage.jsx) -- COMPLETED 2026-04-05
29. **B8** -- Card disappears after swipe race condition (App.jsx) -- COMPLETED 2026-04-05

### Phase 12: Critical Swipe Bug Fixes -- COMPLETED 2026-04-05
30. **B9** -- Cards stop loading after ~N swipes (never set currentCard null) -- COMPLETED 2026-04-05
31. **B10** -- Refresh creates new session instead of resuming (SessionStateView + currentHint) -- COMPLETED 2026-04-05
32. **B11** -- Same card appears twice (client_buffer_ids in exposed_ids) -- COMPLETED 2026-04-05

### Phase 13: Profile System -- COMPLETED 2026-05-06
33. **PROF1** -- OfficeProfile model + Make DB integration (blue-mark, project list, external links, basic info) -- COMPLETED 2026-04-29
34. **PROF2** -- UserProfile extension (MBTI, avatar, bio, external DM links) -- COMPLETED 2026-04-29
35. **PROF3** -- Firm profile page UI (project card grid + website/email links) -- COMPLETED 2026-05-02
36. **PROF4** -- User profile page UI (feed style, board list) -- COMPLETED 2026-05-02

### Phase 14: Board System -- COMPLETED 2026-05-06
37. **BOARD1** -- Board model (public/private visibility, owner FK) -- COMPLETED 2026-04-30
38. **BOARD2** -- Project creation: visibility selection UI -- COMPLETED 2026-05-06
39. **BOARD3** -- Profile page: board browse/manage UI -- COMPLETED 2026-05-06

### Phase 15: Social Foundation -- COMPLETED 2026-05-06
40. **SOC1** -- Follow model + API (follow/unfollow, follower list) -- COMPLETED 2026-05-02
41. **SOC2** -- "Love this!" reaction model + API -- COMPLETED 2026-05-02
42. **SOC3** -- Profile/board: follow button + reaction button UI -- COMPLETED 2026-05-06

### Phase 16: Recommendation Expansion -- PENDING (revised under 2026-05-14 replan; S8 sweep COMPLETED)
> Spec: `docs/specs/phase16-recommendation-expansion.md` (refreshed S8
> 2026-05-14). REC1 already executed as **Push S3**. REC2 / REC3 now
> serve a Profile-tab "사무소 추천" button (Q3 decision); Landing tab
> deleted by Push S6. Endpoint shape changed from
> `/api/v1/landing/{sessionId}/` (deprecated) to a Profile-targeted
> composite (e.g. `/api/v1/recommendations/profile/`).
43. **REC1** -- Post-swipe end screen consolidation (executed in **S3** 2026-05-14)
44. **REC2** -- Firm recommendation logic (Profile-button-triggered)
45. **REC3** -- User recommendation logic (Profile-button-triggered)
46. **REC4** -- ~~Landing tab~~ → removed by Push S6 (Profile-tab button surface instead)

### Phase 17: LLM Reverse-Questioning -- PENDING (S8 sweep COMPLETED)
> Spec: `docs/specs/phase17-llm-reverse-q.md` (refreshed S8 2026-05-14).
> Replan Q6 RESOLVED → Option A: reverse-question lives in the first
> 0-2 turns of the Taste-tab LLM chat (pre-swipe). TTFC budget unchanged.
47. **LLM1** -- Chat reverse-question prompt design (identify user needs)
48. **LLM2** -- Persona classification logic (P1-P4 differentiation; populates `UserProfile.persona_summary`)
49. **LLM3** -- Per-persona UI branching (recommendation card type switching)

### Phase 18: External Connections -- PENDING (S8 sweep COMPLETED)
> Spec: `docs/specs/phase18-external-connections.md` (refreshed S8
> 2026-05-14; scope unchanged). Lower priority than Phase 16-17.
50. **EXT1** -- Firm article crawler (Space, ArchDaily, news — keyword-based)
51. **EXT2** -- Article list UI (inside firm profile)
52. **EXT3** -- External DM link UI (Instagram, email — on profile)

> **Phase 19-26 (2026-05-14 Replan, Tab 3-Structure Transition) + Phase P1-P6
> latency+UX overhaul (2026-05-15..2026-05-18)** — all shipped to production
> via deploy PR #36 (S1-S8) and PR #49 (P1-P6). See git history for detail.

---

## Specs

> Pending-feature specs and decision records live in `docs/specs/` (admin-owned via PR).
> Algorithm theory + production hyperparameters live in `docs/algorithm.md`. Owned by a
> separate collaborator post-2026-05-18; admin role here is limited to (a) reporter
> auto-sync of the Production Value column when `settings.py` RECOMMENDATION dict
> changes, and (b) theory-edit review on PR.
>
> Current pending specs:
> - `docs/specs/phase16-recommendation-expansion.md` — Phase 16 dimensions
> - `docs/specs/phase17-llm-reverse-q.md` — Phase 17 dimensions
> - `docs/specs/phase18-external-connections.md` — Phase 18 dimensions
> - `docs/specs/requirements.md` — still-open cross-cutting questions

---

## Open

### Auth
#### AUTH1. Kakao / Naver OAuth not implemented
Google OAuth only. Korean users need domestic login.
- [ ] Kakao social auth backend + frontend button
- [ ] Naver social auth backend + frontend button

### Audit Tier 2/3/4 — pending next sessions
Remaining items from the full codebase audit report.
- [ ] Tier 2 — UX-contract bugs: #3/#4/#5/#7/#9/#10
- [ ] Tier 3 — ops risk: #14/#16/#17
- [ ] Tier 4 — file decomp: App.jsx, engine.py, BoardDetailPage, UserProfilePage

---

## In Progress

### Design-system redesign — per-component rework (pending)
Foundation shipped (PR #54: `tokens.css` 4 themes + `ThemeContext` +
`AppearanceSettings`). Remaining: per-component visual rework (~7,700 LOC,
inline styles → CSS Modules + `:hover`, light-theme visuals) across the
frontend, leaf→hub order. Scope with `/plan` per slice.

---

## Resolved

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
