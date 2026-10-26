"""
test_guest_handle_retry.py -- POST /auth/guest/ retries once on IntegrityError
(check-then-insert handle race), mirroring _get_or_create_user.
"""
import pytest
from unittest.mock import patch
from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


PAYLOAD = {'display_name': 'Test Guest', 'consent_accepted': True}


@pytest.mark.django_db
def test_first_create_integrity_error_retries_with_fresh_suggestion():
    real_create = UserProfile.objects.create
    calls = {'n': 0}

    def flaky(*a, **k):
        calls['n'] += 1
        if calls['n'] == 1:
            raise IntegrityError('handle taken')
        return real_create(*a, **k)

    with patch('apps.accounts.views.auth._suggest_handle',
               side_effect=['taken_handle', 'fresh_handle']) as sg, \
            patch.object(UserProfile.objects, 'create', side_effect=flaky):
        res = APIClient().post('/api/v1/auth/guest/', PAYLOAD, format='json')

    assert res.status_code == 200
    assert sg.call_count == 2
    profile = UserProfile.objects.get(handle='fresh_handle')
    assert profile.display_name == 'fresh_handle'
    assert not UserProfile.objects.filter(handle='taken_handle').exists()


@pytest.mark.django_db
def test_second_integrity_error_propagates():
    with patch.object(UserProfile.objects, 'create', side_effect=IntegrityError('x')):
        client = APIClient(raise_request_exception=False)
        res = client.post('/api/v1/auth/guest/', PAYLOAD, format='json')
    assert res.status_code == 500
