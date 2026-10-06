"""Behaviour of each admin dashboard endpoint (admin is already admitted here)."""
import re
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.cache import cache

from apps.admin_dashboard import flags as flags_mod
from apps.admin_dashboard.models import AdminAuditLog

BASE = '/api/v1/admin/dashboard/'


def _resp(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    if status >= 400:
        r.raise_for_status.side_effect = requests.HTTPError(f'{status}')
    else:
        r.raise_for_status.return_value = None
    return r


def _gh_side_effect(url, **kwargs):
    if '/compare/' in url:
        return _resp({
            'status': 'ahead', 'ahead_by': 3,
            'base_commit': {'sha': 'a' * 40},
            'commits': [{'sha': 'b' * 40}, {'sha': 'c' * 40}],
        })
    branch = kwargs['params']['branch']
    return _resp({'workflow_runs': [{
        'conclusion': 'success', 'status': 'completed',
        'html_url': f'https://github.com/x/actions/{branch}', 'created_at': '2026-10-06T00:00:00Z',
    }]})


@pytest.mark.django_db
class TestVersion:

    def test_github_success_shape_and_cache(self, admin_client, monkeypatch):
        monkeypatch.setenv('RAILWAY_GIT_COMMIT_SHA', 'deadbeef')
        monkeypatch.setenv('RAILWAY_DEPLOYMENT_ID', 'dep-1')
        monkeypatch.delenv('RAILWAY_ENVIRONMENT_NAME', raising=False)
        with patch('apps.admin_dashboard.github.requests.get', side_effect=_gh_side_effect) as get:
            body = admin_client.get(BASE + 'version/').json()
            calls_first = get.call_count
            body2 = admin_client.get(BASE + 'version/').json()
            assert get.call_count == calls_first  # second GET served from the 15-min cache
        assert body == body2
        assert body['backend'] == {'sha': 'deadbeef', 'deployment_id': 'dep-1', 'environment': None}
        gh = body['github']
        assert gh['main_sha'] == 'a' * 40
        assert gh['develop_sha'] == 'c' * 40
        assert gh['develop_ahead_by'] == 3
        assert gh['ci']['develop']['conclusion'] == 'success'
        assert gh['ci']['main']['html_url'].endswith('/main')
        assert gh['error'] is None
        assert calls_first == 3  # 1 compare + 2 runs

    def test_github_failure_is_200_with_nulls(self, admin_client):
        with patch('apps.admin_dashboard.github.requests.get', side_effect=requests.ConnectionError('boom')):
            resp = admin_client.get(BASE + 'version/')
        assert resp.status_code == 200
        gh = resp.json()['github']
        assert gh['main_sha'] is None and gh['develop_sha'] is None and gh['develop_ahead_by'] is None
        assert gh['ci'] == {'develop': None, 'main': None}
        assert gh['error']

    def test_github_http_error_degrades(self, admin_client):
        with patch('apps.admin_dashboard.github.requests.get', return_value=_resp({}, status=403)):
            resp = admin_client.get(BASE + 'version/')
        assert resp.status_code == 200
        assert resp.json()['github']['error']

    def test_github_token_sent_when_configured(self, admin_client, settings):
        settings.GITHUB_TOKEN = 'ghp_test'
        with patch('apps.admin_dashboard.github.requests.get', side_effect=_gh_side_effect) as get:
            admin_client.get(BASE + 'version/')
        assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer ghp_test'
        assert get.call_args.kwargs['timeout'] == 5


@pytest.mark.django_db
class TestMigrations:

    def test_returns_list_shape(self, admin_client):
        body = admin_client.get(BASE + 'migrations/').json()
        assert set(body) == {'count', 'unapplied'}
        assert isinstance(body['unapplied'], list)
        assert body['count'] == len(body['unapplied'])

    def test_lists_unapplied_fake_migration(self, admin_client):
        mig = MagicMock(app_label='messaging')
        mig.name = '9999_fake'
        executor = MagicMock()
        executor.migration_plan.return_value = [(mig, False)]
        with patch('apps.admin_dashboard.views.MigrationExecutor', return_value=executor):
            body = admin_client.get(BASE + 'migrations/').json()
        assert body == {'count': 1, 'unapplied': ['messaging.9999_fake']}


@pytest.mark.django_db
class TestFlags:

    def test_shape_and_korean_text(self, admin_client):
        body = admin_client.get(BASE + 'flags/').json()
        items = {f['key']: f for f in body['flags']}
        for key in ('MESSAGING_ENABLED', 'PERF_TIMING_ENABLED', 'PREWARM_ENABLED', 'DB_POOL_ENABLED',
                    'STAGE_DECOUPLE_ENABLED', 'LLM_PROVIDER', 'LLM_IMAGE_PROVIDER',
                    'gemini_rerank_enabled', 'dpp_topk_enabled', 'context_caching_enabled'):
            assert key in items
        hangul = re.compile('[가-힣]')
        for f in items.values():
            assert set(f) == {'key', 'label_ko', 'description_ko', 'value'}
            assert hangul.search(f['label_ko']) and hangul.search(f['description_ko'])
            assert isinstance(f['value'], (bool, str))

    def test_values_read_at_request_time(self, admin_client, settings):
        settings.MESSAGING_ENABLED = True
        settings.LLM_PROVIDER = 'openai'
        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'dpp_topk_enabled': True}
        items = {f['key']: f['value'] for f in admin_client.get(BASE + 'flags/').json()['flags']}
        assert items['MESSAGING_ENABLED'] is True
        assert items['LLM_PROVIDER'] == 'openai'
        assert items['dpp_topk_enabled'] is True

    def test_no_secret_values_in_body(self, admin_client):
        from django.conf import settings as dj
        raw = admin_client.get(BASE + 'flags/').content.decode()
        for name in dir(dj):
            if name.endswith(('_KEY', '_TOKEN', '_SECRET', '_PASSWORD')):
                val = getattr(dj, name, None)
                if isinstance(val, str) and len(val) >= 4:
                    assert val not in raw, name
        assert not any(row[0].endswith(('_KEY', '_TOKEN', '_SECRET')) for row in flags_mod._REGISTRY)


