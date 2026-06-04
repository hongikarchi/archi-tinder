# ARCHITECT-UNIFY — Studio entity unification (Architect-canonical)

> **STATUS: PROPOSAL — not settled architecture.** This document dismantles work from
> PR #180 (office-save, yywon1), PR #182 (architect follow/redesign, admin), and the
> Phase 15 OfficeFollow (KMS). It is a proposal for discussion, **not a decision record**.
> Only **Phase 0 (SavedOffice deletion)** is executed now; Phases 1–4 are coordination-gated.
> Drafted 2026-06-04.

## 한글 TL;DR
건축 도메인에서 건축가=회사=스튜디오=office = **하나의 실체**. 코드가 셋으로 구현해 office-interest
3모델 + 프로필 2페이지가 난립. 유일한 구조적 분리 이유 = 코퍼스(`canonical_v2_architects`)가
read-only → 가변 앱-상태를 app-DB에 둬야 함(스토리지 제약, 도메인 구분 아님). 통합 = corpus `arch_id`를
canonical로 수렴, Office UUID 통째복사 폐기, claim/projects/follow를 arch_id-keyed overlay로 재키잉.
canonical 용어 = **Architect**. Phase 0(SavedOffice 삭제)만 즉시, 나머지는 예원/admin 조율 후.

## Problem
Three overlapping models express "a user is interested in a studio/firm", plus two profile pages:

| Model / page | impl | wired? | author |
|---|---|---|---|
| `ArchitectFollow` + `ArchitectProfilePage` | text `architect_id`, FK-free, COUNT-based | **LIVE, reachable** | admin #182 |
| `OfficeFollow` + `FirmProfilePage` | FK → `Office` UUID, counter-cache signals | wired but **unreachable** (0 nav) | KMS Phase 15 |
| `SavedOffice` | FK → `Office` UUID | **unwired** (no button exists) | yywon1 #180 |
| `Office` table superset | claim FSM + `OfficeProjectLink` + `sync_offices` + serializers/admin | app-managed firm features, currently unwired | yywon1 #180 + KMS PROF1 |

**Root cause (domain):** In architecture, *architect = firm = studio = office* are the same real-world
entity (an architecture practice). The code named it three ways. The **only** structural reason they are
split: `canonical_v2_architects` lives in the read-only Make-DB (`buildings` connection) — mutable app-state
(claims, follows, saves) cannot be written onto the corpus row, so it needs an app-DB home. That is a
**storage-layer constraint, not a domain distinction.**

