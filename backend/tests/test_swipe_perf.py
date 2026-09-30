"""
test_swipe_perf.py -- PERF-SWIPE-1 regression tests.

  1. Per-swipe cache eviction is one batched delete_many, deferred to on_commit,
     over exactly the key set the old inline evict_* calls deleted.
  2. Regression guard: recent swipe actions are queried once per swipe.
  3. Buildings existence SELECT is skipped for trusted pool ids, still runs for
     unknown / client-seeded / client-buffered ids, and rejects with the same 404.
  4. HNSW iterative scan is a connection-startup option on the 'buildings' alias only.
"""
import pytest
from unittest.mock import MagicMock, patch

import apps.recommendation.views  # noqa: F401 — load views first (services<->views import order)
from apps.recommendation import engine
from apps.recommendation.models import AnalysisSession
from tests.test_swipe import _apply_patches, _create_session, _stop_patches

_CACHES = 'apps.recommendation.caches'
_SWIPE_SERVICE = 'apps.recommendation.services.swipe_service'


def _swipe(auth_client, session_id, bid='B00001', action='like', key='k1', **extra):
    payload = {'canonical_bld_id': bid, 'action': action, 'idempotency_key': key}
    payload.update(extra)
    patchers = _apply_patches()
    try:
        return auth_client.post(
            f'/api/v1/analysis/sessions/{session_id}/swipes/', payload, format='json',
        )
    finally:
        _stop_patches(patchers)


