"""PERF-ROUND2 item 6 -- Server-Timing middleware."""
import re
import threading
from unittest.mock import patch

import pytest
from django.db.utils import ConnectionHandler
from django.http import HttpResponse
from django.test import RequestFactory

import apps.recommendation.views  # noqa: F401 -- import-order guard (services<->views cycle when run alone)
from config.middleware import ServerTimingMiddleware

_HEADER_RE = re.compile(
    r'^total;dur=(?P<total>[\d.]+), db;dur=(?P<db>[\d.]+), dbq;desc="(?P<n>\d+) queries"$'
)


@pytest.fixture
def dbs(django_db_blocker):
    """Two real (SQLite in-memory) Django connection aliases behind a real
    ConnectionHandler, swapped into the middleware -- no Postgres needed, and
    connections stay per-thread exactly like django.db.connections."""
    handler = ConnectionHandler({
        alias: {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
        for alias in ('default', 'buildings')
    })
    # pytest-django blocks DB access globally; these are throwaway SQLite handles.
    with django_db_blocker.unblock(), patch('config.middleware.connections', handler):
        yield handler
        handler.close_all()


def _query(handler, alias):
    with handler[alias].cursor() as cur:
        cur.execute('SELECT 1')
        cur.fetchall()


def test_api_response_has_header_covering_all_aliases(dbs):
    def view(request):
        _query(dbs, 'default')
        _query(dbs, 'buildings')
        _query(dbs, 'buildings')
        return HttpResponse('ok')

    resp = ServerTimingMiddleware(view)(RequestFactory().get('/api/v1/anything/'))
    m = _HEADER_RE.match(resp['Server-Timing'])
    assert m, resp['Server-Timing']
    assert int(m['n']) == 3
    assert float(m['total']) >= float(m['db']) >= 0.0


def test_non_api_path_untouched():
    resp = ServerTimingMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/admin/'))
    assert 'Server-Timing' not in resp


def test_view_without_queries_reports_zero():
    resp = ServerTimingMiddleware(lambda r: HttpResponse('ok'))(RequestFactory().get('/api/x/'))
    m = _HEADER_RE.match(resp['Server-Timing'])
    assert m and int(m['n']) == 0 and float(m['db']) == 0.0


def test_failed_statement_still_counted(dbs):
    def view(request):
        try:
            with dbs['default'].cursor() as cur:
                cur.execute('SELECT * FROM table_that_does_not_exist_xyz')
        except Exception:
            pass
        return HttpResponse('ok')

    resp = ServerTimingMiddleware(view)(RequestFactory().get('/api/x/'))
    assert int(_HEADER_RE.match(resp['Server-Timing'])['n']) == 1


def test_fail_open_when_wrapper_install_breaks():
    with patch('config.middleware.connections') as fake:
        fake.all.side_effect = RuntimeError('boom')
        resp = ServerTimingMiddleware(lambda r: HttpResponse('body', status=201))(
            RequestFactory().get('/api/x/'))
    assert resp.status_code == 201 and resp.content == b'body'
    assert _HEADER_RE.match(resp['Server-Timing'])   # still reports total/db=0


def test_existing_server_timing_header_is_preserved():
    def view(request):
        r = HttpResponse('ok')
        r['Server-Timing'] = 'app;dur=1'
        return r
    resp = ServerTimingMiddleware(view)(RequestFactory().get('/api/x/'))
    assert resp['Server-Timing'].startswith('app;dur=1, total;dur=')


def test_per_request_state_is_isolated_across_threads(dbs):
    """Concurrent requests on different threads report their OWN query counts."""
    n_threads = 6
    barrier = threading.Barrier(n_threads)
    counts = {}
    errors = []

    def run(idx):
        try:
            def view(request):
                barrier.wait(timeout=10)          # all requests in flight together
                for _ in range(idx + 1):
                    _query(dbs, 'default')
                barrier.wait(timeout=10)
                return HttpResponse('ok')
            resp = ServerTimingMiddleware(view)(RequestFactory().get('/api/x/'))
            counts[idx] = int(_HEADER_RE.match(resp['Server-Timing'])['n'])
        except Exception as exc:   # noqa: BLE001
            errors.append(exc)
        finally:
            dbs.close_all()

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    assert counts == {i: i + 1 for i in range(n_threads)}


def test_cors_exposes_server_timing():
    from django.conf import settings
    assert 'server-timing' in [h.lower() for h in settings.CORS_EXPOSE_HEADERS]
    mw = list(settings.MIDDLEWARE)
    assert mw[mw.index('config.middleware.ServerTimingMiddleware') - 1] == \
        'corsheaders.middleware.CorsMiddleware'


def test_real_api_response_carries_header(api_client):
    resp = api_client.get('/api/v1/analysis/sessions/00000000-0000-0000-0000-000000000000/result/')
    assert resp.status_code in (401, 403, 404)
    assert _HEADER_RE.match(resp['Server-Timing'])
