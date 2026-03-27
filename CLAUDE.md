# Make Web Service — Claude Code Instructions

  ## What This Repo Does
  React frontend + Django backend that reads from a PostgreSQL DB built by Make DB.
  Full spec is in `02_MAKE_WEB.md`. Shared DB schema is in `00_FLOW.md`.

  ## Rules
  - Read `00_FLOW.md` and `02_MAKE_WEB.md` before writing any code.
  - One phase per session. Do not mix phases.
  - Use `/plan` before coding each phase.
  - All building references must use `building_id` — never name, slug, or language-dependent field.
  - Do NOT create or migrate the `architecture_vectors` table — it is owned by Make DB.
  - SentenceTransformers is NOT a dependency here — embeddings are pre-computed.

  ## Target Structure
  frontend/   ← React 18 + Vite + Tailwind
  backend/    ← Django 6 + DRF + pgvector + Gemini + social auth

  ## Current State
  - frontend/: BUILT — Phase 0 complete; rich inline-style UI adapted from reference app
  - backend/: MISSING — build from scratch (Phase 1+)
  - PostgreSQL: populated by Make DB before Phase 1 starts

  ## Frontend Conventions
  - All component styles are inline JS objects — Tailwind is NOT used in components
  - Viewport-lock layout: body is `height:100vh; overflow:hidden`; pages use `height: calc(100vh - 64px)` (TabBar = 64px fixed bottom)
  - Accent colors are hardcoded hex in inline styles (not CSS vars) — grep all page files when changing colors
  - Do NOT rewrite inline styles; they are the intentional design

  ## Prerequisite Before Phase 1
  architecture_vectors table must have data.
  Verify: SELECT COUNT(*) FROM architecture_vectors;

  ## Session Prompts
  - Phase 0: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 0. Build frontend/ from scratch: React+Vite+Tailwind, AppContext, all pages as empty shells."
  - Phase 1: "Read CLAUDE.md, 00_FLOW.md Section 4.4, 02_MAKE_WEB.md Phase 1. Set up Django backend, social auth (Google/Kakao/Naver), connect to existing
  PostgreSQL."
  - Phase 2: "Read CLAUDE.md, 00_FLOW.md Section 4.4, 02_MAKE_WEB.md Phase 2. Build recommendation engine in engine.py."
  - Phase 3: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 3. Add Gemini LLM: query parsing + persona reports."
  - Phase 4: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 4. Wire frontend ↔ backend, configure image serving."
  - Phase 5: "Read CLAUDE.md, 02_MAKE_WEB.md Phase 5. Testing and polish."