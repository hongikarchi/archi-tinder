# Database Schema: `canonical_v2_buildings`

Owned by **Make DB** (reference-crawling repo). Django reads via raw SQL only —
**never ORM, never migrate**.

**Status as of 2026-05-24:** Live Neon DB is at the **v2 canonical schema**
(31 columns, 39,776 rows, ~99.9% publishable). On 2026-05-24 the orphan
Make Web user/app tables that lingered on this DB (auth_*, accounts_*,
recommendation_*, profiles_*, social_*, token_blacklist_*, django_*) were
dropped along with the legacy v1 `architecture_vectors` table; only
`canonical_v2_buildings` remains on the `buildings` alias.

## Hard rules

- All building references must use `canonical_bld_id` (TEXT PK like
  `'bld_000344'`) — never `name`, `slug`, or any language-dependent field.
- Do NOT create or migrate the `canonical_v2_buildings` table — it is owned
  by Make DB and managed there.
- Every Make Web building query MUST gate on `is_publishable = true`
  (39 of 39,776 rows are flagged non-publishable for image/metadata gaps).
  `engine._build_filter_sql` always emits at least this clause; custom
  raw SQL must add it explicitly.
- SentenceTransformers is NOT a runtime dependency in Make Web — embeddings
  are pre-computed by Make DB and read via raw SQL (`embedding VECTOR(384)`).
- Image URLs are **full source-CDN URLs** stored in the row (Divisare,
  Metalocus, Archello, etc.). R2 composition (`IMAGE_BASE_URL + key`) is
  retired; do not reintroduce it.

## Table definition

```sql
CREATE TABLE canonical_v2_buildings (
    -- Identity
    canonical_bld_id          TEXT PRIMARY KEY,    -- e.g. 'bld_000344'
    name                      TEXT NOT NULL,
    names_alts                TEXT[] NOT NULL,     -- alt project names

    -- Location / time
    location_city             TEXT,
    location_country          TEXT,
    project_year              INTEGER,

    -- Architect linkage (PROF1 join key)
    architect_canonical_ids   TEXT[] NOT NULL,     -- canonical architect cluster IDs
    architect_names           TEXT[] NOT NULL,
    architects_text           TEXT,                -- pre-joined display string

    -- Typology axes (gated by Make DB vocab)
    program                   TEXT NOT NULL,       -- 14-enum (see below)
    style                     TEXT NOT NULL,
    color_tone                TEXT NOT NULL,
    atmosphere                TEXT NOT NULL,
    material_visual           TEXT[] NOT NULL,
    visual_description        TEXT NOT NULL,

    -- Images (canonical v2 model)
    image_derived             JSONB NOT NULL,      -- {style, color_tone, material_visual, visual_description} -- derived snapshot slot
    covers_by_type            JSONB NOT NULL,      -- {exterior, interior, drawing, aerial, detail} -> URL|null
    all_images                JSONB NOT NULL,      -- list of {url, kind(cover|gallery|drawing), type, image_order, rank, phash, phash_cluster_id, source, source_id, ...}
    best_image_per_cluster    JSONB NOT NULL,      -- {phash_cluster_id: image_obj} -- best-of-cluster after phash dedupe
    cover_image_url_default   TEXT,                -- canonical default cover (Make DB pick)
    display_cover_url         TEXT,                -- frontend-displayed cover (Make DB pick, may equal default)

    -- Source provenance
    source_refs               JSONB NOT NULL,      -- {"divisare": ["17580", ...], ...}
    source_urls               JSONB NOT NULL,      -- {"divisare": ["https://...", ...], ...}
    identity_source           TEXT,                -- which source produced canonical identity

    -- Quality + publishability
    confidence_tier           TEXT NOT NULL,       -- 'T1' | 'T2' | 'T3'
    n_sources                 INTEGER NOT NULL,
    is_publishable            BOOLEAN NOT NULL,    -- Make Web MUST filter on this
    publishability_reasons    TEXT[] NOT NULL,     -- e.g. ['missing_all_images']
    needs_image_derived_backfill BOOLEAN NOT NULL,

    -- Embeddings
    embedding                 VECTOR(384) NOT NULL,  -- paraphrase-multilingual-MiniLM-L12-v2

    updated_at                TIMESTAMPTZ NOT NULL
);
```

## Image resolution semantics

The frontend renders one cover image per card. `_row_to_card()` resolves the
cover with this fallback chain (highest preference first):

1. `covers_by_type[image_focus]` — when `image_focus` is set on the request
   and the variant is non-null. `image_focus ∈ {exterior, interior, drawing,
   aerial, detail}`. Set by the LLM intake (`parse_query`) when the user
   signals a preferred view ("외관/실내/도면/조감/디테일").
2. `display_cover_url` — Make DB's preferred display cover.
3. `cover_image_url_default` — Make DB's canonical default.
4. `covers_by_type.exterior` — last covers_by_type try.
5. `all_images[0].url` — first item in the deduped/sorted gallery.
6. `''` (empty string) — when the building has no images at all; the
   frontend then renders a placeholder.

Gallery is built from `all_images` sorted by `(kind: cover→gallery→drawing,
image_order, rank)` with the chosen cover URL removed.
`gallery_drawing_start` is the index of the first `kind=='drawing'` item;
items at index ≥ `gallery_drawing_start` are rendered with `object-fit: contain`
on white background (drawings, not photos).

## Normalized `program` Values

Used in filters and Gemini persona reports. Must use exactly these values —
no raw strings.

`Housing` | `Office` | `Museum` | `Education` | `Religion` | `Sports` |
`Transport` | `Hospitality` | `Healthcare` | `Public` | `Mixed Use` |
`Landscape` | `Infrastructure` | `Other`

## Legacy v1 schema (removed 2026-05-24)

The previous `architecture_vectors` table (23 columns, PK `building_id` like
`'B00042'`) was dropped on 2026-05-24. The v2 cutover had already moved every
runtime code path to `canonical_v2_buildings` (PK `canonical_bld_id` like
`'bld_xxxxxx'`); only ops tools and one test gate still referenced v1, and
they were deleted in the same cleanup.

Historical SwipeEvent / Project rows that contained v1 IDs were left in place
as orphans during the S2 cutover; the buildings-side row drop on 2026-05-24
does not affect them (they live on `user_data`).

<!-- Last reality-synced 2026-05-24 against live Neon (v2, 31 cols, 39,776 rows). -->
<!-- Engine code cutover: feature/admin-s2-new-schema. -->
<!-- v1 + orphan-user-table drop: feature/admin-drop-v1-legacy. -->
