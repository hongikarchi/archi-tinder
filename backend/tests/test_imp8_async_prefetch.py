"""
test_imp8_async_prefetch.py -- IMP-8: Background-thread prefetch + L2 cache.

Tests for:
- TestFlagGating: flag OFF -> sync path unchanged; flag ON -> async path, bg thread spawned
- TestAsyncThreadComputesPrefetch: bg thread writes correct cache entry
- TestAsyncThreadFailureGraceful: engine failure inside bg thread is swallowed; swipe still 200
- TestConnectionClosureOnExit: connections.close_all() called at start and in finally block
- TestBackwardCompat: existing IMP-7 swipe-event assertions pass with flag OFF
- TestSettingsFlagsImp8: new settings keys exist with correct defaults

Threading strategy:
- Integration tests (SwipeView HTTP path): _NoopThread records that a thread was
  constructed but does NOT call the target. This prevents `_async_prefetch_thread`
  from closing the test's DB connection mid-request.
- Unit tests on _async_prefetch_thread directly: call the function directly with
  `patch('django.db.connections.close_all', lambda: None)` so the test DB connection
  survives but the behavior of the function body is exercised.

Cache key contract: prefetch:{session_id}:{cache_round}
  cache_round = saved_current_round + 1
  saved_current_round is captured AFTER session.current_round += 1 (line ~886),
  so for a session starting at round=0: current_round becomes 1, saved=1,
  cache_round = 1+1 = 2.
"""
import numpy as np
import pytest
from unittest.mock import patch
from django.conf import settings
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_card(bid):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid, 'name_en': f'Building {bid}', 'project_name': '',
        'image_url': '', 'url': None, 'gallery': [], 'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Museum', 'axis_architects': None,
            'axis_country': None, 'axis_area_m2': None, 'axis_year': None,
            'axis_style': None, 'axis_atmosphere': 'calm', 'axis_color_tone': None,
            'axis_material': None, 'axis_material_visual': [], 'axis_tags': [],
        },
    }


def _fake_embs(pool_ids):
    return {bid: np.ones(384) / np.linalg.norm(np.ones(384)) for bid in pool_ids}


class _NoopThread:
    """Non-executing shim for threading.Thread used in integration tests.

    Records that a thread was constructed but does NOT call target() on start().
    This is safe for integration tests through SwipeView because it prevents
    _async_prefetch_thread from calling connection.close() on the test's DB
    connection (which would cause InterfaceError on subsequent ORM calls).

    join() is a no-op.
    """
    def __init__(self, target=None, args=(), daemon=None, **kw):
        self._target = target
        self._args = args
        self.daemon = daemon

    def start(self):
        pass  # intentionally does NOT call self._target

    def join(self, timeout=None):
        pass


# Import after class definitions to avoid circular-import issues at parse time.
def _get_async_prefetch_fn():
    from apps.recommendation.views import _async_prefetch_thread
    return _async_prefetch_thread


class _DiscThread:
    """Discriminating thread: suppresses _async_prefetch_thread (unsafe in tests),
    runs all other targets (e.g. telemetry) synchronously so test transaction
    sees the DB writes immediately.
    """
    def __init__(self, target=None, args=(), daemon=None, **kw):
        self._target = target
        self._args = args

    def start(self):
        if self._target is _get_async_prefetch_fn():
            return  # suppress — would close test DB connection
        if self._target:
            self._target(*self._args)

    def join(self, timeout=None):
        pass


def _sync_emit_telemetry(swipe_kwargs, confidence_kwargs):
    """_emit_telemetry_thread replacement: run emits synchronously, no DB close."""
    from apps.recommendation import event_log
    event_log.emit_swipe_event(**swipe_kwargs)
    if confidence_kwargs is not None:
        event_log.emit_event('confidence_update', **confidence_kwargs)


