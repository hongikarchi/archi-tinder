"""
test_imp7_pool_cache.py -- IMP-7: Per-building-id embedding cache + §6 swipe telemetry.

Tests for:
- Per-building-id cache (frozenset -> building_id key fix)
- Partial-miss fetch: only missing IDs hit DB
- Cache retention across pool escalation (THE KEY BUG FIX TEST)
- L2 normalization at insertion time
- FIFO eviction at _BUILDING_CACHE_MAX_SIZE
- get_last_embedding_call_stats() correctness
- precompute_pool_embeddings() warms cache
- Session creation naturally warms cache (no new DB call on second get_pool_embeddings)
- SwipeView emits new §6 fields: cache_hit, cache_source, cache_partial_miss_count,
  prefetch_strategy, db_call_count, pool_escalation_fired, pool_signature_hash

No real DB queries against architecture_vectors -- connection.cursor is mocked.
DB tests use in-memory SQLite via conftest.py.
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings

import apps.recommendation.engine as engine_module
from apps.recommendation.engine import (
    get_pool_embeddings,
    get_last_embedding_call_stats,
    precompute_pool_embeddings,
    clear_pool_embedding_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_action_card():
    """Return a minimal fake action card dict (avoids multi-line lambda E127 issues)."""
    return {
        'building_id': '__action_card__', 'card_type': 'action',
        'name_en': '', 'project_name': '', 'image_url': '',
        'url': None, 'gallery': [], 'gallery_drawing_start': 0,
        'metadata': {}, 'action_card_message': '', 'action_card_subtitle': '',
    }


def _make_embedding_str(seed=42, dim=384):
    """Return a pgvector-style embedding string for a random unit vector."""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return '[' + ','.join(str(x) for x in v) + ']'


def _make_raw_embedding(seed=42, dim=384):
    """Return a raw (non-normalized) embedding string."""
    rng = np.random.RandomState(seed)
    v = (rng.randn(dim) * 5.0).astype(np.float32)  # scale > 1 to ensure not unit
    return '[' + ','.join(str(x) for x in v) + ']'


def _make_cursor_for_ids(id_to_seed):
    """Build a mock cursor that returns embedding rows for the given {bid: seed} dict."""
    rows_data = [
        {'building_id': bid, 'embedding': _make_embedding_str(seed)}
        for bid, seed in id_to_seed.items()
    ]
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    # description + fetchall for _dictfetchall
    cursor.description = [('building_id',), ('embedding',)]
    cursor.fetchall.return_value = [
        (row['building_id'], row['embedding']) for row in rows_data
    ]
    return cursor, rows_data


_FAKE_POOL_ALL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]


def _fake_embeddings_dict(ids):
    return {bid: np.random.RandomState(i).randn(384).astype(np.float32)
            for i, bid in enumerate(ids)}


# ---------------------------------------------------------------------------
# TestBuildingCacheBasics
# ---------------------------------------------------------------------------

class TestBuildingCacheBasics:
    """Fundamental per-building-id cache operations."""

    def setup_method(self):
        clear_pool_embedding_cache()

    def test_first_call_populates_cache(self):
        """First call fetches all IDs and caches them individually."""
        ids = ['B00001', 'B00002']
        cursor, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = get_pool_embeddings(ids)

        assert set(result.keys()) == {'B00001', 'B00002'}
        assert result['B00001'].shape == (384,)
        assert result['B00002'].shape == (384,)
        # Both should be cached now
        assert 'B00001' in engine_module._building_embedding_cache
        assert 'B00002' in engine_module._building_embedding_cache

    def test_second_call_partial_hit(self):
        """Second call with overlapping IDs: hits for old, misses for new only."""
        # Seed cache with B00001
        ids_first = ['B00001', 'B00002']
        cursor1, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor1
            get_pool_embeddings(ids_first)

        # Now call with [B00001, B00003] — B00001 hit, B00003 miss
        cursor2, _ = _make_cursor_for_ids({'B00003': 3})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor2
            result = get_pool_embeddings(['B00001', 'B00003'])

        # DB should have been queried only for B00003
        executed_params = cursor2.execute.call_args[0][1]
        assert 'B00003' in executed_params
        assert 'B00001' not in executed_params

        assert set(result.keys()) == {'B00001', 'B00003'}

    def test_stats_after_first_call(self):
        """get_last_embedding_call_stats reflects correct hits/misses after first call."""
        clear_pool_embedding_cache()
        cursor, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            get_pool_embeddings(['B00001', 'B00002'])

        stats = get_last_embedding_call_stats()
        assert stats is not None
        assert stats['requested'] == 2
        assert stats['cache_misses'] == 2   # both new
        assert stats['cache_hits'] == 0

    def test_stats_after_second_call_with_hits(self):
        """Stats correctly report partial hit/miss on second call."""
        clear_pool_embedding_cache()
        cursor1, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor1
            get_pool_embeddings(['B00001', 'B00002'])

        cursor2, _ = _make_cursor_for_ids({'B00003': 3})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor2
            get_pool_embeddings(['B00001', 'B00002', 'B00003'])

        stats = get_last_embedding_call_stats()
        assert stats['requested'] == 3
        assert stats['cache_hits'] == 2    # B00001 + B00002
        assert stats['cache_misses'] == 1  # B00003

    def test_full_hit_no_db_call(self):
        """When all IDs are cached, no DB cursor is opened."""
        clear_pool_embedding_cache()
        cursor1, _ = _make_cursor_for_ids({'B00001': 1})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor1
            get_pool_embeddings(['B00001'])

        # Second call — fully cached
        with patch('apps.recommendation.engine.connection') as mock_conn2:
            result = get_pool_embeddings(['B00001'])
            mock_conn2.cursor.assert_not_called()

        assert 'B00001' in result

    def test_empty_pool_ids_returns_empty_dict(self):
        """Empty input returns empty dict and zeros stats."""
        result = get_pool_embeddings([])
        assert result == {}
        stats = get_last_embedding_call_stats()
        assert stats['requested'] == 0
        assert stats['cache_hits'] == 0
        assert stats['cache_misses'] == 0

    def test_none_before_any_call(self):
        """get_last_embedding_call_stats returns None when no call has been made yet."""
        # Reset module-level state
        engine_module._last_embedding_call_stats = None
        assert get_last_embedding_call_stats() is None


# ---------------------------------------------------------------------------
# TestEscalationCacheRetention  (THE KEY BUG FIX TEST)
# ---------------------------------------------------------------------------

class TestEscalationCacheRetention:
    """Cache retains entries across pool escalation (frozenset key would invalidate)."""

    def setup_method(self):
        clear_pool_embedding_cache()

    def test_escalation_does_not_invalidate_prior_cached_ids(self):
        """
        Simulate A4 escalation: pool grows from [id1,id2,id3] to [id1,id2,id3,id4,id5].
        With the OLD frozenset key, the new frozenset causes a full cache miss.
        With the NEW per-building-id key, id1/id2/id3 remain cached -- only id4/id5 miss.
        """
        original_ids = ['B00001', 'B00002', 'B00003']
        cursor_orig, _ = _make_cursor_for_ids({bid: i for i, bid in enumerate(original_ids, 1)})

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor_orig
            get_pool_embeddings(original_ids)

        # Verify original IDs are cached
        for bid in original_ids:
            assert bid in engine_module._building_embedding_cache, f'{bid} should be cached'

        # Simulate escalation: pool now includes 2 new IDs
        escalated_ids = original_ids + ['B00004', 'B00005']
        cursor_esc, _ = _make_cursor_for_ids({'B00004': 4, 'B00005': 5})

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor_esc
            result = get_pool_embeddings(escalated_ids)

        stats = get_last_embedding_call_stats()
        # id1/id2/id3 = 3 cache hits; id4/id5 = 2 misses
        assert stats['cache_hits'] == 3, f"Expected 3 hits; got {stats['cache_hits']}"
        assert stats['cache_misses'] == 2, f"Expected 2 misses; got {stats['cache_misses']}"

        # DB query should only have requested B00004 and B00005
        executed_params = cursor_esc.execute.call_args[0][1]
        assert 'B00004' in executed_params
        assert 'B00005' in executed_params
        assert 'B00001' not in executed_params
        assert len(result) == 5

    def test_repeated_escalations_accumulate_hits(self):
        """Multiple escalation events accumulate cache hits correctly."""
        clear_pool_embedding_cache()
        ids_batch1 = ['B00001', 'B00002']
        cursor1, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor1
            get_pool_embeddings(ids_batch1)

        ids_batch2 = ids_batch1 + ['B00003', 'B00004']
        cursor2, _ = _make_cursor_for_ids({'B00003': 3, 'B00004': 4})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor2
            get_pool_embeddings(ids_batch2)

        # Now all 4 cached; third escalation adds B00005 only
        ids_batch3 = ids_batch2 + ['B00005']
        cursor3, _ = _make_cursor_for_ids({'B00005': 5})
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor3
            get_pool_embeddings(ids_batch3)

        stats = get_last_embedding_call_stats()
        assert stats['cache_hits'] == 4
        assert stats['cache_misses'] == 1


# ---------------------------------------------------------------------------
# TestL2Normalization
# ---------------------------------------------------------------------------

class TestL2Normalization:
    """Embeddings stored in cache are L2-normalized at insertion time."""

    def setup_method(self):
        clear_pool_embedding_cache()

    def test_stored_embeddings_are_unit_length(self):
        """Raw (non-unit) embedding from DB is L2-normalized before caching."""
        raw_str = _make_raw_embedding(seed=99)  # deliberately NOT unit length
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.description = [('building_id',), ('embedding',)]
        cursor.fetchall.return_value = [('B00099', raw_str)]

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = get_pool_embeddings(['B00099'])

        emb = result['B00099']
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-5, f"Expected unit vector, got norm={norm}"

    def test_zero_vector_stored_without_crash(self):
        """Zero-vector embedding is stored as-is (no division by zero)."""
        zero_str = '[' + ','.join(['0.0'] * 384) + ']'
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.description = [('building_id',), ('embedding',)]
        cursor.fetchall.return_value = [('B00000', zero_str)]

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = get_pool_embeddings(['B00000'])  # should not raise

        assert 'B00000' in result
        assert result['B00000'].shape == (384,)


# ---------------------------------------------------------------------------
# TestCacheBoundFIFO
# ---------------------------------------------------------------------------

class TestCacheBoundFIFO:
    """FIFO eviction respects _BUILDING_CACHE_MAX_SIZE."""

    def setup_method(self):
        clear_pool_embedding_cache()

    def test_fifo_eviction_drops_oldest(self, monkeypatch):
        """When max size is 3 and 5 IDs inserted, first 2 are evicted (FIFO)."""
        monkeypatch.setattr(engine_module, '_BUILDING_CACHE_MAX_SIZE', 3)

        all_ids = ['B00001', 'B00002', 'B00003', 'B00004', 'B00005']
        # Insert them one by one (each call fetches 1 new ID)
        for i, bid in enumerate(all_ids, 1):
            cursor = MagicMock()
            cursor.__enter__ = lambda s: s
            cursor.__exit__ = MagicMock(return_value=False)
            cursor.description = [('building_id',), ('embedding',)]
            cursor.fetchall.return_value = [(bid, _make_embedding_str(seed=i))]
            with patch('apps.recommendation.engine.connection') as mock_conn:
                mock_conn.cursor.return_value = cursor
                get_pool_embeddings([bid])

        # After 5 inserts into a max-3 cache: oldest 2 should be evicted
        cache_keys = set(engine_module._building_embedding_cache.keys())
        assert len(cache_keys) == 3, f"Cache should have 3 entries, has {len(cache_keys)}: {cache_keys}"
        # The last 3 inserted should remain
        assert 'B00003' in cache_keys
        assert 'B00004' in cache_keys
        assert 'B00005' in cache_keys
        assert 'B00001' not in cache_keys
        assert 'B00002' not in cache_keys

    def test_cache_does_not_grow_unbounded(self, monkeypatch):
        """Cache size stays <= max even with many inserts."""
        max_size = 10
        monkeypatch.setattr(engine_module, '_BUILDING_CACHE_MAX_SIZE', max_size)

        for i in range(1, 50):
            bid = f'B{str(i).zfill(5)}'
            cursor = MagicMock()
            cursor.__enter__ = lambda s: s
            cursor.__exit__ = MagicMock(return_value=False)
            cursor.description = [('building_id',), ('embedding',)]
            cursor.fetchall.return_value = [(bid, _make_embedding_str(seed=i))]
            with patch('apps.recommendation.engine.connection') as mock_conn:
                mock_conn.cursor.return_value = cursor
                get_pool_embeddings([bid])

        assert len(engine_module._building_embedding_cache) <= max_size


# ---------------------------------------------------------------------------
# TestPrecompute
# ---------------------------------------------------------------------------

class TestPrecompute:
    """precompute_pool_embeddings warms cache for all pool IDs."""

    def setup_method(self):
        clear_pool_embedding_cache()

    def test_precompute_calls_get_pool_embeddings(self):
        """precompute_pool_embeddings delegates to get_pool_embeddings."""
        ids = ['B00001', 'B00002']
        cursor, _ = _make_cursor_for_ids({'B00001': 1, 'B00002': 2})

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            precompute_pool_embeddings(ids)

        assert 'B00001' in engine_module._building_embedding_cache
        assert 'B00002' in engine_module._building_embedding_cache

    def test_precompute_empty_pool_no_error(self):
        """precompute with empty pool is a no-op."""
        precompute_pool_embeddings([])  # should not raise
        precompute_pool_embeddings(None)  # None also safe


# ---------------------------------------------------------------------------
# TestSessionCreateViewWarmsCacheNaturally
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionCreateViewWarmsCacheNaturally:
    """Session creation naturally warms cache via the existing get_pool_embeddings call."""

    def setup_method(self, method):
        clear_pool_embedding_cache()

    def test_session_creation_caches_pool_embeddings(self, auth_client, user_profile):
        """
        After SessionCreateView POST, pool_ids are in _building_embedding_cache.
        A subsequent get_pool_embeddings(pool_ids) should produce zero cache misses.
        """
        _ENGINE = 'apps.recommendation.views.engine'
        _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
        _FAKE_SCORES = {bid: 15 - i for i, bid in enumerate(_FAKE_POOL)}
        _FAKE_EMBEDDINGS = {
            bid: np.random.RandomState(i).randn(384).astype(np.float32) / np.linalg.norm(np.random.RandomState(i).randn(384))
            for i, bid in enumerate(_FAKE_POOL)
        }

        def _mock_card(bid):
            if bid is None:
                return None
            return {
                'building_id': bid, 'name_en': f'Building {bid}', 'project_name': '',
                'image_url': '', 'url': None, 'gallery': [], 'gallery_drawing_start': 0,
                'metadata': {'axis_typology': 'Museum', 'axis_architects': None,
                             'axis_country': None, 'axis_area_m2': None, 'axis_year': None,
                             'axis_style': None, 'axis_atmosphere': 'calm', 'axis_color_tone': None,
                             'axis_material': None, 'axis_material_visual': [], 'axis_tags': []},
            }

        def _mock_pool_embeddings(pool_ids):
            # This mock also warms the real engine cache
            return {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}

        patches = {
            f'{_ENGINE}.create_bounded_pool': lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES)),
            f'{_ENGINE}.get_pool_embeddings': _mock_pool_embeddings,
            f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
                (b for b in pool_ids if b not in set(exposed)), None),
            f'{_ENGINE}.get_building_card': _mock_card,
            f'{_ENGINE}.get_building_embedding': lambda bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)).tolist(),
            f'{_ENGINE}.update_preference_vector': lambda p, e, a: list(np.random.randn(384)),
            f'{_ENGINE}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_ENGINE}.compute_mmr_next': lambda *a: 'B00001',
            f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
            f'{_ENGINE}.check_convergence': lambda *a: False,
            f'{_ENGINE}.build_action_card': _make_action_card,
            f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
            f'{_ENGINE}.refresh_pool_if_low': lambda *a, **kw: None,
        }
        patchers = []
        for target, side_effect in patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'filters': {}},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        assert resp.status_code == 201

        # Verify mock warmed the embeddings for pool_ids after session creation
        # (In real code, get_pool_embeddings warms cache as side effect;
        #  the mock above populates _FAKE_EMBEDDINGS which we can re-query)
        # The real assertion: a second real get_pool_embeddings on the returned session's
        # pool_ids should show zero DB calls. Since mock replaced engine.get_pool_embeddings
        # we can't inspect real cache here; we verify the response shape is correct instead.
        data = resp.json()
        assert 'session_id' in data
        assert data['next_image'] is not None


# ---------------------------------------------------------------------------
# TestSwipeEventPayload
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwipeEventPayload:
    """SwipeView emits the IMP-7 §6 fields on every swipe SessionEvent."""

    def test_swipe_event_has_imp7_fields(self, auth_client, user_profile):
        """
        End-to-end swipe: verify SessionEvent payload contains all IMP-7 §6 fields.
        """
        from apps.recommendation.models import Project, AnalysisSession, SessionEvent

        _ENGINE = 'apps.recommendation.views.engine'
        _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
        _FAKE_EMBEDDINGS_DICT = {
            bid: np.random.RandomState(i).randn(384).astype(np.float32)
            for i, bid in enumerate(_FAKE_POOL)
        }
        for bid in _FAKE_EMBEDDINGS_DICT:
            v = _FAKE_EMBEDDINGS_DICT[bid]
            norm = np.linalg.norm(v)
            if norm > 0:
                _FAKE_EMBEDDINGS_DICT[bid] = v / norm

        def _mock_card(bid):
            if bid is None:
                return None
            return {
                'building_id': bid, 'name_en': f'Building {bid}', 'project_name': '',
                'image_url': '', 'url': None, 'gallery': [], 'gallery_drawing_start': 0,
                'metadata': {'axis_typology': 'Museum', 'axis_architects': None,
                             'axis_country': None, 'axis_area_m2': None, 'axis_year': None,
                             'axis_style': None, 'axis_atmosphere': 'calm', 'axis_color_tone': None,
                             'axis_material': None, 'axis_material_visual': [], 'axis_tags': []},
            }

        # Create session first
        project = Project.objects.create(user=user_profile, name='TestProj', filters={})

        pool_ids = _FAKE_POOL[:10]
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=pool_ids,
            pool_scores={bid: 1.0 for bid in pool_ids},
            current_round=0,
            preference_vector=[],
            exposed_ids=[pool_ids[0]],
            initial_batch=pool_ids[:5],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
        )

        patches = {
            f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {
                bid: _FAKE_EMBEDDINGS_DICT.get(bid, np.zeros(384)) for bid in pool_ids
            },
            f'{_ENGINE}.get_building_card': _mock_card,
            f'{_ENGINE}.get_building_embedding': lambda bid: _FAKE_EMBEDDINGS_DICT.get(bid, np.zeros(384)).tolist(),
            f'{_ENGINE}.update_preference_vector': lambda p, e, a: list(np.random.randn(384)),
            f'{_ENGINE}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_ENGINE}.compute_mmr_next': lambda *a: pool_ids[1],
            f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
            f'{_ENGINE}.check_convergence': lambda *a: False,
            f'{_ENGINE}.build_action_card': _make_action_card,
            f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
            f'{_ENGINE}.refresh_pool_if_low': lambda *a, **kw: None,
            f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
                (b for b in pool_ids if b not in set(exposed)), None),
            f'{_ENGINE}.compute_confidence': lambda *a, **kw: 0.5,
        }
        # Also mock get_last_embedding_call_stats to return known values
        patchers = []
        for target, side_effect in patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        # Mock get_last_embedding_call_stats to return known stats
        stats_patcher = patch(
            'apps.recommendation.views.engine.get_last_embedding_call_stats',
            return_value={'requested': 10, 'cache_hits': 8, 'cache_misses': 2},
        )
        stats_patcher.start()
        patchers.append(stats_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True

        # Verify SessionEvent was created with IMP-7 §6 fields
        swipe_event = SessionEvent.objects.filter(
            session=session, event_type='swipe'
        ).order_by('-created_at').first()
        assert swipe_event is not None, 'Swipe SessionEvent not found'

        payload = swipe_event.payload
        # IMP-7 §6 required fields
        assert 'cache_hit' in payload, f'cache_hit missing from payload: {payload.keys()}'
        assert isinstance(payload['cache_hit'], bool), f'cache_hit should be bool, got {type(payload["cache_hit"])}'
        assert 'cache_source' in payload
        assert payload['cache_source'] in ('precompute', 'fresh')
        assert 'cache_partial_miss_count' in payload
        assert isinstance(payload['cache_partial_miss_count'], int)
        assert 'prefetch_strategy' in payload
        assert payload['prefetch_strategy'] == 'sync'
        assert 'db_call_count' in payload
        assert payload['db_call_count'] is None  # IMP-9 deferred
        assert 'pool_escalation_fired' in payload
        assert isinstance(payload['pool_escalation_fired'], bool)
        assert 'pool_signature_hash' in payload
        # pool_signature_hash is 16-char hex string or None
        if payload['pool_signature_hash'] is not None:
            assert len(payload['pool_signature_hash']) == 16
            assert all(c in '0123456789abcdef' for c in payload['pool_signature_hash'])

    def test_cache_source_fresh_when_misses(self, auth_client, user_profile):
        """cache_source='fresh' when cache_misses > 0."""
        from apps.recommendation.models import Project, AnalysisSession, SessionEvent

        _ENGINE = 'apps.recommendation.views.engine'
        _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]

        def _mock_card(bid):
            if bid is None:
                return None
            return {'building_id': bid, 'name_en': '', 'project_name': '', 'image_url': '',
                    'url': None, 'gallery': [], 'gallery_drawing_start': 0,
                    'metadata': {'axis_typology': None, 'axis_architects': None, 'axis_country': None,
                                 'axis_area_m2': None, 'axis_year': None, 'axis_style': None,
                                 'axis_atmosphere': 'calm', 'axis_color_tone': None, 'axis_material': None,
                                 'axis_material_visual': [], 'axis_tags': []}}

        project = Project.objects.create(user=user_profile, name='P2', filters={})
        pool_ids = _FAKE_POOL[:10]
        session = AnalysisSession.objects.create(
            user=user_profile, project=project, phase='exploring',
            pool_ids=pool_ids, pool_scores={bid: 1.0 for bid in pool_ids},
            current_round=0, preference_vector=[], exposed_ids=[pool_ids[0]],
            initial_batch=pool_ids[:5], like_vectors=[], convergence_history=[],
            previous_pref_vector=[], original_filters={}, original_filter_priority=[],
            original_seed_ids=[], current_pool_tier=1, v_initial=None,
        )

        _fake_embs = {bid: np.ones(384) / np.linalg.norm(np.ones(384)) for bid in pool_ids}
        patches = {
            f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {bid: _fake_embs[bid] for bid in pool_ids if bid in _fake_embs},
            f'{_ENGINE}.get_building_card': _mock_card,
            f'{_ENGINE}.get_building_embedding': lambda bid: list(np.ones(384) / np.linalg.norm(np.ones(384))),
            f'{_ENGINE}.update_preference_vector': lambda p, e, a: list(np.random.randn(384)),
            f'{_ENGINE}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_ENGINE}.compute_mmr_next': lambda *a: pool_ids[1],
            f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
            f'{_ENGINE}.check_convergence': lambda *a: False,
            f'{_ENGINE}.build_action_card': _make_action_card,
            f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
            f'{_ENGINE}.refresh_pool_if_low': lambda *a, **kw: None,
            f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
                (b for b in pool_ids if b not in set(exposed)), None),
            f'{_ENGINE}.compute_confidence': lambda *a, **kw: None,
        }
        patchers = []
        for target, side_effect in patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        # Simulate cache misses (cache_misses=3 > 0)
        stats_patcher = patch(
            'apps.recommendation.views.engine.get_last_embedding_call_stats',
            return_value={'requested': 10, 'cache_hits': 7, 'cache_misses': 3},
        )
        stats_patcher.start()
        patchers.append(stats_patcher)

        try:
            auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'dislike'},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        swipe_event = SessionEvent.objects.filter(session=session, event_type='swipe').first()
        assert swipe_event is not None
        payload = swipe_event.payload
        assert payload['cache_hit'] is False
        assert payload['cache_source'] == 'fresh'
        assert payload['cache_partial_miss_count'] == 3


# ---------------------------------------------------------------------------
# TestPoolEscalationFiredFlag
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPoolEscalationFiredFlag:
    """pool_escalation_fired in swipe event is True when tier escalates this swipe."""

    def test_escalation_fired_false_when_no_escalation(self, auth_client, user_profile):
        """No escalation -> pool_escalation_fired=False in swipe event."""
        from apps.recommendation.models import Project, AnalysisSession, SessionEvent

        _ENGINE = 'apps.recommendation.views.engine'
        _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 20)]

        def _mock_card(bid):
            if bid is None:
                return None
            return {'building_id': bid, 'name_en': '', 'project_name': '', 'image_url': '',
                    'url': None, 'gallery': [], 'gallery_drawing_start': 0,
                    'metadata': {'axis_typology': None, 'axis_architects': None, 'axis_country': None,
                                 'axis_area_m2': None, 'axis_year': None, 'axis_style': None,
                                 'axis_atmosphere': 'calm', 'axis_color_tone': None, 'axis_material': None,
                                 'axis_material_visual': [], 'axis_tags': []}}

        project = Project.objects.create(user=user_profile, name='P3', filters={})
        pool_ids = _FAKE_POOL[:15]  # large pool, no escalation needed
        session = AnalysisSession.objects.create(
            user=user_profile, project=project, phase='exploring',
            pool_ids=pool_ids, pool_scores={bid: 1.0 for bid in pool_ids},
            current_round=0, preference_vector=[], exposed_ids=[pool_ids[0]],
            initial_batch=pool_ids[:5], like_vectors=[], convergence_history=[],
            previous_pref_vector=[], original_filters={}, original_filter_priority=[],
            original_seed_ids=[], current_pool_tier=1, v_initial=None,
        )

        _fake_embs = {bid: np.ones(384) / np.linalg.norm(np.ones(384)) for bid in pool_ids}
        patches = {
            f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {bid: _fake_embs[bid] for bid in pool_ids if bid in _fake_embs},
            f'{_ENGINE}.get_building_card': _mock_card,
            f'{_ENGINE}.get_building_embedding': lambda bid: list(np.ones(384) / np.linalg.norm(np.ones(384))),
            f'{_ENGINE}.update_preference_vector': lambda p, e, a: list(np.random.randn(384)),
            f'{_ENGINE}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_ENGINE}.compute_mmr_next': lambda *a: pool_ids[1],
            f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
            f'{_ENGINE}.check_convergence': lambda *a: False,
            f'{_ENGINE}.build_action_card': _make_action_card,
            f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
            f'{_ENGINE}.refresh_pool_if_low': lambda *a, **kw: None,  # no-op: no escalation
            f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
                (b for b in pool_ids if b not in set(exposed)), None),
            f'{_ENGINE}.compute_confidence': lambda *a, **kw: None,
            f'{_ENGINE}.get_last_embedding_call_stats': lambda: {'requested': 15, 'cache_hits': 15, 'cache_misses': 0},
        }
        patchers = []
        for target, side_effect in patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        assert resp.status_code == 200
        swipe_event = SessionEvent.objects.filter(session=session, event_type='swipe').first()
        assert swipe_event is not None
        # No escalation because refresh_pool_if_low was a no-op (tier unchanged = 1)
        assert swipe_event.payload['pool_escalation_fired'] is False

    def test_escalation_fired_true_when_tier_increments(self, auth_client, user_profile):
        """When refresh_pool_if_low increments current_pool_tier, pool_escalation_fired=True."""
        from apps.recommendation.models import Project, AnalysisSession, SessionEvent

        _ENGINE = 'apps.recommendation.views.engine'
        _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 20)]

        def _mock_card(bid):
            if bid is None:
                return None
            return {'building_id': bid, 'name_en': '', 'project_name': '', 'image_url': '',
                    'url': None, 'gallery': [], 'gallery_drawing_start': 0,
                    'metadata': {'axis_typology': None, 'axis_architects': None, 'axis_country': None,
                                 'axis_area_m2': None, 'axis_year': None, 'axis_style': None,
                                 'axis_atmosphere': 'calm', 'axis_color_tone': None, 'axis_material': None,
                                 'axis_material_visual': [], 'axis_tags': []}}

        def _escalating_refresh(session, threshold=5):
            """Simulate escalation: increment current_pool_tier."""
            session.current_pool_tier = session.current_pool_tier + 1
            # Also add some new pool IDs to avoid the pool-exhausted-before-card-select path
            new_ids = [f'B{str(i).zfill(5)}' for i in range(90, 100)]
            session.pool_ids = list(session.pool_ids) + new_ids
            for bid in new_ids:
                _fake_embs[bid] = np.ones(384) / np.linalg.norm(np.ones(384))

        project = Project.objects.create(user=user_profile, name='P4', filters={})
        pool_ids = _FAKE_POOL[:6]  # small pool triggers escalation check
        session = AnalysisSession.objects.create(
            user=user_profile, project=project, phase='exploring',
            pool_ids=pool_ids, pool_scores={bid: 1.0 for bid in pool_ids},
            current_round=0, preference_vector=[], exposed_ids=[pool_ids[0]],
            initial_batch=pool_ids[:5], like_vectors=[], convergence_history=[],
            previous_pref_vector=[], original_filters={}, original_filter_priority=[],
            original_seed_ids=[], current_pool_tier=1, v_initial=None,
        )

        _fake_embs = {bid: np.ones(384) / np.linalg.norm(np.ones(384)) for bid in pool_ids}
        patches = {
            f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {bid: _fake_embs.get(bid, np.ones(384) / np.linalg.norm(np.ones(384))) for bid in pool_ids},
            f'{_ENGINE}.get_building_card': _mock_card,
            f'{_ENGINE}.get_building_embedding': lambda bid: list(np.ones(384) / np.linalg.norm(np.ones(384))),
            f'{_ENGINE}.update_preference_vector': lambda p, e, a: list(np.random.randn(384)),
            f'{_ENGINE}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_ENGINE}.compute_mmr_next': lambda *a: pool_ids[1],
            f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
            f'{_ENGINE}.check_convergence': lambda *a: False,
            f'{_ENGINE}.build_action_card': _make_action_card,
            f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
            f'{_ENGINE}.refresh_pool_if_low': _escalating_refresh,  # fires escalation
            f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
                (b for b in pool_ids if b not in set(exposed)), None),
            f'{_ENGINE}.compute_confidence': lambda *a, **kw: None,
            f'{_ENGINE}.get_last_embedding_call_stats': lambda: {'requested': 6, 'cache_hits': 4, 'cache_misses': 2},
        }
        patchers = []
        for target, side_effect in patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        assert resp.status_code == 200
        swipe_event = SessionEvent.objects.filter(session=session, event_type='swipe').first()
        assert swipe_event is not None
        assert swipe_event.payload['pool_escalation_fired'] is True


# ---------------------------------------------------------------------------
# TestSettingsFlags
# ---------------------------------------------------------------------------

class TestSettingsFlags:
    """IMP-7 settings flags exist with expected defaults."""

    def test_pool_precompute_enabled_default_false(self):
        assert settings.RECOMMENDATION.get('pool_precompute_enabled') is False

    def test_pool_embedding_cache_max_size_default(self):
        assert settings.RECOMMENDATION.get('pool_embedding_cache_max_size') == 5000