The mess is that the same "store app-state for a studio" problem was solved **two inconsistent ways**:
- **Office way** (#180 / Phase 15): materialize a full corpus copy into `Office` (via `sync_offices`) and FK
  everything to the `Office` UUID. Heavy — duplicate source-of-truth, requires sync.
- **ArchitectFollow way** (#182): keep the corpus canonical, store only app-deltas keyed by `architect_id`
  text, FK-free (comment: "works before Office sync runs"). Light — corpus stays the single source of truth.

**Verified facts (read-only investigation, 2026-06-04):**
- `FirmProfilePage` (`/office/:officeId`) has **zero UI navigation entry points** — it is unreachable.
  Studio-profile links route to `/architects/` (`UserProfilePage.jsx:809` Studios tab,
  `BoardDetailPage.jsx:987` ArchitectSection). The Phase-13 memory claiming `/offices/{id}/` links is **stale**;
  #182 migrated them to `/architects/`.
- The recommendation engine (`recommendation/views/office_recommendation.py`) reads `Architect` (corpus +
  ArchitectFollow) only — it never joins `Office`.
- `Office` and `Architect` are **separate ID spaces with no backend bridge**; `sync_offices` 1:1-copies
  `canonical_v2_architects WHERE is_recommendable=true` into `Office.canonical_id = arch_id`.
- Nothing in `Office` is intrinsically un-rekeyable to `arch_id` text: claim FSM, `OfficeProjectLink`
  (`unique_together(office, building_id)`), and the `follower_count` counter-cache all need an app-DB row,
  but that row can be keyed by `arch_id` text (the ArchitectFollow pattern).

## Decisions (2026-06-04, with the product owner)
1. Firm / Office / Architect are **one entity** (a studio / architecture practice).
2. Unify by **converging on the corpus `architect_id` (text)** — keep the corpus canonical, collapse the
   `Office` UUID materialization.
3. Canonical term = **Architect** (matches `canonical_v2_architects` / `arch_id` / existing
   `ArchitectProfilePage` / `ArchitectFollow` → least code churn). The architect-as-person vs firm ambiguity
   is accepted (corpus term + product context = practice).

## Target architecture (Architect-canonical)
**One logical Studio = corpus (`canonical_v2_architects`, `arch_id`, read-only, source-of-truth metadata)
\+ a thin app-DB overlay (mutable state only), keyed by `architect_id` text (FK-free, ArchitectFollow pattern).**

- **Reads**: metadata (name / logo / description / website / city) from the corpus directly (`buildings`
  connection). Whether the `Office` full-copy / `sync_offices` is dropped entirely is **Open Decision #3** —
  it may be a read-perf cache (avoiding a cross-DB corpus query on every studio-page load, which bears on the
  <1s page-load goal). Do **not** pre-judge it as removable.
- **App-overlay tables (keyed by `architect_id` text):**
  - `ArchitectFollow` (exists) — follow.
  - **NEW `ArchitectClaim`** (`arch_id` + claim_status FSM + verified + claimant) — absorbs the Office claim flow.
  - **NEW `ArchitectProjectLink`** (`arch_id` + building_id + confidence + source) — absorbs `OfficeProjectLink`.
- **One page** = `ArchitectProfilePage`; fold `FirmProfilePage`'s unique sections (verified badge, projects,
  articles, claim CTA) into it.
- **follower_count** stays COUNT(*) (ArchitectFollow style); drop the Office counter-cache signals.

## Migration phases (multi-PR, multi-session; only Phase 0 now)

### Phase 0 — Delete `SavedOffice` (immediate, safe, no coordination)
- Remove `SavedOffice` model + `OfficeSaveView` + `SavedOfficeListView` + their imports/URLs; new migration
  `0005_delete_savedoffice`.
- Justification: unwired (0 frontend callers, no reverse/cross-app refs) **and** redundant — the "save studio"
  need is already met by ArchitectFollow's saved-studios (wired in #179). It is the loser of a same-day
  collision (#180 SavedOffice vs #182 ArchitectFollow; ArchitectFollow won the wired slot).
- **Note:** this removes yywon1's deliberate #180 feature. yywon1 to be notified.

### Phase 1 — Re-key claim + projects to an `arch_id` overlay
- New `ArchitectClaim` + `ArchitectProjectLink` (text `arch_id`); data-migrate existing
  `Office.claim_status`/`verified` + `OfficeProjectLink` via `Office.canonical_id`. Rewrite
  `OfficeClaimView`/`OfficeAdminQueueView`/`OfficeAdminVerifyView` against `arch_id`.

### Phase 2 — Consolidate follow
- Data-migrate `OfficeFollow` → `ArchitectFollow` (FirmProfilePage unreachable ⇒ ~0 live rows). Drop
  `OfficeFollow` + `Office.follower_count` signals; remove OfficeFollow from the guest-merge FK list.

### Phase 3 — Merge the page (frontend)
- Fold FirmProfilePage's unique sections into `ArchitectProfilePage`; remove `FirmProfilePage.jsx` +
  `firmProfile/*` + the `/office/:officeId` route + `getOffice`/`followOffice`/`OfficeSerializer`.

### Phase 4 — Office table / sync cleanup
- Remove `profiles.Office` + old `OfficeProjectLink` once unreferenced. `sync_offices` / the full-copy is
  kept-or-removed per **Open Decision #3** (direct corpus read vs lightweight perf cache).

## Open decisions (resolve before Phase 1+)
1. **Off-corpus firms** — must a firm *not* in the corpus have a profile/claim? (a) no (corpus members only),
   or (b) mint an app-side `studio_id` space. Depends on the P1 firm scope.
2. **Claim persistence vs corpus re-sync** — orphan policy if a corpus `arch_id` is retired/changed.
3. **Metadata read perf** — per-request corpus (cross-DB) read vs a lightweight cache (replacing the current
   full Office copy). Measure against the <1s page-load goal before deciding `sync_offices`'s fate.
4. **Phase 1–4 PR split + author assignment** (yywon1 / admin / Claude lane) + ordering.

## Coordination (required — touches multiple contributors' recent work)
- yywon1 (#180 Office / SavedOffice / sync_offices), admin (#182 ArchitectFollow / ArchitectProfilePage), KMS
  (Phase 15 OfficeFollow). Phases 1+ need agreement before starting. Phase 0 (SavedOffice) is the only
  coordination-free step (unwired; notify yywon1).
- Deploy-gate: interacts with the pending #180/#182 prod migrations — Phase 0's `0005` DROP joins that batch;
  prod `SavedOffice` is empty ⇒ DROP is safe.