def _create_session_and_project(user_profile, pool_size=10):
    """Create a Project + AnalysisSession for swipe tests."""
    from apps.recommendation.models import Project, AnalysisSession
    _FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, pool_size + 1)]
    project = Project.objects.create(user=user_profile, name='TestProj', filters={})
    session = AnalysisSession.objects.create(
        user=user_profile,
        project=project,
        phase='exploring',
        pool_ids=_FAKE_POOL,
        pool_scores={bid: 1.0 for bid in _FAKE_POOL},
        current_round=0,
        preference_vector=[],
        exposed_ids=[_FAKE_POOL[0]],
        initial_batch=_FAKE_POOL[:5],
        like_vectors=[],
        convergence_history=[],
        previous_pref_vector=[],
        original_filters={},
        original_filter_priority=[],
        original_seed_ids=[],
        current_pool_tier=1,
        v_initial=None,
    )
    return session, _FAKE_POOL


def _base_engine_patches(pool_ids):
    """Return the common engine mock dict reused across all swipe tests."""
    _ENGINE = 'apps.recommendation.views.engine'
    return {
        f'{_ENGINE}.get_pool_embeddings': lambda ids: _fake_embs(ids),
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
        f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
        f'{_ENGINE}.refresh_pool_if_low': lambda *a, **kw: None,
        f'{_ENGINE}.farthest_point_from_pool': lambda pool_ids, exposed, embs: next(
            (b for b in pool_ids if b not in set(exposed)), None
        ),
        f'{_ENGINE}.compute_confidence': lambda *a, **kw: None,
        f'{_ENGINE}.get_last_embedding_call_stats': lambda: {
            'requested': 10, 'cache_hits': 10, 'cache_misses': 0,
        },
        f'{_ENGINE}.get_last_clustering_stats': lambda: None,
        # Telemetry thread patches: run synchronously so test transaction sees DB writes.
        'apps.recommendation.views.swipe._emit_telemetry_thread': _sync_emit_telemetry,
        'apps.recommendation.views.threading.Thread': _DiscThread,
    }


def _apply_patches(patches_dict):
    patchers = []
    for target, side_effect in patches_dict.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# TestFlagGating
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFlagGating:
    """Flag OFF -> sync path, prefetch returned; flag ON -> async path, prefetch=None."""

    def test_flag_off_sync_path_prefetch_returned(self, auth_client, user_profile, settings):
        """With async_prefetch_enabled=False (default), sync prefetch runs normally."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))
        spawned = []

        try:
            # Patch Thread to detect if it gets spawned (it should NOT with flag OFF)
            thread_patcher = patch(
                'apps.recommendation.views.threading.Thread',
                side_effect=lambda *a, **kw: spawned.append(1) or _NoopThread(*a, **kw),
            )
            thread_patcher.start()
            patchers.append(thread_patcher)

            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        # Sync path: prefetch_image should be a card dict (not None)
        assert data['prefetch_image'] is not None
        # Only the telemetry thread is spawned; no async prefetch thread when flag is OFF.
        # _async_warm_taste is now gated by async_prefetch_enabled (BACK-CI-HOTFIX-2),
        # so flag=OFF means no warm thread either.
        assert len(spawned) == 1, 'Only telemetry thread spawned when async prefetch flag is OFF'

    def test_flag_on_async_path_prefetch_null(self, auth_client, user_profile, settings):
        """With async_prefetch_enabled=True, primary response has null prefetches."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': True}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))
        spawned_threads = []

        try:
            # _NoopThread: records construction but does NOT run _async_prefetch_thread.
            # This keeps the test's DB connection alive while verifying the async path.
            thread_patcher = patch(
                'apps.recommendation.views.threading.Thread',
                side_effect=lambda *a, **kw: spawned_threads.append(_NoopThread(*a, **kw)) or spawned_threads[-1],
            )
            thread_patcher.start()
            patchers.append(thread_patcher)

            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        # Async path: prefetch_image and prefetch_image_2 are null
        assert data['prefetch_image'] is None, (
            f'Expected None for prefetch_image in async path, got {data["prefetch_image"]}'
        )
        assert data['prefetch_image_2'] is None, (
            f'Expected None for prefetch_image_2 in async path, got {data["prefetch_image_2"]}'
        )
        # Async prefetch thread + telemetry thread both spawned when flag is ON
        assert len(spawned_threads) == 3, 'Async prefetch + telemetry + async_warm_taste threads spawned when flag is ON'

    def test_flag_on_prefetch_strategy_async_thread_in_event(self, auth_client, user_profile, settings):
        """With flag ON, swipe event has prefetch_strategy='async-thread'."""
        from apps.recommendation.models import SessionEvent
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': True}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))

        try:
            # _DiscThread: suppresses async prefetch (unsafe), runs telemetry synchronously.
            thread_patcher = patch(
                'apps.recommendation.views.threading.Thread',
                side_effect=lambda *a, **kw: _DiscThread(*a, **kw),
            )
            thread_patcher.start()
            patchers.append(thread_patcher)

            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        swipe_event = SessionEvent.objects.filter(
            session=session, event_type='swipe',
        ).order_by('-created_at').first()
        assert swipe_event is not None
        assert swipe_event.payload['prefetch_strategy'] == 'async-thread'

    def test_flag_off_prefetch_strategy_sync_in_event(self, auth_client, user_profile, settings):
        """With flag OFF, swipe event still has prefetch_strategy='sync'."""
        from apps.recommendation.models import SessionEvent
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        swipe_event = SessionEvent.objects.filter(
            session=session, event_type='swipe',
        ).order_by('-created_at').first()
        assert swipe_event is not None
        assert swipe_event.payload['prefetch_strategy'] == 'sync'


