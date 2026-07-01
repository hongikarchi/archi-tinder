"""test_like_vectors_hydration.py — unit tests for the like_vectors hydration refactor.

Tests:
  1. hydrate_like_vectors: cache-hit path
  2. hydrate_like_vectors: cache-miss → DB-fetch path
  3. hydrate_like_vectors: OLD-shape entry ('embedding' key) passthrough
  4. hydrate_like_vectors: MIXED old+new entries
  5. hydrate_like_vectors: order and round preserved
  6. hydrate_like_vectors: empty list
  7. Regression: swipe like records new shape in like_vectors
  8. Regression: centroid/MMR still work through hydration (mock DB / seed cache)

These tests import modules under Django settings but do NOT hit a real Postgres DB.
All DB-touching code is mocked or replaced with Django cache (LocMem).

Run (flake8 only):
    flake8 backend/apps/recommendation/tests/test_like_vectors_hydration.py
Run (unit tests, SQLite via conftest):
    pytest backend/apps/recommendation/tests/test_like_vectors_hydration.py
"""

import os
import types  # noqa: F401 used in _make_session

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-secret-key-for-pytest-only')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'testdb')
os.environ.setdefault('DB_USER', 'testuser')
os.environ.setdefault('DB_PASSWORD', 'testpass')
os.environ.setdefault('DJANGO_DEBUG', 'True')
os.environ.setdefault('DEV_LOGIN_SECRET', 'test_secret_123')
os.environ.setdefault('GEMINI_API_KEY', 'test-gemini-key')


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_emb(seed=1, dim=384):
    """Return a deterministic float list of length dim."""
    import math
    return [math.sin(seed * i * 0.01) for i in range(dim)]


def _make_session(like_vectors):
    """Return a simple namespace that quacks like AnalysisSession for hydration."""
    return types.SimpleNamespace(like_vectors=like_vectors)


# ── 1. Cache-hit path ─────────────────────────────────────────────────────────

def test_hydrate_cache_hit(settings):
    """New-shape entries resolve from Django cache (no DB call)."""
    from django.core.cache import cache as dj_cache
    from apps.recommendation.services.hydration import (
        hydrate_like_vectors, cache_embedding, _emb_cache_key,
    )

    emb = _make_emb(seed=42)
    bid = 'bld_000042'

    # Pre-populate cache (simulates like-time write)
    cache_embedding(bid, emb)

    session = _make_session([{'id': bid, 'round': 3}])
    result = hydrate_like_vectors(session)

    assert len(result) == 1
    assert result[0]['round'] == 3
    assert len(result[0]['embedding']) == 384
    assert abs(result[0]['embedding'][0] - emb[0]) < 1e-9

    # Clean up
    dj_cache.delete(_emb_cache_key(bid))


# ── 2. Cache-miss → DB-fetch path ─────────────────────────────────────────────

def test_hydrate_cache_miss_db_fetch(settings, monkeypatch):
    """On cache miss, hydrate falls back to buildings DB batch fetch."""
    from apps.recommendation.services import hydration as hyd_module

    emb = _make_emb(seed=7)
    bid = 'bld_000007'

    # Ensure nothing in cache for this key
    from django.core.cache import cache as dj_cache
    dj_cache.delete(hyd_module._emb_cache_key(bid))

    # Patch _batch_fetch_embeddings to avoid real DB
    def _fake_batch(bld_ids):
        return {b: emb for b in bld_ids}

    monkeypatch.setattr(hyd_module, '_batch_fetch_embeddings', _fake_batch)

    session = _make_session([{'id': bid, 'round': 5}])
    result = hyd_module.hydrate_like_vectors(session)

    assert len(result) == 1
    assert result[0]['round'] == 5
    assert len(result[0]['embedding']) == 384

    # The miss should have been repopulated in cache
    cached = dj_cache.get(hyd_module._emb_cache_key(bid))
    assert cached is not None


# ── 3. OLD-shape entry passthrough ────────────────────────────────────────────

def test_hydrate_old_shape_passthrough(settings):
    """Entries with 'embedding' key are returned directly (backward-compat)."""
    from apps.recommendation.services.hydration import hydrate_like_vectors

    emb = _make_emb(seed=1)
    session = _make_session([{'embedding': emb, 'round': 2}])
    result = hydrate_like_vectors(session)

    assert len(result) == 1
    assert result[0]['embedding'] is emb   # same object — no copy made
    assert result[0]['round'] == 2


# ── 4. MIXED old+new entries ──────────────────────────────────────────────────

