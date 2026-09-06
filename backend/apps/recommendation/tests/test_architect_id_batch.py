"""
test_architect_id_batch.py — FRONT-FUNC-CHECK-1 backend coverage.

Covers:
  - _row_to_card emits metadata['architect_id'] as the first element of
    architect_canonical_ids when present.
  - metadata['architect_id'] is None when architect_canonical_ids is missing,
    empty, or None on the source row (never crashes).
  - metadata['axis_architects'] display string is unaffected.
  - POST /api/v1/images/batch/ surfaces architect_id through to the response
    card metadata (view-level, mocked at engine.get_buildings_by_ids per the
    existing TestBuildingBatch pattern in backend/tests/test_projects.py).
  - FIX cycle regression: get_building_card and get_buildings_by_ids share one
    cache namespace (_card_cache_key). Before the fix, get_building_card's
    SELECT omitted architect_canonical_ids, so calling it first would cache a
    None-architect card that get_buildings_by_ids then served stale (cache
    cross-contamination). TestCachePoisoningFix reproduces that call order
    against the real Django LocMemCache and asserts architect_id survives.
"""
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.engine import _row_to_card, clear_available_columns_cache


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


class TestRowToCardArchitectId:
    """_row_to_card metadata['architect_id'] — None-safe first-element extraction."""

    def test_architect_id_present(self):
        row = _minimal_row(architect_canonical_ids=['arch_000123', 'arch_000456'])
        card = _row_to_card(row)
        assert card['metadata']['architect_id'] == 'arch_000123'

    def test_architect_id_missing_column_is_none(self):
        """Row from a SELECT that never included architect_canonical_ids (row.get -> None)."""
        row = _minimal_row()
        assert 'architect_canonical_ids' not in row
        card = _row_to_card(row)
        assert card['metadata']['architect_id'] is None

    def test_architect_id_none_value_is_none(self):
        row = _minimal_row(architect_canonical_ids=None)
        card = _row_to_card(row)
        assert card['metadata']['architect_id'] is None

    def test_architect_id_empty_array_is_none(self):
        row = _minimal_row(architect_canonical_ids=[])
        card = _row_to_card(row)
        assert card['metadata']['architect_id'] is None

    def test_axis_architects_display_unaffected(self):
        """axis_architects keeps its existing joined/derived display string."""
        row = _minimal_row(
            architects_text='Studio A',
            architect_canonical_ids=['arch_000789'],
        )
        card = _row_to_card(row)
        assert card['metadata']['axis_architects'] == 'Studio A'
        assert card['metadata']['architect_id'] == 'arch_000789'


MOCK_CARD_WITH_ARCHITECT = {
    'canonical_bld_id': 'bld_000001',
    'name': 'Test Building',
    'image_url': 'https://example.com/img.jpg',
    'image_focus': None,
    'image_kind': None,
    'covers_by_type': {},
    'url': None,
    'gallery': [],
    'gallery_meta': [],
    'gallery_drawing_start': 0,
    'metadata': {
        'axis_typology': 'Museum',
        'axis_architects': 'Studio A',
        'architect_id': 'arch_000123',
        'axis_country': 'Spain',
        'axis_city': None,
        'axis_year': 2020,
        'axis_style': None,
        'axis_atmosphere': None,
        'axis_color_tone': None,
        'axis_material_visual': [],
        'axis_typology_primary': None,
        'axis_typology_tags': [],
        'axis_architectural_elements': [],
        'visual_description': '',
    },
}

MOCK_CARD_NO_ARCHITECT = {
    **MOCK_CARD_WITH_ARCHITECT,
    'canonical_bld_id': 'bld_000002',
    'metadata': {
        **MOCK_CARD_WITH_ARCHITECT['metadata'],
        'architect_id': None,
    },
}


@pytest.mark.django_db
class TestBuildingBatchArchitectId:
    """POST /api/v1/images/batch/ surfaces metadata.architect_id end-to-end."""

    @patch('apps.recommendation.views.engine.get_buildings_by_ids')
    def test_batch_response_includes_architect_id_when_present(self, mock_batch, auth_client):
        mock_batch.return_value = [MOCK_CARD_WITH_ARCHITECT]
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': ['bld_000001']},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['metadata']['architect_id'] == 'arch_000123'
        # axis_architects unchanged
        assert data[0]['metadata']['axis_architects'] == 'Studio A'

    @patch('apps.recommendation.views.engine.get_buildings_by_ids')
    def test_batch_response_architect_id_none_when_absent(self, mock_batch, auth_client):
        mock_batch.return_value = [MOCK_CARD_NO_ARCHITECT]
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': ['bld_000002']},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['metadata']['architect_id'] is None


