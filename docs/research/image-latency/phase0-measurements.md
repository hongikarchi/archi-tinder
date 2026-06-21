# Phase 0 Image-Latency Measurements

**Date:** 2026-06-15
**Method:** Django shell (real `get_buildings_by_ids` engine) → `curl` + `sips` (macOS) + Playwright browser session
**Sample:** 50/50 primary `image_url` values (HTTP 200), random publishable buildings
**Geo caveat:** Download times from local machine (US west coast), NOT Singapore prod. Byte counts, pixel dimensions, and format are geo-independent.

---

## PART A — Sample Overview

| Metric | Value |
|---|---|
| Cards sampled | 50 |
| HTTP 200 OK | 50 (100%) |
| Failed / timeout | 0 |
| CDN hosts in primary URLs | images.divisare.com (42), architizer-prod.imgix.net (8) |
| image_kind distribution | exterior (49), cover (1) |

---

## PART B/C — Server-Side Measurements

### Format Distribution

| Format | Count | % |
|---|---|---|
| jpeg | 50 | 100% |
| webp | 0 | 0% |
| avif | 0 | 0% |

**All 50 primary `image_url` values served JPEG. Zero modern formats.**

### Source Pixel Dimensions

| Stat | Width (px) | Height (px) | Megapixels |
|---|---|---|---|
| min | 644 | 473 | 0.33 |
| median | 2402 | 1974 | 5.0 |
| p90 | 5541 | 4669 | 23.95 |
| max | 8256 | 6720 | 38.34 |

### Transfer Size

| Stat | Value |
|---|---|
| min | 36 KB |
| median | 642 KB |
| p90 | 3139 KB |
| max | 4841 KB |
| total (50 images) | 56.4 MB |

### Over-Fetch Ratio

Displayed device area ≈ 840×1300 = 1,092,000 px (DPR 2, CSS card ~420×595).
Over-fetch = source_W × source_H / displayed_device_px.

| Stat | Ratio |
|---|---|
| median | 4.6x |
| p90 | 21.9x |
| max | 35.1x |
| > 2x | 33/50 (66%) |
| > 4x | 26/50 (52%) |
| > 8x | 18/50 (36%) |

**Top 5 over-fetch offenders:**

| Over-fetch | Source res | Size | Host |
|---|---|---|---|
| 35.1x | 8256×4644 | 3089 KB | images.divisare.com |
| 29.9x | 7000×4669 | 3036 KB | images.divisare.com |
| 29.9x | 7000×4669 | 3939 KB | images.divisare.com |
| 27.6x | 6720×4480 | 3597 KB | images.divisare.com |
| 27.6x | 4480×6720 | 4841 KB | images.divisare.com |

### Download Time (local machine, not Singapore)

| Stat | time_total | time_ttfb |
|---|---|---|
| min | 0.04s | 0.02s |
| median | 2.05s | 0.87s |
| p90 | 2.72s | 1.1s |
| max | 2.92s | 1.19s |

Redirects: 0/50 (0%).

### Per-CDN Host Summary

| Host | n | median KB | median s (local) | p90 s (local) | fail % | format |
|---|---|---|---|---|---|---|
| images.divisare.com | 42 | 1086 | 2.25 | 2.73 | 0% | jpeg(42) |
| architizer-prod.imgix.net | 8 | 395 | 0.05 | 0.06 | 0% | jpeg(8) |

---

## PART D — Browser Timing (Playwright, ~10 swipes)

**Viewport:** 1454×815 CSS px, DPR=2
**Actual rendered card size:** ~386–420 CSS px wide × ~547–595 CSS px tall
**Note:** Divisare and Archello do not set `Timing-Allow-Origin`, so `transferSize` is 0 (opaque). Duration is real.

### Image load duration (browser, n=18)

| Host | n | durations (ms) | note |
|---|---|---|---|
| images.divisare.com | 14 | [1283, 1448, 1509, 1576, 1626, 1729, 1941, 1971, 2039, 2064, 2209, 2215, 2259] | CORS opaque, bytes hidden |
| architizer-prod.imgix.net | 4 | [180, 206, 589, 810] | bytes visible |
| archello.s3.eu-central-1.amazonaws.com | 1 | [2313] | CORS opaque |

Divisare median load time (browser): **1941 ms**
Architizer median load time (browser): **398 ms**

### DOM Over-Fetch Samples (measured live from browser)

| Host | Natural WxH | Display device WxH | Over-fetch |
|---|---|---|---|
| images.divisare.com | 988×658 | 773×1095 | 0.8x |
| images.divisare.com | 1200×1798 | 806×1142 | 2.3x |
| images.divisare.com | 7015×4960 | 840×1190 | 34.8x |
| architizer-prod.imgix.net | 1680×2240 | 773×1095 | 4.4x |
| images.divisare.com | 4096×2304 | 806×1142 | 10.2x |
| images.divisare.com | 1800×1200 | 840×1190 | 2.2x |

---

## Special Findings

### 1. Divisare format lock — f_auto is NOT negotiating WebP/AVIF
Divisare URLs use the pattern `/images/f_auto,q_auto,w_auto/...`. Cloudinary's `f_auto` is supposed to serve WebP/AVIF based on `Accept` header. **Tested with:**
- No Accept header → JPEG
- `Accept: image/webp` → JPEG
- `Accept: image/avif,image/webp,...` + Chrome UA → JPEG

**Divisare's CDN (Cloudflare in front of Cloudinary) is returning cached JPEG regardless.** Possible causes: CDN cache keyed without `Vary: Accept`, or Divisare has disabled format negotiation. This is outside our control unless we proxy.

