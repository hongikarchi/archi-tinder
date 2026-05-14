"""
Unit tests for _row_to_card() — regression guard against the canonical_v2
schema. Original tests covered the v1 (architecture_vectors / R2-composed)
shape; this version targets the v2 (canonical_v2_buildings / source-CDN URL /
covers_by_type JSONB / image_focus) shape produced by S2.

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

from apps.recommendation.engine import _row_to_card  # noqa: E402


def _minimal_row(**overrides):
    """Synthetic canonical_v2 row sufficient for _row_to_card not to crash."""
    base = {
        'canonical_bld_id': 'bld_000001',
        'name': 'Test Building',
        'architect_names': ['Test Architect'],
        'architects_text': 'Test Architect',
        'location_country': None,
        'location_city': None,
        'project_year': None,
        'program': None,
        'style': None,
        'atmosphere': None,
        'color_tone': None,
        'material_visual': [],
        'visual_description': None,
        'covers_by_type': None,
        'all_images': [],
        'display_cover_url': None,
        'cover_image_url_default': None,
        'source_urls': None,
    }
    base.update(overrides)
    return base


class TestRowToCardVisualDescription:
    """Regression: visual_description survives row -> card mapping."""

    def test_visual_description_present(self):
        row = _minimal_row(visual_description='vd-test')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == 'vd-test'

    def test_visual_description_missing(self):
        row = _minimal_row()
        row.pop('visual_description')
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == ''

    def test_visual_description_none_coerces_to_empty(self):
        row = _minimal_row(visual_description=None)
        card = _row_to_card(row)
        assert card['metadata']['visual_description'] == ''


class TestRowToCardCoverResolution:
    """Cover-image resolution: image_focus then fallback chain."""

    def test_image_focus_uses_covers_by_type(self):
        row = _minimal_row(
            display_cover_url='https://default/cover.jpg',
            covers_by_type={
                'exterior': 'https://ext/cover.jpg',
                'interior': 'https://int/cover.jpg',
                'drawing': None, 'aerial': None, 'detail': None,
            },
        )
        card = _row_to_card(row, image_focus='interior')
        assert card['image_url'] == 'https://int/cover.jpg'

    def test_image_focus_null_falls_through(self):
        """When covers_by_type[focus] is null, fall back to display_cover_url."""
        row = _minimal_row(
            display_cover_url='https://default/cover.jpg',
            covers_by_type={
                'exterior': 'https://ext/cover.jpg',
                'interior': None, 'drawing': None, 'aerial': None, 'detail': None,
            },
        )
        card = _row_to_card(row, image_focus='interior')
        assert card['image_url'] == 'https://default/cover.jpg'

    def test_no_focus_uses_display_cover_url(self):
        row = _minimal_row(display_cover_url='https://default/cover.jpg')
        card = _row_to_card(row)
        assert card['image_url'] == 'https://default/cover.jpg'

    def test_no_display_falls_to_cover_image_url_default(self):
        row = _minimal_row(
            display_cover_url=None,
            cover_image_url_default='https://upload/cover.jpg',
        )
        card = _row_to_card(row)
        assert card['image_url'] == 'https://upload/cover.jpg'

    def test_no_explicit_covers_falls_to_exterior_in_covers_by_type(self):
        row = _minimal_row(
            display_cover_url=None,
            cover_image_url_default=None,
            covers_by_type={
                'exterior': 'https://ext/cover.jpg',
                'interior': None, 'drawing': None, 'aerial': None, 'detail': None,
            },
        )
        card = _row_to_card(row)
        assert card['image_url'] == 'https://ext/cover.jpg'

    def test_only_all_images_falls_to_first_url(self):
        row = _minimal_row(
            display_cover_url=None,
            cover_image_url_default=None,
            covers_by_type={'exterior': None, 'interior': None, 'drawing': None,
                            'aerial': None, 'detail': None},
            all_images=[
                {'url': 'https://gallery/first.jpg', 'kind': 'cover', 'image_order': 0},
            ],
        )
        card = _row_to_card(row)
        assert card['image_url'] == 'https://gallery/first.jpg'

    def test_empty_row_gives_empty_string(self):
        row = _minimal_row()
        card = _row_to_card(row)
        assert card['image_url'] == ''

    def test_invalid_image_focus_ignored(self):
        row = _minimal_row(
            display_cover_url='https://default/cover.jpg',
            covers_by_type={'exterior': 'https://ext/cover.jpg', 'interior': None,
                            'drawing': None, 'aerial': None, 'detail': None},
        )
        card = _row_to_card(row, image_focus='bogus')
        assert card['image_url'] == 'https://default/cover.jpg'


class TestRowToCardGallery:
    """Gallery ordering + drawing_start boundary."""

    def test_gallery_excludes_cover_url(self):
        row = _minimal_row(
            display_cover_url='https://a/1.jpg',
            all_images=[
                {'url': 'https://a/1.jpg', 'kind': 'cover',  'image_order': 0},
                {'url': 'https://a/2.jpg', 'kind': 'gallery', 'image_order': 1},
                {'url': 'https://a/3.jpg', 'kind': 'drawing', 'image_order': 2},
            ],
        )
        card = _row_to_card(row)
        assert 'https://a/1.jpg' not in card['gallery']
        assert 'https://a/2.jpg' in card['gallery']

    def test_gallery_drawing_start_is_first_drawing(self):
        row = _minimal_row(
            display_cover_url='https://a/cover.jpg',
            all_images=[
                {'url': 'https://a/2.jpg', 'kind': 'gallery', 'image_order': 1},
                {'url': 'https://a/3.jpg', 'kind': 'gallery', 'image_order': 2},
                {'url': 'https://a/4.jpg', 'kind': 'drawing', 'image_order': 3},
                {'url': 'https://a/5.jpg', 'kind': 'drawing', 'image_order': 4},
            ],
        )
        card = _row_to_card(row)
        assert card['gallery_drawing_start'] == 2

    def test_gallery_drawing_start_is_length_when_no_drawings(self):
        row = _minimal_row(
            display_cover_url='https://a/cover.jpg',
            all_images=[
                {'url': 'https://a/2.jpg', 'kind': 'gallery', 'image_order': 1},
                {'url': 'https://a/3.jpg', 'kind': 'gallery', 'image_order': 2},
            ],
        )
        card = _row_to_card(row)
        assert card['gallery_drawing_start'] == len(card['gallery'])

    def test_all_images_jsonb_string_decoded(self):
        """When DB driver returns jsonb as a raw JSON string, _row_to_card decodes it."""
        row = _minimal_row(
            display_cover_url='https://a/cover.jpg',
            all_images='[{"url": "https://a/2.jpg", "kind": "gallery", "image_order": 1}]',
            covers_by_type='{"exterior": null, "interior": null, "drawing": null, '
                           '"aerial": null, "detail": null}',
        )
        card = _row_to_card(row)
        assert 'https://a/2.jpg' in card['gallery']


class TestRowToCardMetadataAxes:
    """canonical_v2 axis_* metadata mapping."""

    def test_program_maps_to_axis_typology(self):
        row = _minimal_row(program='Museum')
        card = _row_to_card(row)
        assert card['metadata']['axis_typology'] == 'Museum'

    def test_architects_text_preferred_over_array(self):
        row = _minimal_row(
            architects_text='Studio A',
            architect_names=['Studio B'],
        )
        card = _row_to_card(row)
        assert card['metadata']['axis_architects'] == 'Studio A'

    def test_architects_falls_back_to_joined_array(self):
        row = _minimal_row(architects_text=None, architect_names=['Studio B', 'Studio C'])
        card = _row_to_card(row)
        assert card['metadata']['axis_architects'] == 'Studio B, Studio C'

    def test_project_year_maps_to_axis_year(self):
        row = _minimal_row(project_year=2024)
        card = _row_to_card(row)
        assert card['metadata']['axis_year'] == 2024

    def test_material_visual_preserved_as_list(self):
        row = _minimal_row(material_visual=['concrete', 'glass'])
        card = _row_to_card(row)
        assert card['metadata']['axis_material_visual'] == ['concrete', 'glass']

    def test_canonical_bld_id_preserved_at_top_level(self):
        row = _minimal_row(canonical_bld_id='bld_999')
        card = _row_to_card(row)
        assert card['canonical_bld_id'] == 'bld_999'

    def test_name_preserved_at_top_level(self):
        row = _minimal_row(name='Test Tower')
        card = _row_to_card(row)
        assert card['name'] == 'Test Tower'
