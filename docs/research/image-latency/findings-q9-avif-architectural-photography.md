# Q9 Findings — AVIF Compression on High-Detail / High-Frequency Architectural Photography

**Date:** 2026-06-21
**Scope:** Does AVIF save more, less, or similar to the content-averaged 50–60% figure on
high-frequency, high-detail photographic content (facades, textures, fine lines) specifically?
What is the decode-time tradeoff on mobile for high-detail AVIF?
**Status:** partially-resolved
**Our corpus context:** 840px-wide swipe cards; CDN split = Divisare/Cloudinary 84% + imgix 16%;
100% JPEG at source; architectural photography (facades, concrete, brick, window grids, structural
lines).

---

## 1. The "50–60% vs JPEG" Figure — What It Actually Measures

The headline "50–60% savings over JPEG" appears in multiple sources, but the number is sensitive to
(a) quality-regime and (b) content mix tested. Both matter for our use case.

### 1.1 The most rigorous independent benchmark (ctrl.blog / Daniel Aleksandersen)

**Source:** https://www.ctrl.blog/entry/webp-avif-comparison.html
**Method:** 600 photos and images, 6 sizes (96–1080 px wide), quality-matched via binary search to
structural dissimilarity (DSSIM) threshold 0.0025 using MozJPEG, libwebp, and cavif/libavif.

**Key data:**

| Format | Median savings vs JPEG | 85th-pct savings vs JPEG | Images larger than JPEG |
|--------|------------------------|--------------------------|------------------------|
| WebP   | 31.5%                  | 20%                      | 2.7%                   |
| AVIF   | 50.3%                  | 39.6%                    | 0%                     |

**Verbatim:** "AVIF's 85th percentile was the same as WebP's 15th percentile."

Quality settings reached by the binary search:
- JPEG: quality range 50–99, mean 84
- WebP: quality range 55–99, mean 93
- AVIF: quality range 33–0 (inverted scale), mean 12

**Interpretation:** At perceptually-matched quality across a mixed corpus, AVIF has a real 50.3%
median advantage. But the 85th-percentile figure (39.6%) reveals that 15% of images save less
than that — the lower tail exists. The source does NOT characterize what image types fall in
that lower tail.

### 1.2 The quality-regime sensitivity finding (Cloudinary engineering blog)

**Source:** https://cloudinary.com/blog/contemplating-codec-comparisons

At practical web compression levels (~1 bit per pixel), AVIF gives a compression gain of
approximately 15% over mozjpeg. The source explicitly states that comparing codecs at "extremely
low quality settings (below 1 bpp) skews the aggregate results in AVIF's favor since such
ultra-low quality is impractical for web use."

**Interpretation:** The widely-cited 50–60% figure is partly an artifact of benchmarking at
below-1bpp (heavily-compressed) test conditions. At practical web quality (~1bpp), the documented
advantage narrows to ~15% over mozjpeg. At high-quality targets (above 1bpp), the advantage
narrows further. This is the critical calibration finding for any professional photographic corpus
where quality must be maintained.

### 1.3 The web.dev headline vs. its own worked example

**Source:** https://web.dev/articles/compress-images-avif

**Verbatim:** "teams have seen greater than 50% savings vs. JPEG."

**Verbatim (worked example on the same page):** A 1120×840 pixel image measured 18,769 bytes in
AVIF vs. 20,036 bytes as JPEG — approximately **6% savings** in that specific case.

**Verbatim:** "the exact savings will depend on the content, encoding settings, and quality target."

**Interpretation:** The source that uses the ">50%" headline also documents a case where savings
were only 6%. The content type of that 6%-savings image is not stated. It illustrates that at high
quality targets, the gap can be minimal.

---

## 2. High-Frequency / High-Detail Content — What Primary Sources Actually Say

### 2.1 Jake Archibald's high-detail photographic example

**Source:** https://jakearchibald.com/2020/avif-has-landed/

The article demonstrates AVIF on an F1 race car image described as having "low-frequency detail
(road), high-frequency detail (car livery), sharp color transitions (red/blue)":

| Format | File size |
|--------|-----------|
| JPEG   | 74.4 KB   |
| WebP   | 43 KB     |
| AVIF   | 18.2 KB   |

AVIF = **75.5% smaller than JPEG**; WebP = 42.2% smaller than JPEG.

**Verbatim:** "roughly speaking, at an acceptable quality, the WebP is almost half the size of
JPEG, and AVIF is under half the size of WebP."

