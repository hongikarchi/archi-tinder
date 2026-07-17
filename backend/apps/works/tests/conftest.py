"""conftest.py — pytest fixtures for apps.works tests.

Mirrors the accounts/tests/conftest.py pattern: sets env vars before Django
settings import and overrides DATABASES to in-memory SQLite.

Must NOT touch django.db.connections: in a full-suite run another package's
test has already driven django_db_setup, so the live in-memory SQLite DB
(migrated) hangs off the existing connection wrapper — deleting/resetting
connections here discards that DB and every later works test dies with
"no such table: auth_user" (exactly what broke CI while isolated
`pytest apps/works/tests/` runs stayed green).
"""
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
    """Override both databases to SQLite in-memory for isolated test runs.

    Mirrors 'buildings' to 'default' so no real PostgreSQL is needed.
    Matches the root backend/conftest.py pattern.
    """
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
