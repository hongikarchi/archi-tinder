"""
_gemini.py -- Low-level Gemini API client wrapper and retry logic.

Self-contained: no imports from sibling sub-modules.
"""
import logging
import time

from django.conf import settings
from google import genai

logger = logging.getLogger('apps.recommendation')

_client = None

_GEMINI_MAX_RETRIES = 1
_GEMINI_RETRY_DELAY = 1.0  # seconds


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _retry_gemini_call(func, *args, **kwargs):
    """
    Execute a Gemini API call with one retry on failure.
    Logs the specific error on each attempt.
    Returns the result on success, raises on final failure.
    """
    last_error = None
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(
                'Gemini API call failed (attempt %d/%d): %s: %s',
                attempt + 1, _GEMINI_MAX_RETRIES + 1,
                type(e).__name__, str(e),
            )
            if attempt < _GEMINI_MAX_RETRIES:
                time.sleep(_GEMINI_RETRY_DELAY)
    raise last_error
