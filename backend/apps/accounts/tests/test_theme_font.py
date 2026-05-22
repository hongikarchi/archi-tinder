"""
test_theme_font.py -- Theme + font server-side persistence tests (design-system PR2).

Coverage:
  TestThemeFontPatch          (3 tests) -- PATCH /api/v1/users/me/ valid, invalid, persistence
  TestThemeFontMeView         (1 test)  -- GET /api/v1/auth/me/ includes theme + font
  TestLoginResponseThemeFont  (1 test)  -- login response user object includes theme + font
  TestThemeFontPartialIsolation (1 test) -- single-field PATCH leaves other field untouched
"""
import importlib

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


def _ensure_dev_login_urls():
    """Reload URL modules so the DEBUG-only dev-login route is registered."""
    from django.conf import settings
    if not settings.DEBUG:
        settings.DEBUG = True
    from django.urls import clear_url_caches
    import apps.accounts.urls
    import config.urls
    importlib.reload(apps.accounts.urls)
    importlib.reload(config.urls)
    clear_url_caches()


# ---------------------------------------------------------------------------
# Fixtures (mirror test_phase13_userprofile.py style)
# ---------------------------------------------------------------------------

@pytest.fixture
def tf_user_and_profile(db):
    """Fresh User + UserProfile for theme/font tests."""
    user = User.objects.create_user(
        username='tfuser', email='tf@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='TF User')
    return user, profile


@pytest.fixture
def tf_auth_client(tf_user_and_profile):
    """Authenticated APIClient for the tf_user_and_profile user."""
    user, _ = tf_user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestThemeFontPatch
# ---------------------------------------------------------------------------

class TestThemeFontPatch:

    @pytest.mark.django_db
    def test_patch_theme_and_font_persisted(self, tf_user_and_profile, tf_auth_client):
        """PATCH with valid theme + font returns 200 and values are stored on UserProfile."""
        user, _ = tf_user_and_profile
        response = tf_auth_client.patch(
            '/api/v1/users/me/',
            {'theme': 'ayu-light', 'font': 'noto-serif'},
            format='json',
        )
        assert response.status_code == 200
        # Re-fetch from DB to confirm persistence (not just serializer echo)
        profile = UserProfile.objects.get(user=user)
        assert profile.theme == 'ayu-light'
        assert profile.font == 'noto-serif'

    @pytest.mark.django_db
    def test_patch_invalid_theme_returns_400(self, tf_user_and_profile, tf_auth_client):
        """PATCH with an unrecognised theme value returns 400."""
        response = tf_auth_client.patch(
            '/api/v1/users/me/',
            {'theme': 'bogus'},
            format='json',
        )
        assert response.status_code == 400

    @pytest.mark.django_db
    def test_patch_invalid_font_returns_400(self, tf_user_and_profile, tf_auth_client):
        """PATCH with an unrecognised font value returns 400."""
        response = tf_auth_client.patch(
            '/api/v1/users/me/',
            {'font': 'comic-sans'},
            format='json',
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestThemeFontMeView
# ---------------------------------------------------------------------------

class TestThemeFontMeView:

    @pytest.mark.django_db
    def test_me_response_includes_theme_and_font(self, tf_user_and_profile, tf_auth_client):
        """GET /api/v1/auth/me/ response body includes theme and font with default values."""
        response = tf_auth_client.get('/api/v1/auth/me/')
        assert response.status_code == 200
        data = response.json()
        assert 'theme' in data
        assert 'font' in data
        # Defaults must match model defaults
        assert data['theme'] == 'github-light'
        assert data['font'] == 'plex'


# ---------------------------------------------------------------------------
# TestLoginResponseThemeFont
# ---------------------------------------------------------------------------

class TestLoginResponseThemeFont:

    @pytest.mark.django_db
    def test_dev_login_response_user_includes_theme_and_font(self, db, monkeypatch):
        """POST /api/v1/auth/dev-login/ response user object carries theme and font fields."""
        _TEST_SECRET = 'pytest_tf_dev_secret'
        _ensure_dev_login_urls()
        monkeypatch.setenv('DEV_LOGIN_SECRET', _TEST_SECRET)
        client = APIClient()
        response = client.post(
            '/api/v1/auth/dev-login/',
            {'secret': _TEST_SECRET},
            format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'user' in data
        user_obj = data['user']
        assert 'theme' in user_obj
        assert 'font' in user_obj
        # Defaults: a freshly created dev-login profile uses model defaults
        assert user_obj['theme'] == 'github-light'
        assert user_obj['font'] == 'plex'


# ---------------------------------------------------------------------------
# TestThemeFontPartialIsolation
# ---------------------------------------------------------------------------

class TestThemeFontPartialIsolation:

    @pytest.mark.django_db
    def test_patch_theme_only_leaves_font_unchanged(self, tf_user_and_profile, tf_auth_client):
        """PATCH with only theme leaves font at its prior value (no accidental field reset)."""
        user, profile = tf_user_and_profile
        # Establish a known non-default starting state for both fields
        profile.theme = 'github-dark'
        profile.font = 'noto-serif'
        profile.save(update_fields=['theme', 'font'])

        response = tf_auth_client.patch(
            '/api/v1/users/me/',
            {'theme': 'ayu-light'},
            format='json',
        )
        assert response.status_code == 200
        # Re-fetch from DB to confirm actual persistence, not just echo
        profile.refresh_from_db()
        assert profile.theme == 'ayu-light'
        assert profile.font == 'noto-serif'
