"""Gunicorn config (PERF-MISC-1 item c). Loaded via `-c gunicorn.conf.py` in
railway.toml's startCommand.

Only the pre-warm hook lives here; workers/threads/bind/timeout stay on the
startCommand so the DB-connection math next to it in railway.toml stays visible.
"""


def post_worker_init(worker):
    """Runs inside each worker process AFTER the WSGI app (Django) is loaded.

    (`post_fork` runs BEFORE the app is loaded when --preload is off, so Django is
    not set up yet there -- hence this hook.) Spawns a daemon thread that warms
    caches / singletons; honours PREWARM_ENABLED; never raises into gunicorn.
    """
    try:
        from apps.recommendation.prewarm import start_prewarm_thread
        start_prewarm_thread()
    except Exception as exc:  # noqa: BLE001 -- never crash worker boot over a warm-up
        worker.log.warning('prewarm: could not start (%s: %s)', type(exc).__name__, exc)
