# Building DB cleanup — request to the Make DB owner

**From:** Make Web (ksangjo)
**To:** Make DB owner (sole writer of `archi_data`; Make Web only reads `canonical_v2_buildings`)
**Measured:** 2026-10-16 on prod `archi_data` (release c27), read-only. Publishable
buildings (`is_publishable = true`): **36,673**. Counts below are publishable buildings unless
stated otherwise. Measurement queries: Appendix B.

## Summary

| # | Field | Problem | Scale | What to do | Ready-made script |
|---|---|---|---|---|---|
| **1** | Image URLs (Archello) | `archello.com/thumbs/…` is hotlink-blocked outside archello.com (HTTP 403) | 7,714 rows, ~285k URLs | Rewrite to the S3 original URL | **S1** |
| **2** | `location_country` | One country under several spellings; cities, addresses, postcodes in the country column | 15 spellings (186 rows) + 13 single rows | Normalize; move cities to `location_city` | **S2** |
| **3** | `material_visual` | Free text: the same material under many names (wood / timber / oak …) | 15,561 distinct values | Add `material_group TEXT[]` (12 values) | **S3** + loader change |
| 4 | `program` / `typology_primary` | No retail program; typology→program relation not defined | `Other` 2,365 (Retail 792) | Vocabulary decision: relation table + `Retail` | — |
| 5 | `architectural_elements` | Filled only when the source site tagged it | 66% empty | Re-extract from `visual_description` (LLM) | — |
| 6 | `year_kind` | "Completed" is decided by year only | competition / unbuilt entries counted as built | Add a build-status column (recrawl) | — |
| 7 | Feedback reports (`user_data`) | New Make Web tables to apply and review | — | Apply migration; review reports by SQL | — |

Items 1–3 can be done with SQL; Make Web prepared the scripts (Appendix A). §8 lists the run
order and everything that must be recomputed or synced afterwards. Priority order is §9.

Supporting files (in this repo, `docs/db-fixes/`) — only item 3 needs them, because its
mapping (6,540 rows) is too large to inline; S1 and S2 are complete inside this document:
- `material_group_rules.py` — **source of truth** for the material grouping (rules + a
  command that regenerates the CSV)
- `material_group_map.csv` — generated from the rules on 2026-10-16 prod values; S3 loads it.
  Regenerate instead of editing (Appendix A, S3 step 0)

---

## 1. Archello image URLs (highest priority)

**Problem:** `https://archello.com/thumbs/…` URLs open in a browser address bar but are blocked
when embedded in another site (HTTP 403). Most Archello covers already use the S3 URL; the
detail gallery of Archello buildings shows empty tiles.

**Scale:** 7,714 rows (7,591 publishable). Rows per column: `all_images` 7,714 ·
`best_image_per_cluster` 7,709 · `covers_by_type` 1,560 · `display_cover_url` 5 ·
`cover_image_url_default` 0.

**Rule:** `https://archello.com/thumbs/<path>?…` → `https://archello.s3.eu-central-1.amazonaws.com/<path>`
(query string dropped). Every thumbs URL in the DB has the same query shape
(`?fit=&w=&h=`), so this one rule covers all of them.

| | Example |
|---|---|
| Before | `https://archello.com/thumbs/images/2019/01/08/1Casa-MKAC-TAL-06.1546951725.1092.jpg?fit=crop&w=225&h=148` |
| After | `https://archello.s3.eu-central-1.amazonaws.com/images/2019/01/08/1Casa-MKAC-TAL-06.1546951725.1092.jpg` |

**Verified:**
- 100 random rewritten URLs: all HTTP 200 (the current URLs return 403).
- The rewrite creates no duplicate URL inside any building.
- S1 dry-run on prod (read-only): 7,714 rows change, 0 old URLs remain, all JSON stays valid,
  `covers_by_type` keeps its 5 keys.
- No `publishability_reasons` value depends on these URLs.

**Note:** the result is the original image (~2000 px, some 1–2 MB) instead of a 225×148
thumbnail. Make Web handles display size on its side.