**Verbatim on decode / hardware:** "dedicated hardware will be tuned for video, and not so great
at decoding a page full of images" (regarding AV1 hardware acceleration limitations for
still-image decode).

**Verbatim on rendering:** AVIF lacks multi-pass rendering support. Author states "it's
all-or-nothing" loading, whereas JPEG and WebP render progressively.

**Verbatim on flat/sharp content:** "lossy AVIF can handle solid colour and sharp lines really
well" — demonstrated outperforming SVG on flat illustration with antialiased edges.

**Important caveat:** This image's high-frequency elements are sharp-edged, clean-line (livery
text and panel edges) + smooth-gradient (road surface) — AV1's documented wheelhouse.
Architectural facades combine sharp edges (window mullions, structural lines — AV1 good) AND dense
stochastic texture (brick, concrete aggregate, stone grain — where AV1 may over-smooth at lower
quality settings). The F1 example cannot be taken as representative of both sub-categories.

### 2.2 Smashing Magazine photographic evidence

**Source:** https://www.smashingmagazine.com/2021/09/modern-image-formats-avif-webp/

On a sunset photo with extensive textures: JPEG q=75 = 289 KB, WebP q=75 = 206 KB, AVIF q=30
= 101 KB ("up to 81% in compression savings"). This was at mismatched quality levels (AVIF q=30
is aggressive vs JPEG q=75), not a perceptually-matched comparison.

**Verbatim:** "Decoding AVIF images for display can also take up more CPU power than other codecs,
though smaller file sizes may compensate for this."

**Verbatim on encoding improvement:** "47% improvement in transcode time" since January 2021 at
default settings, "73% improvement" across calendar year 2021.

### 2.3 No architecture-specific study found

No primary study isolating architectural photography as a content category was found in any of
the sources surveyed (Netflix TechBlog, ctrl.blog, Jake Archibald, web.dev, Cloudinary,
imgix, Cloudflare, Smashing Magazine). This is an explicit gap that must be closed empirically
on our own 840px corpus.

---

## 3. Mobile Decode Performance

### 3.1 Primary source statements (general)

