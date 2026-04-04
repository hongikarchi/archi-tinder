"""
test_auth.py -- Auth flow integration tests.

Covers Google login (mocked HTTP), token refresh, logout/blacklist, and dev-login.
"""
import importlib
import os
import pytest
from unittest.mock import patch, MagicMock
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient


# -- Google Login --------------------------------------------------------------

@pytest.mark.django_db
def test_google_login_with_auth_code(api_client):
    """Auth-code flow: exchanges code for access_token, fetches userinfo, returns JWT."""
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {'access_token': 'mock_at'}

    mock_userinfo_resp = MagicMock()
    mock_userinfo_resp.status_code = 200
    mock_userinfo_resp.json.return_value = {
        'sub': '12345',
        'email': 'test@gmail.com',
        'name': 'Test',
        'picture': None,
    }

    with patch('apps.accounts.views.requests.post', return_value=mock_token_resp), \
         patch('apps.accounts.views.requests.get', return_value=mock_userinfo_resp):
        response = api_client.post(
            '/api/v1/auth/social/google/',
            {'code': 'mock_code'},
            format='json',
        )

    assert response.status_code == 200
    data = response.json()
    assert 'access' in data
    assert 'refresh' in data
    assert 'user' in data


@pytest.mark.django_db
def test_google_login_invalid_token(api_client):
    """Userinfo endpoint returning 401 causes login to fail with 401."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = 'Unauthorized'

    with patch('apps.accounts.views.requests.get', return_value=mock_resp):
        response = api_client.post(
            '/api/v1/auth/social/google/',
            {'access_token': 'invalid'},
            format='json',
        )

    assert response.status_code == 401


# -- Token Refresh -------------------------------------------------------------

@pytest.mark.django_db
def test_token_refresh_valid(api_client):
    """Valid refresh token returns a new access token."""
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(username='refreshuser', email='refresh@example.com')
    UserProfile.objects.create(user=user, display_name='Refresh User')

    refresh = RefreshToken.for_user(user)
    response = api_client.post(
        '/api/v1/auth/token/refresh/',
        {'refresh': str(refresh)},
        format='json',
    )

    assert response.status_code == 200
    assert 'access' in response.json()


@pytest.mark.django_db
def test_token_refresh_invalid(api_client):
    """Garbage refresh token string returns 401."""
    response = api_client.post(
        '/api/v1/auth/token/refresh/',
        {'refresh': 'invalid_token'},
        format='json',
    )

    assert response.status_code == 401


# -- Logout / Blacklist --------------------------------------------------------

@pytest.mark.django_db
def test_logout_blacklists_token(auth_client, user_profile):
    """Logout blacklists the refresh token; subsequent use returns 401."""
    refresh = RefreshToken.for_user(user_profile.user)
    refresh_str = str(refresh)

    resp = auth_client.post(
        '/api/v1/auth/logout/',
        {'refresh': refresh_str},
        format='json',
    )
    assert resp.status_code == 204

    # The same token must now be rejected
    anon = APIClient()
    resp2 = anon.post(
        '/api/v1/auth/token/refresh/',
        {'refresh': refresh_str},
        format='json',
    )
    assert resp2.status_code == 401


# -- Dev Login -----------------------------------------------------------------
# The dev-login URL is conditionally registered with `if settings.DEBUG`.
# Since URLs are loaded at import time, we must reload the URL modules
# after ensuring DEBUG=True. The view reads DEV_LOGIN_SECRET from os.getenv
# at request time, so we must also patch the environment variable.

_TEST_DEV_SECRET = 'pytest_dev_secret_42'


def _ensure_dev_login_urls():
    """Reload URL modules to include dev-login route (DEBUG-only)."""
    from django.conf import settings
    if not settings.DEBUG:
        settings.DEBUG = True
    from django.urls import clear_url_caches
    import apps.accounts.urls
    import config.urls
    importlib.reload(apps.accounts.urls)
    importlib.reload(config.urls)
    clear_url_caches()


@pytest.mark.django_db
def test_dev_login_with_secret(api_client, monkeypatch):
    """Dev-login with correct secret returns JWT tokens and user info."""
    _ensure_dev_login_urls()
    monkeypatch.setenv('DEV_LOGIN_SECRET', _TEST_DEV_SECRET)

    response = api_client.post(
        '/api/v1/auth/dev-login/',
        {'secret': _TEST_DEV_SECRET},
        format='json',
    )

    assert response.status_code == 200
    data = response.json()
    assert 'access' in data
    assert 'refresh' in data
    assert 'user' in data


@pytest.mark.django_db
def test_dev_login_wrong_secret(api_client, monkeypatch):
    """Dev-login with wrong secret returns 403."""
    _ensure_dev_login_urls()
    monkeypatch.setenv('DEV_LOGIN_SECRET', _TEST_DEV_SECRET)

    response = api_client.post(
        '/api/v1/auth/dev-login/',
        {'secret': 'wrong'},
        format='json',
    )

    assert response.status_code == 403
