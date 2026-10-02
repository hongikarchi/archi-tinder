"""conftest.py -- fixtures for messaging tests (mirrors apps/social/tests/conftest.py)."""
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


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache — isolate every test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def messaging_on(settings):
    """Default ON for these tests; flag-OFF tests flip it back explicitly."""
    settings.MESSAGING_ENABLED = True


def make_user(username, opt_in=True, personality=True, guest=False):
    from django.contrib.auth.models import User
    from apps.accounts.models import PersonalityProfile, UserProfile
    user = User.objects.create_user(
        username=username, email=f'{username}@example.com', password='testpass123',
    )
    profile = UserProfile.objects.create(
        user=user, display_name=username.capitalize(), is_guest=guest,
    )
    if personality:
        PersonalityProfile.objects.create(
            user=profile, axis_1=0.1, axis_2=0.2, axis_3=0.3, axis_4=0.4, axis_5=0.5,
            type_code='CLON', discovery_opt_in=opt_in,
        )
    return user, profile


def client_for(user):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


@pytest.fixture
def alice(db):
    return make_user('alice')


@pytest.fixture
def bob(db):
    return make_user('bob')


@pytest.fixture
def carol(db):
    return make_user('carol')


@pytest.fixture
def ca(alice):
    return client_for(alice[0])


@pytest.fixture
def cb(bob):
    return client_for(bob[0])


@pytest.fixture
def cc(carol):
    return client_for(carol[0])
