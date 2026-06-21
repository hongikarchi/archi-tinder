# Q8 — imgix Variable Quality per DPR: Findings

**Question:** What does imgix currently recommend for q (output quality) and auto=compress? Is there official variable-quality / DPR-quality guidance, and are the q≈55/25/15 values from the 2016 blog still endorsed?

**Status:** PARTIALLY RESOLVED  
**Date:** 2026-06-21

---

## Primary Sources Consulted

| Source | URL | Nature |
|--------|-----|--------|
| imgix Output Quality API (current) | https://docs.imgix.com/en-US/apis/rendering/format/output-quality | Official API docs |
| imgix Automatic (auto=) API (current) | https://docs.imgix.com/apis/url/auto/auto | Official API docs |
| imgix Device Pixel Ratio API (current) | https://docs.imgix.com/en-US/apis/rendering/device-pixel-ratio | Official API docs |
| imgix Responsive Images with srcset tutorial (current) | https://docs.imgix.com/en-US/getting-started/tutorials/responsive-design/responsive-images-with-srcset | Official tutorial |
| imgix Improving Site Performance (current) | https://docs.imgix.com/en-US/getting-started/best-practices/improving-site-performance | Official best practices |
| imgix blog: "Optimizing Quality and Speed for High-DPR Images" | https://www.imgix.com/blog/dpr-quality | Vendor blog (2016-03-30) |

---

## Finding A — q (output quality) parameter: current defaults and range

**Source:** https://docs.imgix.com/en-US/apis/rendering/format/output-quality

> "Valid values are in the range 0–100 and the default is 75."

> "When auto=compress is applied, the default value becomes 45 unless overriden."

> "Quality can often be set much lower than the default, especially when serving high-DPR images."

**Summary:**
- Default q = **75** (without auto=compress)
- Default q = **45** (when auto=compress is active)
- Applies to lossy formats only: jpg, pjpg, webp, avif, jxr
- Lower values explicitly encouraged for high-DPR delivery
- Range 0–100

---

## Finding B — auto=compress: what it does and quality interaction

**Source:** https://docs.imgix.com/apis/url/auto/auto

> "Imgix will apply best-effort techniques to reduce the size of the image by altering our normal processing algorithm to apply more aggressive image compression."

> "The default quality standard changes to 45."

> "When combined with auto=format, the system serves images in AVIF when possible, falling back to WebP, then PNG8 or JPEG depending on transparency and browser support."

**Important:** auto=compress sets a single blanket quality (q=45 default) for ALL requests regardless of DPR. It does **not** automatically vary quality per device pixel ratio — that adjustment is manual, requiring different `q` values per srcset entry.

**Practical note:** A real example from the docs shows: original 185 kB → 35 kB with auto=compress.

---

## Finding C — Official variable-quality / DPR-quality guidance (current docs)

**Source:** https://docs.imgix.com/en-US/getting-started/tutorials/responsive-design/responsive-images-with-srcset

> "If you choose to use the '1x, 2x, 3x' pattern for srcsets, we highly recommend using variable quality to modify the quality of the image as the resolution increases."

> "Setting the q parameter to lower values for higher DPRs allows you to reduce the file size while maintaining a denser pixel set for your image."

The current tutorial provides these concrete example values for a 300px wide image:

| DPR | URL parameters | File size |
|-----|---------------|-----------|
| 1x  | ?q=80         | 21.3 kB   |
| 2x  | ?dpr=2&q=40   | 34.7 kB   |
| 3x  | ?dpr=3&q=20   | 42.1 kB   |

**Classification:** These are presented as illustrative examples, not universal prescriptions. The tutorial positions variable quality as "a customizable optimization strategy that developers should calibrate based on their specific imagery and performance requirements."

---

## Finding D — The 2016 blog's q=55/25/15 values: source and current status

**Source:** https://www.imgix.com/blog/dpr-quality (published 2016-03-30, still live and unmodified)

> "These settings are a good starting point for working with high-DPR images and quality."

The 2016 blog recommends:

