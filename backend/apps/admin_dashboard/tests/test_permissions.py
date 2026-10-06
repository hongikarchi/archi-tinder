"""Permission matrix for every /api/v1/admin/dashboard/* endpoint + /auth/me/ is_admin."""
from unittest.mock import patch

import pytest

from apps.admin_dashboard.models import AdminAuditLog
from apps.admin_dashboard.testing import make_operator_client

ENDPOINTS = [
    '/api/v1/admin/dashboard/version/',
    '/api/v1/admin/dashboard/migrations/',
    '/api/v1/admin/dashboard/flags/',
    '/api/v1/admin/dashboard/stats/',
    '/api/v1/admin/dashboard/audit-log/',
]

_GH_STUB = {'main_sha': None, 'develop_sha': None, 'develop_ahead_by': None,
            'ci': {'develop': None, 'main': None}, 'error': None}

# name -> kwargs for make_operator_client producing exactly one failing lock
DENIED_VARIANTS = {
    'guest': {'guest': True},
    'staff_not_in_list': {'in_list': False},
    'in_list_not_staff': {'is_staff': False},
    'no_google_social_account': {'google': False},
}


@pytest.fixture(autouse=True)
def _no_network():
    with patch('apps.admin_dashboard.views.fetch_github_state', return_value=dict(_GH_STUB)):
        yield


@pytest.mark.django_db
@pytest.mark.parametrize('url', ENDPOINTS)
class TestPermissionMatrix:

    def test_anonymous_401(self, api_client, url):
        assert api_client.get(url).status_code == 401

    @pytest.mark.parametrize('variant', sorted(DENIED_VARIANTS))
    def test_denied_variants_403(self, settings, url, variant):
        client, _ = make_operator_client(settings, **DENIED_VARIANTS[variant])
        assert client.get(url).status_code == 403

    def test_empty_admin_emails_403(self, settings, url):
        client, _ = make_operator_client(settings)
        settings.ADMIN_EMAILS = frozenset()
        assert client.get(url).status_code == 403

    def test_email_match_is_case_insensitive(self, settings, url):
        client, _ = make_operator_client(settings, email='Admin@Example.com')
        settings.ADMIN_EMAILS = frozenset({'admin@example.com'})
        assert client.get(url).status_code == 200

    def test_admin_200(self, admin_client, url):
        assert admin_client.get(url).status_code == 200

    def test_post_not_allowed(self, admin_client, url):
        assert admin_client.post(url, {}, format='json').status_code == 405


@pytest.mark.django_db
class TestDeniedWritesNothing:

    def test_denied_calls_create_zero_audit_rows(self, settings, api_client):
        for i, kwargs in enumerate(DENIED_VARIANTS.values()):
            client, _ = make_operator_client(
                settings, username=f'denied{i}', email=f'd{i}@example.com', **kwargs)
            for url in ENDPOINTS:
                assert client.get(url).status_code == 403
        for url in ENDPOINTS:
            assert api_client.get(url).status_code == 401
        assert AdminAuditLog.objects.count() == 0

    def test_denial_logs_warning_with_user_id_and_path(self, settings, caplog):
        client, user = make_operator_client(settings, in_list=False)
        with caplog.at_level('WARNING', logger='apps.admin_dashboard'):
            client.get(ENDPOINTS[2])
        msgs = [r.getMessage() for r in caplog.records]
        assert any(f'user={user.pk}' in m and ENDPOINTS[2] in m for m in msgs)

    def test_dashboard_open_logged_once_per_version_get(self, admin_client):
        admin_client.get(ENDPOINTS[0])
        admin_client.get(ENDPOINTS[2])  # other endpoints do not log
        rows = AdminAuditLog.objects.all()
        assert rows.count() == 1
        assert rows[0].action == 'dashboard_open'
        assert rows[0].actor.email == 'admin@example.com'


@pytest.mark.django_db
class TestMeIsAdmin:

    def test_admin_sees_true(self, admin_client):
        resp = admin_client.get('/api/v1/auth/me/')
        assert resp.status_code == 200
        assert resp.json()['is_admin'] is True

    @pytest.mark.parametrize('variant', sorted(DENIED_VARIANTS))
    def test_non_admin_sees_false(self, settings, variant):
        client, _ = make_operator_client(settings, **DENIED_VARIANTS[variant])
        assert client.get('/api/v1/auth/me/').json()['is_admin'] is False

    def test_empty_allow_list_false(self, settings):
        client, _ = make_operator_client(settings, in_list=False)
        assert client.get('/api/v1/auth/me/').json()['is_admin'] is False