### 2. Divisare w_auto = no width constraint → full-resolution originals
Primary URLs use `w_auto` (no pixel constraint). The Cloudinary `w_auto` param picks width based on client hints (`DPR`, `Viewport-Width` headers), but `curl` and standard `<img>` don't send these → Divisare serves **original full-resolution**. Some originals exceed 8000px wide.

**The gallery fallback URLs** (`/image/upload/c_fit,f_jpg,q_80,w_1200/`) ARE capped at 1200px and JPEG q=80. These would be 4–10x smaller for swipe cards.

### 3. Architizer imgix — AVIF negotiation WORKS but browser never triggers it
`?auto=format,compress` on imgix.net sends AVIF when `Accept: image/avif` is present.
Measured: **380 KB JPEG → 115 KB AVIF (70% reduction)** on the same image.
Browser `<img>` tags send a generic `Accept: image/*` that imgix treats as JPEG.
A server-side URL rewrite that injects `&fm=avif` (or a proxy with proper `Accept` forwarding) would unlock this.

### 4. Archello S3 (Frankfurt) — appeared in gallery + browser
`archello.s3.eu-central-1.amazonaws.com` surfaces in gallery URLs and appeared in browser session. Not measured at curl level in this 50-card sample. Browser duration: 2313ms (CORS opaque). Frankfurt origin = higher latency from Singapore.

---

## Hypothesis Verdicts

### H1 — Source images are too high-resolution: **CONFIRMED**

- Median source: 2402×1974 px = 5.0 MP
- Median over-fetch: **4.6x** (52% exceed 4x, 36% exceed 8x)
- Worst case: 38 MP image displayed at 1.09 MP → **35x over-fetch, 3.9 MB transfer**
- Browser confirms: a 7015×4960 card rendered at 840×1190 device px → 34.8x real over-fetch
- **Impact:** The browser downloads and decodes 4–35x more pixels than it renders. On mobile this is decode time + memory pressure, not just bandwidth.

### H2 — PNG/JPEG instead of WebP is costing bytes: **CONFIRMED (but nuanced)**

- 100% JPEG across the sample. Zero WebP, zero AVIF.
- **Divisare (84% of cards):** f_auto is NOT auto-negotiating → locked JPEG. No quick fix without a proxy. Expected saving if WebP were served: ~30–40%.
- **Architizer (16% of cards):** imgix CAN serve AVIF (verified, 70% reduction). A URL param fix (`&fm=avif`) or proxy would unlock immediately.
- Format is a **secondary problem** behind resolution. Even WebP of a 38 MP source would still be 1–3 MB and still be 35x over-fetched.

---

## Recommended Next Steps (for Phase 1 planning)

1. **Resize first (highest ROI):** For Divisare URLs, rewrite `w_auto` → `w_840` (or `w_1200` for headroom) in `_row_to_card`. This alone reduces median transfer from 642 KB to ~150 KB and eliminates the worst overfetch. No proxy needed — just a string transform on stored URLs.
2. **Architizer format:** Add `&fm=avif` param detection when serving Architizer imgix URLs, or let a CF worker inject it. 70% byte reduction on 16% of cards.
3. **Gallery URL fallback:** For Divisare primaries that already have a `/image/upload/c_fit,f_jpg,q_80,w_1200/` sibling in gallery, prefer that URL for swipe-card cover. It's already width-capped.
4. **Proxy (optional, bigger scope):** An image proxy (e.g., Cloudflare Worker → `url=<original>&w=840&f=webp`) would solve both H1 and H2 for all CDNs uniformly but adds infra complexity.
5. **Timing-Allow-Origin missing on Divisare/Archello** — blocks RUM byte monitoring. File a request or add a proxy header to expose actual transfer sizes.

---

## PART E — Empirical Fix Confirmation (direct curl, 2026-06-15)

Tested the highest-ROI hypothesis (URL rewrite, no proxy) on a live Divisare primary URL
(`.../images/f_auto,q_auto,w_auto/.../zest-architecture-casa-creueta.jpg`):

| Variant | Resolved px | Bytes | ctype | Result |
|---|---|---|---|---|
| original `w_auto` | 3000×3725 | **1,471 KB** | image/jpeg | full-res original |
| `w_auto` → `w_840,c_limit` | **840×1043** | **136 KB** | image/jpeg | **90.7% smaller**, matches display |
| `f_auto` → `f_webp` (+ w_840) | 840×1043 | 136 KB | image/**jpeg** | format param **IGNORED** by Divisare CF |

**Conclusions (empirical, not inferred):**
- **Resolution lever WORKS via URL on Divisare (Cloudinary).** `w_840,c_limit` is honored → ~90% byte reduction with NO proxy and NO infra change. This addresses the dominant issue (H1) for 84% of cards by a string transform at card-build time.
- **Format lever is BLOCKED on Divisare via URL.** Explicit `f_webp` returns JPEG (Cloudflare layer in front of Cloudinary strips/ignores it, consistent with the `f_auto` non-negotiation finding). Format change on Divisare requires a proxy or re-encode — but is secondary, since resolution is the bigger win.
- **imgix (Architizer, 16%) honors both** resize and `&fm=avif` (380 KB→115 KB measured).

This corrects the initial framing ("we don't control the bytes → a proxy is required"): the dominant
resolution fix needs no proxy because both source CDNs are image-transform CDNs whose URLs accept
sizing params. Only the Divisare *format* change remains proxy-gated.
