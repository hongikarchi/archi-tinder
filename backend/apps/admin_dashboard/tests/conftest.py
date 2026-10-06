"""conftest.py -- fixtures for admin_dashboard tests (mirrors messaging/social conftests)."""
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-secret-key-for-pytest-only-not-production-use')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'testdb')
os.environ.setdefault('DB_USER', 'testuser')
os.environ.setdefault('DB_PASSWORD', 'testpass')
os.environ.setdefault('BUILDINGS_DB_HOST', 'localhost')
os.environ.setdefault('BUILDINGS_DB_PORT', '5432')
os.environ.setdefault('BUILDINGS_DB_NAME', 'buildings_testdb')
os.environ.setdefault('BUILDINGS_DB_USER', 'testuser')
os.environ.setdefault('BUILDINGS_DB_PASSWORD', 'testpass')
os.environ.setdefault('DJANGO_DEBUG', 'True')
os.environ.setdefault('DEV_LOGIN_SECRET', 'test_secret_123')
os.environ.setdefault('GEMINI_API_KEY', 'test-gemini-key')

import pytest  # noqa: E402


@pytest.fixture(scope='session')
def django_db_modify_db_settings():
    """Override both databases to SQLite in-memory (buildings mirrors default)."""
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    settings.DATABASES['buildings'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
        'TEST': {'MIRROR': 'default'},
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters + stats/github caches live in the cache -- isolate every test."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def admin_client(db, settings):
    from apps.admin_dashboard.testing import make_operator_client
    client, _user = make_operator_client(settings)
    return client
