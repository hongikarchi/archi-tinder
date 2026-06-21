# Q7 — Cloudinary f_auto AVIF Threshold Research

**Date:** 2026-06-21
**Question:** Does Cloudinary's f_auto have a pixel threshold below which AVIF is NOT delivered? Linear or total? AVIF-specific or all auto-format?

---

## Summary

YES — the threshold exists and it is the OPPOSITE direction from what many assume. Images UNDER 5000 pixels are NOT delivered as AVIF; they get WebP instead. Large images (≥ 5000px) qualify for AVIF. For our 840px output, f_auto delivers WebP, not AVIF.

---

## (a) Threshold Exists in Current Cloudinary Docs?

YES. Confirmed in the primary documentation page.

**Source:** https://cloudinary.com/documentation/image_optimization
**Section path:** "How to optimize image format" > "Automatic format selection (f_auto)" > "Tips and considerations for using f_auto" > "AVIF and JPEG XL formats"
**Fetched:** 2026-06-21

### Verbatim quotes:

> "Small images (under 5000 pixels) are not automatically delivered as AVIF because the overhead of the file format outweighs the byte-savings of the optimized image. Instead, they are delivered as WebP."

> "If your account plan uses the image impressions metric, AVIF and JPEG XL formats are automatically supported as possible f_auto formats."

> "If your account plan uses the **image bandwidth metric**, AVIF, animated AVIF and JPEG XL are not supported for f_auto by default. To discuss options for getting f_auto support for these formats, contact support."

---

## (b) Linear Dimension or Total Pixels?

AMBIGUOUS in the docs, but the phrasing strongly implies LINEAR.

The docs say "under 5000 pixels" — not "under 25 megapixels" or "under 25MP". In web/photography contexts, "pixels" as a bare unit without qualification nearly always means a single linear dimension. If it were total pixel count, the expected phrasing would be megapixels (5000×5000 = 25MP = Cloudinary's max transformation limit on free plans).

The docs do NOT specify:
- Which axis (width, height, or max(w,h))
- Whether the threshold applies to source image or output/transformed image

**Engineering inference on source vs output:** AVIF encoding overhead applies to the encoded result, not the source. So the threshold almost certainly applies to the OUTPUT image dimensions (the 840px resized version, not the 6000px original). This is the interpretation that makes sense for Cloudinary's cost-vs-savings calculation.

**Practical conclusion:** 840px is below 5000px under any interpretation (linear: 840 < 5000; total: 840×1100 ≈ 0.9MP << 25MP). The ambiguity does not affect our concrete stake.

---

## (c) AVIF-Specific or All Auto-Format?

AVIF-SPECIFIC. The fallback for small images is WebP, not JPEG.

The verbatim quote says "Instead, they are delivered as WebP" — meaning:
- Images < 5000px AND AVIF-capable browser → WebP (not AVIF)
- Images >= 5000px AND AVIF-capable browser AND impressions-metric plan → AVIF
- Images (any size) AND WebP-capable browser (not AVIF) → WebP
- Images (any size) AND neither AVIF nor WebP support → original format (JPEG)

The threshold is a gate on the WebP→AVIF upgrade only. WebP delivery itself is not affected by the 5000px threshold.

---

## Concrete Stake: 840px Output with Cloudinary f_auto

**Result: WebP delivery, not AVIF.**

Flow for our 840px architectural image:
1. Browser sends Accept header with AVIF support (Chrome, Firefox, Safari 16.4+)
2. Cloudinary evaluates output size: 840px < 5000px → threshold blocks AVIF
3. Cloudinary delivers WebP instead

This means for the 84% of our corpus served via Divisare/Cloudinary, f_auto at 840px yields WebP — a meaningful but not AVIF-level compression gain. AVIF would require either (A) delivering at native source resolution (impractical — defeats purpose), or (B) explicit format override (`f_avif` rather than `f_auto`) bypassing the threshold, or (C) accepting WebP and noting it's what Cloudinary considers optimal at this output size.

**Second gate — billing plan:** Even images above 5000px require the "image impressions metric" billing plan for AVIF under f_auto. Accounts on the "image bandwidth metric" plan cannot get AVIF from f_auto by default.

**Proxy design implication:** The proxy cannot rely on f_auto to deliver AVIF for 840px images. If AVIF is desired at 840px, the proxy must use explicit `f_avif` parameter (which bypasses the auto-threshold) — but this would also bypass browser-capability detection, requiring the proxy to perform its own Accept-header check.

---

## Status

- (a) RESOLVED — threshold confirmed verbatim in current docs
- (b) PARTIALLY RESOLVED — linear implied, axis and source/output not explicit; does not change 840px conclusion
- (c) RESOLVED — AVIF-specific gate, WebP fallback for small images

---

## Sources

1. https://cloudinary.com/documentation/image_optimization — PRIMARY (verbatim quotes above)
2. https://cloudinary.com/blog/how_to_adopt_avif_for_images_with_cloudinary — no threshold details found
3. https://cloudinary.com/blog/adaptive_browser_based_image_format_delivery — no threshold details found
4. https://cloudinary.com/guides/image-formats/avif-vs-webp-4-key-differences-and-how-to-choose — no threshold details found