**To do:** run S1 → apply the same rewrite to the c27 artifact → store future Archello crawl
output with the same rule. Longer term: a periodic dead-URL check, and consider re-hosting
images on R2.

---

## 2. Country (`location_country`)

178 distinct values (176 among publishable). Most are clean English country names.

### 2-1. Same country, different spelling (publishable counts)

| Normalize to | Current values |
|---|---|
| **Turkey** | `Turkey` 128 · `Türkiye` 110 |
| Iran | `Iran` 189 · `Iran, Islamic Republic of` 39 |
| United Arab Emirates | `United Arab Emirates` 136 · `Dubai - United Arab Emirates` 2 · `Dubai - UAE` 1 · `Abu Dhabi - United Arab Emirates` 1 |
| Saudi Arabia | `Saudi Arabia` 36 · `Riyadh Saudi Arabia` 4 · `AlUla Saudi Arabia` 1 |
| Spain | `Spain` 3,554 · `España` 1 |
| Bahamas | `The Bahamas` 3 · `Bahamas` 2 |
| Laos | `Lao People's Democratic Republic` 2 · `Laos` 1 |
| Myanmar | `Myanmar` 1 · `Myanmar (Burma)` 1 |
| France | `France` 2,806 · `France -` 1 |
| Singapore | `Singapore` 81 · `Singapore 299583` 1 |
| **Palestine** | `Palestine, State of` 12 |
| **DR Congo** | `Congo, The Democratic Republic of the` 1 |

**Naming rule:** Make Web matches the English country name its LLM produces. The LLM writes
"Turkey", so normalize to `Turkey`, not `Türkiye`. `Palestine` and `DR Congo` match Make Web's
country vocabulary. With these names Make Web can match countries exactly.

### 2-2. City, address or postcode in the country column (per-row fixes)

Country confirmed from the city column and the source page. Where the city column is also
wrong, it is fixed too.

| Building | Current country | → Country | City |
|---|---|---|---|
| `bld_038101` ANOTHER GLASS HOUSE | `Tokyo` | Japan | keep (Tokyo) |
| `bld_034408` Hankyu Hanshin Brokerage Hommachi office | `1 Chome−3−15 関電不動産西本町ビル` | Japan | `Japan` → **Osaka** |
| `bld_039193` Huigu Lake Innovation Town | `Chongqing` | China | `China` → **Chongqing** |
| `bld_035203` 文化锚地 (Shunde) | `SHUNDE` | China | keep (Shunde) |
| `bld_034561` Riftline | `Tabriz` | Iran | keep (Tabriz) |
| `bld_031431` Albino Authenticity | `Prishtinë` | Kosovo | keep |
| `bld_032625` ZUCCA cucina | `Pristina` | Kosovo | `M542+RFV` (plus code) → **Pristina** |
| `bld_002452` Forum Shopping Centre | `- Nis` | Serbia | NULL → **Niš** |
| `bld_033448` Zhytniy Market | `02000` (postcode) | Ukraine | `Verkhnii Val St` (street) → **Kyiv** |
| `bld_034611` School Hub | `61000` (postcode) | Ukraine | `Heorhiya Tarasenka St` (street) → **Kharkiv** |
| `bld_000315` Boon The Shop | `Korea, Democratic People's Republic of` | **South Korea** | keep (Seoul) |
| `bld_000404` Element House | `Korea, Democratic People's Republic of` | **South Korea** | keep (Anyang) |
| `bld_032913` (not publishable) | `전주 완산구 중화산1동 164-17` | South Korea | `South Korea` → **Jeonju** (country and city swapped) |

`Antarctica` (2 buildings) is a real research station — leave it.

### 2-3. Why it matters
Make Web currently matches countries by substring (`location_country ILIKE '%value%'`):
`Turkey` misses the 110 `Türkiye` buildings (46% of the country); `Niger` also matches the
3 `Nigeria` buildings. After S2 Make Web switches to exact match.

