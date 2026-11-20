"""Pre-built, user-independent Discovery candidate pool.

``_fetch_candidates`` used to pay two DB round trips per request (ids + embedding
text for ~80 rows) and the final card fetch was cold. This module samples a pool
once per process (at prewarm), parses embeddings once, and warms the per-building
card cache. Requests then sample from memory.

Guarantees: nothing here raises into the request path; the rebuild thread is a
daemon that closes its DB connections in ``finally``.
"""
import logging
import threading
import time

import numpy as np
from django.conf import settings
from django.db import connections as _dj_connections

logger = logging.getLogger('apps.recommendation')

_CARD_WARM_CHUNK = 50

_lock = threading.Lock()
_pool = None          # list[dict] | None
_built_at = 0.0       # time.monotonic() of last successful build
_rebuilding = False   # guarded by _lock


def _rc():
    return settings.RECOMMENDATION


def build_pool():
    """Sample + fetch embeddings + warm card cache. Returns list of rows, or None on failure."""
    try:
        rc = _rc()
        size = int(rc.get('discovery_pool_size', 400))
        sample_pct = float(rc.get('discovery_tablesample_pct', 2.0))
        conn = _dj_connections['buildings']

        # TABLESAMPLE SYSTEM, same bounded sampling as the per-request path.
        # sample_pct is a settings float (not user input) so inlining is safe.
        sampled_ids = []
        for _attempt in range(3):
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT canonical_bld_id FROM canonical_v2_buildings'
                    f' TABLESAMPLE SYSTEM ({sample_pct}) WHERE is_publishable = true LIMIT %s',
                    [size],
                )
                sampled_ids = [r[0] for r in cur.fetchall()]
            if len(sampled_ids) >= size:
                break
            sample_pct = min(sample_pct * 2, 100.0)  # raise only if needed to reach size
        if not sampled_ids:
            return None

        with conn.cursor() as cur:
            cur.execute(
                'SELECT canonical_bld_id, embedding::text FROM canonical_v2_buildings'
                ' WHERE canonical_bld_id = ANY(%s) AND is_publishable = true',
                [sampled_ids],
            )
            raw_rows = cur.fetchall()
        by_id = {r[0]: r[1] for r in raw_rows}

        rows = []
        for bid in sampled_ids:
            raw = by_id.get(bid)
            if not raw:
                continue
            vec = np.fromstring(raw.strip('[]'), sep=',', dtype=np.float64).tolist()
            rows.append({'canonical_bld_id': bid, 'embedding': raw, '_vec': vec})
        if not rows:
            return None

        # Warm the card cache (cache-aware fetch) so request-time cards are hits.
        from . import engine
        ids = [r['canonical_bld_id'] for r in rows]
        for i in range(0, len(ids), _CARD_WARM_CHUNK):
            try:
                engine.get_buildings_by_ids(ids[i:i + _CARD_WARM_CHUNK])
            except Exception as exc:  # noqa: BLE001
                logger.warning('discovery_pool: card warm chunk failed (%s: %s)',
                               type(exc).__name__, exc)
        return rows
    except Exception as exc:  # noqa: BLE001 -- never raise into callers
        logger.warning('discovery_pool: build failed (%s: %s)', type(exc).__name__, exc)
        return None


def _refresh():
    """Build and store the pool. Returns True on success. Never raises."""
    global _pool, _built_at
    rows = build_pool()
    if not rows:
        return False
    with _lock:
        _pool = rows
        _built_at = time.monotonic()
    logger.info('discovery_pool: built %d rows', len(rows))
    return True


def _rebuild_worker():
    global _rebuilding
    try:
        _refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning('discovery_pool: rebuild failed (%s: %s)', type(exc).__name__, exc)
    finally:
        try:
            _dj_connections.close_all()
        except Exception:  # noqa: BLE001
            pass
        with _lock:
            _rebuilding = False


def get_pool():
    """Current pool (possibly stale) or None if never built. Triggers one background
    rebuild when expired. Never raises."""
    global _rebuilding
    try:
        ttl = float(_rc().get('discovery_pool_ttl', 1800))
        with _lock:
            pool = _pool
            if pool is None:
                return None
            start = (time.monotonic() - _built_at) > ttl and not _rebuilding
            if start:
                _rebuilding = True
        if start:
            try:
                threading.Thread(target=_rebuild_worker, name='discovery-pool-rebuild',
                                 daemon=True).start()
            except Exception:  # noqa: BLE001
                with _lock:
                    _rebuilding = False
        return pool
    except Exception as exc:  # noqa: BLE001
        logger.warning('discovery_pool: get_pool failed (%s: %s)', type(exc).__name__, exc)
        return None


def reset_for_tests():
    global _pool, _built_at, _rebuilding
    with _lock:
        _pool, _built_at, _rebuilding = None, 0.0, False
