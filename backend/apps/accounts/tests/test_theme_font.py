"""
test_theme_font.py -- Theme + font server-side persistence tests (design-system PR2).

Coverage:
  TestThemeFontPatch  (3 tests) -- PATCH /api/v1/users/me/ valid, invalid, persistence
  TestThemeFontMeView (1 test)  -- GET /api/v1/auth/me/ includes theme + font
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


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
