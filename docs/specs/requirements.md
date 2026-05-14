# Search Flow Requirements (consolidated, post-shipped)

**Status**: Phase 13-15 (Profile / Board / Social Foundation) shipped on origin/main as of 2026-05-09. This document keeps only the still-pending items.

For implementation theory + production hyperparameters: see `docs/algorithm.md`.
For pending phase work: see `docs/specs/phase16-recommendation-expansion.md`, `phase17-llm-reverse-q.md`, `phase18-external-connections.md`.

---

## Open Design Questions (still tracked)

### Cross-session signal transfer (deferred)
Same project's multiple sessions — should `liked_ids` / `pref_vector` carry over between sessions? Current spec is implicit independence (each session starts fresh). Six options analysed historically:
- A: independent (status quo — current behavior)
- B: exposure-only carryover (don't re-show but no positive signal carry)
- C: asymmetric (negative-only carry, positive resets)
- D: fade-decay carry
- E: full warm-start
- F: user-controlled toggle

**Status**: pending admin decision. Defer until traffic justifies the experiment cost.

### Empty-state UX (Project = 0)
First-time user with 0 projects sees Home → project picker. Need an explicit empty-state path: guided flow / empty-state + create button / demo query?

**Status**: pending — low priority since current users are existing accounts.

### Multi-language behavior (partial)
Chat phase has bilingual rendering rule. Mobile UI / detail page / persona report's multi-language posture is unresolved.

**Status**: pending — Korea-first per Goal.md §6, English supported but not co-equal.

### Mobile vs desktop UX divergence
Current viewport-lock layout is mobile-first. Detail pages on desktop work but aren't optimised.

**Status**: pending — desktop is secondary.

### Privacy / sharing posture
Phase 13+ Profile/Board system established public/private visibility. PIPA + GDPR posture for what user data is collected at signup, consent flow, retention policy is still open.

**Status**: pending — required before public launch.

### Conversation history persistence
Probe-turn chat history during a session is currently transient. Should it persist for session resume?

**Status**: pending — low priority.

---

## Hard System Constraints (cross-cutting, do not violate)

- All building references use `canonical_bld_id` (TEXT PK like `'bld_000344'`), never name / slug / language-dependent field.
- `canonical_v2_buildings` table is owned by Make DB — read-only via raw SQL only. No Django ORM, no migrations.
- Every building query MUST gate on `is_publishable = true` (39 of 39,776 rows are non-publishable; `engine._build_filter_sql` emits this clause automatically).
- Cover image resolution honors LLM-derived `image_focus` ∈ {`exterior`, `interior`, `drawing`, `aerial`, `detail`} → `covers_by_type[focus]` with fallback chain to `display_cover_url` → `cover_image_url_default` → `covers_by_type.exterior` → `all_images[0].url` → `''`.
- SentenceTransformers is NOT a runtime dependency — embeddings are pre-computed by Make DB.
- All URL patterns end with trailing slash (Django `APPEND_SLASH` only redirects GET).
- JWT: access 1hr, refresh 30 days, rotate + blacklist via `simplejwt`.
- Neon PostgreSQL: `sslmode=require`, `psycopg2-binary` (not asyncpg).

(See `CLAUDE.md` for the full list of project conventions; see `docs/database-schema.md` for the full `canonical_v2_buildings` CREATE TABLE + image-resolution semantics.)