**Cloudflare blog** (https://blog.cloudflare.com/generate-avif-images-with-image-resizing/):
**Verbatim:** "Decoding AVIF images for display takes relatively more CPU power than other codecs,
but it should be fast enough in practice. Even low-end Android devices can play AV1 videos in
full HD" without hardware acceleration.

**Verbatim (same source):** "images can reduce to half the size of JPEG and WebP" with AVIF.

**Jake Archibald** (same source as §2.1): AV1 hardware decode is optimized for video frames, not
still-image decode bursts.

**SpeedVitals** (https://speedvitals.com/blog/webp-vs-avif/): "WebP has an edge in this case"
regarding decoding speeds, but "for most users, the difference won't be noticeable. In 2025, the
improved algorithms and optimizations have significantly improved the decoding speeds." No
millisecond figures are provided.

### 3.2 Only quantified mobile decode benchmark found (outdated)

**Source:** https://github.com/dreampiggy/ModernImageFormatBenchmark

Measured on iPhone X (iOS 12.4), 512×512 px Lenna test image, software decoders:

| Format | Decode time |
|--------|-------------|
| JPEG   | 0.98 ms     |
| WebP   | 35.33 ms    |
| AVIF   | 105.15 ms   |

HEIC (hardware-decoded by Apple's ImageIO framework) measured 9.88 ms — confirming software vs.
hardware decode is the dominant factor.

**Critical caveat:** This benchmark used **libavif 0.4.4** (2019/early-2020 era). libavif has
since shipped versions 0.9.x through 1.x with substantial SIMD and multi-threading improvements.
The 105/35/1 ms ratio (AVIF/WebP/JPEG) is directional only and cannot be cited as current.
**No 2023–2025 primary benchmark with current libavif on mid-range Android was found.**

### 3.3 Hardware AVIF decode on mobile — status

AV1 hardware decode (MediaCodec, V4L2) is available on 2023+ Android SoCs (Snapdragon 8 Gen 2+,
Exynos 2200+, Dimensity 9200+). However, still-image AVIF decode in Chrome/WebView does not
necessarily route through the video-pipeline hardware decoder. Software decode via libavif/dav1d
is the de-facto path on most devices as of 2024–2025. No primary silicon-vendor benchmark for
still-image AVIF decode on mid-range Android was found.

### 3.4 Decode complexity and image detail — unresolved

AVIF's AV1 decode involves entropy decoding of more complex transform blocks than JPEG DCT, plus
loop-filtering passes. For a high-detail image (denser bitstream, more non-zero coefficients),
decode time is plausibly higher than for a smooth image. **No source quantifies the decode-time
scaling with image spatial frequency for AVIF.** This is an unresolved gap that is relevant to our
burst-decode swipe pattern.

---

## 4. WebP Baseline on Photographic Content (for comparison)

**ctrl.blog:** WebP median 31.5% savings vs JPEG, 85th-percentile 20%, 2.7% of images larger
than JPEG. At matched perceptual quality, WebP needed mean quality=93 vs JPEG mean quality=84 to
achieve parity.

**Verbatim (ctrl.blog):** "I was surprised to learn that the WebP images needed a higher quality
setting to match MozJPEG's visual quality."

WebP decodes faster than AVIF on software mobile paths (all sources consistent on this direction).
WebP supports 8-bit color only, uses 4:2:0 chroma subsampling by default.

---

## 5. imgix Customer Data (our 16% segment)

**Source:** https://www.imgix.com/blog/avif-best-image-format

**Verbatim:** "Since the launch of imgix's AVIF conversion feature in 2022, many of their
customers have seen file sizes drop by nearly 60% when they convert JPEG files to AVIF."

**Verbatim:** "30% decrease in file sizes by converting WebP files to AVIF" (citing Unsplash study).

This fleet-level figure (60% vs JPEG) aggregates all content types in imgix's customer base
(photos, graphics, product images, editorial). It is not specific to architectural photography.

**Phase 0 first-party measurement (our own):** imgix URL with `&fm=avif` measured 380 KB JPEG →
115 KB AVIF = **70% reduction** on a single test card. This is our only first-party AVIF
measurement — one architectural photo at one quality level; not a corpus figure.

---

## 6. Synthesis and Assessment

### 6.1 The "50–60%" headline is NOT a reliable estimate for our high-quality architectural corpus

Evidence establishes three quality regimes with different AVIF advantages:

| Quality regime | AVIF vs JPEG gain | Source basis |
|----------------|-------------------|--------------|
| Low quality (< 1bpp, heavy compression) | 50–80% | ctrl.blog DSSIM-matched median; Jake Archibald example |
| Practical web quality (~1bpp) | ~15% over mozjpeg | Cloudinary codec comparison |
| High quality (near-lossless) | ~6% (documented) | web.dev worked example |

For architectural photography, where facade texture detail, brick lines, and concrete aggregate
must be preserved for the aesthetic purpose of the product, we are operating in the
**practical-to-high quality regime**. The realistic expectation is **~15–50% savings** from AVIF
vs. JPEG, not the 50–60% headline. The headline is inflated by low-quality / high-stress test
conditions that are unsuitable for an architecture photo discovery experience.

### 6.2 Content sub-type matters within architectural photography

Architectural photos combine two sub-categories with different AVIF behavior:

- **Sharp geometric edges** (window grids, mullions, structural joints, facade articulation):
  AV1 intra-prediction handles these efficiently → AVIF advantage at or above median.
- **Dense stochastic texture** (brick, concrete aggregate, stone, scored plaster, weathered
  metal): AV1 tends to smooth stochastic detail at lower quality settings, requiring higher
  bitrate to preserve texture fidelity → advantage over JPEG narrows.

No primary study isolates these sub-categories. The practical implication: for a corpus that
skews toward textured facade photography (common in ArchiTinder's content), the average AVIF
savings will likely be **similar-to-less than the content-averaged 50% figure**, not more.

### 6.3 Validation of C3 ("do not blanket-AVIF without a decode A/B")

The C3 caution is validated by the evidence:

1. **Decode is heavier than JPEG/WebP** — confirmed by multiple primary sources. The magnitude
   is unknown on current devices, but the direction is consistent across all sources.
2. **No hardware AVIF still-image decode on most mobile devices** as of 2024–2025. Software decode
   via dav1d/libavif is the current path. For 840px-wide cards this may be tolerable, but
   it is not measured.
3. **High-detail AVIF bitstreams plausibly decode more slowly** than smooth content due to denser
   transform coefficients — directionally plausible, quantitatively unresolved.
4. **WebP is the safer swipe-path default** for burst-decode patterns (new card every ~1–2 s)
   until a real decode A/B on target devices is done. WebP offers ~31.5% vs JPEG (confirmed
   primary source) + well-understood decode performance + 97% browser support.
5. **For the imgix 16% segment** where AVIF is a free URL param, the measured 70% savings on one
   card is compelling but not corpus-level. Implement with a `<picture>` fallback to WebP and
   add `HTMLImageElement.decode()` timing RUM to capture real decode performance in the field.

### 6.4 Non-progressive rendering — UX consideration for swipe cards

AVIF is all-or-nothing (no progressive scan). Jake Archibald: "it's all-or-nothing." At 840px
with a well-sized AVIF (~70–150 KB), on Korean 5G/LTE this transfer completes quickly. On slow
3G or congested WiFi, the blank-to-image transition is harder than JPEG's gradual progressive
reveal. This is a secondary UX factor, particularly relevant for the Divisare ~1.9 s load tail.

---

## 7. What Remains Unresolved

1. **No architecture-specific AVIF study exists.** Savings on our 840px corpus must be confirmed
   empirically. Recommended: run `&fm=avif` across all 50 Phase 0 cards + measure byte savings
   + add `img.decode()` timing to capture decode latency distribution on real devices.
2. **No 2023+ primary mobile decode benchmark (ms/MP, current libavif, mid-range Android).**
   The 105/35/1ms ratio (AVIF/WebP/JPEG) from 2019 is stale.
3. **The corpus-level figure** from Phase 0 is one card (70%). Fleet figure is unknown.

---

## 8. Recommendation Impact on the Report

- **A3 (imgix `&fm=avif`):** Remains valid Tier A. But the savings should be stated as
  "~40–70% on our imgix segment (one card measured at 70%; fleet figure unknown; high-quality
  architectural targets likely in 25–50% range)" rather than citing the 50–60% headline
  uncritically.
- **C3 ("do not blanket-AVIF without a decode A/B"):** Validated and strengthened. The savings
  upside is real but uncertain for high-quality architectural content; the decode downside is
  directionally real but unquantified. The combination makes an A/B the correct gate before
  switching the proxy output to AVIF (when proxy is approved).
- **WebP as Tier B proxy default:** Supported by the evidence. Confirmed 31.5% savings vs JPEG,
  faster decode than AVIF on mobile software paths, 97% browser support. Switch to AVIF after
  an A/B confirms acceptable decode latency on mid-range Android.

---

## 9. Source Registry

| Source | URL | Key data used |
|--------|-----|---------------|
| ctrl.blog / Daniel Aleksandersen | https://www.ctrl.blog/entry/webp-avif-comparison.html | 600-image DSSIM study; AVIF median 50.3%, 85th-pct 39.6%; WebP 31.5% |
| Jake Archibald | https://jakearchibald.com/2020/avif-has-landed/ | High-detail F1 car: JPEG 74.4KB → AVIF 18.2KB (75.5%); all-or-nothing; hardware decode caveat |
| web.dev compress-images-avif | https://web.dev/articles/compress-images-avif | ">50%" headline; 1120×840 specific case = 6.3% savings; encode CPU 6.5x improvement libaom 2→3 |
| Cloudinary codec comparisons | https://cloudinary.com/blog/contemplating-codec-comparisons | ~15% over mozjpeg at ~1bpp; below-1bpp testing "skews aggregate in AVIF's favor" |
| Smashing Magazine | https://www.smashingmagazine.com/2021/09/modern-image-formats-avif-webp/ | Sunset photo at mismatched quality: 289KB JPEG → 101KB AVIF; decode "more CPU power"; 47–73% encode speedup |
| Cloudflare AVIF blog | https://blog.cloudflare.com/generate-avif-images-with-image-resizing/ | "half the size of JPEG and WebP"; decode "relatively more CPU power... fast enough in practice" |
| imgix AVIF blog | https://www.imgix.com/blog/avif-best-image-format | "nearly 60%" JPEG→AVIF customer fleet average; "30% vs WebP" (Unsplash); 8–10x encode cost |
| GitHub ModernImageFormatBenchmark | https://github.com/dreampiggy/ModernImageFormatBenchmark | iPhone X: AVIF 105ms, WebP 35ms, JPEG 1ms — libavif 0.4.4, 2019-era, stale |
| SpeedVitals WebP vs AVIF | https://speedvitals.com/blog/webp-vs-avif/ | "WebP has an edge" in decode speed; "algorithms improved significantly" by 2025; no ms figure |
| web.dev avif-updates-2023 | https://web.dev/articles/avif-updates-2023 | imgix 60% vs JPEG, 35% vs WebP; animated AVIF 86% smaller than GIF |
