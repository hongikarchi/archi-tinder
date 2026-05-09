"""
conftest.py -- pytest fixtures for backend integration tests.

Sets environment variables before Django settings import, overrides
DATABASES to SQLite in-memory, and handles URL reloading for DEBUG-only
routes (dev-login).
"""
import os

# Environment variables must be set BEFORE Django settings import.
# pytest-django reads DJANGO_SETTINGS_MODULE from pytest.ini, which
# triggers config.settings import, which reads these env vars.
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

import pytest


@pytest.fixture(scope='session')
def django_db_modify_db_settings():
    """Override database to SQLite in-memory before test DB creation.

    This fixture is called by pytest-django before django_db_setup.
    We must include ATOMIC_REQUESTS because Django's request handler
    checks for it even when the view itself doesn't use it.
    """
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