### 2-4. To do
Run S2 → recompute the architects' `primary_country` / `countries` → apply the same change to
the c27 artifact. Optional: an ISO `location_country_code` column; recovering the country of
the 1,936 non-publishable rows where it is NULL (`missing_country`).

---

## 3. Material groups (`material_visual` → new `material_group`)

`material_visual` is free text from image analysis: 15,561 distinct values, 12,983 (83%) used
by a single building, 19 empty arrays.

### 3-1. Same material, many names (publishable counts, top values)

| Group | Current values |
|---|---|
| **wood** | `wood` 8,544 · `timber` 2,625 · `oak` 344 · `bamboo` 274 · `plywood` 239 · `larch wood` 98 · `oak wood` 83 · `pine wood` 70 · `birch plywood` 70 |
| **metal** | `steel` 3,368 · `metal` 3,348 · `aluminum` 561 · `metal cladding` 404 · `iron` 308 · `stainless steel` 306 · `brass` 240 · `corten steel` 227 · `copper` 184 · `perforated metal` 161 · `aluminium` 150 |
| **concrete** | `concrete` 8,794 · `reinforced concrete` 398 · `exposed concrete` 279 |
| **stone** | `stone` 5,123 · `marble` 825 · `granite` 258 · `rock` 224 · `limestone` 216 · `natural stone` 163 · `sandstone` 96 |
| **brick** | `brick` 2,981 · `masonry` 1,491 · `terracotta` 269 · `historic masonry` 186 |
| **plaster** | `plaster` 3,608 · `white plaster` 230 · `stucco` 174 |
| **tile** | `tile` 840 · `ceramic tile` 223 · `terrazzo` 202 · `tiles` 199 · `ceramic` 167 |
| **earth** | `earth` 531 · `rammed earth` 125 |
| **glass** | `glass` 14,896 |
| **plastic** | `polycarbonate` 388 |

Example: of 8,544 `wood` buildings and 2,625 `timber` buildings, only 601 have both — a
search for "timber" misses ~7,900 wood buildings. Substring search adds false matches:
`tile` also hits `textiles` 76 · `textile` 65; `glass` hits `fiberglass` 30.

### 3-2. Request: new column `material_group`

Keep `material_visual` as is and add a controlled column:

```
material_group  TEXT[]  NOT NULL DEFAULT '{}'      -- e.g. {concrete,wood}
values (12): wood, metal, concrete, stone, brick, plaster, tile, earth, glass, fabric, plastic, other
```

**How the values are made (prepared by Make Web):**
- `docs/db-fixes/material_group_rules.py` — word-boundary rules mapping one free-text value to
  zero or more groups ("glass and steel" → glass + metal; "unspecified" → none). Word
  boundaries avoid substring errors: textile ≠ tile, fiberglass → plastic, "urban fabric" /
  "historic fabric" (building fabric) → not a material.
- `docs/db-fixes/material_group_map.csv` — the rules applied to all 16,409 distinct values in
  prod (all rows, not only publishable): 6,540 (value, group) rows. S3 loads this file.

**Result on prod data:**
- Publishable buildings with at least one group: **30,475 (83%)**.
- Per group: glass 15,826 · wood 13,927 · concrete 10,939 · metal 10,801 · stone 7,993 ·
  brick 5,445 · plaster 4,839 · tile 2,804 · fabric 1,562 · plastic 1,145 · earth 1,057 · other 759.
- The wood group finds 13,927 buildings vs 8,544 for the literal `'wood'`.
- The other 6,198 (17%) list no real material (`unspecified` 2,601, `painted surfaces`,
  `historic fabric`, …). Filling them needs LLM extraction from `visual_description` — out of
  scope here, your call.

**Classification choices:** `masonry` → brick, but `stone masonry` → stone; `terracotta` →
brick (`terracotta tile` → brick + tile); `polycarbonate`, `acrylic`, `fiberglass` → plastic;
`cork`, `paper`, `thatch`, `straw`, `leather`, `asphalt`, `composite` → other; `mortar`,
`membrane`, `paving` → no group (too ambiguous).