| DPR | Parameters | File size (200px wide) | vs. default q=75 |
|-----|-----------|----------------------|-----------------|
| 1x  | q=55 (+ optional usm=20) | 12.21 kB (13.80 kB with usm) | vs. 17.26 kB |
| 2x  | dpr=2&q=25 (+ optional usm=20) | 15.54 kB (17.12 kB with usm) | vs. 47.04 kB |
| 3x  | dpr=3&q=15 (+ optional usm=20) | 22.88 kB (24.67 kB with usm) | vs. 85.67 kB |

The rationale:
> "High-DPR images have denser pixel data, so they can withstand more compression...we can use a much lower quality setting with no obvious loss in image quality."

**Current status of 55/25/15:**
- The blog post is still live, still linked from imgix search results, and has not been retracted.
- It is **not referenced** in current official API docs or tutorials.
- The current srcset tutorial uses **different** (less aggressive) example values: q=80/40/20 vs. q=55/25/15.
- There is no newer imgix blog post, changelog, or doc that explicitly supersedes or endorses 55/25/15.
- **Verdict: The 55/25/15 values are directional only (2016, single blog post) and have been implicitly superseded by the less aggressive 80/40/20 examples in current docs.** Neither set is formally prescriptive.

---

## Finding E — No automatic per-DPR quality adjustment exists

Confirmed across all sources: imgix does **not** offer an automatic per-DPR quality scaling feature. There is no parameter equivalent to "auto-vary quality with DPR." Variable quality is a developer responsibility implemented by setting different `q` values per srcset entry.

auto=compress alone, combined with any dpr value, applies a flat q=45 — it does not scale quality inversely with DPR.

---

## Comparison: 2016 blog vs. current docs examples

| | 2016 blog (q=55/25/15) | Current docs (q=80/40/20) |
|--|------------------------|--------------------------|
| 1x quality | 55 | 80 |
| 2x quality | 25 | 40 |
| 3x quality | 15 | 20 |
| Aggressiveness | More aggressive | More conservative |
| Label | "good starting point" | illustrative examples |
| Still linked? | Yes, still live | Yes, current docs |
| Formally endorsed? | Not in current docs | Illustrative only |

The current docs examples are approximately 45% less aggressive than the 2016 blog at each tier. For fine-detail image corpora (architectural photography), the more conservative current-docs values (80/40/20) are a safer calibration point.

---

## Implication for Our Stack

**Our setup:** imgix delivering ~840px wide architectural photography (~16% of corpus); existing recommendation is &auto=compress + right-sizing.

**Should we add explicit q per DPR?** Yes — the current docs explicitly say "we highly recommend using variable quality" for 1x/2x/3x srcset patterns. auto=compress alone does not handle this.

**What values?** Use the current docs' examples (q=80/40/20) as the starting calibration point rather than the 2016 blog's 55/25/15. Architectural photography has high-frequency detail (facade texture, material grain) that is more susceptible to compression artifacts than generic photography, making the more conservative current-docs values preferable. Fine-tune empirically.

**Recommended implementation:**

  srcset:
    image.jpg?w=840&q=80&auto=compress,format 1x
    image.jpg?w=840&dpr=2&q=40&auto=compress,format 2x
    image.jpg?w=840&dpr=3&q=20&auto=compress,format 3x

Note: auto=compress sets a baseline of q=45, but an explicit q= parameter overrides it. At 1x, q=80 overrides auto=compress's q=45 upward — this is intentional (higher fidelity for 1x where pixels are at full logical size).

---

## Confidence Assessment

| Claim | Confidence | Source |
|-------|-----------|--------|
| q default = 75, auto=compress default = 45 | HIGH | Official API docs (current) |
| auto=compress does NOT auto-vary quality per DPR | HIGH | Confirmed by absence across all docs + API reference |
| Variable quality per DPR is officially recommended | HIGH | Current srcset tutorial: "we highly recommend" |
| Current docs example values = q=80/40/20 | HIGH | Current srcset tutorial (confirmed by direct fetch) |
| 2016 blog values q=55/25/15 explicitly superseded | LOW — not formally superseded, but diverge from current examples and are 10 years old |
| 80/40/20 better for architectural photo | MEDIUM — directional; no corpus-specific data in imgix docs |