@pytest.mark.django_db
class TestStats:

    def _seed(self):
        from datetime import timedelta
        from django.contrib.auth.models import User
        from django.utils import timezone
        from apps.accounts.models import UserProfile
        from apps.works.models import Work
        for i, (guest, age_days) in enumerate([(False, 0), (True, 0), (False, 10), (True, 40)]):
            u = User.objects.create_user(username=f'seed{i}', email=f'seed{i}@example.com')
            p = UserProfile.objects.create(user=u, display_name=f's{i}', is_guest=guest)
            if age_days:
                UserProfile.objects.filter(pk=p.pk).update(
                    created_at=timezone.now() - timedelta(days=age_days))
        owner = UserProfile.objects.first()
        common = dict(owner=owner, title='t', program='museum', is_copyright_confirmed=True)
        Work.objects.create(upload_id='usr_1', is_publishable=True, **common)
        Work.objects.create(upload_id='usr_2', is_publishable=False, gate_reason='not architecture', **common)
        Work.objects.create(upload_id='usr_3', is_publishable=False, gate_reason='', **common)

    def test_counts_and_buildings_sql(self, admin_client):
        self._seed()
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = (39478,)
        conns = MagicMock()
        conns.__getitem__.return_value.cursor.return_value = cur
        with patch('apps.admin_dashboard.views.connections', conns):
            body = admin_client.get(BASE + 'stats/').json()
        sql = cur.execute.call_args.args[0]
        assert 'canonical_v2_buildings' in sql and 'is_publishable = true' in sql
        conns.__getitem__.assert_called_with('buildings')
        # 4 seeded + the admin user's own profile (non-guest, created now)
        assert body['users'] == {'total': 5, 'google_verified': 3, 'guest': 2, 'new_7d': 3, 'new_30d': 4}
        assert body['works'] == {'total': 3, 'published': 1, 'rejected': 1, 'processing': 1}
        assert body['reports'] == {'total': 0, 'last_7d': 0}
        assert body['sessions'] == {'last_24h': 0, 'last_7d': 0, 'converged_7d': 0}
        assert body['buildings'] == {'publishable': 39478}

    def test_buildings_failure_is_null_not_500(self, admin_client):
        conns = MagicMock()
        conns.__getitem__.side_effect = RuntimeError('db down')
        with patch('apps.admin_dashboard.views.connections', conns):
            resp = admin_client.get(BASE + 'stats/')
        assert resp.status_code == 200
        body = resp.json()
        assert body['buildings'] is None
        assert body['users']['total'] >= 1

    def test_cached(self, admin_client):
        admin_client.get(BASE + 'stats/')
        assert cache.get('admin_dash:stats') is not None


@pytest.mark.django_db
class TestAuditLog:

    def test_newest_first_and_pagination(self, admin_client):
        from django.contrib.auth.models import User
        actor = User.objects.get(email='admin@example.com')
        for i in range(5):
            AdminAuditLog.objects.create(actor=actor, action=f'a{i}', payload={'i': i})
        body = admin_client.get(BASE + 'audit-log/?page=1&page_size=2').json()
        assert body['count'] == 5
        assert [r['action'] for r in body['results']] == ['a4', 'a3']
        row = body['results'][0]
        assert set(row) == {'id', 'actor_email', 'action', 'target_type', 'target_id',
                            'payload', 'ip', 'created_at'}
        assert row['actor_email'] == 'admin@example.com'
        page3 = admin_client.get(BASE + 'audit-log/?page=3&page_size=2').json()
        assert [r['action'] for r in page3['results']] == ['a0']

    def test_page_size_capped_and_bad_params(self, admin_client):
        for i in range(3):
            AdminAuditLog.objects.create(action=f'x{i}')
        body = admin_client.get(BASE + 'audit-log/?page_size=9999&page=abc').json()
        assert body['count'] == 3 and len(body['results']) == 3
        assert body['results'][0]['actor_email'] is None
