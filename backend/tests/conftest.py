"""
conftest.py — global test fixtures for backend/tests/.

canonical_v2_buildings is owned by Make DB and never present in test_neondb
(Django never migrates it — see CLAUDE.md hard rules).  Any test that drives
the session-create or swipe endpoint will call engine.get_buildings_by_ids,
which queries canonical_v2_buildings.  The autouse mock below keeps every test
hermetic without requiring each file to repeat the patch.

Tests that need a specific card shape (e.g. to assert on name) can override
with their own `with patch('apps.recommendation.engine.get_buildings_by_ids',
side_effect=my_mock)` block inside the test body; the inner patch wins for its
duration and this autouse mock resumes when the inner patch exits.
"""
import pytest
from unittest.mock import patch


def _fake_card(canonical_bld_id):
    if canonical_bld_id is None:
        return None
    return {
        'canonical_bld_id': canonical_bld_id,
        'name': f'Building {canonical_bld_id}',
        'image_url': '',
        'covers_by_type': {},
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Museum',
            'axis_architects': 'Test Arch',
            'axis_country': 'Korea',
            'axis_city': None,
            'axis_year': 2022,
            'axis_style': 'Modern',
            'axis_atmosphere': 'bold',
            'axis_color_tone': 'Dark',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


@pytest.fixture(autouse=True)
def _patch_get_buildings_by_ids():
    with patch(
        'apps.recommendation.engine.get_buildings_by_ids',
        side_effect=lambda ids, image_focus=None: [_fake_card(bid) for bid in ids if bid],
    ):
        yield