**Ownership:** the 12 groups are a new controlled vocabulary, so the final list is your
decision (make_db `core/vocab.py` rule). After S3, the rules belong in make_db — copy
`material_group_rules.py` into the pipeline (or reimplement it) and treat that copy as the
source of truth; Make Web's copy is then only a reference.

**To do:** confirm the 12 groups → add the column to the loader (§8) → run S3 → add the field
to the c27 artifact → classify future crawl values with `classify()`. Once live, Make Web
replaces substring search with `'wood' = ANY(material_group)`.

---

## 4. Program (`program`) and typology (`typology_primary`)

`program` has 14 values; `typology_primary` 35 (2,670 NULL). Of 34,003 buildings with a
typology, 2,290 (6.7%) carry a program different from the majority for their typology.
Most are defensible double memberships:

| Typology | Program distribution |
|---|---|
| Library | `Public` 251 · `Education` 135 · `Museum` 5 |
| Pavilion | `Public` 471 · `Landscape` 118 · `Other` 83 · `Museum` 27 · 10 others |
| Winery | `Hospitality` 103 · `Other` 46 · `Mixed Use` 6 |

→ A user asking for "public buildings" misses the 135 `Education` libraries; "education"
misses the 251 `Public` libraries.

`program = 'Other'` (2,365) breaks down as: `Retail` 792 · no typology 1,146 · `Industrial`
96 · `Pavilion` 83 · `Winery` 46 · `Warehouse` 40 · `Shopping Centre` 34 · `Gallery` 33 ·
`Office` 31 · `House` 26.

**Requests (vocabulary decisions):**
1. **Define a typology → allowed-program table** (e.g. Library → Public, Education; Winery →
   Hospitality; Gallery, Museum → Museum; Pavilion → Public, Landscape, Museum). Keep it as
   one reference table rather than per-row data. This looks like widening your
   `TYP_PROGRAM_OK` map.
2. **Add `Retail` to the program vocabulary.** It gives 792 retail + 34 shopping-centre
   buildings a proper program.
3. Optional: review the few remaining odd pairs — `House + Landscape` 42 · `House + Other` 26 ·
   `House + Hospitality` 20.

Make Web already merges the two columns into one "use" tag (specific words match typology,
broad words match program) and will widen broad matches with the relation table once it exists.

---

## 5. Architectural elements (`architectural_elements`)

66% (24,298) of publishable buildings have an empty array. It depends on the source site:

| `identity_source` | Buildings | With element tags |
|---|---|---|
| divisare | 29,221 | 40% |
| architizer | 7,441 | 10% |
| archello | 11 | 0% |

`visual_description` (present on every building) mentions far more:

| Element | Tag present | Mentioned in description | Both |
|---|---|---|---|
| Courtyard | 1,365 | 3,745 | 956 |
| Atrium | 429 | 721 | 200 |
| Garden | 1,302 | 5,028 | 979 |
| Terrace | 978 | 3,671 | 832 |

**Request:** re-extract element tags for every building from `visual_description`, using the
existing vocabulary, tagging only elements the text says exist (skip "no courtyard"), and
store the union with the current source tags. Until then Make Web matches "tag OR
description mention".

---

## 6. Build status (`year_kind`)

`year_kind` is `completed` 36,301 · `future` 250 · `unknown` 122, and `future` only means
"year after this year". Past-year competition entries, proposals and unbuilt projects are
all `completed`. 42 `completed` buildings have competition / proposal / concept / render in
the name alone; descriptions add more (hard to count precisely — "design concept" is common
wording).

**Request:**
1. Collect the project status from the source page (Built / Unbuilt / Competition / Under
   construction) into a new column, e.g. `build_status` ∈ `built`, `unbuilt`,
   `under_construction`, `unknown`.
2. For sources without a status, infer from name / description cues and record the basis
   separately.
3. Tell Make Web the column name and values; its "built only" filter will switch to it.

---

## 7. Feedback reports (`user_data`) — what the owner needs to know

