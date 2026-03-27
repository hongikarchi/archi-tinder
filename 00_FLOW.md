# ArchiTinder — Master Project Flow

> Read this first. It connects the two sub-projects and defines the shared database contract.

---

## 1. What Is This Project?

**ArchiTinder** is a web application for architects and architecture students to discover and curate building references through Tinder-style swiping. Users create projects, swipe through buildings (right = like, left = skip), and receive an AI-generated persona report based on their taste.

### The Two Sub-Projects

| # | Name | Repo | What It Does |
|---|------|------|--------------|
| 1 | **Make DB** | [reference-crawling](https://github.com/hongikarchi/reference-crawling.git) | 3-stage pipeline: crawl → ML enrich+embed → load PostgreSQL |
| 2 | **Make Web Service** | `archithon-tinder` (this repo) | Frontend (React) + Backend (Django) reading from PostgreSQL |

These are **independent repos**. Make DB fully builds the database. Make Web Service only reads from it.

### Reference Repos (Dirty Code — Do Not Copy Directly)

| Repo | URL | Notes |
|------|-----|-------|
| Old Frontend | https://github.com/yywon1/archithon-app | Logic is correct, code is messy |
| Old Backend | https://github.com/dain75954929-wq/ARCHITON/ | Algorithm is correct, structure is messy |
| Crawler | https://github.com/hongikarchi/reference-crawling.git | Mostly clean, needs Stage 2 + 3 added |

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  PROJECT 1: Make DB  (reference-crawling repo)                   │
│                                                                  │
│  Stage 1: CRAWL                                                  │
│  metalocus.es ──► scraper ──► SQLite + images/                   │
│       │                                                          │
│       ▼  buildings_raw.json                                      │
│  Stage 2: ML (Deduplicate + Enrich + Embed)                      │
│  buildings_raw.json                                              │
│    ──► 2a preliminary embed → fuzzy+cosine deduplication+merge   │
│    ──► 2b assign stable building_id → id_registry.json           │
│    ──► 2c Claude Code session: fill nulls (mood, material, name_en)  │
│    ──► 2d SentenceTransformers: generate 384-dim final embeddings│
│       │                                                          │
│       ▼  buildings_processed.json  (complete, self-contained)    │
│  Stage 3: POSTGRESQL                                             │
│  buildings_processed.json ──► bulk INSERT ──► architecture_vectors│
│                                                                  │
└──────────────────────────────┬───────────────────────────────────┘
                               │  PostgreSQL connection only
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  PROJECT 2: Make Web Service  (archithon-tinder repo)            │
│                                                                  │
│  Backend (Django 6 + DRF)                                        │
│    ──► reads architecture_vectors via pgvector queries           │
│    ──► epsilon-greedy recommendation engine                      │
│    ──► Gemini: persona reports + query parsing                   │
│    ──► REST API → Frontend                                       │
│                                                                  │
│  Frontend (React 18 + Vite)                                      │
│    ──► swipe UI, project management, favorites & reports         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Full Data Flow (Step by Step)

```
Stage 1 — CRAWL
  metalocus.es → scraper → SQLite (metalocus.db) + images/
  └─► stage1_crawl.py exports: buildings_raw.json

Stage 2 — ML (Deduplicate + Enrich + Embed)
  buildings_raw.json
  └─► 2a: preliminary embed (throwaway) → fuzzy+cosine deduplication → merge records
  └─► 2b: assign stable building_id (B00001…) per unique building → id_registry.json
  └─► 2c: Claude Code session fills nulls (mood, material, program, name_en)
  └─► 2d: final 384-dim embedding per building (uses enriched name_en)
  └─► outputs: buildings_processed.json  ← complete, self-contained

Stage 3 — POSTGRESQL
  buildings_processed.json
  └─► stage3_postgres.py reads embeddings as-is (no ML needed)
  └─► bulk INSERT into architecture_vectors table
  └─► PostgreSQL is now fully populated ← Make DB is done

Stage 4 — WEB SERVICE
  Django backend connects to PostgreSQL
  └─► serves buildings via REST API
  └─► runs recommendation engine (pgvector similarity queries)
  └─► generates persona reports via Gemini
  React frontend connects to Django
  └─► user swipes → feedback → preference vector update → report
```

---

## 3. Document Map

| File | Scope | When to Use |
|------|-------|-------------|
| `00_FLOW.md` | **This file** — master flow + shared DB contract | Start here. Always read before working on either sub-project. |
| `01_MAKE_DB.md` | Stage 1–3: Crawl, ML, PostgreSQL | When working on `reference-crawling` |
| `02_MAKE_WEB.md` | Stage 4: Frontend + Backend web service | When working on React frontend or Django backend |

---

## 4. Shared Database Contract

**This is the single source of truth for data format between the two projects.**

If any schema here changes, update both `01_MAKE_DB.md` and `02_MAKE_WEB.md` to match.

---

### 4.1 `buildings_raw.json` — Stage 1 Output (Crawl)

Produced by Stage 1. Raw scraped data — fields may be null or inconsistently formatted.

```json
[
  {
    "slug": "string (required, unique) — from article URL slug",
    "project_name": "string (required)",
    "architect": "string | null",
    "location_country": "string | null",
    "city": "string | null",
    "year": "integer | null",
    "area_sqm": "number | null",
    "building_type": "string | null — raw, un-normalized (e.g. 'museums', 'Museum', 'museum')",
    "mood": "string | null — often null, filled in Stage 2",
    "material": "string | null — often null, filled in Stage 2",
    "description": "string | null",
    "url": "string | null — source URL on metalocus.es",
    "images": [
      {
        "filename": "string (required)",
        "alt_text": "string | null",
        "order": "integer — 0 = cover"
      }
    ],
    "tags": ["string"]
  }
]
```

---

### 4.2 `buildings_processed.json` — Stage 2 Output (ML)

Produced by Stage 2. Deduplicated, enriched, and embedded.
This is the **handoff file** from Make DB to Stage 3 (PostgreSQL loader).

```json
[
  {
    "building_id": "string (required, stable) — e.g. 'B00042', canonical identifier",
    "slug": "string (required, unique) — URL-safe, from winning source article slug",
    "name_en": "string (required) — canonical English name",
    "project_name": "string (required) — display name (may be non-English)",
    "source_slugs": ["string"],
    "architect": "string | null",
    "location_country": "string | null",
    "city": "string | null",
    "year": "integer | null",
    "area_sqm": "number | null",
    "program": "string — normalized, from vocabulary in Section 4.5",
    "mood": "string — enriched by Claude if was null",
    "material": "string — enriched by Claude if was null",
    "description": "string | null",
    "url": "string | null",
    "images": [
      {
        "filename": "string (required)",
        "alt_text": "string | null",
        "order": "integer — 0 = cover"
      }
    ],
    "tags": ["string"],
    "embedding": [0.023, -0.142, 0.881, "..."]
  }
]
```

**Rules:**
- `building_id` is the **only** safe cross-reference key. Never link buildings by name — names vary by language and source.
- `building_id` is stable across re-crawls. Assigned once, persisted in `data/id_registry.json`.
- `name_en` is the canonical English name, normalized by Claude during enrichment.
- `source_slugs` lists all raw slugs that were merged into this record (all of them, not just the winner's slug — useful for debugging and id_registry lookups).
- `embedding` is a JSON array of 384 floats. Always present — Stage 3 will not compute it.
- `program` must use exactly the vocabulary in Section 4.5. No nulls allowed after Stage 2.
- `mood` and `material` must be non-null after Stage 2.
- `images[0]` (order=0) is the cover image. Building is skipped if no cover image exists.

---

### 4.3 Image Directory Structure

Downloaded by Stage 1 (organized by slug). After Stage 2 deduplication, images are re-organized by `building_id`.

**Stage 1 layout** (by slug, temporary):
```
images/
└── {slug}/
    ├── 0_main.jpg
    └── 1_gallery.jpg
```

**Stage 2 layout** (by building_id, final):
```
images/
└── {building_id}/        ← e.g. B00042/
    ├── 0_main.jpg        # Cover image (order=0) — required
    ├── 1_gallery.jpg
    └── ...
```

**Rules:**
- Final directory name = `building_id` (not slug — slug can vary across sources)
- Filename = `{order}_{original_filename}`
- Format: JPG preferred, PNG accepted
- Minimum cover image: 600 × 800 px (portrait orientation)
- When merging duplicates, union all images and re-index order starting from 0

---

### 4.4 PostgreSQL `architecture_vectors` Table — Stage 3 Output

Populated by Stage 3 (bulk INSERT from `buildings_processed.json`).
Read by Make Web Service via pgvector queries.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE architecture_vectors (
    building_id      TEXT PRIMARY KEY,           -- e.g. 'B00042', stable across re-crawls
    slug             TEXT UNIQUE NOT NULL,        -- URL-safe display identifier
    name_en          TEXT NOT NULL,               -- canonical English name
    project_name     TEXT NOT NULL,               -- display name (may be non-English)
    architect        TEXT,
    location_country TEXT,
    city             TEXT,
    year             INTEGER,
    area_sqm         NUMERIC,
    program          TEXT NOT NULL,               -- normalized, never null
    mood             TEXT NOT NULL,               -- enriched, never null
    material         TEXT NOT NULL,               -- enriched, never null
    description      TEXT,
    url              TEXT,
    tags             TEXT[],
    source_slugs     TEXT[],                      -- all slugs merged into this record (from Stage 2)
    image_cover      TEXT,                        -- cover image filename under images/{building_id}/
    embedding        VECTOR(384) NOT NULL         -- pre-computed by Stage 2
);

-- Scalar indexes: create immediately
CREATE INDEX ON architecture_vectors (program);
CREATE INDEX ON architecture_vectors (location_country);
CREATE INDEX ON architecture_vectors (year);

-- Vector index: create AFTER bulk INSERT (ivfflat requires data to build lists)
-- For datasets < 300 rows use hnsw instead (works on empty tables):
--   CREATE INDEX ON architecture_vectors USING hnsw (embedding vector_cosine_ops);
-- For full dataset (300+ rows):
--   CREATE INDEX ON architecture_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Key:** `building_id` is the primary key. `slug` is secondary (for URLs). Never join or reference buildings by `name_en` or `project_name` — use `building_id` only.

**Stage 3 only does INSERT/UPSERT — no embedding computation happens here.**
**Stage 3 creates the vector index AFTER the bulk INSERT (ivfflat requires data; use hnsw for < 300 rows).**

---

### 4.5 Normalized `program` Values

Stage 2 (ML) maps all raw `building_type` strings to this exact vocabulary.
Make Web Service uses these values for filtering.

| Value | Raw Examples |
|-------|-------------|
| `Housing` | apartment, residential, house, villa, dwelling |
| `Office` | headquarters, workspace, coworking, corporate |
| `Museum` | gallery, exhibition, cultural center, art center |
| `Education` | school, university, library, campus |
| `Religion` | church, mosque, temple, chapel |
| `Sports` | stadium, arena, aquatic center, gymnasium |
| `Transport` | airport, train station, terminal, mobility hub |
| `Hospitality` | hotel, resort, restaurant, bar, café |
| `Healthcare` | hospital, clinic, medical center |
| `Public` | civic center, town hall, plaza, community center |
| `Mixed Use` | multi-program, mixed-use |
| `Landscape` | park, urban design, garden, masterplan |
| `Infrastructure` | bridge, tower, utility, pavilion |
| `Other` | anything that doesn't fit above |

---

## 5. Development Order

**Always work in this order. Stage 3 must complete before starting Make Web.**

```
Step 1 → reference-crawling repo: Stage 1 (Crawl)
         Clone repo, run crawler test, verify buildings_raw.json output

Step 2 → reference-crawling repo: Stage 2 (ML)
         Build stage2_ml.py — Gemini enrichment + SentenceTransformers embedding
         Verify buildings_processed.json schema matches Section 4.2

Step 3 → reference-crawling repo: Stage 3 (PostgreSQL)
         Build stage3_postgres.py — bulk INSERT buildings_processed.json
         Verify architecture_vectors table is populated

         ← Make DB is complete. PostgreSQL is ready. ─────────────────┐
                                                                       │
Step 4 → archithon-tinder repo: Phase 0 (Clean Frontend)              │
         Delete dead code, add .env, Tailwind-ify                      │
                                                                       │
Step 5 → archithon-tinder repo: Phase 1 (Backend Setup)               │
         Django project, models, auth/project endpoints                │
         Connect to existing PostgreSQL ◄──────────────────────────────┘

Step 6 → archithon-tinder repo: Phase 2 (Recommendation Engine)
         Epsilon-greedy + pgvector queries

Step 7 → archithon-tinder repo: Phase 3 (Gemini LLM)
         Query parsing + persona reports

Step 8 → archithon-tinder repo: Phase 4 (Integration)
         Wire frontend ↔ backend

Step 9 → archithon-tinder repo: Phase 5 (Testing & Polish)
```

---

## 6. Claude Code Session Guide

### Rules for Every Session

1. **Read the right doc first:**
   - Stage 1–3 work → *"Read 00_FLOW.md and 01_MAKE_DB.md"*
   - Stage 4 work → *"Read 00_FLOW.md and 02_MAKE_WEB.md"*

2. **One stage/phase per session** — don't mix stages or skip ahead.

3. **Use `/plan` before coding** — always let Claude Code propose before writing code.

4. **Commit after each stage/phase** — one commit per unit of work.

5. **Schema lives only here** — Sections 4.1–4.5 are the single source of truth. Never copy schema into other docs.

### Recommended Session Prompts

```
# Stage 1 — Crawl:
"Read 00_FLOW.md and 01_MAKE_DB.md. Run Stage 1 (crawl) and verify
 buildings_raw.json matches the schema in 00_FLOW.md Section 4.1."

# Stage 2 — ML (pre-enrich):
"Read 00_FLOW.md Sections 4.1, 4.2, 4.5 and 01_MAKE_DB.md Stage 2.
 Build stage2_ml.py --pre-enrich: dedup, assign IDs → buildings_to_enrich.json"

# Stage 2 — ML (Claude Code enrichment session):
"Read data/buildings_to_enrich.json. Fill null fields per 01_MAKE_DB.md
 Sub-step 2d. Write completed data to data/buildings_enriched.json."

# Stage 2 — ML (post-enrich):
"Run stage2_ml.py --post-enrich: validate programs, generate 384-dim
 embeddings → buildings_processed.json"

# Stage 3 — PostgreSQL:
"Read 00_FLOW.md Section 4.4 and 01_MAKE_DB.md Stage 3.
 Build stage3_postgres.py: bulk INSERT buildings_processed.json
 into architecture_vectors."

# Phase 1 — Backend setup:
"Read 00_FLOW.md Section 4.4 and 02_MAKE_WEB.md. PostgreSQL is
 already populated. Set up Django backend and connect to the DB."
```

---

*Last updated: 2026-03-27*
*Crawler ref: https://github.com/hongikarchi/reference-crawling.git*
*Old frontend ref: https://github.com/yywon1/archithon-app*
*Old backend ref: https://github.com/dain75954929-wq/ARCHITON/*
