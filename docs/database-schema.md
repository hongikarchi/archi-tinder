# Database Schema: `architecture_vectors`

Owned by **Make DB** (reference-crawling repo). Django reads via raw SQL only —
**never ORM, never migrate**.

<!-- Last synced 2026-04-29 with Make DB v2 + Divisare migration. -->

## Hard rules
- All building references must use `building_id` — never `name`, `slug`, or
  any language-dependent field.
- Do NOT create or migrate the `architecture_vectors` table — it is owned by
  Make DB and managed there.
- SentenceTransformers is NOT a runtime dependency in Make Web — embeddings
  are pre-computed by Make DB and read via raw SQL.

## Table definition

```sql
CREATE TABLE architecture_vectors (
    building_id      TEXT PRIMARY KEY,   -- e.g. 'B00042', stable canonical key
    slug             TEXT UNIQUE NOT NULL,
    name_en          TEXT NOT NULL,
    project_name     TEXT NOT NULL,
    architect        TEXT,
    location_country TEXT,
    city             TEXT,
    year             INTEGER,
    area_sqm         NUMERIC,
    program          TEXT NOT NULL,      -- see normalized vocabulary below
    style            TEXT,               -- e.g. Brutalist, Classical, Contemporary
    atmosphere       TEXT NOT NULL,      -- free-form e.g. "fluid, sweeping, atmospheric"
    color_tone       TEXT,               -- e.g. Colorful, Cool White, Dark, Earthy
    material         TEXT,               -- nullable (977 rows NULL)
    material_visual  TEXT[] NOT NULL,    -- array of visual material descriptors
    visual_description TEXT NOT NULL,    -- rich text description
    description      TEXT,
    url              TEXT,
    tags             TEXT[],
    source_slugs     TEXT[],
    image_photos     TEXT[],             -- all photo filenames
    image_drawings   TEXT[],             -- all drawing filenames
    embedding        VECTOR(384) NOT NULL,

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
);
```

## Normalized `program` Values

Used in filters and Gemini persona reports. Must use exactly these values —
no raw strings.

`Housing` | `Office` | `Museum` | `Education` | `Religion` | `Sports` |
`Transport` | `Hospitality` | `Healthcare` | `Public` | `Mixed Use` |
`Landscape` | `Infrastructure` | `Other`
