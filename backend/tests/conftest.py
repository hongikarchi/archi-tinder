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
from unittest.mock import patch, MagicMock
from django.core.cache import cache


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
def _clear_cache():
    """Clear Django LocMemCache between tests to prevent cache pollution."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _patch_get_buildings_by_ids():
    with patch(
        'apps.recommendation.engine.get_buildings_by_ids',
        side_effect=lambda ids, image_focus=None: [_fake_card(bid) for bid in ids if bid],
    ):
        yield


@pytest.fixture(autouse=True)
def _patch_swipe_service_connections():
    """Make the swipe/bookmark building-existence guard pass by default.

    handle_swipe_normal + handle_bookmark validate canonical_bld_id against
    canonical_v2_buildings (owned by Make DB, absent in the test DB) via
    connections['buildings'] before any write.  Default the check to
    'building exists'; tests asserting the 404 path override with their own
    fetchone()->None patch on the same target.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    # 6-tuple: truthy for the existence-guard (SELECT 1) AND correctly shaped for
    # _update_question_state's 6-column SELECT. All tag values None/empty so the
    # default stub counts no tags (tests needing specific tags override this patch).
    mock_cursor.fetchone.return_value = (None, None, [], None, [], [])
    mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor
    with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
        yield
