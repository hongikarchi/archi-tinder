"""
conftest.py -- pytest fixtures for social app tests.

Mirrors the pattern in apps/accounts/tests/conftest.py so that
social tests can be run in isolation or as part of the full suite.
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


def _make_user_and_profile(username, email):
    """Helper: create a Django User + UserProfile."""
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(username=username, email=email, password='testpass123')
    profile = UserProfile.objects.create(user=user, display_name=username.capitalize())
    return user, profile


def _auth_client(user):
    """Helper: return authenticated APIClient for a given user."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def user_a(db):
    user, profile = _make_user_and_profile('alice', 'alice@example.com')
    return user, profile


@pytest.fixture
def user_b(db):
    user, profile = _make_user_and_profile('bob', 'bob@example.com')
    return user, profile


@pytest.fixture
def user_c(db):
    user, profile = _make_user_and_profile('carol', 'carol@example.com')
    return user, profile


@pytest.fixture
def auth_client_a(user_a):
    user, _ = user_a
    return _auth_client(user)


@pytest.fixture
def auth_client_b(user_b):
    user, _ = user_b
    return _auth_client(user)


@pytest.fixture
def anon_client():
    from rest_framework.test import APIClient
    return APIClient()
