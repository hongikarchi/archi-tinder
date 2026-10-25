"""FULL-AUTH-4: display_name == handle on every write path."""
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserMiniSerializer


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _profile(username, handle=None, display_name='x', is_guest=True):
    user = User.objects.create_user(username=username, password='pw-123456')
    return UserProfile.objects.create(
        user=user, handle=handle, display_name=display_name, is_guest=is_guest,
    )


def _client(profile):
    c = APIClient()
    token = RefreshToken.for_user(profile.user).access_token
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return c


@pytest.mark.django_db
def test_guest_create_sets_handle_equal_display_name():
    r = APIClient().post(
        '/api/v1/auth/guest/',
        {'display_name': 'Some Guest', 'consent_accepted': True}, format='json',
    )
    assert r.status_code == 200
    p = UserProfile.objects.get(is_guest=True)
    assert p.handle and p.display_name == p.handle


@pytest.mark.django_db
def test_guest_create_collision_gets_unique_handle():
    for _ in range(2):
        cache.clear()
        APIClient().post(
            '/api/v1/auth/guest/', {'consent_accepted': True}, format='json',
        )
    handles = list(UserProfile.objects.values_list('handle', flat=True))
    assert len(handles) == 2 and len({h.lower() for h in handles}) == 2


@pytest.mark.django_db
def test_promote_in_place_assigns_handle_when_missing():
    guest = _profile('g1', handle=None, display_name='Legacy Name')
    google = {
        'provider_id': 'gid-1', 'email': 'a@example.com', 'display_name': 'G',
        'avatar_url': '', 'email_verified': True,
    }
    with mock.patch('apps.accounts.views.auth._exchange_google_code', return_value=google):
        r = _client(guest).post(
            '/api/v1/auth/promote/', {'provider': 'google', 'code': 'c'}, format='json',
        )
    assert r.status_code == 200
    guest.refresh_from_db()
    assert guest.is_guest is False
    assert guest.handle and guest.display_name == guest.handle


@pytest.mark.django_db
def test_promote_keeps_existing_handle():
    guest = _profile('g2', handle='keepme', display_name='keepme')
    google = {
        'provider_id': 'gid-2', 'email': '', 'display_name': 'Other',
        'avatar_url': '', 'email_verified': False,
    }
    with mock.patch('apps.accounts.views.auth._exchange_google_code', return_value=google):
        _client(guest).post(
            '/api/v1/auth/promote/', {'provider': 'google', 'code': 'c'}, format='json',
        )
    guest.refresh_from_db()
    assert guest.handle == 'keepme' and guest.display_name == 'keepme'


def _ensure_dev_login_urls():
    import importlib
    from django.conf import settings
    from django.urls import clear_url_caches
    settings.DEBUG = True
    import apps.accounts.urls
    import config.urls
    importlib.reload(apps.accounts.urls)
    importlib.reload(config.urls)
    clear_url_caches()


@pytest.mark.django_db
def test_dev_login_sets_handle_and_no_first_name(monkeypatch):
    monkeypatch.setenv('DEV_LOGIN_SECRET', 'uid-secret')
    _ensure_dev_login_urls()
    for _ in range(2):  # second call must not rename
        r = APIClient().post('/api/v1/auth/dev-login/', {'secret': 'uid-secret'}, format='json')
        assert r.status_code == 200
    p = UserProfile.objects.get(user__username='test_architinder')
    assert p.handle and p.display_name == p.handle
    assert p.user.first_name == ''


@pytest.mark.django_db
def test_dev_login_does_not_rename_existing_handle(monkeypatch):
    monkeypatch.setenv('DEV_LOGIN_SECRET', 'uid-secret')
    _ensure_dev_login_urls()
    user = User.objects.create_user(username='test_architinder', password='x')
    UserProfile.objects.create(user=user, handle='custom_id', display_name='Old')
    APIClient().post('/api/v1/auth/dev-login/', {'secret': 'uid-secret'}, format='json')
    p = UserProfile.objects.get(user=user)
    assert p.handle == 'custom_id' and p.display_name == 'custom_id'


@pytest.mark.django_db
def test_patch_handle_null_rejected():
    p = _profile('p1', handle='abc', display_name='abc')
    r = _client(p).patch('/api/v1/users/me/', {'handle': None}, format='json')
    assert r.status_code == 400
    p.refresh_from_db()
    assert p.handle == 'abc'


@pytest.mark.django_db
def test_patch_display_name_only_syncs_handle():
    p = _profile('p2', handle='abc', display_name='abc')
    r = _client(p).patch('/api/v1/users/me/', {'display_name': 'newname'}, format='json')
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.handle == 'newname' and p.display_name == 'newname'


@pytest.mark.django_db
def test_patch_without_handle_leaves_identity_untouched():
    p = _profile('p3', handle='abc', display_name='abc')
    r = _client(p).patch('/api/v1/users/me/', {'bio': 'hi'}, format='json')
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.handle == 'abc' and p.display_name == 'abc'


@pytest.mark.django_db
def test_user_mini_serializer_has_handle():
    p = _profile('p4', handle='mini_id', display_name='mini_id')
    data = UserMiniSerializer(p).data
    assert data['handle'] == 'mini_id'


@pytest.mark.django_db
def test_resync_identity_dry_run_then_apply():
    a = _profile('r1', handle=None, display_name='Nameless')
    b = _profile('r2', handle='good_id', display_name='Different')
    c = _profile('r3', handle='ok_id', display_name='ok_id')

    out = StringIO()
    call_command('resync_identity', stdout=out)
    assert 'DRY-RUN' in out.getvalue()
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.handle is None and b.display_name == 'Different'

    out = StringIO()
    call_command('resync_identity', '--apply', stdout=out)
    for prof in (a, b, c):
        prof.refresh_from_db()
        assert prof.handle and prof.display_name == prof.handle
    assert b.handle == 'good_id'
    assert c.handle == 'ok_id'
    assert 'x@' not in out.getvalue()


@pytest.mark.django_db
def test_resync_identity_refuses_prod_host(settings):
    settings.DATABASES['default'] = {
        **settings.DATABASES['default'], 'HOST': 'ep-broad-hat-123.neon.tech',
    }
    with pytest.raises(CommandError):
        call_command('resync_identity', '--apply', stdout=StringIO())


@pytest.mark.django_db
@pytest.mark.parametrize('seed', ['', None, 'a', 'user', 'admin'])
def test_suggest_handle_fallback_is_not_reserved(seed):
    from apps.accounts.identity import suggest_handle
    from apps.accounts.serializers import handle_format_ok
    handle = suggest_handle(seed)
    assert handle_format_ok(handle)
