# Phase 16 — Recommendation Expansion

**Status**: Pending dialogue. Phase 13-15 (Profile / Board / Social Foundation) shipped on origin/main; Phase 16 builds on that data foundation.

**Owner**: admin-driven dialogue, then implementation via orchestrator pipeline.

**Pre-context**: Phase 13-15 social-graph triplet (User-follow / Project-reaction / Office-follow) is live. PostSwipeLandingPage MOCKUP is in `frontend/src/pages/PostSwipeLandingPage.jsx` — surfaces 3 recommendation tabs (Projects / Offices / Users) with mock data; the backend endpoint that powers it is the work of this phase.

---

## 1. Designer mocks already constrain shape

`PostSwipeLandingPage.jsx` defines 3 recommendation tabs:
- **Projects** — top-K bookmarked from current session (search-flow output, already shipped)
- **Offices** — firm-level recommendations from user taste
- **Users** — user-level recommendations from taste similarity

Backend endpoint to ship: `GET /api/v1/landing/{sessionId}/` returning the 3-tab payload.

## 2. Open dimensions (need admin decision before implementation)

| Dimension | Question | Notes |
|---|---|---|
| Firm vector composition | Mean of firm's project embeddings / weighted mean / curated subset / max-similarity? | Shapes how Office recs are scored. |
| User taste vector | Aggregated from user's `liked_ids` across all Projects — recency-weighted? curated subset? | UserProfile already has the data. |
| Cold-start strategy | New user with no swipes → "popular users" / generic taste cluster / disable User tab until N swipes? | UX decision. |
| Match score visibility | Show "92% match" on cards, or hide? | UX precision concern. |
| Diversity vs follow exclusion | Recommend already-followed firms? (probably no — exclude) | Easy default but worth confirming. |
| Tie-breakers | Followers count / recency / random / hybrid? | Implementation detail. |

## 3. Acceptance criteria

- New endpoint `GET /api/v1/landing/{sessionId}/` returns `{projects: [...], offices: [...], users: [...]}` with stable shape.
- PostSwipeLandingPage replaces MOCK_LANDING with real data.
- Tab switching is instant (data preloaded with the session response).
- Cold-start UX is not broken (user with 0 prior sessions sees a graceful "explore more" fallback rather than empty tabs).
- Latency budget for `/landing/{id}/` ≤ 800 ms p95 on Singapore-Singapore deploy.

## 4. Implementation order

1. Admin elicits decisions for §2 dimensions (single dialogue; produce decisions doc inline).
2. Backend: implement `LandingView` per `engine.py` recommendation primitives (firm vector + user vector composition).
3. Frontend: wire `usePostSwipeLanding(sessionId)` hook + replace MOCK_LANDING.
4. /review (Part B browser) verifies the 3-tab UX + latency budget.

## 5. Dependencies

- Builds on Phase 13 Office (`backend/apps/profiles/`) + Project schema (`saved_ids`, `liked_ids`)
- Builds on Phase 14 reactions (`apps/social/Reaction`)
- Builds on Phase 15 follows (`apps/social/UserFollow`, `apps/social/OfficeFollow`)
- All three phases live on origin/main as of 2026-05-09.
