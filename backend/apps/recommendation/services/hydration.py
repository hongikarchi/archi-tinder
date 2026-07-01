"""hydration.py — like_vectors embedding hydration helper.

Converts the new compact shape `[{'id': canonical_bld_id, 'round': int}, ...]`
stored in AnalysisSession.like_vectors back into the full shape
`[{'embedding': [384 floats], 'round': int}, ...]` that all engine functions
expect.

Why this exists
---------------
AnalysisSession.like_vectors was changed to store only {id, round} (~20 B/entry)
instead of {embedding: [384 floats], round} (~3 kB/entry) so that every swipe
no longer reads and writes an O(n) growing float payload over the remote Neon
connection.  Embeddings are pre-computed and immutable, so they can be fetched
on demand from the Django cache (Redis in prod / LocMem local) or, on cache miss,
batch-fetched from the buildings DB.

Backward compatibility
----------------------
Sessions created before this change have entries with an 'embedding' key.
hydrate_like_vectors handles both shapes transparently:
  - 'embedding' key present → use directly (old shape).
  - 'id' key present        → resolve from cache / DB (new shape).
  - both keys present        → 'embedding' wins (safety: already hydrated).

Order and round values are ALWAYS preserved (recency weighting uses 'round').

Cache key scheme
----------------
  emb:v2:{canonical_bld_id}

Long TTL (7 days, configurable via RECOMMENDATION['embedding_cache_ttl_seconds']).
Embeddings are immutable once computed by Make DB, so there is no staleness risk.

Buildings DB fetch
------------------
Uses connections['buildings'] raw SQL on canonical_v2_buildings, same as
engine.get_pool_embeddings().  Batch IN query for all missing ids.
Results are stored as plain list[float] in the Django cache (JSON-serialisable;
no numpy dependency on the cache layer).

Typical flow
------------
  Normal swipe: embedding cached at like-time → hydrate() always hits → 0 DB calls.
  Cold resume: first hydrate() call misses → one batch DB fetch → cached for next call.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connections

logger = logging.getLogger('apps.recommendation')

# Cache TTL for embedding entries.  Embeddings are immutable (pre-computed by
# Make DB) so a long TTL is safe.  Override via RECOMMENDATION setting.
_DEFAULT_EMB_TTL = 7 * 24 * 3600  # 7 days


def _emb_cache_key(canonical_bld_id):
    """Return the Django-cache key for a building's embedding."""
    return f'emb:v2:{canonical_bld_id}'


def _emb_ttl():
    RC = settings.RECOMMENDATION
    return int(RC.get('embedding_cache_ttl_seconds', _DEFAULT_EMB_TTL))


def cache_embedding(canonical_bld_id, embedding):
    """Store a single embedding in Django cache.

    embedding may be a list[float] or a numpy array; stored as list[float]
    (JSON-serialisable, cache-backend agnostic).

    Called by write sites immediately after a like is recorded so that the
    same-process hydration path always hits without a DB round-trip.
    """
    if not canonical_bld_id or embedding is None:
        return
    emb_list = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
    cache.set(_emb_cache_key(canonical_bld_id), emb_list, timeout=_emb_ttl())


def hydrate_like_vectors(session):
    """Return like_vectors with embeddings resolved.

    Accepts AnalysisSession (or any object with a .like_vectors attribute).
    Returns list[{'embedding': list[float], 'round': int}] in INPUT ORDER.

    Handles both shapes transparently:
      Old shape: {'embedding': [...], 'round': int}  → used directly.
      New shape: {'id': canonical_bld_id, 'round': int} → embedding resolved.

    Returns [] for an empty or None like_vectors.
    """
    raw = getattr(session, 'like_vectors', None) or []
    if not raw:
        return []

    result = []
    need_ids = []        # ids where we must go to cache / DB
    need_positions = []  # index in `result` to backfill

    # First pass: separate already-hydrated entries from id-only entries.
    for entry in raw:
        if not isinstance(entry, dict):
            continue  # malformed entry; skip
        if 'embedding' in entry:
            # Old shape (or already-hydrated) — use as-is.
            result.append({'embedding': entry['embedding'], 'round': entry.get('round', 0)})
        elif 'id' in entry:
            # New shape — placeholder in result; resolve below.
            result.append(None)  # backfill later
            need_ids.append(entry['id'])
            need_positions.append(len(result) - 1)
        # Entry with neither key → skip (corrupt data guard)

    if not need_ids:
        return result

    # Build round lookup in one O(N) pass (same filter/order used to build need_ids).
    _need_rounds = [
        e.get('round', 0)
        for e in raw
        if isinstance(e, dict) and 'id' in e and 'embedding' not in e
    ]

    # Second pass: batch-resolve from Django cache.
    cache_keys = [_emb_cache_key(bid) for bid in need_ids]
    cached_map = cache.get_many(cache_keys)  # {key: list[float]}

    still_missing = []  # (index_in_need, canonical_bld_id)
    for i, (bid, pos) in enumerate(zip(need_ids, need_positions)):
        key = _emb_cache_key(bid)
        if key in cached_map:
            result[pos] = {'embedding': cached_map[key], 'round': _need_rounds[i]}
        else:
            still_missing.append((i, bid, pos))

    if not still_missing:
        # Filter None (skipped entries) — should not be any, but defensive.
        return [r for r in result if r is not None]

    # Third pass: batch-fetch from buildings DB for cache misses.
    missing_bids = [bid for _, bid, _ in still_missing]
    fetched = _batch_fetch_embeddings(missing_bids)

    set_map = {}
    for i, bid, pos in still_missing:
        emb = fetched.get(bid)
        if emb is not None:
            result[pos] = {'embedding': emb, 'round': _need_rounds[i]}
            set_map[_emb_cache_key(bid)] = emb
        else:
            logger.warning('hydrate_like_vectors: embedding not found for %s — entry dropped', bid)
            result[pos] = None  # will be filtered below

    if set_map:
        cache.set_many(set_map, timeout=_emb_ttl())

    return [r for r in result if r is not None]


def _batch_fetch_embeddings(bld_ids):
    """Batch-fetch embeddings from buildings DB for a list of ids.

    Returns dict {canonical_bld_id: list[float]}.
    Missing ids (not in DB) are absent from the result.

    Uses the same 'buildings' connection and canonical_v2_buildings table as
    engine.get_pool_embeddings().  No is_publishable gate needed here because
    these ids are already-liked buildings (they were publishable when served).
    """
    if not bld_ids:
        return {}

    # Import _parse_embedding_text from engine to reuse the existing parser.
    # Import is deferred to avoid circular imports (hydration <- services <- engine).
    try:
        from apps.recommendation.engine_vecmath import _parse_embedding_text
    except ImportError:
        from ..engine_vecmath import _parse_embedding_text

    placeholders = ','.join(['%s'] * len(bld_ids))
    result = {}
    try:
        with connections['buildings'].cursor() as cur:
            cur.execute(
                f'SELECT canonical_bld_id, embedding::text'
                f' FROM canonical_v2_buildings'
                f' WHERE canonical_bld_id IN ({placeholders})',
                list(bld_ids),
            )
            rows = cur.fetchall()
        for row in rows:
            bid, emb_text = row[0], row[1]
            emb = _parse_embedding_text(emb_text)
            if emb is not None:
                result[bid] = emb.tolist()
    except Exception as exc:
        logger.error('hydrate_like_vectors: buildings DB batch fetch failed: %s', exc)

    return result