def _probe_cursor(col_names):
    """Mock cursor for the information_schema availability probe."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [(c,) for c in col_names]
    return cursor


def _row_cursor(row_dict):
    """Mock cursor whose _dictfetchall returns [row_dict] (single-row SELECT)."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cols = list(row_dict.keys())
    cursor.description = [(c,) for c in cols]
    cursor.fetchall.return_value = [tuple(row_dict[c] for c in cols)]
    return cursor


def _rows_cursor(row_dicts):
    """Mock cursor whose _dictfetchall returns multiple rows (IN (...) SELECT)."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cols = list(row_dicts[0].keys()) if row_dicts else []
    cursor.description = [(c,) for c in cols]
    cursor.fetchall.return_value = [tuple(r[c] for c in cols) for r in row_dicts]
    return cursor


_DB_ROW = {
    'canonical_bld_id': 'bld_000777',
    'name': 'Poison Test Building',
    'architect_names': ['Real Architect'],
    'architects_text': 'Real Architect',
    'architect_canonical_ids': ['arch_000999'],
    'location_country': None,
    'location_city': None,
    'project_year': None,
    'program': None,
    'style': None,
    'atmosphere': None,
    'color_tone': None,
    'material_visual': [],
    'typology_primary': None,
    'typology_tags': [],
    'architectural_elements': [],
    'visual_description': None,
    'covers_by_type': None,
    'all_images': [],
    'display_cover_url': None,
    'cover_image_url_default': None,
    'source_urls': None,
}

_ALL_COLS = list(_DB_ROW.keys())


class TestCachePoisoningFix:
    """get_building_card and get_buildings_by_ids share _card_cache_key.

    Regression for the reviewed cache cross-contamination finding: both
    fetchers must SELECT architect_canonical_ids, or whichever one runs
    first poisons the shared cache entry for the other with architect_id=None.

    No @pytest.mark.django_db here — these tests exercise engine.py's raw-SQL
    fetchers against mocked cursors + the real Django LocMemCache, never the
    ORM/'default' DB, so they don't need a test database (INFRA-DB-2: local
    pytest without `make test-local` cannot create one).
    """

    def setup_method(self):
        clear_available_columns_cache()
        from django.core.cache import cache
        cache.clear()

    def teardown_method(self):
        clear_available_columns_cache()

    def test_get_building_card_then_batch_preserves_architect_id(self):
        """
        Reproduces the exact poisoning order from the finding:
        get_building_card() runs first (as it does on every swipe/prefetch via
        session_service.py / swipe_service.py), caching the card under
        bcard:v3:<bid>. get_buildings_by_ids() for the SAME id must then read
        back a card with the real architect_id, not a stale None.
        """
        from apps.recommendation.engine import get_building_card, get_buildings_by_ids

        probe_cursor = _probe_cursor(_ALL_COLS)
        card_cursor = _row_cursor(_DB_ROW)

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = [probe_cursor, card_cursor]
            first = get_building_card('bld_000777')

        assert first is not None
        assert first['metadata']['architect_id'] == 'arch_000999'

        # get_buildings_by_ids must now hit the cache (no DB call needed) and
        # still see the real architect_id -- not a None poisoned by a fetcher
        # whose SELECT once omitted the column.
        with patch('apps.recommendation.engine.connection') as mock_conn2:
            batch = get_buildings_by_ids(['bld_000777'])

        assert len(batch) == 1
        assert batch[0]['metadata']['architect_id'] == 'arch_000999'
        mock_conn2.cursor.assert_not_called()

    def test_get_buildings_by_ids_cache_miss_selects_architect_id(self):
        """get_buildings_by_ids on a cold cache fetches + caches architect_id."""
        from apps.recommendation.engine import get_buildings_by_ids

        probe_cursor = _probe_cursor(_ALL_COLS)
        rows_cursor = _rows_cursor([_DB_ROW])

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = [probe_cursor, rows_cursor]
            result = get_buildings_by_ids(['bld_000777'])

        assert len(result) == 1
        assert result[0]['metadata']['architect_id'] == 'arch_000999'
        executed_sql = rows_cursor.execute.call_args[0][0]
        assert 'architect_canonical_ids' in executed_sql

    def test_get_building_card_select_includes_architect_canonical_ids(self):
        """get_building_card's SELECT must include architect_canonical_ids
        (the actual root cause: it previously omitted the column)."""
        from apps.recommendation.engine import get_building_card

        probe_cursor = _probe_cursor(_ALL_COLS)
        card_cursor = _row_cursor(_DB_ROW)

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = [probe_cursor, card_cursor]
            get_building_card('bld_000777')

        executed_sql = card_cursor.execute.call_args[0][0]
        assert 'architect_canonical_ids' in executed_sql