# ---------------------------------------------------------------------------
# TestAsyncThreadComputesPrefetch
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAsyncThreadComputesPrefetch:
    """_async_prefetch_thread called directly writes the cache entry correctly.

    These are unit tests that call _async_prefetch_thread() directly (bypassing
    SwipeView) with connection.close patched to a no-op so the test DB connection
    survives. The real Django cache is used so cache.get assertions are real.

    Cache key formula: prefetch:{session_id}:{cache_round}
    In integration context: saved_current_round = 1 (0 + the +1 increment at
    session.current_round += 1 before the save), cache_round = 1+1 = 2.
    In direct-call context: we pass cache_round explicitly.
    """

    def setup_method(self):
        """Clear cache before each test to avoid cross-test pollution."""
        cache.clear()

    def test_cache_entry_written_after_thread(self):
        """_async_prefetch_thread writes a cache entry for the given cache_round."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        fake_embs = _fake_embs(pool_ids)
        session_id = 'test-session-cache-entry-001'
        cache_round = 2  # matches integration: saved_current_round(1) + 1

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.farthest_point_from_pool',
                   side_effect=lambda pid, exp, embs: next(
                       (b for b in pid if b not in set(exp)), None
                   )), \
             patch('apps.recommendation.views.engine.get_building_card',
                   side_effect=_mock_card):

            _async_prefetch_thread(
                session_id=session_id,
                cache_round=cache_round,
                phase='exploring',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap=fake_embs,
                like_vectors_snap=[],
                initial_batch_snap=pool_ids[:3],
                current_round_snap=1,
            )

        cache_key = f'prefetch:{session_id}:{cache_round}'
        cached = cache.get(cache_key)
        assert cached is not None, f'Cache entry missing for key={cache_key}'
        assert 'prefetch_card_id' in cached
        assert 'prefetch_card_2_id' in cached
        assert 'computed_at' in cached

    def test_cache_key_format(self):
        """Cache key is prefetch:{session_id}:{cache_round}."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        fake_embs = _fake_embs(pool_ids)
        session_id = 'test-session-cache-key-002'
        cache_round = 5  # arbitrary; we check the key includes this exact value

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.farthest_point_from_pool',
                   side_effect=lambda pid, exp, embs: next(
                       (b for b in pid if b not in set(exp)), None
                   )), \
             patch('apps.recommendation.views.engine.get_building_card',
                   side_effect=_mock_card):

            _async_prefetch_thread(
                session_id=session_id,
                cache_round=cache_round,
                phase='exploring',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap=fake_embs,
                like_vectors_snap=[],
                initial_batch_snap=pool_ids[:3],
                current_round_snap=1,
            )

        expected_key = f'prefetch:{session_id}:{cache_round}'
        assert cache.get(expected_key) is not None, (
            f'Expected cache entry at {expected_key}'
        )
        # Verify a different cache_round key is absent (correct format, not just any entry)
        wrong_key = f'prefetch:{session_id}:{cache_round + 99}'
        assert cache.get(wrong_key) is None

    def test_cache_entry_has_required_fields(self):
        """Cached entry has prefetch_card_id, prefetch_card_2_id, computed_at."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        fake_embs = _fake_embs(pool_ids)
        session_id = 'test-session-fields-003'
        cache_round = 2

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.farthest_point_from_pool',
                   side_effect=lambda pid, exp, embs: next(
                       (b for b in pid if b not in set(exp)), None
                   )), \
             patch('apps.recommendation.views.engine.get_building_card',
                   side_effect=_mock_card):

            _async_prefetch_thread(
                session_id=session_id,
                cache_round=cache_round,
                phase='exploring',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap=fake_embs,
                like_vectors_snap=[],
                initial_batch_snap=pool_ids[:3],
                current_round_snap=1,
            )

        cached = cache.get(f'prefetch:{session_id}:{cache_round}')
        assert cached is not None
        assert set(cached.keys()) >= {'prefetch_card_id', 'prefetch_card_2_id', 'computed_at'}
        # computed_at must be a non-empty ISO timestamp string
        assert isinstance(cached['computed_at'], str)
        assert len(cached['computed_at']) > 10

    def test_analyzing_phase_uses_compute_mmr_next(self):
        """In analyzing phase, thread uses compute_mmr_next (not farthest_point)."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 8)]
        fake_embs = _fake_embs(pool_ids)
        session_id = 'test-session-analyzing-004'
        cache_round = 3
        mmr_calls = []

        def _counting_mmr(*args):
            mmr_calls.append(args)
            return pool_ids[2]

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.compute_mmr_next',
                   side_effect=_counting_mmr), \
             patch('apps.recommendation.views.engine.get_building_card',
                   side_effect=_mock_card):

            _async_prefetch_thread(
                session_id=session_id,
                cache_round=cache_round,
                phase='analyzing',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap=fake_embs,
                like_vectors_snap=[list(np.ones(384))],
                initial_batch_snap=pool_ids[:3],
                current_round_snap=2,
            )

        assert len(mmr_calls) >= 1, 'compute_mmr_next should be called in analyzing phase'
        cached = cache.get(f'prefetch:{session_id}:{cache_round}')
        assert cached is not None
        assert cached['prefetch_card_id'] == pool_ids[2]


