"""
test_schema_robustness.py -- Schema Robustness A: forward-compatible SELECT probe.

Tests cover:
  - _get_available_columns: probe success, caching, probe failure (no cache poisoning)
  - _build_select_columns: optional present, optional absent, probe-failed fallback
  - get_building_card: dev-schema (no divisare cols) -> no 500, image_url fallback
  - clear_available_columns_cache: resets probe cache for isolation
"""
from unittest.mock import patch, MagicMock

import apps.recommendation.engine as engine_module
from apps.recommendation.engine import (
    _get_available_columns,
    _build_select_columns,
    clear_available_columns_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEGACY_COLS = frozenset([
    'building_id', 'name_en', 'project_name', 'architect', 'location_country',
    'city', 'year', 'area_sqm', 'program', 'style', 'atmosphere', 'color_tone',
    'material', 'material_visual', 'url', 'tags', 'image_photos', 'image_drawings',
    'embedding', 'slug', 'description', 'source_slugs', 'vocab_version',
    'prompt_version',
])

_PROD_COLS = _LEGACY_COLS | frozenset([
    'cover_image_url_divisare', 'divisare_gallery_urls', 'divisare_id',
    'divisare_slug', 'abstract', 'architect_canonical_ids', 'divisare_tags',
    'divisare_credits', 'provenance',
])

_REQUIRED = [
    'building_id', 'name_en', 'project_name', 'architect', 'location_country',
    'city', 'year', 'area_sqm', 'program', 'style', 'atmosphere', 'color_tone',
    'material', 'material_visual', 'url', 'tags', 'image_photos', 'image_drawings',
]
_OPTIONAL = ['cover_image_url_divisare', 'divisare_gallery_urls']


def _make_probe_cursor(col_names):
    """Return a mock cursor whose fetchall yields information_schema rows."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = [(c,) for c in col_names]
    return cursor


def _make_card_cursor(row_dict):
    """Return a mock cursor whose _dictfetchall returns [row_dict]."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cols = list(row_dict.keys())
    cursor.description = [(c,) for c in cols]
    cursor.fetchall.return_value = [tuple(row_dict[c] for c in cols)]
    return cursor


# ---------------------------------------------------------------------------
# TestGetAvailableColumns
# ---------------------------------------------------------------------------

class TestGetAvailableColumns:
    """_get_available_columns probe behaviour."""

    def setup_method(self):
        clear_available_columns_cache()

    def test_probe_success_returns_frozenset(self):
        """Successful probe returns frozenset of column names."""
        cursor = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _get_available_columns()
        assert isinstance(result, frozenset)
        assert 'building_id' in result
        assert 'cover_image_url_divisare' not in result

    def test_probe_cached_after_first_call(self):
        """Second call does not hit the DB — returns cached value."""
        cursor = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            first = _get_available_columns()

        # Second call with a different mock — if it's hit, the test would see new cols
        cursor2 = _make_probe_cursor(_PROD_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn2:
            mock_conn2.cursor.return_value = cursor2
            second = _get_available_columns()
            mock_conn2.cursor.assert_not_called()

        assert second is first

    def test_probe_failure_returns_none(self):
        """When the DB raises, _get_available_columns returns None (not frozenset)."""
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.execute.side_effect = Exception('DB unreachable')

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _get_available_columns()
        assert result is None

    def test_probe_failure_does_not_cache(self):
        """Probe failure leaves _AVAILABLE_COLUMNS = None — next call retries."""
        cursor_bad = MagicMock()
        cursor_bad.__enter__ = lambda s: s
        cursor_bad.__exit__ = MagicMock(return_value=False)
        cursor_bad.execute.side_effect = Exception('transient error')

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor_bad
            _get_available_columns()

        # Module-level state should still be None — NOT poisoned
        assert engine_module._AVAILABLE_COLUMNS is None

        # Subsequent call with working DB should succeed and cache
        cursor_ok = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn2:
            mock_conn2.cursor.return_value = cursor_ok
            result = _get_available_columns()

        assert result is not None
        assert 'building_id' in result

    def test_clear_available_columns_cache_resets_state(self):
        """clear_available_columns_cache sets _AVAILABLE_COLUMNS back to None."""
        cursor = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            _get_available_columns()

        assert engine_module._AVAILABLE_COLUMNS is not None
        clear_available_columns_cache()
        assert engine_module._AVAILABLE_COLUMNS is None


# ---------------------------------------------------------------------------
# TestBuildSelectColumns
# ---------------------------------------------------------------------------

class TestBuildSelectColumns:
    """_build_select_columns column list construction."""

    def setup_method(self):
        clear_available_columns_cache()

    def test_optional_included_when_present_in_schema(self):
        """Optional columns present in probe result are included in SELECT list."""
        cursor = _make_probe_cursor(_PROD_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _build_select_columns(_REQUIRED, _OPTIONAL)

        for col in _REQUIRED:
            assert col in result
        assert 'cover_image_url_divisare' in result
        assert 'divisare_gallery_urls' in result

    def test_optional_excluded_when_absent_from_schema(self):
        """Optional columns absent from probe result are excluded from SELECT list."""
        cursor = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _build_select_columns(_REQUIRED, _OPTIONAL)

        for col in _REQUIRED:
            assert col in result
        assert 'cover_image_url_divisare' not in result
        assert 'divisare_gallery_urls' not in result

    def test_probe_failed_includes_all_candidates(self):
        """When probe fails (returns None), all columns (required + optional) are included."""
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.execute.side_effect = Exception('DB down')

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _build_select_columns(_REQUIRED, _OPTIONAL)

        # Both required and optional should be present (legacy fail-loud behavior)
        for col in _REQUIRED:
            assert col in result
        assert 'cover_image_url_divisare' in result
        assert 'divisare_gallery_urls' in result

    def test_required_always_included(self):
        """Required columns are present regardless of probe result."""
        # With probe returning empty frozenset (edge: table has no columns?)
        cursor = _make_probe_cursor([])
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            # probe returns None because cols is falsy (empty frozenset is falsy)
            result = _build_select_columns(_REQUIRED, _OPTIONAL)

        for col in _REQUIRED:
            assert col in result

    def test_no_optional_always_returns_required(self):
        """When no optional columns provided, result is just the required list."""
        cursor = _make_probe_cursor(_LEGACY_COLS)
        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = cursor
            result = _build_select_columns(_REQUIRED)

        cols_in_result = [c.strip() for c in result.split(',')]
        assert set(cols_in_result) == set(_REQUIRED)


# ---------------------------------------------------------------------------
# TestGetBuildingCardDevSchema
# ---------------------------------------------------------------------------

class TestGetBuildingCardDevSchema:
    """get_building_card with dev schema (no divisare columns) does not 500."""

    def setup_method(self):
        clear_available_columns_cache()

    def test_dev_schema_no_divisare_cols_returns_card(self):
        """
        Simulate dev DB: probe returns legacy columns only (no divisare_*).
        get_building_card should return a valid card with image_url='' (no photos).
        """
        from apps.recommendation.engine import get_building_card

        dev_row = {
            'building_id': 'B00001',
            'name_en': 'Test Building',
            'project_name': 'Test Project',
            'architect': 'Arch',
            'location_country': 'Japan',
            'city': 'Tokyo',
            'year': 2020,
            'area_sqm': None,
            'program': 'Museum',
            'style': 'Contemporary',
            'atmosphere': 'calm',
            'color_tone': 'Cool White',
            'material': 'concrete',
            'material_visual': ['concrete'],
            'url': 'https://example.com',
            'tags': ['t1'],
            'image_photos': [],
            'image_drawings': [],
            # NOTE: divisare cols intentionally absent — dev schema
        }

        probe_cursor = _make_probe_cursor(_LEGACY_COLS)
        card_cursor = _make_card_cursor(dev_row)

        call_count = [0]

        def _cursor_factory():
            call_count[0] += 1
            if call_count[0] == 1:
                return probe_cursor
            return card_cursor

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = _cursor_factory
            result = get_building_card('B00001')

        assert result is not None
        assert result['building_id'] == 'B00001'
        # No photos and no divisare cover -> image_url = ''
        assert result['image_url'] == ''
        assert result['gallery'] == []

    def test_dev_schema_select_excludes_divisare_cols(self):
        """
        With dev schema, the SELECT issued to the card cursor must NOT contain
        cover_image_url_divisare or divisare_gallery_urls.
        """
        from apps.recommendation.engine import get_building_card

        dev_row = {
            'building_id': 'B00002',
            'name_en': 'B', 'project_name': 'P', 'architect': None,
            'location_country': None, 'city': None, 'year': None,
            'area_sqm': None, 'program': 'Office', 'style': None,
            'atmosphere': 'stark', 'color_tone': None, 'material': None,
            'material_visual': [], 'url': None, 'tags': [],
            'image_photos': [], 'image_drawings': [],
        }

        probe_cursor = _make_probe_cursor(_LEGACY_COLS)
        card_cursor = _make_card_cursor(dev_row)

        call_count = [0]

        def _cursor_factory():
            call_count[0] += 1
            if call_count[0] == 1:
                return probe_cursor
            return card_cursor

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = _cursor_factory
            get_building_card('B00002')

        # Inspect the SQL passed to the card cursor's execute
        executed_sql = card_cursor.execute.call_args[0][0]
        assert 'cover_image_url_divisare' not in executed_sql
        assert 'divisare_gallery_urls' not in executed_sql

    def test_prod_schema_select_includes_divisare_cols(self):
        """
        With prod schema (all cols present), the SELECT includes the optional cols.
        """
        from apps.recommendation.engine import get_building_card

        prod_row = {
            'building_id': 'B00003',
            'name_en': 'C', 'project_name': 'P', 'architect': None,
            'location_country': None, 'city': None, 'year': None,
            'area_sqm': None, 'program': 'Museum', 'style': None,
            'atmosphere': 'airy', 'color_tone': None, 'material': None,
            'material_visual': [], 'url': None, 'tags': [],
            'image_photos': [], 'image_drawings': [],
            'cover_image_url_divisare': 'https://example.com/cover.jpg',
            'divisare_gallery_urls': [],
        }

        probe_cursor = _make_probe_cursor(_PROD_COLS)
        card_cursor = _make_card_cursor(prod_row)

        call_count = [0]

        def _cursor_factory():
            call_count[0] += 1
            if call_count[0] == 1:
                return probe_cursor
            return card_cursor

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.side_effect = _cursor_factory
            result = get_building_card('B00003')

        executed_sql = card_cursor.execute.call_args[0][0]
        assert 'cover_image_url_divisare' in executed_sql
        assert 'divisare_gallery_urls' in executed_sql
        # image_url should use the divisare cover since no R2 photos
        assert result['image_url'] == 'https://example.com/cover.jpg'
