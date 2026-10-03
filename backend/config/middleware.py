"""Request-level middleware.

ServerTimingMiddleware (PERF-ROUND2 item 6): adds an HTTP ``Server-Timing`` header
to every ``/api/`` response so client-vs-server time can be attributed exactly:

    Server-Timing: total;dur=41.2, db;dur=12.7, dbq;desc="9 queries"

- ``total`` -- wall time of everything inside this middleware (inner middleware,
  auth, view, serialization, ``transaction.on_commit`` callbacks that fire inside the
  request). Registered right after CorsMiddleware so it covers all other middleware.
- ``db``    -- summed SQL execution time across EVERY connection alias in use
  (``default`` and ``buildings``), measured with ``connection.execute_wrapper``.
  Excludes the driver's implicit BEGIN/COMMIT and the pool/CONN_HEALTH_CHECKS liveness check
  (both bypass ``execute_wrapper``), so it is statement time only.
- ``dbq``   -- number of statements that went through the wrapper.

Thread-safety: all state lives in a per-request ``_Timing`` object captured by the
wrapper closure -- no module globals. ``django.db.connections`` is per-thread, so the
wrappers are installed only on THIS request thread's connection objects; background
threads a request spawns (prefetch / telemetry) get their own connections and never
leak queries into this request's totals.

Fail-open: any error while installing wrappers or building the header is swallowed
(logged at debug); the response is never altered or blocked because of measurement.
"""
import logging
import time
from contextlib import ExitStack

from django.db import connections
from django.middleware.gzip import GZipMiddleware

logger = logging.getLogger('apps.recommendation')

API_PREFIX = '/api/'


class _Timing:
    __slots__ = ('db_seconds', 'db_queries')

    def __init__(self):
        self.db_seconds = 0.0
        self.db_queries = 0

    def wrapper(self, execute, sql, params, many, context):
        t0 = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:  # failed statements still cost time
            self.db_seconds += time.perf_counter() - t0
            self.db_queries += 1


class ServerTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(API_PREFIX):
            return self.get_response(request)

        t0 = time.perf_counter()
        timing = _Timing()
        stack = ExitStack()
        try:
            for conn in connections.all():
                stack.enter_context(conn.execute_wrapper(timing.wrapper))
        except Exception as exc:  # noqa: BLE001 -- measurement must never break a request
            logger.debug('ServerTimingMiddleware: wrapper install failed: %s', exc)

        try:
            response = self.get_response(request)
        finally:
            try:
                stack.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug('ServerTimingMiddleware: wrapper teardown failed: %s', exc)

        try:
            total_ms = (time.perf_counter() - t0) * 1000.0
            value = (
                f'total;dur={total_ms:.1f}, '
                f'db;dur={timing.db_seconds * 1000.0:.1f}, '
                f'dbq;desc="{timing.db_queries} queries"'
            )
            existing = response.get('Server-Timing')
            response['Server-Timing'] = f'{existing}, {value}' if existing else value
        except Exception as exc:  # noqa: BLE001
            logger.debug('ServerTimingMiddleware: header build failed: %s', exc)
        return response


class ApiGZipMiddleware(GZipMiddleware):
    """gzip for JSON API responses only (PERF-MISC-1 item d).

    Django's stock GZipMiddleware is too broad for this API, so this subclass
    compresses a response ONLY when ALL of these hold (otherwise it is returned
    untouched):

    - not a streaming response -- SSE (``text/event-stream``, the parse-query
      stream) must be delivered incrementally; gzip would buffer it.
      ``response.streaming`` is the primary guard, the content-type check is a
      belt-and-braces for any non-streaming event-stream response.
    - ``Content-Type`` is ``application/json`` (never HTML/static/images).
    - path is not under ``/api/v1/auth/`` -- those responses carry access/refresh
      tokens next to attacker-influenced reflected data; compressing secrets that
      share a body with reflected input is the BREACH pattern. Every token-issuing
      endpoint lives under that prefix (apps/accounts/urls.py).
    - body >= ``min_length`` (1 KB): below that the gzip header + CPU outweigh
      the saving (stock Django's floor is only 200 bytes).

    Register in MIDDLEWARE right after ServerTimingMiddleware (so Server-Timing's
    ``total`` still covers compression) and before CommonMiddleware.
    """

    min_length = 1024
    no_compress_prefixes = ('/api/v1/auth/',)

    def process_response(self, request, response):
        if response.streaming:
            return response
        content_type = (response.get('Content-Type') or '').split(';')[0].strip().lower()
        if content_type != 'application/json':  # also excludes text/event-stream
            return response
        if request.path.startswith(self.no_compress_prefixes):
            return response
        if len(response.content) < self.min_length:
            return response
        return super().process_response(request, response)
