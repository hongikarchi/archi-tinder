# Image-Rendering Latency — Research Report

**Date:** 2026-06-15
**Status:** Research only — no production code. Deliverable lives entirely in `docs/research/image-latency/`.
**Inputs:** Phase 0 first-party measurements (`phase0-measurements.md` / `.json`) + per-dimension web research with adversarial citation verification.

> **Sourcing conventions used throughout.** Vendor-doc / standards claims are cited inline as
> [title](url). Numbers prefixed **"(Phase 0)"** are our own first-party `curl` / `sips` / Playwright
> measurements — they are NOT attributable to any vendor doc and are labeled as such. Where the
> adversarial verifier flagged a claim as *overstated / unsupported / misattributed*, the figure is
> either dropped or explicitly marked **directional / unverified**; such items are never presented as
> settled fact. *(Revision 2026-06-15: the two initially-thin dimensions — delivery-CDN-proxy and
> decode-render-loading — were re-researched with dedicated primary sources after a synthesis-input
> truncation left them under-grounded; §2.3 and §2.4 are now fully cited. Backing data:
> `findings-delivery-cdn-proxy.json`, `findings-decode-render-loading.json`.)*

---

## 1. Executive Summary

### The measured problem

Across a 50-card random publishable sample (Phase 0):

- **Over-fetch (resolution).** Median source image is **2402×1974 px (5.0 MP)**; the swipe card displays
  ≈ **840×1300 device px (1.09 MP)** at DPR 2. Median **over-fetch = 4.6x**, p90 **21.9x**, max **35.1x**.
  **66% of cards over-fetch >2x, 52% >4x, 36% >8x** (Phase 0). The worst card is a 38 MP source shipped
  to a 1.09 MP slot — a **35x over-fetch at 3.9 MB**.
- **Format (JPEG-only).** **100% of the sample is JPEG — zero WebP, zero AVIF** (Phase 0). Modern formats
  are entirely absent on the swipe path.
- **Transfer + latency.** Median transfer **642 KB**, p90 **3139 KB**, **56.4 MB total for 50 cards**
  (Phase 0). In the browser, Divisare cards load at a **median 1941 ms** vs Architizer imgix at
  **398 ms** (Phase 0) — load time tracks byte size, and the byte size is dominated by un-resized
  source pixels.

CDN split of the swipe corpus: **Divisare `images.divisare.com` = 84%** (42/50), **Architizer
`architizer-prod.imgix.net` = 16%** (8/50) (Phase 0). Both are image-transform CDNs (Cloudinary FETCH
and imgix respectively), which is the crux of the corrected conclusion below.

### Headline conclusion (corrected framing)

The original project assumption was *"we serve raw external CDN URLs, so we don't control the bytes →
fixing this needs a re-introduced image proxy."* **Phase 0 falsifies that for the dominant lever.**

- **The dominant fix — resolution — needs NO proxy.** Both source CDNs accept sizing parameters
  directly in the URL path. Rewriting Divisare `w_auto` → `w_840,c_limit` is **honored at the
  Cloudinary edge** and was measured to cut a 3000×3725 / **1,471 KB** original to 840×1043 / **136 KB
  — a 90.7% reduction, no proxy, no infra** (Phase 0, Part E). imgix honors the same resize via
  `w=840&fit=max`. This is a **URL-string rewrite applied where cards are built** — backend
  `_row_to_card` / the card API (or the frontend `normalizeCard` step) — a low-complexity string
  transform (no proxy, no infra, not algorithm/engine logic) that addresses H1 for 100% of cards.
  **Scope note:** the dominant lever most naturally lives in the **backend card-shaping layer**,
  slightly outside the "프론트 부분" the request scoped — stated plainly so the top fix isn't mistaken
  for a pure-frontend change.
- **Only the Divisare *format* fix is proxy-gated.** Explicit `f_webp` on a Divisare URL **returned
  JPEG** (Phase 0) — the Cloudflare layer in front of Cloudinary freezes the first-cached format and
  ignores `Vary: Accept`. Format conversion for the 84% Divisare segment therefore requires a
  self-controlled proxy / re-encode. For the 16% imgix segment, **format is also a free URL rewrite**:
  `&fm=avif` was measured to take a 380 KB JPEG to **115 KB AVIF (70% reduction)** (Phase 0).

