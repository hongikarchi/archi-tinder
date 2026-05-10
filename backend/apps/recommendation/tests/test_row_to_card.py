"""
Unit tests for _row_to_card() — regression guard for visual_description and
description fields exposed in commit 20b0d45 (BUILDING-CARD-EXPOSE).

Runs in isolation (no DB required):
    pytest apps/recommendation/tests/test_row_to_card.py -v
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

import django  # noqa: E402
django.setup()

import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402
from apps.recommendation.engine import _row_to_card  # noqa: E402


def _minimal_row(**overrides):
    """Return a minimal synthetic row dict sufficient for _row_to_card not to crash."""
    base = {
        'building_id': 'bld-001',
        'image_photos': [],
        'image_drawings': [],
        'cover_image_url_divisare': '',
        'divisare_gallery_urls': [],
        'name_en': 'Test Building',
        'project_name': 'Test Project',
        'url': 'https://example.com/bld-001',
        'program': None,
        'architect': None,
        'location_country': None,
        'area_sqm': None,
        'year': None,
        'style': None,
        'atmosphere': None,
        'color_tone': None,
        'material': None,
        'material_visual': [],
        'tags': [],
        'visual_description': None,
        'description': None,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def mock_image_base_url():
    """Patch settings.IMAGE_BASE_URL so tests do not need a real settings file."""
    with patch('django.conf.settings.IMAGE_BASE_URL', 'https://cdn.example.com'):
        yield


class TestRowToCardVisualDescriptionAndDescription:
    """Regression tests: visual_description + description are present in metadata."""

    def test_both_present(self):
        """Both fields set in row → both appear verbatim in metadata."""
        row = _minimal_row(visual_description='vd-test', description='desc-test')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == 'vd-test'
        assert card['metadata']['description'] == 'desc-test'

    def test_both_missing(self):
        """Neither field in row → both fall back to empty string."""
        row = _minimal_row()
        # Explicitly remove both keys to simulate a row without these columns.
        row.pop('visual_description')
        row.pop('description')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == ''
        assert card['metadata']['description'] == ''

    def test_only_visual_description_present(self):
        """Row has visual_description but no description → description defaults to ''."""
        row = _minimal_row(visual_description='only-vd')
        row.pop('description')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == 'only-vd'
        assert card['metadata']['description'] == ''

    def test_only_description_present(self):
        """Row has description but no visual_description → visual_description defaults to ''."""
        row = _minimal_row(description='only-desc')
        row.pop('visual_description')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == ''
        assert card['metadata']['description'] == 'only-desc'

    def test_falsy_values_coerce_to_empty_string(self):
        """None values (explicit) are coerced to '' via `or ''` fallback."""
        row = _minimal_row(visual_description=None, description=None)
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == ''
        assert card['metadata']['description'] == ''