def _existence_conn(found):
    """connections mock recording every buildings execute(); fetchone -> found."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = (1,) if found else None
    conn = MagicMock()
    conn.__getitem__.return_value.cursor.return_value = cursor
    return conn, cursor


# ---------------------------------------------------------------------------
# 1. Batched, deferred cache eviction
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwipeEvictionBatch:

    def test_eviction_is_one_delete_many_after_commit_with_same_keys(
        self, auth_client, user_profile, django_capture_on_commit_callbacks,
    ):
        project, session_id = _create_session(auth_client, user_profile, 'Evict Batch')
        pid = user_profile.id

        with patch(f'{_CACHES}.cache.delete_many') as dm, \
                patch(f'{_CACHES}.cache.delete') as d, \
                django_capture_on_commit_callbacks(execute=False) as callbacks:
            resp = _swipe(auth_client, session_id, 'B00001', 'like', 'evict_1')
            assert resp.status_code == 200
            # Deferred: nothing evicted until the transaction commits.
            assert dm.call_count == 0
            assert d.call_count == 0
        assert len(callbacks) == 1

        with patch(f'{_CACHES}.cache.delete_many') as dm, \
                patch(f'{_CACHES}.cache.delete') as d:
            for cb in callbacks:
                cb()
        assert dm.call_count == 1
        assert d.call_count == 0
        expected = {
            f'taste:{pid}',
            *(f'projects_list:{pid}:p1:ps{ps}' for ps in (50, 10, 20, 25)),
            *(f'discovery_feed:{pid}:cursor0:limit{lim}' for lim in (12, 10, 20, 30)),
        }
        (keys,), _ = dm.call_args
        assert set(keys) == expected
        assert len(keys) == len(expected)

    def test_project_detail_version_is_bumped_on_commit(
        self, auth_client, user_profile, django_capture_on_commit_callbacks,
    ):
        from django.core.cache import cache
        project, session_id = _create_session(auth_client, user_profile, 'Evict Detail')
        ver_key = f'project_detail_version:{project.project_id}'
        cache.set(ver_key, 7, None)
        with django_capture_on_commit_callbacks(execute=True):
            assert _swipe(auth_client, session_id, 'B00002', 'dislike', 'evict_2').status_code == 200
        assert cache.get(ver_key) == 8

    def test_cache_error_does_not_fail_committed_swipe(
        self, auth_client, user_profile, django_capture_on_commit_callbacks,
    ):
        project, session_id = _create_session(auth_client, user_profile, 'Evict Err')
        with patch(f'{_CACHES}.cache.delete_many', side_effect=RuntimeError('redis down')), \
                django_capture_on_commit_callbacks(execute=True):
            assert _swipe(auth_client, session_id, 'B00003', 'like', 'evict_3').status_code == 200

    def test_public_evict_helpers_still_delete_same_keys(self):
        from apps.recommendation import caches
        with patch(f'{_CACHES}.cache.delete_many') as dm:
            caches.evict_taste(5)
            caches.evict_projects_list(5)
            caches.evict_discovery_feed(5)
        assert [set(c.args[0]) for c in dm.call_args_list] == [
            {'taste:5'},
            {f'projects_list:5:p1:ps{ps}' for ps in (50, 10, 20, 25)},
            {f'discovery_feed:5:cursor0:limit{lim}' for lim in (12, 10, 20, 30)},
        ]


# ---------------------------------------------------------------------------
# 2. Recent actions queried once (regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_recent_actions_queried_once_per_swipe(auth_client, user_profile):
    # Regression guard: no dedupe was needed -- _recent_actions was already
    # called once per swipe. Fails if a second call is ever introduced.
    from apps.recommendation.services import swipe_service
    project, session_id = _create_session(auth_client, user_profile, 'Recent Once')
    with patch(f'{_SWIPE_SERVICE}._recent_actions', wraps=swipe_service._recent_actions) as ra:
        assert _swipe(auth_client, session_id, 'B00001', 'like', 'ra_1').status_code == 200
    assert ra.call_count == 1


# ---------------------------------------------------------------------------
# 3. Buildings existence check skip / rejection
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExistenceCheckSkip:

    def test_pool_id_skips_buildings_query(self, auth_client, user_profile):
        project, session_id = _create_session(auth_client, user_profile, 'Skip Pool')
        assert 'B00005' in AnalysisSession.objects.get(session_id=session_id).pool_ids
        conn, cursor = _existence_conn(found=False)  # would 404 if consulted
        with patch(f'{_SWIPE_SERVICE}.connections', conn):
            resp = _swipe(auth_client, session_id, 'B00005', 'like', 'skip_1')
        assert resp.status_code == 200
        assert cursor.execute.call_count == 0

    def test_unknown_id_still_checked_and_rejected(self, auth_client, user_profile):
        project, session_id = _create_session(auth_client, user_profile, 'Reject Unknown')
        conn, cursor = _existence_conn(found=False)
        with patch(f'{_SWIPE_SERVICE}.connections', conn):
            resp = _swipe(auth_client, session_id, 'NOPE999', 'like', 'skip_2')
        assert resp.status_code == 404
        assert resp.json() == {'detail': 'building not found'}
        assert cursor.execute.call_count == 1

    def test_client_seed_in_pool_is_still_checked(self, auth_client, user_profile):
        project, session_id = _create_session(auth_client, user_profile, 'Seed Checked')
        AnalysisSession.objects.filter(session_id=session_id).update(
            pool_ids=['BOGUS01', 'B00001'], original_seed_ids=['BOGUS01'],
        )
        conn, cursor = _existence_conn(found=False)
        with patch(f'{_SWIPE_SERVICE}.connections', conn):
            resp = _swipe(auth_client, session_id, 'BOGUS01', 'like', 'skip_3')
        assert resp.status_code == 404
        assert cursor.execute.call_count == 1

    def test_client_buffered_exposed_id_is_still_checked(self, auth_client, user_profile):
        project, session_id = _create_session(auth_client, user_profile, 'Buffer Checked')
        AnalysisSession.objects.filter(session_id=session_id).update(exposed_ids=['BUF0001'])
        conn, cursor = _existence_conn(found=False)
        with patch(f'{_SWIPE_SERVICE}.connections', conn):
            resp = _swipe(auth_client, session_id, 'BUF0001', 'like', 'skip_4')
        assert resp.status_code == 404
        assert cursor.execute.call_count == 1


# ---------------------------------------------------------------------------
# 4. HNSW iterative scan as a buildings-connection startup option
# ---------------------------------------------------------------------------

def _fresh_settings_module():
    """Re-execute config/settings.py from disk.

    backend/conftest.py rewrites settings.DATABASES to SQLite for DB tests, so
    the live settings object may not reflect what production would load.
    """
    import importlib.util
    import config.settings as mod
    spec = importlib.util.spec_from_file_location('_settings_probe', mod.__file__)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


class TestHnswStartupOption:

    def test_buildings_alias_sets_iterative_scan_at_startup(self):
        dbs = _fresh_settings_module().DATABASES
        options = dbs['buildings']['OPTIONS']
        assert 'hnsw.iterative_scan=strict_order' in options['options']
        # merged with, not replacing, the existing sslmode option
        assert 'sslmode' in options

    def test_default_alias_has_no_hnsw_option(self):
        dbs = _fresh_settings_module().DATABASES
        assert 'options' not in dbs['default']['OPTIONS']
        assert 'hnsw' not in str(dbs['default'])

    def test_engine_has_no_per_query_hnsw_wrapper(self):
        assert not hasattr(engine, 'hnsw_topk_scan')
