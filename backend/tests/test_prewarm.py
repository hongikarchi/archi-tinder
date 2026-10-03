"""PERF-MISC-1 (c): per-worker pre-warm."""
import importlib.util
import inspect
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import apps.recommendation.views  # noqa: F401 -- resolves services.* patch targets (circular-import-safe order)
from apps.recommendation import prewarm

BACKEND = Path(__file__).resolve().parent.parent

# Captured at collection time, before any test runs. Some older tests (test_imp8_async_prefetch)
# leave a fake `threading.Thread` patched globally; these tests need the real one
# (daemon thread assertions, subprocess.run's reader threads).
_REAL_THREAD = threading.Thread


@pytest.fixture(autouse=True)
def _real_threading_thread(monkeypatch):
    monkeypatch.setattr(threading, 'Thread', _REAL_THREAD)


TARGETS = {
    'axis_vocab': 'apps.recommendation.services.get_axis_vocab',
    'corpus_tag_df': 'apps.recommendation.caches.get_corpus_tag_df',
    'random_pool': 'apps.recommendation.engine._random_pool',
}


@pytest.fixture
def warm_mocks(settings):
    """Mock every warm target + close_all; yields a dict of the mocks."""
    settings.LLM_PROVIDER = 'gemini'
    settings.GEMINI_API_KEY = 'k'
    settings.OPENAI_API_KEY = ''
    patches = {name: patch(target) for name, target in TARGETS.items()}
    patches['client'] = patch('apps.recommendation.services._get_client')
    patches['gemini_client'] = patch('apps.recommendation.services._get_gemini_client')
    patches['imports'] = patch.object(prewarm, '_step_imports')
    patches['close'] = patch.object(prewarm.connections, 'close_all')
    started = {k: p.start() for k, p in patches.items()}
    # _STEPS holds function objects bound at import time -> rebuild with the mocked imports step.
    steps = patch.object(prewarm, '_STEPS', (
        ('imports', started['imports']),
        ('axis_vocab', prewarm._step_axis_vocab),
        ('corpus_tag_df', prewarm._step_corpus_tag_df),
        ('random_pool', prewarm._step_random_pool),
        ('llm_clients', prewarm._step_llm_clients),
    ))
    steps.start()
    yield started
    steps.stop()
    for p in patches.values():
        p.stop()


class TestRunPrewarm:

    def test_runs_every_step_and_closes_connections(self, warm_mocks):
        res = prewarm.run_prewarm()
        assert set(res.values()) == {'ok'}
        warm_mocks['axis_vocab'].assert_called_once_with()
        warm_mocks['corpus_tag_df'].assert_called_once_with()
        warm_mocks['random_pool'].assert_called_once()
        warm_mocks['client'].assert_called_once_with()          # constructed, never invoked
        warm_mocks['gemini_client'].assert_called_once_with()
        warm_mocks['close'].assert_called_once()

    def test_one_failing_step_does_not_skip_the_rest_and_never_raises(self, warm_mocks):
        warm_mocks['axis_vocab'].side_effect = RuntimeError('db down')
        warm_mocks['corpus_tag_df'].side_effect = ValueError('boom')
        res = prewarm.run_prewarm()  # must not raise
        assert res['axis_vocab'].startswith('error: RuntimeError')
        assert res['corpus_tag_df'].startswith('error: ValueError')
        assert res['random_pool'] == 'ok' and res['llm_clients'] == 'ok'
        warm_mocks['random_pool'].assert_called_once()
        warm_mocks['close'].assert_called_once()  # closed even though steps raised

    def test_close_all_failure_is_swallowed(self, warm_mocks):
        warm_mocks['close'].side_effect = RuntimeError('pool gone')
        prewarm.run_prewarm()  # must not raise

    def test_close_all_runs_even_on_non_exception_abort(self, warm_mocks):
        warm_mocks['random_pool'].side_effect = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            prewarm.run_prewarm()
        warm_mocks['close'].assert_called_once()

    def test_no_llm_request_is_made(self, warm_mocks):
        client = MagicMock()
        warm_mocks['client'].return_value = client
        prewarm.run_prewarm()
        assert client.mock_calls == []  # constructed only; no models.generate_content etc.

    def test_clients_skipped_when_no_api_key(self, warm_mocks, settings):
        settings.GEMINI_API_KEY = ''
        prewarm.run_prewarm()
        warm_mocks['client'].assert_not_called()
        warm_mocks['gemini_client'].assert_not_called()

    def test_openai_provider_builds_openai_client_only_with_key(self, warm_mocks, settings):
        settings.LLM_PROVIDER = 'openai'
        settings.OPENAI_API_KEY = 'sk'
        settings.GEMINI_API_KEY = ''
        prewarm.run_prewarm()
        warm_mocks['client'].assert_called_once_with()
        warm_mocks['gemini_client'].assert_not_called()


