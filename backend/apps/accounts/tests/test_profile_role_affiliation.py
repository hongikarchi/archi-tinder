"""
test_profile_role_affiliation.py -- Backend tests for SETTINGS-2 role + affiliation fields.

New free-text fields on UserProfile:
  role        (max_length=50, blank=True, default='')
  affiliation (max_length=100, blank=True, default='')

Coverage:
  TestRoleAffiliationPatch     (6 tests) -- valid patch persisted + returned,
                                            over-max-length rejects 400,
                                            whitespace stripped, blank clears field
  TestRoleAffiliationPublic    (3 tests) -- both fields in public /users/{id}/,
                                            both fields in /auth/me/,
                                            PATCH /users/me/ returns updated values
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_and_profile(db):
    user = User.objects.create_user(
        username='roleuser', email='role@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Role User')
    return user, profile


@pytest.fixture
def auth_client(user_and_profile):
    user, _ = user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# TestRoleAffiliationPatch
# ---------------------------------------------------------------------------

class TestRoleAffiliationPatch:

    @pytest.mark.django_db
    def test_valid_role_and_affiliation_saved_and_returned(self, user_and_profile, auth_client):
        """PATCH with valid role + affiliation returns 200; values persisted + echoed."""
        user, _ = user_and_profile
        payload = {
            'role': 'Architecture Student',
            'affiliation': 'Korea University',
        }
        response = auth_client.patch('/api/v1/users/me/', payload, format='json')
        assert response.status_code == 200
        data = response.json()
        assert data['role'] == 'Architecture Student'
        assert data['affiliation'] == 'Korea University'
        # Confirm DB persistence
        profile = UserProfile.objects.get(user=user)
        assert profile.role == 'Architecture Student'
        assert profile.affiliation == 'Korea University'

    @pytest.mark.django_db
    def test_role_over_max_length_returns_400(self, user_and_profile, auth_client):
        """PATCH with role exceeding 50 chars returns 400."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'role': 'A' * 51}, format='json',
        )
        assert response.status_code == 400
        assert 'role' in response.json()

    @pytest.mark.django_db
    def test_affiliation_over_max_length_returns_400(self, user_and_profile, auth_client):
        """PATCH with affiliation exceeding 100 chars returns 400."""
        response = auth_client.patch(
            '/api/v1/users/me/', {'affiliation': 'B' * 101}, format='json',
        )
        assert response.status_code == 400
        assert 'affiliation' in response.json()

    @pytest.mark.django_db
    def test_role_whitespace_stripped(self, user_and_profile, auth_client):
        """PATCH role with leading/trailing whitespace stores stripped value."""
        user, _ = user_and_profile
        response = auth_client.patch(
            '/api/v1/users/me/', {'role': '  Architect  '}, format='json',
        )
        assert response.status_code == 200
        profile = UserProfile.objects.get(user=user)
        assert profile.role == 'Architect'

    @pytest.mark.django_db
    def test_affiliation_whitespace_stripped(self, user_and_profile, auth_client):
        """PATCH affiliation with leading/trailing whitespace stores stripped value."""
        user, _ = user_and_profile
        response = auth_client.patch(
            '/api/v1/users/me/', {'affiliation': '  Seoul National University  '}, format='json',
        )
        assert response.status_code == 200
        profile = UserProfile.objects.get(user=user)
        assert profile.affiliation == 'Seoul National University'

    @pytest.mark.django_db
    def test_role_blank_clears_field(self, user_and_profile, auth_client):
        """PATCH role='' clears a previously set value."""
        user, _ = user_and_profile
        # Set a value first
        auth_client.patch('/api/v1/users/me/', {'role': 'Designer'}, format='json')
        # Clear it
        response = auth_client.patch('/api/v1/users/me/', {'role': ''}, format='json')
        assert response.status_code == 200
        profile = UserProfile.objects.get(user=user)
        assert profile.role == ''


# ---------------------------------------------------------------------------
# TestRoleAffiliationPublic
# ---------------------------------------------------------------------------

class TestRoleAffiliationPublic:

    @pytest.mark.django_db
    def test_role_and_affiliation_in_public_profile(self, user_and_profile, auth_client):
        """GET /api/v1/users/{user_id}/ includes role + affiliation."""
        user, _ = user_and_profile
        auth_client.patch(
            '/api/v1/users/me/',
            {'role': 'Architecture Student', 'affiliation': 'Korea University'},
            format='json',
        )
        client = APIClient()
        response = client.get(f'/api/v1/users/{user.id}/')
        assert response.status_code == 200
        data = response.json()
        assert 'role' in data
        assert 'affiliation' in data
        assert data['role'] == 'Architecture Student'
        assert data['affiliation'] == 'Korea University'

    @pytest.mark.django_db
    def test_role_and_affiliation_in_auth_me(self, user_and_profile, auth_client):
        """GET /api/v1/auth/me/ includes role + affiliation."""
        auth_client.patch(
            '/api/v1/users/me/',
            {'role': 'Project Manager', 'affiliation': 'Samoo Architects'},
            format='json',
        )
        response = auth_client.get('/api/v1/auth/me/')
        assert response.status_code == 200
        data = response.json()
        assert 'role' in data
        assert 'affiliation' in data
        assert data['role'] == 'Project Manager'
        assert data['affiliation'] == 'Samoo Architects'

    @pytest.mark.django_db
    def test_role_affiliation_default_empty_string(self, user_and_profile):
        """Newly created profile has role='' and affiliation='' (not null)."""
        _, profile = user_and_profile
        assert profile.role == ''
        assert profile.affiliation == ''