So the priority inverts the original worry: **the big win (resolution, ~90% at the tail, ~77% at the
median) is zero-infra — a backend/frontend URL-string rewrite; the proxy is needed only for the
secondary win (Divisare format) on most cards.** Right-sizing alone moves the swipe path materially toward the project's <1 s
page-load target, because resource load duration for the LCP image drops with bytes
([Image performance | web.dev](https://web.dev/learn/performance/image-performance)).

---

## 2. Issue Sections

### 2.1 Resolution / right-sizing — **the dominant lever (no proxy)**

**What the primary sources establish.**

- **Cloudinary `c_limit` is downscale-only, aspect-preserving, never crops.** Per the API reference,
  it is "the same as the fit mode but only if the original asset is larger than the specified limit …
  in which case the asset is scaled down so that it takes up as much space as possible within a
  bounding box" ([Transformation URL API Reference | Cloudinary](https://cloudinary.com/documentation/transformation_reference)).
  With width only (`w_840,c_limit`, no `h_`), height adjusts proportionally.
- **`c_fill` produces exact dimensions by cropping; `c_fit` scales up or down without cropping.**
  `c_fill` "creates an asset with the exact specified width and height" by scaling "as much as needed
  to at least fill both" dimensions ([Transformation URL API Reference | Cloudinary](https://cloudinary.com/documentation/transformation_reference)).
  So `w_840,h_1300,c_fill` yields a pixel-exact 840×1300 by center-cropping (the crop mechanism is an
  inference from the doc, not a verbatim word — verifier note).
- **`w_auto` is inert without client-hint infrastructure.** Cloudinary states that if client hints are
  unavailable "`w_auto` will be treated as if no scaling is requested" — i.e. it delivers the original
  hi-res dimensions ([Responsive Images Using Client Hints | Cloudinary](https://cloudinary.com/documentation/responsive_server_side_client_hints)).
  Client hints require a Chromium browser **and** an `Accept-CH` opt-in response header from the origin
  **and** a `sizes` attribute on the `<img>`. We control none of those on a plain `<img src>`, so
  **`w_auto` is present-but-inert → full-res over-fetch.** This is the documented root cause of H1.
  (Verifier note: the secondary "42% / 51 KB per image" figure once cited here was **not found in the
  cited blog and is dropped.**)
- **FETCH transforms are applied client-hint-independently at the CDN edge** — fetched remote images
  are "transformed and optimized on the fly, before being cached and delivered through fast, localized
  CDNs" ([Deliver remote media files | Cloudinary](https://cloudinary.com/documentation/fetch_remote_images)),
  using the same URL path position as uploaded assets. This is why a hardcoded `w_840` works where
  `w_auto` does not.
- **imgix `fit=max` is the equivalent of `c_limit`** — it "resizes the image to fit within the width
  and height dimensions without cropping or distorting the image, but will not increase the size of
  the image if it is smaller than the output size"
  ([Resize Fit Mode | imgix](https://docs.imgix.com/en-US/apis/rendering/size/resize-fit-mode)).
- **Right-sizing is the documented LCP lever.** "Serving desktop-sized images to mobile devices can use
  2–4x more data than needed" ([Serve responsive images | web.dev](https://web.dev/articles/serve-responsive-images));
  serving responsively "can reduce resource load duration for LCP elements"
  ([Image performance | web.dev](https://web.dev/learn/performance/image-performance)).
- **srcset descriptor choice.** w-descriptors + `sizes` are for layout-variable images; **x-descriptors
  are correct for a fixed-size container** — MDN: it is "incorrect to mix width descriptors and pixel
  density descriptors in the same `srcset`"
  ([Responsive images | MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Responsive_images)).
  web.dev notes "in most cases, the human eye is unable to benefit from a DPR of 3"
  ([Image performance | web.dev](https://web.dev/learn/performance/image-performance)), which justifies
  a 2x cap for the swipe card.

**How it applies to our situation.**

Our card is a fixed ~420×650 CSS px container → ~840×1300 device px at DPR 2. The median source is
2402×1974 (Phase 0) — i.e. it carries **~2.4x the horizontal pixels and far more vertical pixels than
the slot can show**, decoded and discarded on the client. The fix is a string rewrite at card-build
time:

- **Divisare (84%):** `…/images/f_auto,q_auto,w_auto/…` → `…/images/f_auto,q_auto,w_840,c_limit/…`.
  **Measured: 1,471 KB → 136 KB (90.7%)** on a live URL (Phase 0, Part E). Keep the existing
  `q_auto` segment so Cloudinary's per-image quality stays active.
- **imgix (16%):** add `w=840&fit=max&auto=compress` (and `&fm=avif`, see §2.2). imgix honors both
  resize and format directly (Phase 0).
- **DPR handling:** prefer `srcset` with **x-descriptors** (`…w_420 1x, …w_840 2x`) on our own
  frontend over Cloudinary `w_auto` client hints — simpler, browser-agnostic, deterministic output
  size. Capping at 2x is justified by the perceptual evidence above; **Korea-first caveat:** Samsung
  Galaxy S-series are DPR-3 devices and common in Korea, so the 2x cap should be a *conscious* decision
  informed by real DPR distribution (see Open Questions), not silent.

**A second no-infra Divisare lever (from Phase 0).** Many Divisare primaries already have a sibling
gallery URL of the form `/image/upload/c_fit,f_jpg,q_80,w_1200/…` that is **already width-capped at
1200 px and JPEG q=80** (Phase 0, Special Finding #2). Preferring that sibling for the swipe-card cover
is a pure URL-selection change — no transform-param construction needed at all — and is 4–10x smaller
than the un-capped primary. It is a fallback/complementary lever to the `w_840` rewrite.

**Options & tradeoffs.**

| Option | Output | Tradeoff |
|---|---|---|
| `w_840,c_limit` (recommended default) | aspect-preserving, no crop; landscape sources (e.g. 2402×1974 → 840×690) end shorter than the 840×1300 card | safe, lossless rewrite; client may upscale vertically under `object-fit:cover` |
| `w_840,h_1300,c_fill` | pixel-exact 840×1300 by center-crop | matches the fixed card geometry exactly; removes out-of-frame content, subject may sit off-center |
| Prefer existing `c_fit,…,w_1200` gallery sibling | already 1200px-capped JPEG q=80 | zero param construction; 1200px > 840px so slightly larger than a tuned `w_840`, and depends on the sibling existing |

**Quantified expectation.** The confirmed 90.7% is the large-source tail. Fleet-wide, the over-fetch
distribution (median 4.6x → deliver ~1/4.6 ≈ 22% of bytes) implies **~77–78% median byte reduction**,
with tail savings toward ~97% (Phase 0-derived; assumes `q_auto` output quality is comparable — medium
confidence on the fleet aggregate, high on the per-URL measurement).

**Confidence:** **High** on the mechanism and the per-URL measurement; **medium** on the fleet-wide
aggregate (depends on the full source-dimension distribution).

---

### 2.2 Modern formats (WebP / AVIF / JPEG XL)

**What the primary sources establish.**

- **WebP ≈ 25–35% smaller than JPEG.** web.dev cites Facebook's deployment and states savings are
  "usually on the magnitude of a 25–35% reduction in filesize"
  ([Use WebP images | web.dev](https://web.dev/articles/serve-images-webp)). Google's compression study
  found "WebP lossy images are 25–34% smaller than comparable JPEG images at equivalent SSIM"
  ([WebP Compression Study | Google](https://developers.google.com/speed/webp/docs/webp_study)).
  This is the **highest-confidence format figure** (multi-source, methodology-described).
- **AVIF ≈ 50%+ smaller than JPEG, ~20–30% smaller than WebP — but content-dependent.** web.dev cites
  ">50% savings vs. JPEG" from Google/Netflix testing
  ([Using AVIF to compress images | web.dev](https://web.dev/articles/compress-images-avif)). The same
  article's single worked example showed only ~6% for one specific 8 MP image — **savings are highly
  content-dependent** and this medium-confidence figure should not be presented as a guaranteed
  per-image number.
- **AVIF browser support ≈ 93.4% (mid-2026):** Chrome 85+, Firefox 93+, Safari 16.4+, iOS Safari 16.0+,
  Edge 121+, Samsung Internet 14.0+; the remaining ~6–7% is mainly iOS 15 and older
  ([AVIF | caniuse.com](https://caniuse.com/avif)). WebP support is higher (~97%).
- **Decode cost — AVIF heavier than WebP/JPEG on mobile (medium confidence, self-flagged).** Secondary
  sources report WebP decoding faster than AVIF on mobile and recommend WebP for high-frequency mobile
  decode paths ([WebP vs AVIF | SpeedVitals](https://speedvitals.com/blog/webp-vs-avif/)); libavif
  improved in 2024–2025 but hardware AVIF decode is not universal. **No primary silicon-vendor / Google
  performance-team benchmark was found** — treat as directional. This matters for a swipe UI that
  decodes a new card every ~1–2 s.
- **JPEG XL: do not deploy in 2026.** ~14% global support (Safari 17+ partial, Chrome flag-only,
  Firefox disabled) ([JPEG XL | caniuse.com](https://caniuse.com/jpegxl)). The ~20% gain over AVIF does
  not justify a third format in the delivery chain while AVIF still isn't fully rolled out.

**How it applies to our situation.**

- **Divisare (84%): format is BLOCKED via URL.** `f_webp` returned JPEG in our test (Phase 0). Even if
  it weren't, Cloudinary's documented behavior is that **images under 5000 px are delivered as WebP,
  not AVIF**, so an 840px output would top out at WebP via `f_auto` anyway
  ([Optimize Images | Cloudinary](https://cloudinary.com/documentation/image_optimization)). Divisare
  format conversion therefore needs a proxy (§2.3). Expected proxy gain on the *already-resized* 136 KB
  JPEG: **WebP ~25–34% (→ ~90–100 KB)**; AVIF ~50% (→ ~68 KB, content-dependent).
- **imgix (16%): format is FREE via URL.** `&fm=avif` is encoded in the URL cache key, bypassing all
  content negotiation — measured **380 KB → 115 KB AVIF (70%)** (Phase 0). The ~6–7% of clients that
  can't decode AVIF (mainly iOS 15) need a fallback: either `&fm=webp` (~97% support) or a
  `<picture>` element.

> **Verifier carry-over.** The Cloudinary claim that f_auto looks beyond the Accept header reuses the
> phrase *"does not blindly select the format only by browser, and not even by the accepts-header."*
> The resolution-sizing adversarial verify flagged that exact phrasing as **not found verbatim in the
> cited pages (paraphrased/misattributed)** — the *substance* (f_auto uses more than the Accept header)
> holds, but the quote should not be presented as a verbatim vendor quote. (modern-formats had no
> independent verify block, so its confidence levels are taken from the claims' own self-ratings.)

**Options & tradeoffs.**

| Segment | Format option | Tradeoff |
|---|---|---|
| imgix 16% | Always `&fm=avif` | 70% measured; breaks on iOS 15 (~6%) as a bare `<img src>` |
| imgix 16% | `<picture>` AVIF source + `fm=webp` `<img>` fallback | standards-correct, no broken images; adds HTML complexity |
| imgix 16% | `&fm=webp` only | ~97% support, simplest; sacrifices ~20–30% vs AVIF |
| Divisare 84% | proxy → WebP/AVIF re-encode | only path that works; adds infra (§2.3) |

**Confidence:** **High** on WebP 25–35% + browser-support numbers + the imgix-AVIF measurement;
**medium** on the AVIF savings magnitude for our corpus — the 50–60% headline is inflated by sub-1bpp
testing, and for high-quality 840 px architectural photos the realistic range is **~25–50%** (Q9, 2026-06-21;
`findings-q9-avif-architectural-photography.md`); AVIF mobile decode cost remains directional (no current-
hardware benchmark).

---

### 2.3 Delivery / CDN / proxy mechanics — **why Divisare format is frozen**

**What the primary sources establish.**

- **HTTP format negotiation needs `Vary: Accept`.** The browser advertises capability via the `Accept`
  header and the server must respond `Vary: Accept` so shared caches keep separate entries per format
  ([Content negotiation | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Content_negotiation)).
  Without it a cache stores the first-served format and returns it to everyone.
- **Cloudflare ignores `Vary: Accept` by default.** Cloudflare "does not consider vary values in
  caching decisions" except `Vary: Accept-Encoding` and the optional "Vary for Images" feature
  ([Origin Cache Control | Cloudflare](https://developers.cloudflare.com/cache/concepts/cache-control/)).
  So it caches whichever format arrives first and serves it to all clients — independently corroborated
  by an engineering writeup
  ([Vary for images on Cloudflare CDN | timomeh.de](https://timomeh.de/posts/vary-for-images-on-cloudflare-cdn-for-free)).
- **Cloudflare Polish is WebP-only and Vary-blocked.** Polish "only converts standard image formats to
  the WebP format" and bails out with a `vary_header_present` status when the origin sends any `Vary`
  other than `accept-encoding`
  ([Polish compression | Cloudflare](https://developers.cloudflare.com/images/polish/compression/);
  [Cf-Polished statuses | Cloudflare](https://developers.cloudflare.com/images/polish/cf-polished-statuses/)).
- **"Vary for Images" exists but is gated.** It requires a Pro/Business/Enterprise plan, an explicit
  variants API config, origin `Vary: Accept`, and the file extension **in the path** (not the query)
  ([Vary for Images | Cloudflare](https://developers.cloudflare.com/cache/advanced-configuration/vary-for-images/)).
- **imgix `fm=avif` sidesteps all of this** — the format is in the URL cache key, so every client
  requesting that URL gets AVIF with no Vary negotiation
  ([Output Format | imgix](https://docs.imgix.com/en-US/apis/rendering/format/output-format)).

**How it applies to our situation.**

The Divisare delivery chain is **browser → Cloudflare (Divisare's zone) → Cloudinary FETCH.** Cloudinary
`f_auto` would negotiate **WebP** *if the request reached it with the right headers* (note per Q7 the
under-5000px size gate means `f_auto` tops out at **WebP, not AVIF**, at our 840px output — and even at
Divisare's ~2402px median source), but **Divisare's
Cloudflare zone freezes the first-cached format (JPEG, matching the `.jpg` path) and ignores
`Vary: Accept`** — and that zone is **not under our control.** This is the mechanistic explanation for
Phase 0 Special Finding #1 (all Accept-header variants returned JPEG). It also explains the asymmetry we
measured: the **resize rewrite worked** because it changes the transform string → a *different URL cache
key*, whereas the **format param failed** because it depends on Vary negotiation the frozen cache never
performs.

**Options & tradeoffs (proxy is a policy decision — flag to user).**

| Option | What it unlocks | Tradeoff / policy flag |
|---|---|---|
| **No proxy** (resize-only on both CDNs + `fm=avif` on imgix) | ~77–90% bytes (resolution) for 100% of cards + 70% format on 16% | Divisare 84% stays JPEG; **zero infra, zero new policy** |
| **Self-controlled proxy** (Cloudflare Worker / imgproxy / libvips on Railway-Singapore) fetching Divisare JPEG → re-encode WebP/AVIF with a deterministic URL key | format win on the 84% too (incremental ~25–50% on top of resize) | **adds a network hop + ops; a NEW Make-Web layer — NOT a revival of the retired R2 composition (that was an upstream Make-DB data-layer artifact); raises 3rd-party-hotlinking / ToS / cost questions — all USER policy decisions** |
| Cloudflare "Vary for Images" on *our* edge (if a proxy exists) | correct per-format caching at our edge | Pro+ plan + config; only relevant once we own the edge |

**Policy items to surface to the user explicitly:** (1) a Make-Web image proxy is a NEW layer (NOT a
revival of the upstream-retired R2 composition); the *reason* Make DB retired R2 must be understood
first because it may itself be a licensing bar — investigated 2026-06-18, WHY still unknown (lives in an
external spec not in our repo), see Open Question #1 + `findings-r2-retirement.md`; (2) a proxy fetching
Divisare/Archello originals is third-party hotlinking + re-encoding —
a licensing / ToS / bandwidth-cost question, not a pure engineering one; (3) the proxy must be
co-located with Korea/Singapore users to avoid a round-trip penalty.

**Proxy options & costs, if the Divisare format fix is pursued (primary-source).** Estimated scale
≈15.6K unique variants/month (≈7.8K unique images × 2 format variants).

| Option | What it does | Cost (primary-source) | Ops |
|---|---|---|---|
| **Vercel Image Optimization** | Proxies whitelisted remote URLs (`remotePatterns`) → WebP/AVIF + resize, caches ≤31 d on Vercel CDN (Singapore PoP near KR) ([Vercel Image Optimization](https://vercel.com/docs/image-optimization)) | ~$0.05–0.08/1K transforms + cache R/W; Hobby 5K free → **≈$1–2/mo** ([Limits & Pricing](https://vercel.com/docs/image-optimization/limits-and-pricing)) | Lowest — but swipe cards use plain `<img>`, not `next/image` → needs a frontend route change |
| **Cloudflare Worker `cf.image.format`** | Worker `fetch(url,{cf:{image:{format:'avif',width}}})` → re-encode, edge-cached per (URL×params) ([Transform via Workers](https://developers.cloudflare.com/images/transform-images/transform-via-workers/)) | $0.50/1K unique, 5K free → **≈$8/mo** ([CF Images pricing](https://developers.cloudflare.com/images/pricing/)) | Low — managed, keeps existing hotlink URLs (rewrite at backend) |
| **imgproxy (self-host, Singapore)** | OSS on-the-fly resize/format/AVIF, HMAC-signed, signature excluded from cache key ([imgproxy v4 cache](https://imgproxy.net/blog/v4-caching/)) | OSS free / Pro $49/mo + ~$5–20/mo compute | Highest — deploy/scale/monitor; full header control; best at scale |
| **Thumbor (self-host)** | OSS `AUTO_WEBP`/`AUTO_AVIF`, HMAC `SECURITY_KEY`, pluggable result storage ([Thumbor docs](https://thumbor.readthedocs.io/en/latest/)) | OSS free + compute | Highest — full operator burden |

Any proxy we control should also set **`Timing-Allow-Origin: *`** to restore cross-origin Resource-Timing
RUM (Divisare/Archello omit it → the browser zeros `transferSize`/`encodedBodySize`)
([Timing-Allow-Origin | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Timing-Allow-Origin)),
and `Cache-Control: public, max-age=31536000, immutable` on versioned variants to drop revalidation
round-trips ([Cache-Control | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control);
[RFC 9111](https://httpwg.org/specs/rfc9111.html)). **Cache-key rule:** key on (source-URL × transform-params),
exclude any signature token, else hit-rate collapses. **Do NOT proxy the imgix 16% segment** — imgix
already has a Seoul PoP and explicitly warns against a second CDN in front
([imgix CDN guidelines](https://docs.imgix.com/en-US/getting-started/best-practices/cdn-guidelines)); fix
it by URL param instead (§2.2).

**Confidence:** **High** on the Cloudflare/Vary mechanics and the imgix-URL-key behavior — these are
verbatim-doc-backed and corroborated by our Phase 0 measurements.

---

### 2.4 Decode / render / loading — **(re-researched 2026-06-15, now primary-source cited)**

**What the primary sources establish.**

- **Decode memory scales with pixel count, not file size.** A decoded bitmap occupies
  width×height×bytes-per-pixel in RAM regardless of JPEG compression — a 5 MP source expands to
  **~15–20 MB RGBA** when decoded ([Multimedia: Images | MDN](https://developer.mozilla.org/en-US/docs/Learn/Performance/Multimedia);
  [Image performance | web.dev](https://web.dev/learn/performance/image-performance)). Our DPR-2 card
  needs only ~1.09 MP, so the median 5 MP source makes the browser **decode ~4.6x more pixels than it
  paints**, then discards them — extra CPU decode + memory pressure on every ~1–2 s card swap.
  **Right-sizing (§2.1) is therefore also the single largest decode lever (~78% less decode work)**, not
  only a bytes lever.
- **`img.decode()` resolves after DECODE; `new Image().onload` only after DOWNLOAD.** MDN: `decode()`
  "resolves once the image is decoded and is safe to be appended to the DOM … [it] prevents the
  rendering of the next frame … from causing a delay"
  ([HTMLImageElement.decode() | MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode)).
  Our `preloadImage()` uses `new Image()` + `onload`, which resolves on bytes-received, **not**
  decode-complete — so a 1-frame decode stutter can still occur at swap, even on the "instant" path.
  **A lever we do not currently use.**
- **`decoding="async"` can flash empty on dynamic insertion.** MDN: `async` "can result in flashes of
  unstyled content" for in-viewport dynamic swaps, and "Using `HTMLImageElement.decode()` is usually a
  better way"
  ([HTMLImageElement.decoding | MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decoding)).
  We set `decoding="async"` on the card `<img>`; for the JS-driven swap, `img.decode()` supersedes it.
- **`fetchpriority="high"` is correctly set; preloads default to Low.** In-viewport images are boosted to
  High after layout, but `<link rel=preload as=image>` stays Low unless given `fetchpriority="high"`
  ([Fetch Priority API | web.dev](https://web.dev/articles/fetch-priority);
  [Optimize LCP | web.dev](https://web.dev/articles/optimize-lcp)). Any preload link we add needs it.
- **`loading="lazy"` on an above-the-fold image = measured 624 ms slower LCP at p75** (2,922 ms → 3,546 ms,
  CrUX field data; the "~21%" relative figure is an arithmetic derivation, NOT stated by the article)
  ([The performance effects of too much lazy loading | web.dev](https://web.dev/articles/lcp-lazy-loading)).
  We correctly never lazy-load the visible card.
- **LCP image DOWNLOAD is only ~10% of poor-LCP time; load DELAY dominates (~1.3 s median).** web.dev /
  CrUX: poor-LCP origins "spend less than 10% of their p75 LCP time downloading the LCP image", and the
  median wastes ~1.3 s before the download even starts
  ([Common misconceptions about LCP | web.dev](https://web.dev/blog/common-misconceptions-lcp)).
  **Calibration for us:** the Divisare 1941 ms vs imgix 398 ms browser-load gap is **transfer/CDN-bound**
  (origin latency + un-resized bytes), not decode-bound — decode attributes fix swap *jank*, but the
  byte/latency win comes from §2.1 (right-size) and §2.3 (delivery), not from `decoding`/`fetchpriority`.
- **Progressive JPEG paints a full-frame blurry image immediately**, with "very minor" extra decode —
  web.dev calls it "a sensible default" ([Image formats: JPEG | web.dev](https://web.dev/learn/images/jpeg)).
- **`content-visibility:auto` is not a lever here** — it accelerates long, many-section pages (7x in
  web.dev's example), not a 1–3-node card stack; our explicit `width`/`height` already prevents CLS
  ([content-visibility | web.dev](https://web.dev/articles/content-visibility)).

**What we don't yet use (cited recommendations).**

- **Upgrade `preloadImage()` from `new Image().onload` to `await img.decode()`** — guarantees paint-ready
  before swap, killing decode stutter; Baseline since Jan 2020. Cheapest jank fix.
- **Placeholder on the non-instant path** (Divisare ~1.9 s wait): dominant-color or LQIP/blur (imgix can
  emit a tiny `?w=20&blur=…` thumbnail for free) — perceived-latency win, no change to real load
  ([Perceived performance | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Performance/Perceived_performance)).
- **Declarative `<link rel=preload as=image fetchpriority=high>` for card[0]** if its URL is known at
  HTML time — starts the fetch before React executes
  ([Preload responsive images | web.dev](https://web.dev/articles/preload-responsive-images)).
- **Progressive JPEG** as a CDN encoding default where controllable (imgix `fm=pjpg`; Divisare not
  controllable).

**Measurement gap (carried to Open Questions).** Phase 0 measured end-to-end load, not isolated
`img.decode()` / Element-Timing decode (Divisare/Archello omit `Timing-Allow-Origin` → `transferSize`
opaque). Per-device ms/MP decode cost on mid-range Android is unmeasured.

**Confidence:** **High** on the MDN/web.dev mechanics and the LCP-breakdown field data; **medium** on
per-device decode-time magnitude (no ms/MP benchmark).

---

## 3. Prioritized Recommendations

Ranked by measured impact × implementation cost. **Frontend-only / URL-rewrite levers carry no infra
and no new policy** and should ship first; **proxy levers are policy decisions for the user.**

### Tier A — Frontend-only, URL rewrite, NO infra, NO policy (ship first)

| # | Action | Segment | Evidence | Expected impact |
|---|---|---|---|---|
| **A1** | Rewrite Divisare `w_auto` → **`w_840,c_limit`** (keep `q_auto`) at card-build time | Divisare 84% | (Phase 0) 1471 KB → 136 KB = **90.7%**; [Cloudinary FETCH](https://cloudinary.com/documentation/fetch_remote_images) | Dominant. ~77–90% bytes on the largest segment; also cuts decode ~4.6x |
| **A2** | imgix: add **`w=840&fit=max&auto=compress`** | imgix 16% | [imgix fit=max](https://docs.imgix.com/en-US/apis/rendering/size/resize-fit-mode) | Right-sizes the 16% segment |
| **A3** | imgix: add **`&fm=avif`** (with a `<picture>`/`fm=webp` fallback for ~6% non-AVIF clients) | imgix 16% | (Phase 0) 380 KB → 115 KB = **70% on n=1 card**; corpus figure unknown — **high-quality architectural targets likely ~25–50%** (Q9, 2026-06-21); [imgix fm](https://docs.imgix.com/en-US/apis/rendering/format/output-format); [AVIF support 93.4%](https://caniuse.com/avif) | Format win on the imgix segment; pair with the C3 decode A/B before defaulting AVIF |
| **A4** | Add **`srcset` x-descriptors** (`w_420 1x, w_840 2x`) on the card `<img>`; cap at 2x. On imgix, set **explicit per-DPR quality `q=80/40/20`** for 1x/2x/3x (NOT the dated `55/25/15`; `auto=compress` alone only applies a flat `q=45`) | both | [MDN responsive images](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Responsive_images); [imgix variable quality](https://docs.imgix.com/en-US/getting-started/tutorials/responsive-design/responsive-images-with-srcset) (Q8, 2026-06-21); DPR-3 perceptual cap [web.dev](https://web.dev/learn/performance/image-performance) | Eliminates DPR-1 over-fetch; conscious 2x cap (Korea DPR-3 caveat); per-DPR `q` from current imgix docs |
| **A5** | Prefer the existing **`c_fit,f_jpg,q_80,w_1200`** gallery sibling for the swipe cover where present | Divisare 84% | (Phase 0 Special Finding #2) already 1200px-capped q80 | Complementary no-param fallback; 4–10x smaller than un-capped primary |
| **A6** | Upgrade `preloadImage()`: `new Image().onload` → **`await img.decode()`** before card swap | both (frontend) | [img.decode() \| MDN](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode) | Kills decode-stutter at swap; Baseline since 2020; frontend-only, no infra |
| **A7** | **Dominant-color / LQIP placeholder** on the non-instant swap wait (~1.9 s Divisare) | both (frontend) | [Perceived performance \| MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Performance/Perceived_performance); imgix `w=20&blur` free | Perceived-latency win, real load unchanged; frontend-only |
| **A8** | Encode imgix as **progressive JPEG** (`fm=pjpg`) where AVIF unsuitable | imgix 16% | [Image formats: JPEG \| web.dev](https://web.dev/learn/images/jpeg) | "Sensible default"; minor decode cost; Divisare not controllable |

### Tier B — Needs a proxy / infra (POLICY DECISION for the user)

| # | Action | Segment | Evidence | Policy flag |
|---|---|---|---|---|
| **B1** | Stand up a self-controlled proxy (Singapore-co-located) to re-encode the **already-resized** Divisare JPEG → WebP/AVIF with a deterministic URL key. Cheapest paths (see §2.3 table): **Vercel Image Opt ≈$1–2/mo** (needs frontend route change) or **CF Worker ≈$8/mo** (keeps hotlink URLs); imgproxy only at scale. Set `Timing-Allow-Origin` + `immutable` | Divisare 84% only (NOT imgix) | f_webp ignored (Phase 0); [Cloudflare ignores Vary:Accept](https://developers.cloudflare.com/cache/concepts/cache-control/) | **NEW Make-Web layer (not a revival — R2 was a Make-DB data-layer artifact, retired upstream); 3rd-party hotlinking/ToS/cost; ops + cold-start.** Blocked on Q1/Q2 (the R2-retirement reason may itself be a licensing bar). Sequence AFTER A1 and re-measure |
| **B2** | If a proxy exists, configure correct per-format caching (Cloudflare "Vary for Images" Pro+, or the free Transform-Rule `?format=` URL-key workaround) | both via proxy | [Vary for Images | Cloudflare](https://developers.cloudflare.com/cache/advanced-configuration/vary-for-images/) | Plan cost; only after B1 |

### Tier C — Explicitly do NOT do

- **C1 — Do not rely on Cloudinary `w_auto` client hints.** Requires Chromium-only + origin `Accept-CH`
  (not ours) + `sizes` attr; A4 srcset achieves DPR-awareness more reliably
  ([Cloudinary client hints](https://cloudinary.com/documentation/responsive_server_side_client_hints)).
- **C2 — Do not deploy JPEG XL in 2026.** ~14% support ([caniuse](https://caniuse.com/jpegxl)); AVIF
  already covers 93.4% and the marginal gain doesn't justify a third format.
- **C3 — Do not blanket-default to AVIF on the proxy path without a decode A/B.** AVIF mobile decode is
  heavier (medium confidence, no primary benchmark); WebP may be the better swipe-path target.

**Sequencing.** Ship **Tier A first** (zero infra, dominant win, reversible), re-measure bytes + load
on the real corpus, **then** decide Tier B with data — because A1 alone already takes the median card
from 642 KB toward ~150 KB, and the proxy's incremental format gain (~25–50% of the *remaining* bytes)
is secondary.

---

## 4. Open Questions / Follow-ups (need user decision or prod telemetry)

**Need the user.**

1. **Why was the R2 image-composition layer retired?** **Partially investigated 2026-06-18** (repo git
   history + live code; `findings-r2-retirement.md`). **WHAT is established:** R2 paths lived in the
   **Make-DB-owned building table**, retired by an **upstream Make-DB decision** ("R2 cleanup → divisare
   records"); Make Web *adapted* via "Path C — cover CDN-mirror, gallery hotlink hybrid"
   (`engine._row_to_card` fallback + preconnect + telemetry). **WHY is NOT established** — the rationale
   lived in `research/infra/02-image-hosting-strategy.md §6+§7`, which was **never git-tracked here and is
   not on disk** (likely the Make-DB repo). **The WHY is the Tier-B gate and is the same question as #2:**
   if R2 was dropped for **licensing/ToS** reasons, that same bar kills a Make-Web re-encoding proxy; if
   **cost/maintenance**, the calculus differs. → **Surface to user: retrieve the external spec.** Q1 stays
   OPEN.
2. **Proxy / hotlinking policy.** Re-encoding Divisare/Archello originals through our proxy is a
   licensing / ToS / bandwidth-cost decision, not just engineering. Approve before B1. **Coupled to #1** —
   the unknown R2-retirement reason may already answer this.
3. **DPR-3 cap decision.** Samsung Galaxy S-series (DPR-3) are common in Korea; the A4 2x cap trades a
   marginal perceptual loss for bytes. Needs the real DPR distribution to confirm.

**Need prod telemetry — but ANSWERABLE from EXISTING instrumentation (gated prod read, no new code).**

> **We already ship production image-load RUM** (Path C, live on `develop`):
> `POST /api/v1/telemetry/image-load/` → `SessionEvent(event_type='image_load')` in the **app DB
> (ORM-queryable)**, `payload = { url, outcome, domain, canonical_bld_id, context, load_ms }`,
> **sampled 100% failures / 5% successes**. Q4 + Q6 below are answerable by querying it — no new
> instrumentation. See `findings-r2-retirement.md`.

4. **Real Singapore geo latency.** All Phase 0 download times are from a US-west machine; byte/pixel/
   format are geo-independent but *time* is not. **Answerable:** `SessionEvent('image_load').payload→load_ms`
   grouped by `domain` from real prod users = geo-true load time per CDN (quantifies the Archello-Frankfurt
   2313 ms penalty). `load_ms` is the frontend-measured end-to-end load window (gated prod read).
5. **Isolated decode cost.** Phase 0 measured end-to-end load, not `img.decode()` / Element-Timing
   decode time (`Timing-Allow-Origin` absent on Divisare/Archello → opaque). **Still open** — the existing
   `load_ms` telemetry is also end-to-end, NOT isolated decode. Needs Element-Timing instrumentation to
   confirm the "resize = decode fix" magnitude and the AVIF-vs-WebP mobile decode tradeoff (C3).
6. **Archello / CDN impression share.** Archello (Frankfurt, no transform API → proxy-only) appeared in the
   browser session but wasn't in the 50-card curl sample. **Answerable:** `domain` distribution of
   `SessionEvent('image_load')`. ⚠️ **Sampling caveat** — 100%-fail / 5%-success = 20:1 failure
   oversampling; raw event counts are failure-skewed. For true impression share count **success events
   only** (uniform 5% → unbiased) or weight successes ×20; read `outcome='failure'` rate per `domain`
   separately as a reliability signal.

**Research/verification residue — RESOLVED 2026-06-21** (primary-source web research, each load-bearing
claim adversarially re-fetched & confirmed verbatim; see `findings-q7/q8/q9-*.md`).

7. **Cloudinary AVIF "<5000 px" threshold → RESOLVED, and it runs OPPOSITE to the original worry.**
   Verbatim from [Cloudinary image_optimization docs](https://cloudinary.com/documentation/image_optimization)
   ("Tips and considerations for using f_auto"): *"Small images (under 5000 pixels) are not automatically
   delivered as AVIF because the overhead of the file format outweighs the byte-savings… Instead, they are
   delivered as WebP."* So images **under** 5000 px get **WebP** (not "never AVIF→JPEG"); "pixels" reads as
   a **linear** dimension. **At our 840 px output, `f_auto` delivers WebP, not AVIF** — which Cloudinary
   deems optimal at that size. Two consequences: (a) any plan assuming `f_auto`→AVIF at 840 px is wrong —
   force AVIF needs explicit `f_avif` + the proxy doing its own Accept-header capability check; (b) a second
   gate — `f_auto` AVIF also requires the account be on the **image-impressions** billing metric (not
   image-bandwidth). *Confidence: high (verbatim-confirmed).*
8. **imgix per-DPR quality → RESOLVED: the 2016 `q≈55/25/15` is superseded; use `q=80/40/20`.** Current
   [imgix srcset tutorial](https://docs.imgix.com/en-US/getting-started/tutorials/responsive-design/responsive-images-with-srcset)
   gives **`q=80` (1x) / `dpr=2&q=40` (2x) / `dpr=3&q=20` (3x)** as its worked example; the `55/25/15`
   values survive only on the dated 2016 marketing blog, not in current docs. `auto=compress` applies a
   **flat `q=45`** and does **not** vary quality per DPR (that stays a manual concern). → **A4/A2 update:**
   set explicit per-DPR `q` in the imgix srcset (`q=80/40/20` as the calibration baseline, higher than
   55/25/15 — safer for fine architectural detail); explicit `q` overrides the `auto=compress` default.
   *Confidence: high (verbatim-confirmed, incl. file sizes).*
9. **AVIF on architectural photography → RESOLVED (qualified): the 50–60 % headline is inflated for our
   case.** It is skewed by sub-1 bpp test conditions
   ([Cloudinary codec-comparison](https://cloudinary.com/blog/contemplating-codec-comparisons): below-1bpp
   is *"impractical for web use"*; **only ~15 % gain over mozjpeg at real web quality**); web.dev's own
   1120×840 example shows **6.3 %** savings ([compress-images-avif](https://web.dev/articles/compress-images-avif)).
   No architecture-specific primary benchmark exists. High-frequency stochastic texture (brick/concrete
   grain) is where AV1 over-smooths and the advantage narrows; sharp geometric edges compress at/above
   median. **Realistic for our 840 px arch corpus: ~25–50 %, not 50–60 %** — note the one Phase-0 imgix
   card hit 70 % (n=1), but a single card is plausibly favorable/smooth content, whereas the web-research
   prior flags high-frequency architectural texture as the *worse*-compressing case; so 25–50 % is a
   **conservative corpus prior, not a ceiling** the 70 % measurement contradicts. Mobile decode is heavier
   than JPEG/WebP (directionally confirmed; only a stale 2019
   libavif-0.4.4 benchmark quantifies it), and **AVIF is not progressive** (all-or-nothing). → **A3
   savings claim re-qualified below; C3 "no blanket-AVIF without a decode A/B" validated & now
   primary-sourced.** *Confidence: medium (data-backed, but no arch-specific or current-hardware benchmark).*

---

*Revision note (2026-06-15): the initial synthesis under-grounded two dimensions (delivery-CDN-proxy,
decode-render-loading) because of an input-truncation in the synthesis step. Both were re-researched
against dedicated primary sources (`findings-delivery-cdn-proxy.json`, `findings-decode-render-loading.json`),
and §2.3 / §2.4 / the recommendations are now fully cited. Remaining unknowns live in §4 Open Questions,
not as unsourced assertions. The re-researched §2.3/§2.4 citations did NOT pass the workflow's Opus
adversarial-verify gate that §2.1/§2.2 went through; instead their load-bearing figures were
**spot-verified post-hoc by direct source fetch (2026-06-15)** — confirmed verbatim: CF Images
$0.50/1K + 5K free, Vercel $0.05–0.0812/1K, "Cloudflare does not consider vary values… except
vary: accept-encoding", LCP-download <10% / ~1.3 s load-delay, `img.decode()` resolves-after-decode,
lazy-loading 624 ms at p75 (the "21%" was a derived ratio, corrected in §2.4).*

*Revision note (2026-06-21): research residue Q7/Q8/Q9 closed via a primary-source web-research workflow,
each load-bearing claim **adversarially re-fetched and confirmed verbatim** (high confidence on Q7/Q8,
medium on Q9; `findings-q7/q8/q9-*.md`). Net changes: **Q7** — Cloudinary `f_auto` at 840 px delivers
**WebP, not AVIF** (under-5000px gate runs opposite to the original worry; force-AVIF needs explicit
`f_avif` + an image-impressions billing plan). **Q8** — imgix per-DPR quality `55/25/15` is superseded by
current docs' **`80/40/20`**; `auto=compress` is a flat `q=45` and does not vary per DPR (A4 updated).
**Q9** — the 50–60% AVIF headline is inflated by sub-1bpp testing (~15% over mozjpeg at real web quality;
a web.dev case shows 6.3%); realistic for our 840 px architectural corpus ~25–50% (A3 savings re-qualified,
C3 validated & primary-sourced). No Tier A/B/C recommendation reverses direction; A3's interval widened,
A4 gained explicit per-DPR `q`. With Q7–9 resolved, §4's remaining opens are only user-decisions (Q1–Q3)
and gated prod-telemetry (Q4–Q6).*

*Revision note (2026-06-18): Open Question #1 (R2 retirement) investigated from repo git history + live
code (`findings-r2-retirement.md`). Established the WHAT — R2 paths were a Make-DB data-layer artifact
retired by an upstream "R2 cleanup → divisare records" decision, to which Make Web adapted via "Path C"
(`engine._row_to_card` fallback + preconnect + image-load telemetry). The WHY is unrecovered (external
spec `research/infra/02-image-hosting-strategy.md §6+§7`, not in this repo) and remains the Tier-B gate,
coupled to Q2. Corrected the B1 "reverses R2-retirement" framing throughout: a proxy is a NEW Make-Web
layer, not a revival. Surfaced that EXISTING `SessionEvent('image_load')` RUM (live, ORM-queryable,
100%-fail/5%-success sampled) makes Q4 (geo latency by CDN) + Q6 (CDN share, with a failure-skew caveat)
answerable via a gated prod query with no new code; Q5 (isolated decode) stays open.*
