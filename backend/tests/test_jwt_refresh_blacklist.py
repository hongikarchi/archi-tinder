"""
test_jwt_refresh_blacklist.py -- JWT refresh blacklist regression tests.

Verifies that the custom TokenRefreshView blacklists the consumed refresh token
before issuing a rotated replacement, preventing replay attacks.

Uses real JWT issuance via rest_framework_simplejwt (in-memory SQLite DB with
token_blacklist app migrations applied by pytest-django).
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile


@pytest.fixture
def test_user(db):
    """Create a user with a profile for JWT testing."""
    user = User.objects.create_user(
        username='jwtuser', email='jwt@test.com', password='pass',
    )
    UserProfile.objects.create(user=user, display_name='JWT User')
    return user


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.mark.django_db
class TestJWTRefreshBlacklist:

    def test_refresh_returns_new_tokens(self, test_user, anon_client):
        """Valid refresh token → 200 with new access + new refresh (rotation enabled)."""
        refresh = RefreshToken.for_user(test_user)

        resp = anon_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': str(refresh)},
            format='json',
        )

        assert resp.status_code == 200
        data = resp.json()
        assert 'access' in data, 'access token missing from response'
        assert 'refresh' in data, (
            'refresh token missing — ROTATE_REFRESH_TOKENS is True but no new refresh returned'
        )
        # New refresh must be different from the original
        assert data['refresh'] != str(refresh), (
            'Rotated refresh token is identical to original — rotation not applied'
        )

    def test_old_refresh_blacklisted_after_use(self, test_user, anon_client):
        """
        After using R1 to get R2, re-using R1 must return 401 (blacklisted).

        This is the core security property: once a refresh token is consumed for
        rotation, it must be invalidated so a stolen token cannot be replayed.
        """
        r1 = RefreshToken.for_user(test_user)
        r1_str = str(r1)

        # First use: R1 → R2
        resp1 = anon_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': r1_str},
            format='json',
        )
        assert resp1.status_code == 200, (
            f'First refresh failed unexpectedly: {resp1.json()}'
        )

        # Second use: R1 again → must be rejected (blacklisted)
        resp2 = anon_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': r1_str},
            format='json',
        )
        assert resp2.status_code == 401, (
            f'Expected 401 for blacklisted token, got {resp2.status_code}: {resp2.json()}. '
            'Old refresh token was NOT blacklisted after first use.'
        )

    def test_refresh_missing_body_returns_400(self, anon_client):
        """POST /refresh with no body returns 400 (not 500)."""
        resp = anon_client.post('/api/v1/auth/token/refresh/', {}, format='json')
        assert resp.status_code == 400

    def test_refresh_invalid_token_returns_401(self, anon_client):
        """Garbage token string returns 401 (TokenError caught, not bare Exception)."""
        resp = anon_client.post(
            '/api/v1/auth/token/refresh/',
            {'refresh': 'this.is.not.a.valid.token'},
            format='json',
        )
        assert resp.status_code == 401
