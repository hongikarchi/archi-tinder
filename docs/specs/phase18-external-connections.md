# Phase 18 — External Connections

**Status**: Pending dialogue. Lowest priority of the pending phases
(Phase 16 / 17 first).

**Owner**: admin-driven dialogue.

**Pre-context**: `.claude/Goal.md` § 7 Phase 18 — "External connections —
firm article crawl (Space, ArchDaily, news keyword matching), external
DM wiring".

---

## 1. Scope

**1.1 Firm article surfacing** — the actual Phase 18 deliverable. When
viewing a FirmProfilePage, surface external articles about that firm:
- Source candidates: Space (Korean architecture magazine), ArchDaily,
  general news (keyword match on firm name).
- Storage: cached per-firm, refreshed on a TBD schedule.

**1.2 External DM wiring** — ✅ **shipped in Phase 15** (`Office.contact_email`
+ `Office.website` + `UserProfile.external_links` JSON shape already wired
and rendered on Office / User profile pages). What remains for Phase 18
under this sub-scope is optional, deferred:
- Click-through analytics (PIPA / GDPR consent posture required first).
- Pre-fill DM templates / launch-with-context links.
- These belong to a Phase 18.1 follow-up; not in the v1 Phase 18 scope.

## 2. Open dimensions (admin decision)

Phase 18 v1 = firm article surfacing only. Dimensions to resolve:

| Dimension | Question | Notes |
|---|---|---|
| Article source priority | Space first (Korean), or ArchDaily first (global), or both at parity? | Korea-first principle (Goal.md § 6) suggests Space first. |
| Crawl freshness | Real-time API call on profile view / scheduled batch (daily/weekly) / event-driven (on firm publish)? | Cost vs freshness trade-off. |
| Storage | Cache in `Office` row (denormalised) / separate `OfficeArticle` table / external CDN? | Schema decision. |
| Article fallback | When 0 articles match: empty section / hide section / show "no recent articles" placeholder? | UX. |

## 3. Acceptance criteria (illustrative)

- FirmProfilePage shows ≤10 most recent articles from configured sources.
- Articles open in a new tab (no in-app embed; legal posture).
- DM/contact links are click-tracked only if user has consented.
- No regression in FirmProfilePage TTFC (article fetch is async, doesn't
  block initial paint).

## 4. Dependencies

- Phase 13 Office shipped (`backend/apps/profiles/Office`).
- External API access for Space / ArchDaily (legal review needed for
  crawling posture).
- Likely after Phase 16-17 — articles are nice-to-have once core
  recommendation + persona work lands.

---

_Last swept (S8 2026-05-14)_: Goal.md reference path corrected to
`.claude/Goal.md`; otherwise no structural change (lowest priority,
unchanged scope).
