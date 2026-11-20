import logging
import os
import sys

from django.apps import AppConfig

logger = logging.getLogger('apps.recommendation')


def _is_serving_runserver(argv=None, environ=None):
    """True only inside the process that actually serves requests under
    ``manage.py runserver``: the autoreloader child (RUN_MAIN=true) or a
    ``--noreload`` process. The reloader parent and every other command
    (migrate, collectstatic, shell, test, pytest) return False."""
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    if 'runserver' not in argv:
        return False
    return environ.get('RUN_MAIN') == 'true' or '--noreload' in argv


class RecommendationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recommendation'

    def ready(self):
        # Local dev has no gunicorn post_worker_init hook, so wire the prewarm
        # (Discovery candidate pool etc.) for `runserver` only. See prewarm.py.
        if not _is_serving_runserver():
            return
        try:
            from apps.recommendation.prewarm import start_prewarm_thread
            start_prewarm_thread()
        except Exception as exc:  # noqa: BLE001 -- never break boot
            logger.warning('prewarm: runserver start failed (%s: %s)', type(exc).__name__, exc)
