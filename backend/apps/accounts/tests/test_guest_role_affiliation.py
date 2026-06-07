"""
test_guest_role_affiliation.py -- POST /auth/guest/ accepts optional role + affiliation.

Covers:
  TestGuestRoleAffiliation  (5 tests)
    - role + affiliation present → stored on created UserProfile
    - over-max-length role (>50) → truncated to 50, 200 response (not 500)
    - over-max-length affiliation (>100) → truncated to 100, 200 response (not 500)
    - absent role + affiliation → stored as empty strings
    - non-string values (int) → coerced to '' (not 500)
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guest_payload(**overrides):
    """Minimal valid guest signup payload."""
    base = {
        'display_name': 'Test Guest',
        'consent_accepted': True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGuestRoleAffiliation:

    @pytest.mark.django_db
    def test_role_and_affiliation_stored_on_profile(self):
        """POST /auth/guest/ with role + affiliation → values persisted on profile."""
        client = APIClient()
        payload = _guest_payload(role='Architecture Student', affiliation='Korea University')
        response = client.post('/api/v1/auth/guest/', payload, format='json')

        assert response.status_code == 200
        data = response.json()
        # UserSerializer exposes both fields in the 'user' block
        assert data['user']['role'] == 'Architecture Student'
        assert data['user']['affiliation'] == 'Korea University'
        # Confirm DB persistence
        profile = UserProfile.objects.get(is_guest=True, display_name='Test Guest')
        assert profile.role == 'Architecture Student'
        assert profile.affiliation == 'Korea University'

    @pytest.mark.django_db
    def test_over_max_length_role_truncated_not_500(self):
        """role longer than 50 chars is silently truncated; response is 200."""
        client = APIClient()
        long_role = 'R' * 60
        payload = _guest_payload(role=long_role)
        response = client.post('/api/v1/auth/guest/', payload, format='json')

        assert response.status_code == 200
        profile = UserProfile.objects.get(is_guest=True, display_name='Test Guest')
        assert profile.role == 'R' * 50
        assert len(profile.role) == 50

    @pytest.mark.django_db
    def test_over_max_length_affiliation_truncated_not_500(self):
        """affiliation longer than 100 chars is silently truncated; response is 200."""
        client = APIClient()
        long_affiliation = 'A' * 120
        payload = _guest_payload(affiliation=long_affiliation)
        response = client.post('/api/v1/auth/guest/', payload, format='json')

        assert response.status_code == 200
        profile = UserProfile.objects.get(is_guest=True, display_name='Test Guest')
        assert profile.affiliation == 'A' * 100
        assert len(profile.affiliation) == 100

    @pytest.mark.django_db
    def test_absent_role_and_affiliation_default_to_empty_string(self):
        """POST /auth/guest/ without role or affiliation → profile stores ''."""
        client = APIClient()
        payload = _guest_payload()
        response = client.post('/api/v1/auth/guest/', payload, format='json')

        assert response.status_code == 200
        profile = UserProfile.objects.get(is_guest=True, display_name='Test Guest')
        assert profile.role == ''
        assert profile.affiliation == ''

    @pytest.mark.django_db
    def test_non_string_role_and_affiliation_coerced_to_empty(self):
        """Non-string role/affiliation (e.g. int) is coerced to '' without error."""
        client = APIClient()
        payload = _guest_payload(role=42, affiliation=None)
        response = client.post('/api/v1/auth/guest/', payload, format='json')

        assert response.status_code == 200
        profile = UserProfile.objects.get(is_guest=True, display_name='Test Guest')
        assert profile.role == ''
        assert profile.affiliation == ''