# ---------------------------------------------------------------------------
# TestAsyncThreadFailureGraceful
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAsyncThreadFailureGraceful:
    """Engine exception inside bg thread is swallowed; primary response still 200."""

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()

    def test_engine_exception_in_bg_thread_does_not_fail_swipe(self, auth_client, user_profile, settings):
        """When async path enabled and _NoopThread used, primary swipe still 200.

        With _NoopThread the bg thread is never executed, verifying that the primary
        response path is independent of any bg thread activity. This also implicitly
        verifies the async path does not raise in the primary request context.
        """
        from apps.recommendation.models import SessionEvent
        settings.RECOMMENDATION = {
            **settings.RECOMMENDATION,
            'async_prefetch_enabled': True,
        }
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))

        try:
            thread_patcher = patch(
                'apps.recommendation.views.threading.Thread',
                side_effect=lambda *a, **kw: _NoopThread(*a, **kw),
            )
            thread_patcher.start()
            patchers.append(thread_patcher)

            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        # Primary swipe must still succeed regardless of bg thread state
        assert resp.status_code == 200, f'Swipe failed with {resp.status_code}: {resp.json()}'
        assert resp.json()['accepted'] is True

        # No 'prefetch_failure' event emitted (purely opportunistic optimization)
        failure_events = SessionEvent.objects.filter(
            session=session, event_type='prefetch_failure',
        )
        assert failure_events.count() == 0, 'No prefetch_failure event should be emitted'

    def test_bg_thread_failure_leaves_cache_empty(self):
        """When bg thread fails internally, cache entry for that round is absent.

        Direct-call test: invokes _async_prefetch_thread with engine functions raising,
        verifies no cache entry is written (exception caught before cache.set).
        """
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        session_id = 'test-session-failure-cache-005'
        cache_round = 2

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.farthest_point_from_pool',
                   side_effect=RuntimeError('forced failure')), \
             patch('apps.recommendation.views.engine.compute_mmr_next',
                   side_effect=RuntimeError('forced failure')), \
             patch('apps.recommendation.views.engine.get_building_card',
                   side_effect=RuntimeError('forced failure')):

            # Should NOT raise (exception is caught inside the function)
            _async_prefetch_thread(
                session_id=session_id,
                cache_round=cache_round,
                phase='exploring',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap={},
                like_vectors_snap=[],
                initial_batch_snap=[],
                current_round_snap=0,
            )

        # Cache should be empty (not populated on failure)
        cache_key = f'prefetch:{session_id}:{cache_round}'
        assert cache.get(cache_key) is None, (
            'Cache entry should be absent when bg thread fails'
        )

    def test_bg_thread_exception_swallowed_not_raised(self):
        """_async_prefetch_thread never raises -- exception is logged and swallowed."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 4)]

        with patch('django.db.connections.close_all', lambda: None), \
             patch('apps.recommendation.views.engine.farthest_point_from_pool',
                   side_effect=ValueError('boom')), \
             patch('apps.recommendation.views.engine.compute_mmr_next',
                   side_effect=ValueError('boom')):

            # Must not raise
            try:
                _async_prefetch_thread(
                    session_id='test-session-swallow-006',
                    cache_round=1,
                    phase='analyzing',
                    pool_ids_snap=pool_ids,
                    exposed_ids_snap=[pool_ids[0]],
                    pool_embeddings_snap={},
                    like_vectors_snap=[],
                    initial_batch_snap=[],
                    current_round_snap=0,
                )
            except Exception as exc:
                pytest.fail(f'_async_prefetch_thread raised unexpectedly: {exc!r}')


# ---------------------------------------------------------------------------
# TestConnectionClosureOnExit
# ---------------------------------------------------------------------------

class TestConnectionClosureOnExit:
    """connections.close_all() is called at thread start and in the finally block."""

    def test_connection_close_called_at_start_and_finally(self):
        """_async_prefetch_thread calls connections.close_all() twice: once at start, once in finally."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        fake_embs = {bid: np.ones(384) / np.linalg.norm(np.ones(384)) for bid in pool_ids}
        close_calls = []

        with patch('apps.recommendation.views.engine.farthest_point_from_pool', return_value=pool_ids[1]), \
             patch('apps.recommendation.views.engine.get_building_card', side_effect=_mock_card), \
             patch('apps.recommendation.views.engine.compute_mmr_next', return_value=pool_ids[1]), \
             patch('apps.recommendation.views.cache.set'), \
             patch('apps.recommendation.views.timezone') as mock_tz:

            mock_tz.now.return_value.isoformat.return_value = '2026-04-26T00:00:00+00:00'

            # Patch connections.close_all (used by the refactored multi-DB path)
            with patch('django.db.connections.close_all', side_effect=lambda: close_calls.append('close_all')):
                _async_prefetch_thread(
                    session_id='test-session-123',
                    cache_round=1,
                    phase='exploring',
                    pool_ids_snap=pool_ids,
                    exposed_ids_snap=[pool_ids[0]],
                    pool_embeddings_snap=fake_embs,
                    like_vectors_snap=[],
                    initial_batch_snap=pool_ids[:3],
                    current_round_snap=0,
                )

        # connections.close_all() must be called at least twice:
        # once at start (release parent's conn) and once in finally (release bg thread's conn)
        assert len(close_calls) >= 2, (
            f'Expected at least 2 connections.close_all() calls, got {len(close_calls)}: {close_calls}'
        )

    def test_connection_close_called_in_finally_on_exception(self):
        """connections.close_all() in finally block runs even when the function body raises."""
        from apps.recommendation.views import _async_prefetch_thread

        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        close_calls = []

        # Force an exception inside the try block
        with patch(
            'apps.recommendation.views.engine.farthest_point_from_pool',
            side_effect=RuntimeError('boom'),
        ), patch(
            'apps.recommendation.views.engine.compute_mmr_next',
            side_effect=RuntimeError('boom'),
        ), patch('django.db.connections.close_all', side_effect=lambda: close_calls.append('close_all')):
            # Should NOT raise (exception caught inside the function)
            _async_prefetch_thread(
                session_id='test-session-456',
                cache_round=2,
                phase='analyzing',
                pool_ids_snap=pool_ids,
                exposed_ids_snap=[pool_ids[0]],
                pool_embeddings_snap={},
                like_vectors_snap=[],
                initial_batch_snap=[],
                current_round_snap=0,
            )

        # Even on exception, finally block must have fired
        assert len(close_calls) >= 2, (
            f'Expected at least 2 close_all() calls even on exception, got {len(close_calls)}'
        )


