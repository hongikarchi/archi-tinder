"""PERF-ROUND2 item 3 -- module-level state is safe under gunicorn gthread.

No DB: engine.connection / genai are faked. Tests widen thread interleaving via
sys.setswitchinterval so check-then-act races surface reliably.
"""
import sys
import threading
import time
from unittest.mock import patch

import numpy as np
import pytest

import apps.recommendation.views  # noqa: F401 -- import-order guard (services<->views cycle when run alone)
from apps.recommendation import engine
from apps.recommendation.services import _gemini

DIM = 384


@pytest.fixture
def tight_switching():
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(old)


def _run_threads(target, n):
    errors = []

    def wrapped(i):
        try:
            target(i)
        except Exception as exc:   # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=wrapped, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return errors


# -- get_pool_embeddings: FIFO eviction + assemble ---------------------------------------

class _EmbCursor:
    description = [('canonical_bld_id',), ('embedding',)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._ids = list(params)

    def fetchall(self):
        text = '[' + ','.join(['0.5'] * DIM) + ']'
        return [(bid, text) for bid in self._ids]


class _EmbConn:
    def cursor(self):
        return _EmbCursor()


def test_pool_embedding_cache_survives_concurrent_eviction(tight_switching):
    engine.clear_pool_embedding_cache()
    max_size = 40
    with patch.object(engine, 'connection', _EmbConn()), \
            patch.object(engine, '_BUILDING_CACHE_MAX_SIZE', max_size):
        def work(i):
            for j in range(30):
                ids = [f'B{i:02d}-{j:03d}-{x:02d}' for x in range(15)]
                out = engine.get_pool_embeddings(ids)
                # Eviction by another thread may drop entries, but never raises
                # and never returns a wrong-shaped vector.
                assert set(out) <= set(ids)
                for v in out.values():
                    assert v.shape == (DIM,)

        errors = _run_threads(work, 8)
    assert not errors, errors
    assert len(engine._building_embedding_cache) <= max_size
    engine.clear_pool_embedding_cache()


def test_embedding_call_stats_are_per_thread():
    engine.clear_pool_embedding_cache()
    barrier = threading.Barrier(4)
    seen = {}

    with patch.object(engine, 'connection', _EmbConn()):
        def work(i):
            engine.get_pool_embeddings([f'T{i}-{x}' for x in range(i + 1)])
            barrier.wait(timeout=10)      # every thread has called; stats must still be its own
            seen[i] = engine.get_last_embedding_call_stats()['requested']

        errors = _run_threads(work, 4)
    assert not errors, errors
    assert seen == {i: i + 1 for i in range(4)}
    engine.clear_pool_embedding_cache()


# -- compute_taste_centroids: clear-at-20 cache + per-thread clustering stats --------------

def _likes(rng, n, salt):
    out = []
    for r in range(n):
        v = rng.normal(size=DIM)
        v[0] += salt            # distinct cache keys across calls
        out.append({'round': r, 'embedding': (v / np.linalg.norm(v)).tolist()})
    return out


def test_clustering_stats_are_per_thread_and_cache_clear_is_safe(tight_switching):
    engine.clear_centroid_cache()
    barrier = threading.Barrier(3)
    seen = {}

    def work(i):
        rng = np.random.default_rng(i)
        n_likes = i + 1                      # 1, 2, 3 likes -> distinct n_likes_at_decision
        # many distinct keys => the >20 clear-and-refill path runs concurrently
        for salt in range(25):
            engine.compute_taste_centroids(_likes(rng, n_likes, salt), 5, multimodal_floor=10)
        barrier.wait(timeout=30)
        seen[i] = engine.get_last_clustering_stats()['n_likes_at_decision']

    errors = _run_threads(work, 3)
    assert not errors, errors
    assert seen == {0: 1, 1: 2, 2: 3}
    assert len(engine._centroid_cache) <= 21
    engine.clear_centroid_cache()


# -- lazy client singletons -------------------------------------------------------------

def test_gemini_client_singleton_built_once_under_contention(tight_switching):
    built = []

    class _SlowClient:
        def __init__(self, api_key=None):
            time.sleep(0.02)                 # widen the check-then-set window
            built.append(self)

    old = _gemini._gemini_client
    _gemini._gemini_client = None
    try:
        results = []
        with patch.object(_gemini.genai, 'Client', _SlowClient):
            errors = _run_threads(lambda i: results.append(_gemini._get_gemini_client()), 8)
        assert not errors, errors
        assert len(built) == 1
        assert all(r is built[0] for r in results)
    finally:
        _gemini._gemini_client = old
