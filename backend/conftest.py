"""
conftest.py -- pytest fixtures for backend integration tests.

Sets environment variables before Django settings import, overrides
DATABASES to SQLite in-memory (for tests using `@pytest.mark.django_db`),
and handles URL reloading for DEBUG-only routes (dev-login).

CAVEAT: SQLite override is NOT load-bearing for all test paths.
================================================================

`django_db_modify_db_settings` fixture mutates `settings.DATABASES` at
session-scope before pytest-django's `django_db_setup`. This routes
**`@pytest.mark.django_db`-decorated tests** to an in-memory SQLite DB.

BUT some tests bypass that fixture path entirely:
  - tests that instantiate a connection directly via
    `django.db.connection.cursor()` outside `@pytest.mark.django_db`
  - tests under `backend/tests/test_sessions.py`, `test_topic*.py`,
    `test_topic_composition.py` and similar that hit real schema
    via session-scoped fixtures or module-level setup

Those tests connect to whatever PG is configured by `DB_HOST` / `DB_PORT`
/ `DB_NAME` env vars (`localhost:5432` by default).

Local consequence (false-pass signal):
  - If you have a dev Postgres running on 5432, bypassing tests succeed
    against your live data → green local run.
  - In CI without a PG service container, those same tests fail with
    "Connection refused on 5432". Empirical: PR #10 cycle 1 surfaced
    346 errors locally hidden because dev PG was running.

CI is the canonical validation gate.
================================================================
For a CI-shape local run that surfaces these bypassing tests:
  DB_HOST=nonexistent.invalid python -m pytest -q

Or rely on `.github/workflows/ci.yml` Backend job (real PG with pgvector
service container — see PR #10 fix-loop for the load-bearing config).
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
