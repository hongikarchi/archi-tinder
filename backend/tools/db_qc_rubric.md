# DB QC — Visual Judge Layer: Rubric + Runbook

Companion to `db_qc.py` (machine layer). The machine layer runs on every
DB-rebuild / parser change (cheap, no LLM judging). This judge layer runs on
milestones only — it verifies TAG TRUTHFULNESS (does the photo actually show
what the tag claims) and DB COMPLETENESS (negative-sample audit), which no
script can measure.

Method calibrated 2026-07-31 (session meta-validation): 3 blind judges vs main
session, binary-evidence agreement 94% (30/32), judge unanimity 91%.
Cover-only courtyard sensitivity ~67% (4/6 tagged controls) -> gallery
escalation is MANDATORY before any negative claim.

## Judgment rubric v1

Judge ONLY the subject building of the image (exclude neighboring/context
buildings in frame). Judge each concept independently per image, pixels only —
no file names, tags, or descriptions. One verdict per concept from:
CLEAR / PARTIAL / NOT_VISIBLE / NOT_JUDGEABLE.

- CLEAR (example, brick): concept is dominant — major facade portion or full
  interior feature wall.
- PARTIAL: clearly present but secondary — fence, chimney, floor, trim, small
  exposed patch, partial original wall in renovation.
- NOT_VISIBLE: no evidence of the concept in THIS image. This is an evidence
  statement about the image, NEVER proof the building lacks the concept.
- NOT_JUDGEABLE: image unreadable, no distinguishable subject building
  (e.g. park installation), or material ambiguous at current resolution ->
  escalate (more images / full resolution / human), never force a verdict.

Courtyard specifics: CLEAR = exterior-character open space enclosed on 3+
sides by the subject building (courtyard/patio/cloister/lightwell; glazed-roof
covered court counts, subclass "covered"). PARTIAL = strong indirect evidence
(U/ring massing, view through opening into internal open space, aerial void).
A plaza/park in FRONT of a building is NOT a courtyard.

When torn between two classes, pick the lower-evidence class and note why.

## Protocol (why each rule exists)

1. **Blind by design** — judges see pixels only. (Meta-validation caught the
   main session mis-judging r07 after reading the building name — metadata
   contamination is real.)
2. **Aggregate binary, keep classes as detail** — CLEAR/PARTIAL boundary is
   the fuzzy zone (exact-class agreement 81% vs binary 94%). Report
   evidence-confirmation rate = (CLEAR+PARTIAL)/judgeable.
3. **Never claim absence** — cover shows ~67% of true courtyards. Escalate to
   gallery (2-3 divisare images; prefer drawings/aerials when present) before
   counting a building as no-evidence.
4. **Ensemble on calibration only** — routine passes use 1 judge (sonnet);
   re-run a 3-judge ensemble when the rubric changes or agreement is doubted.
   Below 90% binary agreement -> stop, refine rubric, re-calibrate.
5. **Positive controls** — seed every judged set with 3-5 buildings whose tag
   is near-certain (e.g. elements Courtyard + name/vd corroboration). Judge
   missing those = method broken, discard the pass.
6. **Negative-sample audit (completeness)** — sample ~20 buildings WITHOUT the
   tag, judge their images; evidence-found rate estimates the tag MISS rate
   (e.g. Prado Extension: courtyard visible in gallery, absent from
   architectural_elements).

## Operational flow (a fresh session can follow this verbatim)

1. `cd backend && .venv/Scripts/python tools/db_qc.py`   # machine layer first
2. Run JSON (gitignored `tools/qc_runs/qc_<ts>.json`) carries per-query
   `top10` with `canonical_bld_id` + `image_url` + `gallery_sample` — the
   judge-layer sample set. No server needed.
3. Download images at reduced width (divisare URLs: replace `w_auto`/`w_1200`
   with `w_800`; skip archello `/thumbs/` URLs — tiny + often HTML errors).
4. Dispatch blind judge(s) (sonnet) with THIS rubric + image paths; force
   structured output {image, <concept>: class, note}.
5. Score: evidence rate per concept per query; compare thresholds below; list
   NOT_JUDGEABLE separately (measurement limit, not quality).
6. Ambiguous/disputed verdicts: attach image paths in the report for human
   final call.

## Quality thresholds (scorecard interpretation)

| Metric | Source | Healthy | Investigate | Fail |
|---|---|---|---|---|
| Tag truthfulness (evidence rate on tagged sample) | judge layer | >=90% | 70-90% | <70% -> re-extract axis |
| Tag miss rate (negative-sample audit) | judge layer | <=10% | 10-25% | >25% -> completeness gap |
| tag_match@10 per served concept | db_qc.py | >=70% | 40-70% | <40% |
| Parser unmatchable values | db_qc.py | 0 | any SOFT-SILENT | any HARD-EMPTY |
| Parser null-fallback rate | db_qc.py | <5% | 5-15% | >15% |
| Image health | db_qc.py | >=95% | 90-95% | <90% |
| NOT_JUDGEABLE share | judge layer | <20% | 20-40% -> widen sample | — |

Regression rule: any metric dropping >5pt vs previous run = regression
(db_qc.py exits 1 automatically for machine-layer metrics; judge-layer deltas
are read manually from successive reports).
