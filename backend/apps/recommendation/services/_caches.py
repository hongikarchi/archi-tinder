"""
_caches.py -- Context-caching helpers.

IMP-5 (Spec v1.5 §11.1): Gemini explicit context caching for chat-phase prompt.
IMP-6 (Spec v1.10 §11.1) Commit 1: V_initial cache for late-binding.

Cross-module symbol access uses the late-bound package reference (_svc) so that
mock.patch('apps.recommendation.services.X') continues to work in tests.
"""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache as django_cache
from google.genai import types

logger = logging.getLogger('apps.recommendation')

# ---------------------------------------------------------------------------
# IMP-5 (Spec v1.5 §11.1): Gemini explicit context caching
# ---------------------------------------------------------------------------
# Content-hash suffix ensures cache name uniquely identifies this prompt version.
# Recomputed at import time (constant for a given deployment).
_CACHE_NAME_PREFIX = 'archi-tinder-chat'

# ---------------------------------------------------------------------------
# IMP-6 (Spec v1.10 §11.1) Commit 1: V_initial cache for late-binding
# ---------------------------------------------------------------------------
_V_INITIAL_CACHE_KEY_PREFIX = 'v_initial'
_V_INITIAL_CACHE_TTL_SECONDS = 3600  # 1h -- typical user session length


def _get_prompt_hash():
    """Return 8-char hex prefix of SHA-256 of _CHAT_PHASE_SYSTEM_PROMPT.

    Called lazily (at function-call time) via the late-bound services reference
    to avoid a circular import: _caches.py is loaded before parse_query.py
    which owns _CHAT_PHASE_SYSTEM_PROMPT.
    """
    # Late-bound import: services package is fully initialised by call time.
    from apps.recommendation import services as _svc  # noqa: PLC0415
    return hashlib.sha256(_svc._CHAT_PHASE_SYSTEM_PROMPT.encode('utf-8')).hexdigest()[:8]


def _get_cache_name():
    """Full Gemini cache display_name: 'archi-tinder-chat-{hash8}'."""
    return f'{_CACHE_NAME_PREFIX}-{_get_prompt_hash()}'


def _get_django_cache_key():
    """Django cache key for storing the Gemini cache resource name across requests."""
    return f'gemini_cache_name:{_get_cache_name()}'


def _ensure_chat_cache(client):
    """
    IMP-5: Ensure a Gemini context cache for _CHAT_PHASE_SYSTEM_PROMPT exists
    and return its resource name (e.g. 'cachedContents/abc123').

    Lookup order:
      1. Django cache (fast path -- avoids Gemini API round-trip per request)
      2. Gemini caches.create() -- first call per process / after TTL expiry

    Returns str (Gemini cache resource name) on success.
    Returns None on any failure -- callers fall back to uncached path silently.

    Design notes:
    - No module-level global for the resource name: Django cache is the
      single source of truth, allowing multi-worker deploys (with Redis) to
      share the resource name without per-worker re-creation.
    - TTL invariant: Django cache TTL = 80% of Gemini cache TTL. This ensures
      Django cache expires BEFORE Gemini cache so _ensure_chat_cache recreates
      the Gemini cache entry before generate_content ever receives a stale name.
      The 20% safety window absorbs SDK clock drift and network jitter.
    - 404 recovery: retained as defense-in-depth for the residual edge case
      (SDK clock drift beyond the 20% window). On 404 the Django entry is
      evicted and a fresh Gemini cache is created.
    """
    from apps.recommendation import services as _svc  # noqa: PLC0415

    rc = settings.RECOMMENDATION
    ttl = rc.get('context_caching_ttl_seconds', 3600)
    django_key = _get_django_cache_key()

    # --- Fast path: resource name already in Django cache --------------------
    cached_name = django_cache.get(django_key)
    if cached_name:
        return cached_name

    # --- Slow path: create Gemini cache and store name in Django cache -------
    try:
        cache_obj = client.caches.create(
            model='gemini-2.5-flash',
            config=types.CreateCachedContentConfig(
                display_name=_get_cache_name(),
                system_instruction=_svc._CHAT_PHASE_SYSTEM_PROMPT,
                ttl=f'{ttl}s',
            ),
        )
        resource_name = cache_obj.name
        # Django cache TTL = 80% of Gemini TTL -- recreate before Gemini expiry to avoid
        # the stale-name-passed-to-generate_content double-retry pattern. The 20% safety
        # window absorbs SDK clock drift + network jitter.
        django_cache.set(django_key, resource_name, timeout=int(ttl * 0.8))
        logger.info('IMP-5: created Gemini context cache: %s', resource_name)
        return resource_name
    except Exception as e:
        logger.warning('IMP-5: failed to create Gemini context cache: %s: %s', type(e).__name__, e)
        return None


def _v_initial_cache_key(user_id, raw_query):
    """IMP-6: Django cache key for late-bound V_initial vector.

    Format: 'v_initial:{user_id}:{sha256(raw_query)[:16]}'
    Uses first 16 hex chars of SHA-256 so different queries produce different keys
    while keeping the key compact (64-bit collision resistance >> session count).
    """
    qhash = hashlib.sha256((raw_query or '').encode('utf-8')).hexdigest()[:16]
    return f'{_V_INITIAL_CACHE_KEY_PREFIX}:{user_id}:{qhash}'


def get_cached_v_initial(user_id, raw_query):
    """IMP-6: Read V_initial from Django cache. Returns None on miss or flag OFF.

    Called by SessionCreateView.post() when stage_decouple_enabled=True.
    Returns the cached 384-dim float list, or None (triggers filter-only pool).
    """
    if not settings.RECOMMENDATION.get('stage_decouple_enabled', False):
        return None
    return django_cache.get(_v_initial_cache_key(user_id, raw_query))


def set_cached_v_initial(user_id, raw_query, v_initial_vector):
    """IMP-6: Store V_initial in Django cache for subsequent SessionCreate read.

    Called by Stage 2 async thread (Commit 2) after visual_description embedding.
    No-op when stage_decouple_enabled=False (default).
    """
    if not settings.RECOMMENDATION.get('stage_decouple_enabled', False):
        return
    django_cache.set(
        _v_initial_cache_key(user_id, raw_query),
        v_initial_vector,
        timeout=_V_INITIAL_CACHE_TTL_SECONDS,
    )
