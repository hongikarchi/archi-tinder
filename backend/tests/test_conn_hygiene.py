"""PERF-CONN-1 -- persistent buildings connections + background-thread hygiene.

With CONN_MAX_AGE > 0 Django keeps one connection per THREAD per alias, so every
short-lived thread that touches the DB must connections.close_all() in a finally.
All tests are DB-free: django.db.connections is mocked, and each thread entry point
is driven directly (synchronously) with a BaseException as the "work raises" case so
the assertion proves the close sits in a `finally`, not in an `except Exception`.
"""
import importlib.util
from unittest.mock import MagicMock, patch

import pytest

import apps.recommendation.views  # noqa: F401 -- import-order guard (services<->views cycle when run alone)


def _fresh_settings_module():
    """Re-execute config/settings.py from disk (conftest rewrites live DATABASES)."""
    import config.settings as mod
    spec = importlib.util.spec_from_file_location('_settings_probe_conn', mod.__file__)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


class TestBuildingsPersistentConnection:

    def test_buildings_conn_max_age_and_health_checks(self):
        bldg = _fresh_settings_module().DATABASES['buildings']
        assert bldg['CONN_MAX_AGE'] == 600
        assert bldg['CONN_HEALTH_CHECKS'] is True

    def test_buildings_matches_default_alias_persistence(self):
        dbs = _fresh_settings_module().DATABASES
        assert dbs['buildings']['CONN_MAX_AGE'] == dbs['default']['CONN_MAX_AGE']
        assert dbs['buildings']['CONN_HEALTH_CHECKS'] == dbs['default']['CONN_HEALTH_CHECKS']

    def test_options_keep_sslmode_and_hnsw_startup_option(self):
        options = _fresh_settings_module().DATABASES['buildings']['OPTIONS']
        assert 'sslmode' in options
        assert '-c hnsw.iterative_scan=strict_order' in options['options']

    def test_hnsw_option_appears_exactly_once(self):
        mod = _fresh_settings_module()
        opts = mod.DATABASES['buildings']['OPTIONS']
        assert opts['options'].count('hnsw.iterative_scan') == 1


class _Boom(BaseException):
    """Bypasses every `except Exception` so only a `finally` can run cleanup."""


def _assert_closed(mock_conns):
    assert mock_conns.close_all.call_count >= 1


class TestBackgroundThreadsCloseConnections:

    def test_emit_telemetry_thread_closes_on_raise(self):
        from apps.recommendation.views import swipe
        with patch('django.db.connections') as conns, \
                patch.object(swipe.event_log, 'emit_swipe_event', side_effect=_Boom):
            with pytest.raises(_Boom):
                swipe._emit_telemetry_thread({}, None)
        _assert_closed(conns)

    def test_emit_telemetry_thread_closes_on_success(self):
        from apps.recommendation.views import swipe
        with patch('django.db.connections') as conns, \
                patch.object(swipe.event_log, 'emit_swipe_event'):
            swipe._emit_telemetry_thread({}, None)
        _assert_closed(conns)

    def test_async_prefetch_thread_closes_on_raise(self):
        from apps.recommendation.views import swipe
        with patch('django.db.connections') as conns, \
                patch.object(swipe.engine, 'farthest_point_from_pool', side_effect=_Boom):
            with pytest.raises(_Boom):
                swipe._async_prefetch_thread(
                    'sid', 1, 'exploring', ['a', 'b'], [], None, [], [], 0,
                )
        _assert_closed(conns)

    def test_spawn_stage2_thread_closes_on_raise(self):
        from apps.recommendation.views import search
        captured = {}

        class _CapThread:
            def __init__(self, target=None, **kw):
                captured['target'] = target

            def start(self):
                pass

        with patch.object(search.threading, 'Thread', _CapThread):
            search._spawn_stage2({}, 'q', 1)
        assert 'target' in captured

        with patch('django.db.connections.close_all') as close_all, \
                patch.object(search.services, 'generate_visual_description', side_effect=_Boom):
            with pytest.raises(_Boom):
                captured['target']()
        assert close_all.call_count >= 1

    def test_spawn_stage2_thread_closes_when_work_raises_exception(self):
        from apps.recommendation.views import search
        captured = {}

        class _CapThread:
            def __init__(self, target=None, **kw):
                captured['target'] = target

            def start(self):
                pass

        with patch.object(search.threading, 'Thread', _CapThread):
            search._spawn_stage2({}, 'q', 1)
        with patch('django.db.connections.close_all') as close_all, \
                patch.object(search.services, 'generate_visual_description',
                             side_effect=RuntimeError('llm down')):
            captured['target']()   # swallowed by the thread body
        assert close_all.call_count >= 1

    def test_parse_query_stream_worker_closes_on_raise(self):
        from apps.recommendation.views import search
        conns = MagicMock()
        with patch.object(search, '_db_connections', conns), \
                patch.object(search.services, 'parse_query', side_effect=_Boom):
            with pytest.raises(_Boom):
                search._stream_worker(lambda *a, **k: None, [], 'ko', None, 1)
        conns.close_all.assert_called()

    def test_parse_query_stream_worker_closes_and_emits_error_on_exception(self):
        from apps.recommendation.views import search
        conns = MagicMock()
        events = []
        with patch.object(search, '_db_connections', conns), \
                patch.object(search.services, 'parse_query', side_effect=RuntimeError('x')):
            search._stream_worker(lambda e, d: events.append(e), [], 'ko', None, 1)
        conns.close_all.assert_called()
        assert events[-1] == 'error'

    def test_board_name_thread_closes_on_raise(self):
        from apps.recommendation.services import session_service
        with patch('django.db.connections') as conns, \
                patch.object(session_service.services, '_gemini_board_name_raw', side_effect=_Boom):
            with pytest.raises(_Boom):
                session_service._async_board_name_update(1, 'fb', {}, 'q', 1)
        _assert_closed(conns)

    def test_works_process_thread_closes_on_raise(self):
        from apps.works import services as works_services
        with patch('django.db.connections') as conns, \
                patch.object(works_services, '_do_process_work', side_effect=_Boom):
            with pytest.raises(_Boom):
                works_services._process_work(1)
        _assert_closed(conns)

    def test_works_process_thread_closes_when_work_raises_exception(self):
        from apps.works import services as works_services
        with patch('django.db.connections') as conns, \
                patch.object(works_services, '_do_process_work', side_effect=RuntimeError('x')):
            works_services._process_work(1)
        _assert_closed(conns)
