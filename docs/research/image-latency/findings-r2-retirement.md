# Finding: R2 image-composition retirement + existing image-load telemetry

_Investigation 2026-06-18 — closes part of Open Question #1, upgrades #4/#6. Source: our own repo (git history + live code), no prod read._

## Q1 — Why was the R2 image-composition layer retired?

### WHAT is established (from repo, verified)

- **R2 paths lived in the Make-DB-owned building table, not in a Make-Web layer.** `engine.py:13`
  docstring (current `develop`): _"Image URLs are full source-CDN URLs (Divisare/etc.). **R2 composition is
  no longer used.** `covers_by_type` JSONB allows per-focus cover selection."_
- **The retirement was an upstream Make-DB data decision; Make Web *adapted* to it (did not choose it).**
  Commit `3894bbe` _"feat: Image hosting Path C — backend defensive fallback + telemetry (1/2)"_:
  > "engine._row_to_card previously read only image_photos[] (R2 paths) — divisare-only buildings
  > rendered with broken images (image_url=''). **Make DB transition (R2 cleanup → divisare records)**
  > would have made this worse over time."
- **Our response = "Path C — cover CDN-mirror, gallery hotlink hybrid"** (`research/infra/02-image-hosting-strategy.md`
  §6+§7, referenced by both commits). Implemented as:
  - `engine._row_to_card` fallback chain: `image_photos` → `cover_image_url_divisare` → `''`; gallery merges
    `extra_photos + divisare_gallery_urls + drawing_urls` (R2 drawings strictly at tail).
  - DNS+TLS preconnect to `divisare.com / images.divisare.com / metalocus.es` in `index.html`.
  - `getImageSource(url)` host-anchored CDN classifier (`frontend/src/api/images.js`).
  - Image-load telemetry beacon (see below).
- Commits authored by Claude Opus 4.7; reviewer/security fix-loop applied (gallery-boundary MAJOR +
  telemetry throttle/ownership/NaN CRITICALs). 25 tests in `test_image_hosting_fallback.py`.

### WHY is NOT established (the load-bearing gap)

- The commit bodies give the **recommendation** ("Path C"), not **Make DB's reason for dropping R2**.
- The rationale lived in `research/infra/02-image-hosting-strategy.md §6+§7`. That doc was **never
  git-tracked** in this repo and is **not on disk** (searched `/` + `~/Documents`). Likely in the
  **Make-DB repo** or an external research folder.
- **This WHY is the Tier-B gate.** If Make DB retired R2 for **licensing / ToS** reasons (re-serving
  Divisare/3rd-party images), the *same reason kills a Make-Web re-encoding proxy* — which is exactly
  Open Question #2 (proxy/hotlinking policy). If it was **cost / maintenance**, the calculus differs.
  **→ Q1's unknown WHY and Q2's policy question are the same question.** Cannot be resolved from our repo.

### Correction to report B1 framing

Report §3 Tier B B1 said the proxy "**Reverses R2-retirement**." That is **wrong**: R2 was a Make-DB
data-layer artifact we never controlled, retired by an upstream decision. A Make-Web proxy is a **NEW
independent layer**, not a revival. (We have not confirmed who *operated* the bucket — only that the
paths lived in Make-DB's table.) Framing corrected in §3 + §4.

## Existing image-load RUM — upgrades Q4 / Q6 to "answerable"

**We already ship production image-load telemetry** (Path C, still live on `develop`):

- Endpoint: `POST /api/v1/telemetry/image-load/` → `ImageLoadTelemetryView`
  (`backend/apps/recommendation/views/telemetry.py`), throttled, AllowAny.
- Stored as `SessionEvent(event_type='image_load')` in the **app DB (default connection, ORM-queryable)**,
  `payload = { url, outcome ∈ {success,failure,timeout}, domain, canonical_bld_id, context, load_ms }`.
- Frontend: `useImageTelemetry` hook on `SwipeCard`, `BoardCard`, `ProjectCard`.
- **Sampling: 100% failures, 5% successes** (`SUCCESS_SAMPLE_RATE = 0.05`).

### What it can answer (via a gated prod query — NOT yet run)

- **Q4 (real Singapore geo latency by CDN):** `load_ms` grouped by `domain`, from real prod users =
  the geo-true load time per CDN. Note `load_ms` is the frontend-measured image load window.
- **Q6 (real CDN/domain impression share):** `domain` distribution of events.
  - ⚠️ **Sampling caveat:** 100%-fail / 5%-success = 20:1 failure oversampling. Raw event counts are
    **failure-skewed**, NOT true impression share. For real share, count **success events only** (uniform
    5% → unbiased) or weight successes ×20. `outcome='failure'` rate per `domain` separately = reliability.

### What it does NOT answer (Q5 stays open)

- `load_ms` is **end-to-end image load**, not isolated `img.decode()` / Element-Timing decode. Q5
  (isolated decode cost, ms/MP on mid-range Android) remains unmeasured by this telemetry.

## To surface to the user

1. **The actual WHY (Q1) needs the external spec** `research/infra/02-image-hosting-strategy.md §6+§7` —
   likely in the Make-DB repo. Q1 stays OPEN until that reason is known (it gates Tier B via Q2).
2. **Offer a gated prod query** on `SessionEvent('image_load')` to convert Q4/Q6 from open → answered with
   real Singapore data (with the success-only / ×20 sampling correction).
