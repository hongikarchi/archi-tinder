"""RecommendationConfig.ready starts the prewarm thread only for a serving runserver."""
from unittest import mock

import pytest
from django.apps import apps

TARGET = 'apps.recommendation.prewarm.start_prewarm_thread'


def _run_ready(argv, env):
    cfg = apps.get_app_config('recommendation')
    with mock.patch('sys.argv', argv), mock.patch.dict('os.environ', env, clear=False), \
            mock.patch(TARGET) as start:
        cfg.ready()
    return start


@pytest.fixture(autouse=True)
def _clear_run_main(monkeypatch):
    monkeypatch.delenv('RUN_MAIN', raising=False)


def test_runserver_reloader_child_starts():
    assert _run_ready(['manage.py', 'runserver'], {'RUN_MAIN': 'true'}).called


def test_runserver_noreload_starts():
    assert _run_ready(['manage.py', 'runserver', '--noreload'], {}).called


def test_runserver_reloader_parent_skipped():
    assert not _run_ready(['manage.py', 'runserver'], {}).called


@pytest.mark.parametrize('argv', [['manage.py', 'migrate'], ['pytest'], ['manage.py', 'collectstatic']])
def test_other_commands_skipped(argv):
    assert not _run_ready(argv, {'RUN_MAIN': 'true'}).called


def test_failure_never_raises():
    cfg = apps.get_app_config('recommendation')
    with mock.patch('sys.argv', ['manage.py', 'runserver', '--noreload']), \
            mock.patch(TARGET, side_effect=RuntimeError('boom')):
        cfg.ready()
