"""
conftest.py -- pytest fixtures for accounts app tests.

Re-exports the shared test fixtures from the root test conftest so that
accounts tests can be run in isolation (e.g. pytest backend/apps/accounts/tests/).
Root conftest at backend/tests/conftest.py is automatically picked up when
the full suite runs (pytest backend/tests/ backend/apps/accounts/tests/).
"""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-secret-key-for-pytest-only-not-production-use')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'testdb')
os.environ.setdefault('DB_USER', 'testuser')
os.environ.setdefault('DB_PASSWORD', 'testpass')
os.environ.setdefault('DJANGO_DEBUG', 'True')
os.environ.setdefault('DEV_LOGIN_SECRET', 'test_secret_123')
os.environ.setdefault('GEMINI_API_KEY', 'test-gemini-key')

import pytest  # noqa: E402


@pytest.fixture(scope='session')
def django_db_modify_db_settings():
    """Override database to SQLite in-memory for isolated test runs."""
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }


@pytest.fixture
def user_profile(db):
    """Create a Django User + UserProfile for testing."""
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(
        username='testuser', email='test@test.com', password='testpass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Test User')
    return profile


@pytest.fixture
def auth_client(user_profile):
    """APIClient with JWT Bearer token for the test user."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(user_profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def api_client():
    """Unauthenticated APIClient."""
    from rest_framework.test import APIClient
    return APIClient()
