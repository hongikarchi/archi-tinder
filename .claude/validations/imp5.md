# IMP-5 Staging Validation Results — Control vs Cached A/B

## Run summary
- Date: 2026-04-27T17:12:53.964325+00:00
- Mode: both
- Phase A (control, flag OFF): 10 queries, 10 succeeded
- Phase B (cached, flag ON):   10 queries, 10 succeeded

> **Note on wall_ms for Phase B call 1**: wall_ms on Phase B call 1 includes `caches.create()` HTTP round-trip (outside `gemini_total_ms` window). Phase A has no such inflation. Phase B post-warmup stats exclude call 1 to isolate pure cached-inference latency.

## Phase A — Control (flag OFF, uncached baseline)

| # | Query | wall_ms | caching_mode | cache_hit | gemini_total_ms |
|---|-------|---------|--------------|-----------|-----------------|
| 1 | concrete brutalist museum | 5344 | none | None | 4594.32 |
| 2 | minimalist Japanese teahouse | 3220 | none | None | 3144.26 |
| 3 | curved fluid contemporary library | 2947 | none | None | 2868.09 |
| 4 | sustainable timber school | 3012 | none | None | 2936.87 |
| 5 | colorful playful childcare center | 3024 | none | None | 2948.72 |
| 6 | monumental classical courthouse | 3347 | none | None | 3271.66 |
| 7 | industrial steel converted warehouse l | 2946 | none | None | 2870.73 |
| 8 | organic biophilic office tower | 2576 | none | None | 2500.34 |
| 9 | desert earthen housing complex | 2934 | none | None | 2858.17 |
| 10 | glass crystalline pavilion | 2818 | none | None | 2743.92 |

**Phase A median gemini_total_ms**: 2904ms

## Phase B — Cached (flag ON, with explicit cache)

| # | Query | wall_ms | caching_mode | cache_hit | cached_input_tokens | gemini_total_ms |
|---|-------|---------|--------------|-----------|---------------------|-----------------|
| 1 | concrete brutalist museum | 4552 | explicit | True | 5919 | 2874.44 |
| 2 | minimalist Japanese teahouse | 3170 | explicit | True | 5919 | 3095.07 |
| 3 | curved fluid contemporary library | 3069 | explicit | True | 5919 | 2995.18 |
| 4 | sustainable timber school | 2818 | explicit | True | 5919 | 2743.1 |
| 5 | colorful playful childcare center | 4268 | explicit | True | 5919 | 4191.79 |
| 6 | monumental classical courthouse | 2557 | explicit | True | 5919 | 2483.09 |
| 7 | industrial steel converted warehouse l | 2646 | explicit | True | 5919 | 2571.28 |
| 8 | organic biophilic office tower | 2971 | explicit | True | 5919 | 2890.62 |
| 9 | desert earthen housing complex | 2762 | explicit | True | 5919 | 2686.38 |
| 10 | glass crystalline pavilion | 2094 | explicit | True | 5919 | 2018.41 |

**Phase B median gemini_total_ms (post-warmup, calls 2-10)**: 2743ms
**Phase B cache hit rate (calls 2-10)**: 9/9 = 100.0% — OK (target ≥95%)

## Computed A/B delta

| Metric | Phase A (control) | Phase B (cached, post-warmup) | Delta | % drop |
|--------|-------------------|-------------------------------|-------|--------|
| Median gemini_total_ms | 2904ms | 2743ms | 161ms | 5.5% |
| Spec prediction | — | 1400-1800ms | — | ≥50% drop expected |

## Verdict (same-session A/B comparison)
- FAIL Spec prediction match: FAIL — only 5.5% drop (target ≥50%)
- **Diagnosis**: Phase B median (2743ms) is not sufficiently lower than Phase A baseline (2904ms). IMP-5 caching is not delivering the expected latency savings.
- **Recommend prod flag flip**: no
