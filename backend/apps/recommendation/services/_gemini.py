"""
_gemini.py -- Low-level Gemini API client wrapper and retry logic.

Self-contained: no imports from sibling sub-modules.
"""
import logging
import queue
import time
from threading import Thread as _Thread

from django.conf import settings
from google import genai
from google.api_core import exceptions as gax_exceptions
from google.genai import errors as genai_errors

logger = logging.getLogger('apps.recommendation')

# `_Thread` captures the real `threading.Thread` class at module-load time
# so the timeout wrapper is immune to tests that mock `threading.Thread`
# globally (e.g. `_DiscThread` in test_imp8_async_prefetch.py). Without this
# capture, a leaked synchronous Thread mock would make hung Gemini calls
# return their value before the deadline can fire, breaking the timeout
# guarantee that production depends on.

_client = None

_GEMINI_MAX_RETRIES = 1
_GEMINI_RETRY_DELAY = 1.0  # seconds

# Permanent errors — retry provides no benefit; fast-fail immediately.
# 403/401/400/404 indicate a config or auth issue that won't resolve on retry.
# NOTE: the live google-genai SDK (v1.x, api_key backend) raises
# google.genai.errors.ClientError/ServerError with an HTTP .code — NOT the
# google.api_core.exceptions.* family. The gax tuple below is kept only for
# defensive/legacy compatibility; _is_fatal_gemini() handles BOTH families.
_FATAL_GEMINI_EXC = (
    gax_exceptions.PermissionDenied,   # 403
    gax_exceptions.Unauthenticated,    # 401
    gax_exceptions.InvalidArgument,    # 400
    gax_exceptions.NotFound,           # 404
)


def _is_fatal_gemini(e):
    """
    True if e is a permanent Gemini error that must NOT be retried.

    google-genai ClientError carries an HTTP .code: any 4xx is permanent
    EXCEPT 429 (rate limit — transient, should retry). ServerError (5xx) is
    transient. Falls back to the legacy gax tuple for non-google-genai paths.
    """
    if isinstance(e, genai_errors.ClientError):
        code = getattr(e, 'code', None)
        return code is not None and 400 <= code < 500 and code != 429
    return isinstance(e, _FATAL_GEMINI_EXC)


def _is_model_unavailable(e):
    """
    True if e signals the requested MODEL is unavailable/invalid (404 NotFound
    or 400 InvalidArgument) — the case where retrying with a fallback model
    helps. Excludes 401/403 (auth — a different model on the same key won't
    help). Recognises both the google-genai ClientError family and legacy gax.
    """
    if isinstance(e, genai_errors.ClientError):
        return getattr(e, 'code', None) in (400, 404)
    return isinstance(e, (gax_exceptions.NotFound, gax_exceptions.InvalidArgument))


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _retry_gemini_call(func, *args, timeout=15.0, **kwargs):
    """
    Execute a Gemini API call with one retry on transient failure.

    Permanent errors (4xx auth/permission/invalid) fast-fail immediately —
    retry cannot help and would waste 30-40 s of SDK timeout per attempt.
    Transient errors (5xx, ResourceExhausted, unknown) get one retry after
    _GEMINI_RETRY_DELAY seconds.

    timeout: hard wall-clock deadline in seconds for each attempt. Default 15s.
    On deadline expiry, raises TimeoutError (treated as transient — retried
    once, then re-raised on second failure). Callers that need longer
    deadlines (e.g. persona report generation) should pass timeout=N
    explicitly.

    Implementation: each attempt runs `func` in a daemon thread that pushes
    its result (or error) onto a Queue. The caller blocks on Queue.get with
    a timeout. Using Queue.get instead of Thread.is_alive avoids dependence
    on threading.Thread instance attributes — robust against test mocks that
    substitute Thread with a partial-API stand-in. Daemon threads also die
    with the process so a hung SDK call cannot block pytest or interpreter
    exit; the orphan worker exits naturally when the SDK call returns.

    Returns the result on success, raises on final failure.
    """
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        result_queue = queue.Queue(maxsize=1)

        def _runner():
            try:
                result_queue.put(('ok', func(*args, **kwargs)))
            except BaseException as e:
                result_queue.put(('err', e))

        _Thread(target=_runner, daemon=True).start()

        try:
            kind, value = result_queue.get(timeout=timeout)
        except queue.Empty:
            logger.warning(
                'Gemini API call timeout (attempt %d/%d) after %.1fs',
                attempt + 1, _GEMINI_MAX_RETRIES + 1, timeout,
            )
            if attempt == _GEMINI_MAX_RETRIES:
                raise TimeoutError(
                    f'Gemini call exceeded {timeout}s after '
                    f'{_GEMINI_MAX_RETRIES + 1} attempts'
                )
            time.sleep(_GEMINI_RETRY_DELAY)
            continue

        if kind == 'err':
            e = value
            if _is_fatal_gemini(e):
                logger.warning(
                    'Gemini API permanent error (no retry): %s: %s',
                    type(e).__name__, str(e),
                )
                raise e
            logger.warning(
                'Gemini API call failed (attempt %d/%d): %s: %s',
                attempt + 1, _GEMINI_MAX_RETRIES + 1,
                type(e).__name__, str(e),
            )
            if attempt == _GEMINI_MAX_RETRIES:
                raise e
            time.sleep(_GEMINI_RETRY_DELAY)
            continue

        return value


def generate_content_with_fallback(client, *, timeout=15.0, **kw):
    """
    Call client.models.generate_content with automatic model fallback.

    Uses settings.GEMINI_TEXT_MODEL as the primary model and
    settings.GEMINI_TEXT_MODEL_FALLBACK as the fallback.  Fallback fires when
    the primary model is unavailable/invalid (404 NotFound / 400 InvalidArgument
    — model not available in the API key tier or region). Recognises both the
    google-genai ClientError family and legacy gax errors via _is_model_unavailable.

    All keyword args (contents, config, etc.) are forwarded unchanged so the
    caller's timing block, config, and telemetry keep working as before.

    Returns the raw response object (same as _retry_gemini_call).

    NOTE: the retry is invoked through the services-package facade
    (_svc._retry_gemini_call), NOT the local name, on purpose. Existing tests
    patch 'apps.recommendation.services._retry_gemini_call' (the facade
    re-export). The facade binding and this module's local binding are DIFFERENT
    objects (FULL-REFACTOR-1 lesson: re-export preserves import, not mock.patch
    of a function name). Routing through the facade keeps every existing
    _retry_gemini_call mock seam live, exactly as the pre-wrapper direct call
    sites did.
    """
    from apps.recommendation import services as _svc
    primary = settings.GEMINI_TEXT_MODEL
    fb = settings.GEMINI_TEXT_MODEL_FALLBACK
    try:
        return _svc._retry_gemini_call(
            client.models.generate_content,
            model=primary,
            timeout=timeout,
            **kw,
        )
    except Exception as e:
        if _is_model_unavailable(e) and fb and fb != primary:
            logger.warning(
                'text model %s rejected (%s); fallback -> %s',
                primary, type(e).__name__, fb,
            )
            return _svc._retry_gemini_call(
                client.models.generate_content,
                model=fb,
                timeout=timeout,
                **kw,
            )
        raise