Make Web added a report feature to the Taste-start cards (branch `feature/algo-feedback`,
PR #437). Users report a wrong card or a misrecognized query; the reports are the input for
future building-data fixes.

**Migration (owner applies):** a new Django app `feedback` with two tables in `user_data`.
The PR contains only the migration file; apply it with `make migrate-prod` right after the
PR is deployed (`make migrate-local` on dev). Until it is applied, the report API fails to save.
`archi_data` gets no schema change.

| Table | One row per | Holds |
|---|---|---|
| `feedback_card_report` | (user, session, building) | `canonical_bld_id`, card rank, matched-tag count, reason (`tag` / `photo` / `info` / `etc`) + sub-reasons, per-tag direction (wrongly present / wrongly absent) and where it matched (which column or the description), a snapshot of the building's values at report time |
| `feedback_query_report` | (user, session) | the wrongly recognized tags (axis + values) |

Common fields: user (nulled on account deletion), session id, query text, recognized tags
with JEV confidence, recognizer (`jev` / `dictionary`), free text (≤ 500 chars), language
(`ko` / `en`), status, created / updated time. "Where it matched" and the value snapshot are
computed by the server from `archi_data` at report time.

**Status values** (not shown to users):

| Value | Set by | Meaning |
|---|---|---|
| `unreviewed` | default | not reviewed yet |
| `fixed` | admin | reviewed; building DB or code fixed |
| `not_fixed` | admin | reviewed; data was correct |
| `user_canceled` | user | user withdrew the report (row kept; a new report revives it as `unreviewed`) |

**Review workflow:** there is no admin UI. Query the tables by SQL, fix the building values in
`canonical_v2_buildings` the same way as items 1–3 (Make Web keeps no correction table), and
set the status. Tag matching reads `archi_data` live, so fixes apply immediately; card display
data is cached up to 1 hour (`card_cache_ttl` 3600 s).

---

## 8. Run order and follow-up work

Each script in Appendix A runs **① preview (no writes) → ② one transaction → check the
remaining target count is 0, then COMMIT (otherwise ROLLBACK) → ③ verify**. Expected counts
are from 2026-10-16; if a preview differs a lot, stop and tell Make Web.

### 8-1. Before starting
- Back up prod: branch copy of `production` in Neon (or confirm the point-in-time restore window).
- Connect as the writer (`neondb_owner`). S1 and S2 run in any SQL client; S3 loads a CSV with
  psql `\copy` (any other loading method works).

### 8-2. Per script

| Script | Expected change | Recompute | Loader / artifact | Pipeline |
|---|---|---|---|---|
| **S1** Archello URLs (§1) | 7,714 rows | nothing (URLs only) | same rewrite in the c27 artifact, five columns | store future Archello URLs with the same rule |
| **S2** Country (§2) | 186 + 13 rows | architects `primary_country`, `countries` → `canonical_v2_architects_neon_loader.py` (no tag axis uses country) | same change in the c27 artifact (`location_country`, `location_city`) | — |
| **S3** Material groups (§3) | all 39,478 rows (new column) | optional: a `material_group` tag axis → `canonical_v2_tag_stats_build.py` axis list + `axis` CHECK | **add `material_group` to `canonical_v2_neon_loader.py`** (`ADD COLUMN IF NOT EXISTS` block, `COLUMNS`, `UPSERT_SQL`) **before** running S3; add the field to the c27 artifact | classify new values with `material_group_rules.classify()`; add the column to vNext `PROJECTION_SPEC.md` |

Without the loader change in S3, newly loaded buildings get an empty `material_group` and a
table rebuild drops the column. Adding it to the loader first also keeps handoff §8-6
(no ad-hoc public columns).

### 8-3. After all scripts
1. Confirm the Architizer URL rewrite applied to prod on 2026-10-16 is also in the c27 artifact.
2. Refresh the schema snapshot (`tools/neon_schema_snapshot.py`) and add a `docs/schema/CHANGELOG.md` entry (row counts, new column).
3. Update `HANDOFF_ARCHIBE_DB.md` §5 (add `material_group`) and §7 (C7 Architizer caveat).
4. Reset the `dev-ksangjo` branch from prod and send the new dev credentials.
5. Tell Make Web it is done — Make Web then removes its temporary mappings and switches to exact matching.

---

## 9. Priority

1. **Archello image URLs** (§1, S1) — Archello galleries are empty.
2. **Material groups** (§3, S3) — largest effect on recommendation quality (wood/timber, steel/metal).
3. **Country** (§2, S2) — few rows, but e.g. half of Turkey is missed.
4. **Program relation table + `Retail`** (§4) — vocabulary decision.
5. **Element tags from descriptions** (§5).
6. **Build-status column** (§6).
7. Optional: country-code column.
8. **Feedback migration** (§7) — whenever PR #437 is deployed.

If any column name or format changes, tell Make Web; it will update `docs/database-schema.md`
and its search code.

---

## Appendix A: scripts (owner runs)

### S1. Archello image URLs (§1)

```sql
CREATE OR REPLACE FUNCTION pg_temp.fix_archello(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT regexp_replace(t,
    'https://archello\.com/thumbs/([^?"]*)(\?[^"]*)?',
    'https://archello.s3.eu-central-1.amazonaws.com/\1', 'g')
$$;

-- ① preview (expect 7,714)
SELECT count(*) AS rows_to_change FROM canonical_v2_buildings
WHERE concat_ws(' ', display_cover_url, cover_image_url_default, covers_by_type::text,
                all_images::text, best_image_per_cluster::text) ~ 'archello\.com/thumbs/';

-- ② write
BEGIN;
UPDATE canonical_v2_buildings
SET display_cover_url       = pg_temp.fix_archello(display_cover_url),
    cover_image_url_default = pg_temp.fix_archello(cover_image_url_default),
    covers_by_type          = pg_temp.fix_archello(covers_by_type::text)::jsonb,
    all_images              = pg_temp.fix_archello(all_images::text)::jsonb,
    best_image_per_cluster  = pg_temp.fix_archello(best_image_per_cluster::text)::jsonb
WHERE concat_ws(' ', display_cover_url, cover_image_url_default, covers_by_type::text,
                all_images::text, best_image_per_cluster::text) ~ 'archello\.com/thumbs/';
-- expect: UPDATE 7714

-- must be 0 before COMMIT; otherwise ROLLBACK
SELECT count(*) AS still_old FROM canonical_v2_buildings
WHERE concat_ws(' ', display_cover_url, cover_image_url_default, covers_by_type::text,
                all_images::text, best_image_per_cluster::text) ~ 'archello\.com/thumbs/';
COMMIT;

-- ③ verify: no archello.com host left
SELECT split_part(i->>'url', '/', 3) AS host, count(*)
FROM canonical_v2_buildings, jsonb_array_elements(all_images) i
WHERE is_publishable GROUP BY 1 ORDER BY 2 DESC;
```

### S2. Country normalization + per-row fixes (§2)

```sql
-- spellings
CREATE TEMP TABLE country_fix (old_value TEXT PRIMARY KEY, new_value TEXT NOT NULL);
INSERT INTO country_fix VALUES
  ('Türkiye',                                'Turkey'),
  ('Iran, Islamic Republic of',              'Iran'),
  ('Dubai - United Arab Emirates',           'United Arab Emirates'),
  ('Dubai - UAE',                            'United Arab Emirates'),
  ('Abu Dhabi - United Arab Emirates',       'United Arab Emirates'),
  ('Riyadh Saudi Arabia',                    'Saudi Arabia'),
  ('AlUla Saudi Arabia',                     'Saudi Arabia'),
  ('España',                                 'Spain'),
  ('The Bahamas',                            'Bahamas'),
  ('Lao People''s Democratic Republic',      'Laos'),
  ('Myanmar (Burma)',                        'Myanmar'),
  ('France -',                               'France'),
  ('Singapore 299583',                       'Singapore'),
  ('Palestine, State of',                    'Palestine'),
  ('Congo, The Democratic Republic of the',  'DR Congo');

-- per-row fixes; expect_country guards against a changed release
CREATE TEMP TABLE country_row_fix (
  canonical_bld_id TEXT PRIMARY KEY, expect_country TEXT NOT NULL,
  new_country TEXT NOT NULL, new_city TEXT);            -- new_city NULL = keep city
INSERT INTO country_row_fix VALUES
  ('bld_038101', 'Tokyo',                                   'Japan',       NULL),
  ('bld_034408', '1 Chome−3−15 関電不動産西本町ビル',         'Japan',       'Osaka'),
  ('bld_039193', 'Chongqing',                               'China',       'Chongqing'),
  ('bld_035203', 'SHUNDE',                                  'China',       NULL),
  ('bld_034561', 'Tabriz',                                  'Iran',        NULL),
  ('bld_031431', 'Prishtinë',                               'Kosovo',      NULL),
  ('bld_032625', 'Pristina',                                'Kosovo',      'Pristina'),
  ('bld_002452', '- Nis',                                   'Serbia',      'Niš'),
  ('bld_033448', '02000',                                   'Ukraine',     'Kyiv'),
  ('bld_034611', '61000',                                   'Ukraine',     'Kharkiv'),
  ('bld_000315', 'Korea, Democratic People''s Republic of', 'South Korea', NULL),
  ('bld_000404', 'Korea, Democratic People''s Republic of', 'South Korea', NULL),
  ('bld_032913', '전주 완산구 중화산1동 164-17',              'South Korea', 'Jeonju');

-- ① preview (expect spellings total 186 rows; all 13 per-row ok = true)
SELECT f.old_value, f.new_value, count(b.*) AS rows
FROM country_fix f LEFT JOIN canonical_v2_buildings b ON b.location_country = f.old_value
GROUP BY 1, 2 ORDER BY 3 DESC;
SELECT f.canonical_bld_id, b.name, b.location_country, b.location_city,
       b.location_country = f.expect_country AS ok
FROM country_row_fix f LEFT JOIN canonical_v2_buildings b USING (canonical_bld_id);

-- ② write
BEGIN;
UPDATE canonical_v2_buildings b SET location_country = f.new_value
FROM country_fix f WHERE b.location_country = f.old_value;
-- expect: UPDATE 186

UPDATE canonical_v2_buildings b
SET location_country = f.new_country,
    location_city    = coalesce(f.new_city, b.location_city)
FROM country_row_fix f
WHERE b.canonical_bld_id = f.canonical_bld_id AND b.location_country = f.expect_country;
-- expect: UPDATE 13

-- must return no rows before COMMIT; otherwise ROLLBACK
SELECT location_country, count(*) FROM canonical_v2_buildings
WHERE location_country IN (SELECT old_value FROM country_fix)
   OR location_country IN (SELECT expect_country FROM country_row_fix)
GROUP BY 1;
COMMIT;

-- ③ verify
SELECT location_country, count(*) FROM canonical_v2_buildings
WHERE is_publishable GROUP BY 1 ORDER BY 1;
```

### S3. Material group column (§3)

Input: `docs/db-fixes/material_group_map.csv` (`material_value, material_group`, 6,540 rows).
Add the column through the loader first (§8-2); the `ALTER TABLE` below is then a no-op.

**Step 0 — regenerate the map if `material_visual` changed since 2026-10-16** (otherwise new
values get no group). It reproduces the shipped CSV exactly when the data is unchanged:

```bash
psql "$DSN" -Atc "SELECT DISTINCT e FROM canonical_v2_buildings, unnest(material_visual) e" \
  | python docs/db-fixes/material_group_rules.py > docs/db-fixes/material_group_map.csv
```

```sql
ALTER TABLE canonical_v2_buildings
    ADD COLUMN IF NOT EXISTS material_group TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_canonical_v2_buildings_material_group
    ON canonical_v2_buildings USING GIN (material_group);

-- load the map (psql)
CREATE TEMP TABLE material_group_map (material_value TEXT, material_group TEXT);
\copy material_group_map FROM 'docs/db-fixes/material_group_map.csv' WITH (FORMAT csv, HEADER true)

-- ① preview (expect 6,540)
SELECT count(*) FROM material_group_map;

-- ② write
BEGIN;
UPDATE canonical_v2_buildings b
SET material_group = coalesce((
        SELECT array_agg(DISTINCT m.material_group ORDER BY m.material_group)
        FROM unnest(b.material_visual) v
        JOIN material_group_map m ON m.material_value = v), '{}');
-- expect: UPDATE 39478

-- expect (publishable): glass 15,826 · wood 13,927 · concrete 10,939 · metal 10,801 ·
-- stone 7,993 · brick 5,445 · plaster 4,839 · tile 2,804 · fabric 1,562 · plastic 1,145 ·
-- earth 1,057 · other 759 — ROLLBACK if far off
SELECT g, count(*) FROM canonical_v2_buildings, unnest(material_group) g
WHERE is_publishable GROUP BY 1 ORDER BY 2 DESC;
COMMIT;

-- ③ verify (expect 30,475 / 36,673)
SELECT count(*) FILTER (WHERE cardinality(material_group) > 0), count(*)
FROM canonical_v2_buildings WHERE is_publishable;
```

---

## Appendix B: measurement queries (read-only)

```sql
-- 1. rows still carrying Archello thumbs URLs
SELECT count(*), count(*) FILTER (WHERE is_publishable) FROM canonical_v2_buildings
WHERE concat_ws(' ', display_cover_url, cover_image_url_default, covers_by_type::text,
                all_images::text, best_image_per_cluster::text) ~ 'archello\.com/thumbs/';

-- 2. country values
SELECT location_country, count(*), count(*) FILTER (WHERE is_publishable)
FROM canonical_v2_buildings GROUP BY 1 ORDER BY 1;

-- 3. material: distinct / single-use values; wood-timber overlap
SELECT count(DISTINCT e) FROM canonical_v2_buildings, unnest(material_visual) e WHERE is_publishable;
SELECT count(*) FROM (SELECT e FROM canonical_v2_buildings, unnest(material_visual) e
  WHERE is_publishable GROUP BY 1 HAVING count(*) = 1) t;
SELECT count(*) FILTER (WHERE 'wood' = ANY(material_visual) AND 'timber' = ANY(material_visual)),
       count(*) FILTER (WHERE 'wood' = ANY(material_visual)),
       count(*) FILTER (WHERE 'timber' = ANY(material_visual))
FROM canonical_v2_buildings WHERE is_publishable;

-- 4. buildings whose program differs from their typology's majority program; 'Other' breakdown
WITH t AS (SELECT typology_primary ty, program pr, count(*) n FROM canonical_v2_buildings
           WHERE is_publishable AND typology_primary IS NOT NULL GROUP BY 1, 2),
     d AS (SELECT DISTINCT ON (ty) ty, pr FROM t ORDER BY ty, n DESC)
SELECT sum(t.n) FILTER (WHERE t.pr <> d.pr), sum(t.n) FROM t JOIN d USING (ty);
SELECT typology_primary, count(*) FROM canonical_v2_buildings
WHERE is_publishable AND program = 'Other' GROUP BY 1 ORDER BY 2 DESC;

-- 5. element tags by source; tag vs description mention
SELECT identity_source, count(*), count(*) FILTER (WHERE cardinality(architectural_elements) > 0)
FROM canonical_v2_buildings WHERE is_publishable GROUP BY 1;
SELECT count(*) FILTER (WHERE 'Courtyard' = ANY(architectural_elements)),
       count(*) FILTER (WHERE visual_description ILIKE '%courtyard%'),
       count(*) FILTER (WHERE 'Courtyard' = ANY(architectural_elements) AND visual_description ILIKE '%courtyard%')
FROM canonical_v2_buildings WHERE is_publishable;

-- 6. year_kind; completed buildings with unbuilt cues in the name
SELECT year_kind, count(*) FROM canonical_v2_buildings WHERE is_publishable GROUP BY 1;
SELECT count(*) FROM canonical_v2_buildings
WHERE is_publishable AND year_kind = 'completed' AND name ~* '(competition|proposal|concept|render)';
```