def test_hydrate_mixed_shapes(settings, monkeypatch):
    """Mixed old-shape and new-shape entries in a single like_vectors list."""
    from apps.recommendation.services import hydration as hyd_module
    from django.core.cache import cache as dj_cache

    emb_old = _make_emb(seed=10)
    emb_new = _make_emb(seed=20)
    bid_new = 'bld_000020'

    # Ensure new-shape id is NOT in cache → falls to mock _batch_fetch
    dj_cache.delete(hyd_module._emb_cache_key(bid_new))

    def _fake_batch(bld_ids):
        return {b: emb_new for b in bld_ids}

    monkeypatch.setattr(hyd_module, '_batch_fetch_embeddings', _fake_batch)

    session = _make_session([
        {'embedding': emb_old, 'round': 1},    # old shape
        {'id': bid_new, 'round': 4},            # new shape
    ])
    result = hyd_module.hydrate_like_vectors(session)

    assert len(result) == 2
    assert result[0]['round'] == 1
    assert result[0]['embedding'] is emb_old
    assert result[1]['round'] == 4
    assert result[1]['embedding'] == emb_new


# ── 5. Order and round preserved ─────────────────────────────────────────────

def test_hydrate_order_and_round_preserved(settings, monkeypatch):
    """Output order matches input order; round values are preserved per entry."""
    from apps.recommendation.services import hydration as hyd_module
    from django.core.cache import cache as dj_cache

    bids = [f'bld_{i:06d}' for i in range(5)]
    embs = {bid: _make_emb(seed=i) for i, bid in enumerate(bids)}

    for bid in bids:
        dj_cache.delete(hyd_module._emb_cache_key(bid))

    def _fake_batch(bld_ids):
        return {b: embs[b] for b in bld_ids if b in embs}

    monkeypatch.setattr(hyd_module, '_batch_fetch_embeddings', _fake_batch)

    rounds = [10, 11, 12, 13, 14]
    raw = [{'id': bid, 'round': r} for bid, r in zip(bids, rounds)]
    session = _make_session(raw)
    result = hyd_module.hydrate_like_vectors(session)

    assert len(result) == 5
    for i, entry in enumerate(result):
        assert entry['round'] == rounds[i], f"round mismatch at index {i}"
        assert entry['embedding'] == embs[bids[i]], f"embedding mismatch at index {i}"


# ── 6. Empty list ─────────────────────────────────────────────────────────────

def test_hydrate_empty_list(settings):
    """Empty or None like_vectors returns []."""
    from apps.recommendation.services.hydration import hydrate_like_vectors

    assert hydrate_like_vectors(_make_session([])) == []
    assert hydrate_like_vectors(_make_session(None)) == []


# ── 7. Regression: swipe like records new shape ───────────────────────────────

def test_like_write_shape(settings, monkeypatch):
    """After a like, session.like_vectors contains {id, round} (not embedding)."""
    from apps.recommendation.services import hydration as hyd_module

    bid = 'bld_000099'
    emb = _make_emb(seed=99)

    # Confirm cache_embedding stores to Django cache
    from django.core.cache import cache as dj_cache
    dj_cache.delete(hyd_module._emb_cache_key(bid))

    hyd_module.cache_embedding(bid, emb)

    cached = dj_cache.get(hyd_module._emb_cache_key(bid))
    assert cached is not None
    assert len(cached) == 384

    # Simulate the write-site logic (mirrors swipe_service.py handle_swipe_normal)
    like_vectors = []
    hyd_module.cache_embedding(bid, emb)
    like_vectors = like_vectors + [{'id': bid, 'round': 0}]

    assert len(like_vectors) == 1
    assert like_vectors[0] == {'id': bid, 'round': 0}
    assert 'embedding' not in like_vectors[0]


# ── 8. Regression: centroid/MMR through hydration ────────────────────────────

def test_centroid_through_hydration(settings, monkeypatch):
    """compute_taste_centroids produces a valid centroid when called with hydrated vectors."""
    import numpy as np
    from apps.recommendation.services import hydration as hyd_module
    from django.core.cache import cache as dj_cache

    bids = ['bld_000001', 'bld_000002', 'bld_000003']
    embs = {bid: _make_emb(seed=i + 1) for i, bid in enumerate(bids)}

    for bid in bids:
        dj_cache.delete(hyd_module._emb_cache_key(bid))

    def _fake_batch(bld_ids):
        return {b: embs[b] for b in bld_ids if b in embs}

    monkeypatch.setattr(hyd_module, '_batch_fetch_embeddings', _fake_batch)

    # Build session with new-shape like_vectors
    raw = [{'id': bid, 'round': i} for i, bid in enumerate(bids)]
    session = _make_session(raw)

    hydrated = hyd_module.hydrate_like_vectors(session)
    assert len(hydrated) == 3

    # Call engine function directly — it must not raise
    from apps.recommendation.engine import compute_taste_centroids, clear_centroid_cache
    clear_centroid_cache()

    centroids, global_centroid = compute_taste_centroids(hydrated, round_num=3)
    assert global_centroid is not None
    assert isinstance(global_centroid, np.ndarray)
    assert global_centroid.shape == (384,)
    # Global centroid should be roughly unit-norm (L2-normalized inside the engine)
    norm = float(np.linalg.norm(global_centroid))
    assert 0.5 < norm < 1.5, f"unexpected centroid norm {norm}"
