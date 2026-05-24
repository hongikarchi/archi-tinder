# Phase 16 — Recommendation Expansion

**Status**: Re-scoped 2026-05-14 by the tab-3-structure replan
(`.claude/plans-archive/replan-2026-05-14-tab3-restructure.md`). REC1 already
executed as **Push S3** (swipe end-flow consolidation). REC2 / REC3 now
serve a **Profile-tab "사무소 추천" button** rather than a dedicated
Landing tab — the Landing tab itself was removed in Push S6 (4-tab →
3-tab cutover Discovery / Taste / Profile).

**Owner**: admin-driven dialogue, then implementation via orchestrator
pipeline.

**Pre-context**: Phase 13-15 social-graph triplet (User-follow /
Project-reaction / Office-follow) is live. Push S5 / S6 / S7 (2026-05-14)
completed the tab-3-structure cutover — Library tab absorbed into
Profile, Landing tab removed, Discovery infinite-scroll tab added.

---

## 1. Surface shape (post-replan)

The original 3-tab Landing page (Projects / Offices / Users) is
**deprecated**. New surfaces:

- **Projects** (REC1) — top-K bookmarked from current session. Already
  shipped as the consolidated swipe end-screen in **Push S3**.
- **Offices** (REC2) — firm-level recommendations from user taste.
  Triggered by a "사무소 추천" button on the Profile tab; results render
  as a card list (UX shape to be finalised in dialogue).
- **Users** (REC3) — user-level recommendations from taste similarity.
  Same Profile-tab button surface as REC2 (likely a tab toggle, TBD).

Backend endpoint to ship: a single composite endpoint (e.g.
`GET /api/v1/recommendations/profile/`) returning `{offices: [...],
users: [...]}` for the Profile-tab button. The Landing-style
`{projects, offices, users}` triple is no longer needed.

## 2. Open dimensions (need admin decision before implementation)

| Dimension | Question | Notes |
|---|---|---|
| Firm vector composition | Mean of firm's project embeddings / weighted mean / curated subset / max-similarity? | Shapes how Office recs are scored. |
| User taste vector | Aggregated from user's `liked_ids` across all Projects — recency-weighted? curated subset? | UserProfile already has the data. |
| Cold-start strategy | New user with no swipes → "popular users" / generic taste cluster / disable User tab until N swipes? | UX decision. |
| Match score visibility | Show "92% match" on cards, or hide? | UX precision concern. |
| Diversity vs follow exclusion | Recommend already-followed firms? (probably no — exclude) | Easy default but worth confirming. |
| Tie-breakers | Followers count / recency / random / hybrid? | Implementation detail. |
| Trigger surface UX | Single button "사무소 추천" → modal? full-page? toggle between Office/User? | Replan deferred this; need mock before implementation. |

## 3. Acceptance criteria

- New endpoint `GET /api/v1/recommendations/profile/` returns
  `{offices: [...], users: [...]}` with stable shape.
- Profile-tab "사무소 추천" button surfaces the recommendation cards in
  the agreed UX shape.
- Result rendering is instant after the button press (data preloaded or
  fetched within a tight latency budget).
- Cold-start UX is not broken (user with 0 prior sessions sees a
  graceful "explore more" fallback rather than empty cards).
- Latency budget for `/recommendations/profile/` ≤ 800 ms p95 on
  Singapore-Singapore deploy (same target as the old Landing endpoint).

## 4. Implementation order

1. Admin elicits decisions for §2 dimensions (single dialogue; produce
   decisions doc inline).
2. Backend: implement `RecommendationsProfileView` per `engine.py`
   recommendation primitives (firm vector + user vector composition).
   Note: `engine.py` raw SQL must read from `canonical_v2_buildings`
   with `is_publishable = true` gating (per `CLAUDE.md` hard rules).
3. Frontend: wire the Profile-tab button + result rendering surface
   (replaces the deleted Landing page logic).
4. /review (Part B browser) verifies the recommendation UX + latency
   budget.

## 5. Dependencies

- Builds on Phase 13 Office (`backend/apps/profiles/`) + Project schema
  (`saved_ids`, `liked_ids`).
- Builds on Phase 14 reactions (`apps/social/Reaction`).
- Builds on Phase 15 follows (`apps/social/UserFollow`,
  `apps/social/OfficeFollow`).
- Builds on Push S2 (canonical_v2_buildings cutover) — engine.py
  primitives already operate on the new schema; Phase 16 code must use
  `canonical_bld_id` (text PK) end-to-end.
- All prerequisite phases live on origin/develop as of 2026-05-14.

---

_Last swept (S8 2026-05-14)_: Landing-tab framing replaced by
Profile-button framing per replan; canonical_v2_buildings + is_publishable
gating noted as a hard precondition for engine.py edits.
