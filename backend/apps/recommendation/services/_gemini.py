"""
_gemini.py -- Low-level Gemini API client wrapper and retry logic.

Self-contained: no imports from sibling sub-modules.
"""
import logging
import time

from django.conf import settings
from google import genai
from google.api_core import exceptions as gax_exceptions

logger = logging.getLogger('apps.recommendation')

_client = None

_GEMINI_MAX_RETRIES = 1
_GEMINI_RETRY_DELAY = 1.0  # seconds

# Permanent errors — retry provides no benefit; fast-fail immediately.
# 403/401/400/404 indicate a config or auth issue that won't resolve on retry.
_FATAL_GEMINI_EXC = (
    gax_exceptions.PermissionDenied,   # 403
    gax_exceptions.Unauthenticated,    # 401
    gax_exceptions.InvalidArgument,    # 400
    gax_exceptions.NotFound,           # 404
)


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _retry_gemini_call(func, *args, **kwargs):
    """
    Execute a Gemini API call with one retry on transient failure.

    Permanent errors (4xx auth/permission/invalid) fast-fail immediately —
    retry cannot help and would waste 30-40 s of SDK timeout per attempt.
    Transient errors (5xx, ResourceExhausted, unknown) get one retry after
    _GEMINI_RETRY_DELAY seconds.

    Returns the result on success, raises on final failure.
    """
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except _FATAL_GEMINI_EXC as e:
            logger.warning(
                'Gemini API permanent error (no retry): %s: %s',
                type(e).__name__, str(e),
            )
            raise
        except Exception as e:
            logger.warning(
                'Gemini API call failed (attempt %d/%d): %s: %s',
                attempt + 1, _GEMINI_MAX_RETRIES + 1,
                type(e).__name__, str(e),
            )
            if attempt == _GEMINI_MAX_RETRIES:
                raise
            time.sleep(_GEMINI_RETRY_DELAY)
