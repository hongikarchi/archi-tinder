# Phase 18 — External Connections

**Status**: Pending dialogue. Lowest priority of the pending phases
(Phase 16 / 17 first).

**Owner**: admin-driven dialogue.

**Pre-context**: `.claude/Goal.md` § 7 Phase 18 — "External connections —
firm article crawl (Space, ArchDaily, news keyword matching), external
DM wiring".

---

## 1. Scope

Two distinct sub-problems:

**1.1 Firm article surfacing** — when viewing a FirmProfilePage, surface
external articles about that firm:
- Source candidates: Space (Korean architecture magazine), ArchDaily,
  general news (keyword match on firm name).
- Storage: cached per-firm, refreshed on a TBD schedule.

**1.2 External DM wiring** — DM/contact links on Office and User
profiles:
- Office: email link, website link (already in `Office.contact_email`
  + `Office.website`).
- User: optional Instagram / email links (`UserProfile.external_links`
  JSON shape).
- Phase 18 expands beyond simple link-out to potentially track
  click-through (analytics) or pre-fill DM templates.

## 2. Open dimensions (admin decision)

| Dimension | Question | Notes |
|---|---|---|
| Article source priority | Space first (Korean), or ArchDaily first (global), or both at parity? | Korea-first principle (Goal.md § 6) suggests Space first. |
| Crawl freshness | Real-time API call on profile view / scheduled batch (daily/weekly) / event-driven (on firm publish)? | Cost vs freshness trade-off. |
| Storage | Cache in `Office` row (denormalised) / separate `OfficeArticle` table / external CDN? | Schema decision. |
| Click-through tracking | Track external clicks (privacy implication) / pure link-out (no tracking)? | PIPA / GDPR posture. |
| Instagram/email surface | UserProfilePage already has `external_links` JSON; expose all sources or admin-curated subset? | UX decision. |

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
