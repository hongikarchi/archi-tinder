# Database Schema: `architecture_vectors`

Owned by **Make DB** (reference-crawling repo). Django reads via raw SQL only —
**never ORM, never migrate**.

**Status as of 2026-05-14:** Live Neon DB is at the **v1 baseline** (23 columns,
3,465 rows). The **v2 + Divisare migration** documented below is the agreed
*migration target* but has **not yet been pushed by Make DB owner (권상조)**.
Engine code (`backend/apps/recommendation/engine.py`) is already
forward-compatible: a column probe (`_get_available_columns()`) filters the
SELECT list against `information_schema`, so optional v2 columns are silently
dropped when absent and used when present. No code change needed when v2
arrives — only doc/test fixture refresh per push **S2** (replan
`.claude/plans/replan-2026-05-14-tab3-restructure.md`).

## Hard rules
- All building references must use `building_id` — never `name`, `slug`, or
  any language-dependent field.
- Do NOT create or migrate the `architecture_vectors` table — it is owned by
  Make DB and managed there.
- SentenceTransformers is NOT a runtime dependency in Make Web — embeddings
  are pre-computed by Make DB and read via raw SQL.

## Current live schema (v1 baseline — 23 columns)

This is what `\d architecture_vectors` returns against Neon production today.
Probed 2026-05-14 against 3,465 rows.

```sql
CREATE TABLE architecture_vectors (
    building_id       TEXT PRIMARY KEY,   -- e.g. 'B00042', stable canonical key
    slug              TEXT NOT NULL,
    name_en           TEXT NOT NULL,
    project_name      TEXT NOT NULL,
    architect         TEXT,
    location_country  TEXT,
    city              TEXT,
    year              INTEGER,
    area_sqm          NUMERIC,
    program           TEXT NOT NULL,      -- normalized vocabulary (see below)
    style             TEXT,               -- e.g. Brutalist, Classical, Contemporary
    atmosphere        TEXT,               -- free-form e.g. "fluid, sweeping, atmospheric"
    color_tone        TEXT,               -- e.g. Colorful, Cool White, Dark, Earthy
    material          TEXT,               -- nullable (~977 rows NULL)
    material_visual   TEXT[],             -- array of visual material descriptors
    description       TEXT,
    visual_description TEXT,              -- rich text description
    url               TEXT,
    tags              TEXT[],
    source_slugs      TEXT[],
    image_photos      TEXT[],             -- all photo filenames (R2 keys)
    image_drawings    TEXT[],             -- all drawing filenames (R2 keys)
    embedding         VECTOR(384) NOT NULL  -- pgvector
);
```

Notes vs the original v1 spec:
- `atmosphere`, `visual_description`, `material_visual` are **nullable in live
  DB** (the doc earlier marked them `NOT NULL` to match Make DB v2 intent). Code
  guards via `row.get(...) or ''/[]`.

## Migration target (Make DB v2 + Divisare — NOT YET DEPLOYED)

Make DB owner is preparing the migration that adds versioning + Divisare
provenance columns. When that PR lands and Neon is migrated, run push **S2**
to refresh this doc + test fixtures (engine code already absorbs it via the
probe).

```sql
-- Versioning (Make DB Phase 1)
vocab_version            TEXT DEFAULT 'v2',          -- vocab_version snapshot per row
prompt_version           TEXT,                       -- "{label}-{sha256(prompt)[:8]}"

-- Divisare integration (Make DB Phase 8B+ canonical migration)
divisare_id              INTEGER,                    -- canonical Divisare project ID
divisare_slug            TEXT,                       -- divisare URL slug
abstract                 TEXT,                       -- short Divisare abstract
architect_canonical_ids  INTEGER[],                  -- canonical architect cluster IDs (PROF1 join key)
divisare_tags            TEXT[],                     -- raw Divisare tag taxonomy
divisare_credits         JSONB,                      -- {"structures":[...], "lighting":[...], ...}
cover_image_url_divisare TEXT,                       -- single full external URL, hotlink target
divisare_gallery_urls    TEXT[],                     -- ~10-19 per project, full external URLs

-- Provenance metadata
provenance               JSONB                       -- {"name":"divisare","description":"metalocus", ...}
```

### Engine references to target cols (forward-compatible)

Two columns are already wired through the probe in `engine.py`:
- `cover_image_url_divisare` — used in `_row_to_card` cover fallback when
  `image_photos[0]` is empty (Divisare-only buildings).
- `divisare_gallery_urls` — appended to `gallery` between R2 photos and R2
  drawings (`gallery_drawing_start` calculation).

Both are absent from live DB → silently dropped from SELECT by
`_build_select_columns(required, optional=...)` → `row.get(...)` returns None →
defaults to `''`/`[]`. No 500s, no drift.

The other 10 target columns (`vocab_version`, `prompt_version`, `divisare_id`,
`divisare_slug`, `abstract`, `architect_canonical_ids`, `divisare_tags`,
`divisare_credits`, `provenance`) are **not yet referenced anywhere in Make Web
code** (verified via repo-wide grep 2026-05-14). They will be wired in push
**S2** once the migration lands.

## Normalized `program` Values

Used in filters and Gemini persona reports. Must use exactly these values —
no raw strings.

`Housing` | `Office` | `Museum` | `Education` | `Religion` | `Sports` |
`Transport` | `Hospitality` | `Healthcare` | `Public` | `Mixed Use` |
`Landscape` | `Infrastructure` | `Other`

<!-- Last reality-synced 2026-05-14 against live Neon (v1, 23 cols, 3465 rows). -->
<!-- Previous sync note (2026-04-29) claimed v2 + Divisare but DB still at v1. -->