# ---------------------------------------------------------------------------
# TestBackwardCompat
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackwardCompat:
    """With flag OFF (default), behavior is byte-identical to pre-IMP-8."""

    def setup_method(self):
        """Clear cache before each test to prevent cross-test pollution."""
        cache.clear()

    def test_async_prefetch_is_default(self):
        """async_prefetch_enabled defaults to True after PERF-PREFETCH-CHAIN: thread off-by-one fixed + consumer wired."""
        assert settings.RECOMMENDATION.get('async_prefetch_enabled') is True

    def test_swipe_200_flag_off(self, auth_client, user_profile, settings):
        """Standard swipe still succeeds when the legacy sync path is explicitly enabled."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        assert data['next_image'] is not None

    def test_flag_off_no_thread_spawned(self, auth_client, user_profile, settings):
        """No bg prefetch thread is spawned when the sync path is explicitly enabled."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))
        spawned = []

        try:
            thread_patcher = patch(
                'apps.recommendation.views.threading.Thread',
                side_effect=lambda *a, **kw: spawned.append(1) or _NoopThread(*a, **kw),
            )
            thread_patcher.start()
            patchers.append(thread_patcher)

            auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert len(spawned) == 1, 'Only telemetry thread spawned when async prefetch flag is OFF (warm thread now flag-gated)'

    def test_flag_off_no_cache_write(self, auth_client, user_profile, settings):
        """No async prefetch cache entries are written when the sync path is explicitly enabled."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = _create_session_and_project(user_profile)
        patchers = _apply_patches(_base_engine_patches(pool_ids))

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        # No prefetch cache key should exist for any round
        for rnd in range(0, 5):
            key = f'prefetch:{session.session_id}:{rnd}'
            assert cache.get(key) is None, f'Unexpected cache entry at {key}'


# ---------------------------------------------------------------------------
# TestAsyncBranchConsumerIntegration
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAsyncBranchConsumerIntegration:
    """Async branch reads the prior swipe's thread cache write to hydrate prefetch slots.

    Seed: cache.set('prefetch:{sid}:{N}', {prefetch_card_id: pf_id, prefetch_card_2_id: pf2_id})
    Swipe with saved_current_round == N -> consumer reads key N -> response has hydrated cards.
    """

    def setup_method(self):
        """Clear cache before each test."""
        cache.clear()

    def test_async_branch_consumes_prior_thread_write(self, auth_client, user_profile, settings):
        """Async branch reads cache entry seeded by prior swipe's thread and hydrates prefetch slots.

        The session starts at current_round=0. After the swipe current_round becomes 1
        (saved_current_round=1). Consumer key is prefetch:{sid}:1. We pre-seed that key
        before the swipe so the consumer finds a cache hit.
        """
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': True}
        session, pool_ids = _create_session_and_project(user_profile)

        pf_bld_id = 'bld_test_pf_001'
        pf2_bld_id = 'bld_test_pf_002'

        # Pre-seed the cache at the key the consumer will read: prefetch:{sid}:1
        # (saved_current_round will be 1 after the swipe increments current_round 0->1)
        cache_key = f'prefetch:{session.session_id}:1'
        cache.set(cache_key, {
            'prefetch_card_id': pf_bld_id,
            'prefetch_card_2_id': pf2_bld_id,
            'computed_at': '2026-05-26T00:00:00+00:00',
        }, timeout=60)

        # Extend mock cards to include the seeded IDs so get_buildings_by_ids can return them
        def _extended_mock_buildings(ids):
            result = []
            for bid in ids:
                if bid:
                    result.append({
                        'canonical_bld_id': bid,
                        'name_en': f'Building {bid}',
                        'project_name': '',
                        'image_url': f'https://example.com/{bid}.jpg',
                        'url': None,
                        'gallery': [],
                        'gallery_drawing_start': 0,
                        'metadata': {
                            'axis_typology': 'Museum',
                            'axis_architects': None,
                            'axis_country': None,
                            'axis_area_m2': None,
                            'axis_year': None,
                            'axis_style': None,
                            'axis_atmosphere': 'calm',
                            'axis_color_tone': None,
                            'axis_material': None,
                            'axis_material_visual': [],
                            'axis_tags': [],
                        },
                    })
            return result

        patchers = _apply_patches(_base_engine_patches(pool_ids))
        # Override get_buildings_by_ids to handle the seeded IDs as well
        buildings_patcher = patch(
            'apps.recommendation.views.engine.get_buildings_by_ids',
            side_effect=_extended_mock_buildings,
        )
        buildings_patcher.start()
        patchers.append(buildings_patcher)

        # Use _NoopThread: suppresses async prefetch thread so the seeded cache entry
        # is not overwritten by a concurrent thread write during the test.
        thread_patcher = patch(
            'apps.recommendation.views.threading.Thread',
            side_effect=lambda *a, **kw: _NoopThread(*a, **kw),
        )
        thread_patcher.start()
        patchers.append(thread_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200, f'Swipe failed: {resp.json()}'
        data = resp.json()
        assert data['accepted'] is True

        # Cache hit: prefetch_image and prefetch_image_2 must be hydrated card dicts.
        pf = data['prefetch_image']
        pf2 = data['prefetch_image_2']
        assert pf is not None, 'prefetch_image should be hydrated from cache hit'
        assert pf2 is not None, 'prefetch_image_2 should be hydrated from cache hit'
        assert pf['canonical_bld_id'] == pf_bld_id, (
            f'Expected prefetch_image={pf_bld_id}, got {pf.get("canonical_bld_id")}'
        )
        assert pf2['canonical_bld_id'] == pf2_bld_id, (
            f'Expected prefetch_image_2={pf2_bld_id}, got {pf2.get("canonical_bld_id")}'
        )
        # Verify response shape parity with sync path (required fields present)
        for card in (pf, pf2):
            assert 'canonical_bld_id' in card
            assert 'image_url' in card
            assert 'metadata' in card

    def test_async_branch_cache_miss_graceful(self, auth_client, user_profile, settings):
        """Cache miss on async path: prefetch slots remain None; swipe still 200."""
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': True}
        session, pool_ids = _create_session_and_project(user_profile)

        # Do NOT seed the cache -- test cache miss path
        patchers = _apply_patches(_base_engine_patches(pool_ids))
        thread_patcher = patch(
            'apps.recommendation.views.threading.Thread',
            side_effect=lambda *a, **kw: _NoopThread(*a, **kw),
        )
        thread_patcher.start()
        patchers.append(thread_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200, f'Swipe failed: {resp.json()}'
        data = resp.json()
        assert data['accepted'] is True
        # Cache miss: prefetch slots are None (graceful fallback; frontend handles)
        assert data['prefetch_image'] is None, (
            f'Cache miss should leave prefetch_image=None, got {data["prefetch_image"]}'
        )
        assert data['prefetch_image_2'] is None, (
            f'Cache miss should leave prefetch_image_2=None, got {data["prefetch_image_2"]}'
        )

    def test_async_branch_dedupe_pf_id_matches_next_bid(self, auth_client, user_profile, settings):
        """Regression test for the analyzing-path duplicate.

        Pre-fix: cache had pf_id == next_bid; both response slots returned
        the same card to the user. Post-fix: pf_id is degraded to None
        (same as cache miss) — user never sees a dupe.

        Setup: session starts exploring, current_round=0, initial_batch=pool_ids[:5].
        After swipe on pool_ids[0]:
          - current_round becomes 1 (saved_current_round=1)
          - exploring picker: initial_batch[1] = pool_ids[1] -> next_bid = pool_ids[1]
          - consumer reads prefetch:{sid}:1 -> pf_id = pool_ids[1] (== next_bid)
          - dedupe guard: pf_id degraded to None
        Response: next_image.canonical_bld_id == pool_ids[1], prefetch_image is None.
        """
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': True}
        session, pool_ids = _create_session_and_project(user_profile)

        # Seed cache with pf_id == pool_ids[1], which is the same ID the swipe handler
        # will pick as next_bid (exploring path: initial_batch[current_round=1] = pool_ids[1]).
        saved_current_round = 1  # current_round goes 0->1 during swipe processing
        cache_key = f'prefetch:{session.session_id}:{saved_current_round}'
        cache.set(cache_key, {
            'prefetch_card_id': pool_ids[1],  # SAME as next_bid — collision scenario
            'prefetch_card_2_id': pool_ids[2],
            'computed_at': '2026-05-26T00:00:00+00:00',
        }, timeout=60)

        def _extended_mock_buildings(ids):
            result = []
            for bid in ids:
                if bid:
                    result.append({
                        'canonical_bld_id': bid,
                        'name_en': f'Building {bid}',
                        'project_name': '',
                        'image_url': f'https://example.com/{bid}.jpg',
                        'url': None,
                        'gallery': [],
                        'gallery_drawing_start': 0,
                        'metadata': {
                            'axis_typology': 'Museum',
                            'axis_architects': None,
                            'axis_country': None,
                            'axis_area_m2': None,
                            'axis_year': None,
                            'axis_style': None,
                            'axis_atmosphere': 'calm',
                            'axis_color_tone': None,
                            'axis_material': None,
                            'axis_material_visual': [],
                            'axis_tags': [],
                        },
                    })
            return result

        patchers = _apply_patches(_base_engine_patches(pool_ids))
        buildings_patcher = patch(
            'apps.recommendation.views.engine.get_buildings_by_ids',
            side_effect=_extended_mock_buildings,
        )
        buildings_patcher.start()
        patchers.append(buildings_patcher)

        thread_patcher = patch(
            'apps.recommendation.views.threading.Thread',
            side_effect=lambda *a, **kw: _NoopThread(*a, **kw),
        )
        thread_patcher.start()
        patchers.append(thread_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200, f'Swipe failed: {resp.json()}'
        data = resp.json()
        assert data['accepted'] is True

        # next_image must be the canonical pick (pool_ids[1])
        assert data['next_image'] is not None, 'next_image must not be None'
        assert data['next_image']['canonical_bld_id'] == pool_ids[1], (
            f'Expected next_image={pool_ids[1]}, got {data["next_image"].get("canonical_bld_id")}'
        )

        # prefetch_image must be None: dedupe guard degraded pf_id (== next_bid) to None
        assert data['prefetch_image'] is None, (
            f'Dedupe guard should degrade pf_id==next_bid to None, '
            f'got prefetch_image={data["prefetch_image"]}'
        )

        # prefetch_image_2 may still be hydrated (pool_ids[2] != next_bid)
        # — we only assert the main dupe is gone, not the secondary slot
        # (pf2 is still valid here since pool_ids[2] != pool_ids[1] != None after pf degrade)


# ---------------------------------------------------------------------------
# TestSettingsFlagsImp8
# ---------------------------------------------------------------------------

class TestSettingsFlagsImp8:
    """New IMP-8 settings keys exist with correct defaults."""

    def test_async_prefetch_enabled_default_true(self):
        """async_prefetch_enabled defaults to True after PERF-PREFETCH-CHAIN."""
        assert settings.RECOMMENDATION.get('async_prefetch_enabled') is True

    def test_async_prefetch_cache_timeout_seconds_default(self):
        assert settings.RECOMMENDATION.get('async_prefetch_cache_timeout_seconds') == 60

    def test_async_prefetch_enabled_is_bool(self):
        val = settings.RECOMMENDATION.get('async_prefetch_enabled')
        assert isinstance(val, bool), f'Expected bool, got {type(val)}'

    def test_async_prefetch_cache_timeout_seconds_is_int(self):
        val = settings.RECOMMENDATION.get('async_prefetch_cache_timeout_seconds')
        assert isinstance(val, int), f'Expected int, got {type(val)}'
        assert val > 0
