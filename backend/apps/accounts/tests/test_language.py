"""
test_language.py -- FULL-LANGUAGE-1 Slice 1: UserProfile.language preference tests.

Coverage:
  TestLanguageModelDefault    (1 test) -- language field defaults to 'ko'
  TestLanguagePatch           (3 tests) -- PATCH /api/v1/users/me/ valid, invalid, persistence
  TestLanguageMeView          (1 test) -- GET /api/v1/auth/me/ includes language
  TestUserSerializerLanguage  (1 test) -- UserSerializer includes language field
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserSerializer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lang_user_and_profile(db):
    """Fresh User + UserProfile for language tests."""
    user = User.objects.create_user(
        username='languser', email='lang@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Lang User')
    return user, profile


@pytest.fixture
def lang_auth_client(lang_user_and_profile):
    """Authenticated APIClient for the lang_user_and_profile user."""
    user, _ = lang_user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestLanguageModelDefault
# ---------------------------------------------------------------------------

class TestLanguageModelDefault:

    @pytest.mark.django_db
    def test_language_defaults_to_ko(self, lang_user_and_profile):
        """UserProfile.language field defaults to 'ko'."""
        _, profile = lang_user_and_profile
        assert profile.language == 'ko'


# ---------------------------------------------------------------------------
# TestLanguagePatch
# ---------------------------------------------------------------------------

class TestLanguagePatch:

    @pytest.mark.django_db
    def test_patch_language_en_persisted(self, lang_user_and_profile, lang_auth_client):
        """PATCH with language='en' returns 200 and persists the value on UserProfile."""
        user, _ = lang_user_and_profile
        response = lang_auth_client.patch(
            '/api/v1/users/me/',
            {'language': 'en'},
            format='json',
        )
        assert response.status_code == 200
        profile = UserProfile.objects.get(user=user)
        assert profile.language == 'en'

    @pytest.mark.django_db
    def test_patch_language_ko_persisted(self, lang_user_and_profile, lang_auth_client):
        """PATCH with language='ko' returns 200 and persists the value."""
        user, profile = lang_user_and_profile
        # Start from non-default
        profile.language = 'en'
        profile.save(update_fields=['language'])

        response = lang_auth_client.patch(
            '/api/v1/users/me/',
            {'language': 'ko'},
            format='json',
        )
        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.language == 'ko'

    @pytest.mark.django_db
    def test_patch_invalid_language_returns_400(self, lang_user_and_profile, lang_auth_client):
        """PATCH with an unrecognised language value returns 400 (DRF choices validation)."""
        response = lang_auth_client.patch(
            '/api/v1/users/me/',
            {'language': 'fr'},
            format='json',
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestLanguageMeView
# ---------------------------------------------------------------------------

class TestLanguageMeView:

    @pytest.mark.django_db
    def test_me_response_includes_language(self, lang_user_and_profile, lang_auth_client):
        """GET /api/v1/auth/me/ response body includes language with default value 'ko'."""
        response = lang_auth_client.get('/api/v1/auth/me/')
        assert response.status_code == 200
        data = response.json()
        assert 'language' in data
        assert data['language'] == 'ko'


# ---------------------------------------------------------------------------
# TestUserSerializerLanguage
# ---------------------------------------------------------------------------

class TestUserSerializerLanguage:

    @pytest.mark.django_db
    def test_user_serializer_includes_language(self, lang_user_and_profile):
        """UserSerializer output includes language field (bootstrap-critical)."""
        _, profile = lang_user_and_profile
        data = UserSerializer(profile).data
        assert 'language' in data
        assert data['language'] == 'ko'
