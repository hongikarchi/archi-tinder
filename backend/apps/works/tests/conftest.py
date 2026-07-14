"""conftest.py — pytest fixtures for apps.works tests.

Mirrors the accounts/tests/conftest.py pattern: sets env vars before Django
settings import and overrides DATABASES to in-memory SQLite.

The django_db_modify_db_settings fixture also resets Django's ConnectionHandler
cached_property and thread-local connections so the SQLite override takes effect
even after django.setup() has been called by the root conftest.
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
    """Override DATABASES to in-memory SQLite before pytest-django creates the test DB.

    Also resets Django's ConnectionHandler cached_property and thread-local
    connection objects so the new SQLite backend is used even when the root
    conftest has already called django.setup().
    """
    from django.conf import settings
    from django.db import connections

    sqlite_default = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    sqlite_buildings = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
        'TEST': {'MIRROR': 'default'},
    }

    settings.DATABASES['default'] = sqlite_default
    settings.DATABASES['buildings'] = sqlite_buildings

    # Reset the ConnectionHandler's cached 'settings' property so it re-reads
    # the updated settings.DATABASES on next access.
    try:
        del connections.__dict__['settings']
    except KeyError:
        pass  # not yet cached — nothing to do

    # Delete any already-instantiated DatabaseWrapper objects so create_connection
    # is called fresh with the new SQLite backend.
    for alias in ('default', 'buildings'):
        try:
            del connections[alias]
        except Exception:
            pass
