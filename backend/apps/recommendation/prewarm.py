"""Per-worker pre-warm (PERF-MISC-1 item c).

First-request spikes measured locally: corpus tag stats ~2 s cold, axis vocab
load made the first parse-query 8.4 s. Each gunicorn worker is a fresh process
(no --preload), so every worker pays those once. ``run_prewarm`` pays them at
boot instead, off the request path.

Wired from ``backend/gunicorn.conf.py`` (``post_worker_init`` -> the app is
loaded, we are inside the worker process) which calls ``start_prewarm_thread``.
It is NOT an AppConfig.ready() hook on purpose: ready() also runs for
``collectstatic`` (Railway buildCommand), every manage.py command and pytest's
django.setup(), none of which should open DB connections.

Guarantees:
- Never raises (every step has its own try/except; one failing step does not
  skip the rest) -- a warm-up problem must never break boot.
- No paid calls: LLM clients are only CONSTRUCTED (no request is sent).
- Closes every DB connection the thread opened (``connections.close_all()`` in
  ``finally``; with the psycopg pool a missed close would leak a pool slot).
- Disable-able: env ``PREWARM_ENABLED=false`` (settings.PREWARM_ENABLED, which is
  also forced False under pytest).
"""
import logging
import threading
import time

from django.conf import settings
from django.db import connections

logger = logging.getLogger('apps.recommendation')


def _step_imports():
    """Import the heavy modules request handlers import lazily: the whole URLconf
    (views -> engine -> sklearn/numpy, services, parse_query)."""
    import importlib
    importlib.import_module(settings.ROOT_URLCONF)
    importlib.import_module('apps.recommendation.engine')   # sklearn.cluster / silhouette
    importlib.import_module('apps.recommendation.views')


def _step_axis_vocab():
    from apps.recommendation import services
    services.get_axis_vocab()  # parse_query's vocab prompt block + snap-to-vocab


def _step_corpus_tag_df():
    from apps.recommendation import caches
    caches.get_corpus_tag_df()  # search_by_filters_scored IDF weights


def _step_random_pool():
    from apps.recommendation import engine
    engine._random_pool(1)  # fills the per-process publishable-id list cache


def _step_llm_clients():
    """Construct (not call) the provider client singletons when a key is configured."""
    from apps.recommendation import services
    if settings.LLM_PROVIDER == 'openai':
        if settings.OPENAI_API_KEY:
            services._get_client()
    elif settings.GEMINI_API_KEY:
        services._get_client()
    if settings.GEMINI_API_KEY:
        services._get_gemini_client()  # image path is Gemini-pinned regardless of provider


_STEPS = (
    ('imports', _step_imports),
    ('axis_vocab', _step_axis_vocab),
    ('corpus_tag_df', _step_corpus_tag_df),
    ('random_pool', _step_random_pool),
    ('llm_clients', _step_llm_clients),
)


def run_prewarm():
    """Run every warm-up step. Returns {step_name: 'ok' | 'error: ...'}. Never raises."""
    results = {}
    t_all = time.perf_counter()
    try:
        for name, fn in _STEPS:
            t0 = time.perf_counter()
            try:
                fn()
                results[name] = 'ok'
                logger.info('prewarm: %s ok (%.0f ms)', name, (time.perf_counter() - t0) * 1000)
            except Exception as exc:  # noqa: BLE001 -- warm-up must never break boot
                results[name] = f'error: {type(exc).__name__}: {str(exc)[:120]}'
                logger.warning('prewarm: %s failed (%s: %s)', name, type(exc).__name__, exc)
    finally:
        try:
            connections.close_all()  # return pooled connections held by this thread
        except Exception as exc:  # noqa: BLE001
            logger.warning('prewarm: close_all failed: %s', exc)
    logger.info('prewarm: done in %.0f ms', (time.perf_counter() - t_all) * 1000)
    return results


def start_prewarm_thread():
    """Pre-import the app modules (sync), then run the DB/network warm-up on a daemon
    thread (a slow Neon connect must not delay the worker becoming ready).
    Returns the Thread, or None when disabled."""
    if not getattr(settings, 'PREWARM_ENABLED', False):
        logger.info('prewarm: disabled (PREWARM_ENABLED is false)')
        return None
    # Import the URLconf/views SYNCHRONOUSLY, before the worker accepts requests:
    # the view modules have circular imports (views <-> session_service <->
    # swipe_service) that are only safe single-threaded -- a first request racing
    # this thread's import could observe a half-initialised module. Everything else
    # (DB / network warm-up) is order-independent and runs on the thread.
    try:
        _step_imports()
    except Exception as exc:  # noqa: BLE001
        logger.warning('prewarm: imports failed (%s: %s)', type(exc).__name__, exc)
    thread = threading.Thread(target=run_prewarm, name='prewarm', daemon=True)
    thread.start()
    return thread
