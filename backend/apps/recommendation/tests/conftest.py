"""
conftest.py -- pytest fixtures for recommendation app tests (board1).

Re-uses the shared env setup pattern from backend/tests/conftest.py so this
suite can run in isolation via:
    pytest backend/apps/recommendation/tests/

Root backend/tests/conftest.py is picked up automatically for the full suite.
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
    """Override database to SQLite in-memory."""
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }


@pytest.fixture
def user_profile(db):
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(
        username='testuser', email='test@test.com', password='testpass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Test User')
    return profile


@pytest.fixture
def other_profile(db):
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(
        username='otheruser', email='other@test.com', password='testpass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='Other User')
    return profile


@pytest.fixture
def auth_client(user_profile):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(user_profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def other_auth_client(other_profile):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(other_profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()
