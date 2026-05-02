# IMP-6 Staging Validation Results — Control vs Decoupled A/B

## Run summary
- Date: 2026-04-29T02:37:13.892024+00:00
- Mode: both
- Phase A (control, flag OFF): 10 queries, 10 succeeded
- Phase B (decoupled, flag ON): 10 queries, 10 succeeded, 5 Stage 2 events fired

> **Note**: Stage 2 fires only on terminal turns (probe_needed=False). Clarification turns skip Stage 2 -- visual_description is meaningless before filters stabilize.
> Stage 2 is called synchronously in this command (not via background thread) for clean latency measurement.

## Phase A — Control (flag OFF, single-call legacy)

| # | Query | wall_ms | gemini_total_ms |
|---|-------|---------|-----------------|
| 1 | concrete brutalist museum | 4311 | 3413.12 |
| 2 | minimalist Japanese teahouse | 2508 | 2435.12 |
| 3 | sustainable timber school in Korea | 2730 | 2657.38 |
| 4 | modern art museum with skylight | 2839 | 2765.79 |
| 5 | urban housing complex | 2151 | 2075.54 |
| 6 | industrial converted warehouse loft | 2530 | 2455.37 |
| 7 | modern | 2272 | 2199.35 |
| 8 | interesting building | 1875 | 1801.25 |
| 9 | 한국 전통 목조 건축 | 2415 | 2342.39 |
| 10 | 서울 현대 미술관 | 2371 | 2297.04 |

**Phase A median gemini_total_ms**: 2389ms

## Phase B — Decoupled (flag ON, Stage 1 + Stage 2)

### Stage 1 (parse_query_stage1)

| # | Query | wall_stage1_ms | gemini_total_ms | probe_needed |
|---|-------|----------------|-----------------|--------------|
| 1 | concrete brutalist museum | 2606 | 2532.84 | False |
| 2 | minimalist Japanese teahouse | 1879 | 1805.4 | False |
| 3 | sustainable timber school in Korea | 2449 | 2373.78 | False |
| 4 | modern art museum with skylight | 1835 | 1760.7 | True |
| 5 | urban housing complex | 1979 | 1904.97 | True |
| 6 | industrial converted warehouse loft | 1974 | 1900.45 | False |
| 7 | modern | 2166 | 2093.3 | True |
| 8 | interesting building | 2349 | 2274.41 | True |
| 9 | 한국 전통 목조 건축 | 2246 | 2172.42 | False |
| 10 | 서울 현대 미술관 | 2275 | 2201.96 | True |

**Stage 1 median gemini_total_ms**: 2133ms

### Stage 2 (generate_visual_description, terminal turns only)

| # | Query | wall_stage2_ms | stage2_total_ms | gemini_visual_description_ms | hf_inference_ms | outcome |
|---|-------|----------------|-----------------|------------------------------|-----------------|---------|
| 1 | concrete brutalist museum | 2963 | 2887.13 | 1331.31 | 1555.01 | success |
| 2 | minimalist Japanese teahouse | 1360 | 1287.38 | 936.14 | 350.6 | success |
| 3 | sustainable timber school in Korea | 2376 | 2302.33 | 1328.86 | 973.21 | success |
| 6 | industrial converted warehouse loft | 1778 | 1704.63 | 1339.82 | 364.15 | success |
| 9 | 한국 전통 목조 건축 | 1707 | 1632.44 | 1262.56 | 369.03 | success |

**Stage 2 success rate**: 5/5 = 100.0%
**Stage 2 median stage2_total_ms**: 1705ms
**HF inference median**: 369ms

## Computed A/B delta

| Metric | Phase A (control) | Phase B (Stage 1) | Delta | % drop |
|--------|-------------------|-------------------|-------|--------|
| Median gemini_total_ms | 2389ms | 2133ms | 256ms | 10.7% |
| Spec v1.10 prediction | — | ~1500 ms (45-55% drop) | — | ≥45% drop expected |

## Verdict (same-session A/B comparison)
- Stage 1 latency drop: FAIL (median 2133ms, drop 10.7%)
- Stage 2 success rate: PASS (5/5 = 100.0%)
- Stage 2 stage2_total_ms (observability): 1705ms OK
- **Spec prediction match**: FAIL → research handoff (spec v1.11 re-grounding)

## Diagnosis (data-driven)
Stage 1 gemini_total_ms drop of 10.7% (2389ms → 2133ms) is below the 33% threshold (spec v1.10 predicted ≥45%). Possible cause: _STAGE1_RESPONSE_SCHEMA may not be reducing output tokens as expected -- verify visual_description is absent from Stage 1 responses.
