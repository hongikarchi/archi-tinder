"""grant_admin management command + JWT user-cache invalidation."""
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.admin_dashboard.testing import make_operator_client

FLAGS_URL = '/api/v1/admin/dashboard/flags/'


@pytest.mark.django_db
class TestGrantAdmin:

    def test_grant_sets_is_staff_and_reports_state(self, settings, capsys):
        _client, user = make_operator_client(settings, is_staff=False)
        call_command('grant_admin', 'ADMIN@example.com')  # case-insensitive
        user.refresh_from_db()
        assert user.is_staff is True
        out = capsys.readouterr().out
        assert 'email in ADMIN_EMAILS:       True' in out
        assert 'google SocialAccount exists: True' in out

    def test_revoke_clears_is_staff(self, settings):
        _client, user = make_operator_client(settings)
        call_command('grant_admin', user.email, '--revoke')
        user.refresh_from_db()
        assert user.is_staff is False

    def test_unknown_email_errors(self):
        with pytest.raises(CommandError):
            call_command('grant_admin', 'nobody@example.com')

    def test_grant_takes_effect_without_waiting_cache_ttl(self, settings):
        client, user = make_operator_client(settings, is_staff=False)
        assert client.get(FLAGS_URL).status_code == 403  # caches the (non-staff) user row
        call_command('grant_admin', user.email)
        assert client.get(FLAGS_URL).status_code == 200

    def test_revoke_takes_effect_immediately(self, settings):
        client, user = make_operator_client(settings)
        assert client.get(FLAGS_URL).status_code == 200
        call_command('grant_admin', user.email, '--revoke')
        assert client.get(FLAGS_URL).status_code == 403

    def test_explicit_invalidate_called(self, settings):
        _client, user = make_operator_client(settings, is_staff=False)
        with patch('apps.admin_dashboard.management.commands.grant_admin.invalidate_user_cache') as inv:
            call_command('grant_admin', user.email)
        inv.assert_called_once_with(user.id)
        assert User.objects.get(pk=user.pk).is_staff is True