class TestStartThread:

    def test_disabled_returns_none_and_does_nothing(self, warm_mocks, settings):
        settings.PREWARM_ENABLED = False
        assert prewarm.start_prewarm_thread() is None
        warm_mocks['imports'].assert_not_called()
        warm_mocks['axis_vocab'].assert_not_called()

    def test_enabled_imports_sync_then_warms_on_daemon_thread(self, warm_mocks, settings):
        settings.PREWARM_ENABLED = True
        t = prewarm.start_prewarm_thread()
        assert t is not None and t.daemon is True
        t.join(timeout=5)
        assert not t.is_alive()
        assert warm_mocks['imports'].call_count >= 1
        warm_mocks['axis_vocab'].assert_called_once()
        warm_mocks['close'].assert_called_once()

    def test_import_failure_does_not_prevent_thread(self, warm_mocks, settings):
        settings.PREWARM_ENABLED = True
        warm_mocks['imports'].side_effect = ImportError('x')
        t = prewarm.start_prewarm_thread()
        t.join(timeout=5)
        warm_mocks['random_pool'].assert_called_once()


class TestPrewarmFlag:

    def test_pytest_forces_prewarm_off(self):
        from django.conf import settings as real
        assert real.PREWARM_ENABLED is False  # 'pytest' in sys.modules

    @pytest.mark.parametrize('env_val,expected', [
        (None, True), ('true', True), ('false', False), ('0', False), ('off', False), ('no', False),
    ])
    def test_env_flag_outside_pytest(self, env_val, expected):
        """Fresh interpreter (no 'pytest' in sys.modules) evaluates settings.py's flag."""
        env = {k: v for k, v in os.environ.items() if k != 'PREWARM_ENABLED'}
        if env_val is not None:
            env['PREWARM_ENABLED'] = env_val
        env.setdefault('DJANGO_SECRET_KEY', 'x')
        code = (
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "from config import settings; print(settings.PREWARM_ENABLED)"
        )
        out = subprocess.run(
            [sys.executable, '-c', code], cwd=BACKEND, env=env,
            capture_output=True, text=True, timeout=60,
        )
        assert out.stdout.strip().splitlines()[-1] == str(expected), out.stderr[-500:]


class TestGunicornWiring:

    def _load_conf(self):
        spec = importlib.util.spec_from_file_location('gunicorn_conf_under_test', BACKEND / 'gunicorn.conf.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_hook_starts_prewarm(self):
        conf = self._load_conf()
        worker = MagicMock()
        with patch.object(prewarm, 'start_prewarm_thread') as start:
            conf.post_worker_init(worker)
        start.assert_called_once_with()
        worker.log.warning.assert_not_called()

    def test_hook_never_raises_into_gunicorn(self):
        conf = self._load_conf()
        worker = MagicMock()
        with patch.object(prewarm, 'start_prewarm_thread', side_effect=RuntimeError('x')):
            conf.post_worker_init(worker)  # must not raise
        worker.log.warning.assert_called_once()

    def test_uses_post_worker_init_not_post_fork(self):
        conf = self._load_conf()
        assert inspect.isfunction(conf.post_worker_init)
        assert not hasattr(conf, 'post_fork')  # post_fork runs before Django is loaded

    def test_railway_start_command_references_conf(self):
        toml = (BACKEND / 'railway.toml').read_text(encoding='utf-8')
        cmd = re.search(r'^startCommand = "(.*)"\s*$', toml, re.M).group(1)
        assert '-c gunicorn.conf.py' in cmd
        assert 'config.wsgi:application' in cmd
