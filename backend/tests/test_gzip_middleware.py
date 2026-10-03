"""PERF-MISC-1 (d): ApiGZipMiddleware -- gzip JSON >= 1 KB, never SSE / auth / small."""
import gzip
import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.test import RequestFactory

from config.middleware import ApiGZipMiddleware, ServerTimingMiddleware

GZ = {'HTTP_ACCEPT_ENCODING': 'gzip, deflate'}


def _big_json():
    return JsonResponse({'results': [{'canonical_bld_id': f'bld_{i:06d}', 'name': 'x' * 40} for i in range(60)]})


def _run(response_factory, path='/api/v1/sessions/abc/result/', headers=GZ):
    mw = ApiGZipMiddleware(lambda request: response_factory())
    return mw(RequestFactory().get(path, **headers))


class TestApiGZipMiddleware:

    def test_large_json_is_compressed_and_roundtrips(self):
        plain = _big_json().content
        assert len(plain) > 1024
        resp = _run(_big_json)
        assert resp['Content-Encoding'] == 'gzip'
        assert 'Accept-Encoding' in resp['Vary']
        assert len(resp.content) < len(plain)
        assert json.loads(gzip.decompress(resp.content)) == json.loads(plain)

    def test_small_json_untouched(self):
        resp = _run(lambda: JsonResponse({'ok': True, 'pad': 'x' * 300}))  # 200 B < n < 1 KB
        assert not resp.has_header('Content-Encoding')

    def test_exactly_below_threshold_untouched_and_at_threshold_compressed(self):
        below = ApiGZipMiddleware.min_length - 1
        resp = _run(lambda: HttpResponse(b'a' * below, content_type='application/json'))
        assert not resp.has_header('Content-Encoding')
        resp = _run(lambda: HttpResponse(b'a' * ApiGZipMiddleware.min_length, content_type='application/json'))
        assert resp['Content-Encoding'] == 'gzip'

    def test_sse_streaming_response_never_compressed(self):
        def _sse():
            return StreamingHttpResponse(
                (f'event: x\ndata: {"y" * 2000}\n\n'.encode() for _ in range(3)),
                content_type='text/event-stream',
            )
        resp = _run(_sse, path='/api/v1/parse-query/stream/')
        assert not resp.has_header('Content-Encoding')
        assert resp['Content-Type'] == 'text/event-stream'
        # still incremental: the three chunks come through unmodified
        assert len(list(resp.streaming_content)) == 3

    def test_non_streaming_event_stream_content_type_never_compressed(self):
        resp = _run(lambda: HttpResponse(b'data: ' + b'z' * 5000, content_type='text/event-stream'))
        assert not resp.has_header('Content-Encoding')

    def test_streaming_json_never_compressed(self):
        resp = _run(lambda: StreamingHttpResponse([b'{"a":"' + b'x' * 3000 + b'"}'], content_type='application/json'))
        assert not resp.has_header('Content-Encoding')

    def test_auth_endpoints_never_compressed(self):
        for path in ('/api/v1/auth/social/google/', '/api/v1/auth/token/refresh/',
                     '/api/v1/auth/login/', '/api/v1/auth/guest/'):
            resp = _run(_big_json, path=path)
            assert not resp.has_header('Content-Encoding'), path

    def test_non_json_never_compressed(self):
        resp = _run(lambda: HttpResponse('<html>' + 'x' * 3000, content_type='text/html'))
        assert not resp.has_header('Content-Encoding')

    def test_client_without_gzip_support_untouched(self):
        resp = _run(_big_json, headers={})
        assert not resp.has_header('Content-Encoding')

    def test_server_timing_wraps_gzip(self):
        """Server-Timing (outer) still adds its header on a compressed response."""
        mw = ServerTimingMiddleware(ApiGZipMiddleware(lambda request: _big_json()))
        resp = mw(RequestFactory().get('/api/v1/sessions/abc/result/', **GZ))
        assert resp['Content-Encoding'] == 'gzip'
        assert 'total;dur=' in resp['Server-Timing']


class TestMiddlewareOrdering:

    def test_registered_after_server_timing_before_common(self):
        mw = settings.MIDDLEWARE
        i_timing = mw.index('config.middleware.ServerTimingMiddleware')
        i_gzip = mw.index('config.middleware.ApiGZipMiddleware')
        assert i_timing < i_gzip < mw.index('django.middleware.common.CommonMiddleware')
