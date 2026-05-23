"""
test_get_top_k_no_pref_order.py -- Unit test for get_top_k_results no-pref order fix.

Verifies that when pref_vector is None (no-preference branch), the returned cards
are presented in the Python random.sample order (sampled_ids), NOT in Postgres
IN (...) PK/index order.

No real DB: connection.cursor is mocked; random.sample is patched to return a
deterministic order different from the PK order that Postgres would return.
"""
from unittest.mock import patch, MagicMock

from apps.recommendation.engine import get_top_k_results

# Column set that _get_available_columns() would return from a real DB probe.
_ALL_COLS = frozenset([
    'canonical_bld_id', 'name', 'architect_names', 'architects_text',
    'location_country', 'location_city', 'project_year',
    'program', 'style', 'atmosphere', 'color_tone', 'material_visual',
    'visual_description', 'covers_by_type', 'all_images', 'display_cover_url',
    'cover_image_url_default', 'source_urls',
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor_sequence(*fetchall_returns):
    """
    Return a context-manager-compatible cursor mock that yields successive
    fetchall() return values on each use (one per `with connection.cursor() as cur`).
    """
    cursors = []
    for rows in fetchall_returns:
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = rows
        # description needed by _dictfetchall on the second query
        cur.description = [(col,) for col in [
            'canonical_bld_id', 'name', 'architect_names', 'architects_text',
            'location_country', 'location_city', 'project_year',
            'program', 'style', 'atmosphere', 'color_tone', 'material_visual',
            'visual_description', 'covers_by_type', 'all_images', 'display_cover_url',
            'cover_image_url_default', 'source_urls',
        ]]
        cursors.append(cur)

    conn = MagicMock()
    conn.cursor.side_effect = cursors
    return conn


def _build_full_row(canonical_bld_id):
    """Minimal DB row that _row_to_card won't blow up on."""
    return (
        canonical_bld_id,  # canonical_bld_id
        f'Building {canonical_bld_id}',  # name
        None,   # architect_names
        None,   # architects_text
        None,   # location_country
        None,   # location_city
        None,   # project_year
        None,   # program
        None,   # style
        None,   # atmosphere
        None,   # color_tone
        None,   # material_visual
        None,   # visual_description
        None,   # covers_by_type
        None,   # all_images
        None,   # display_cover_url
        None,   # cover_image_url_default
        None,   # source_urls
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestGetTopKResultsNoPrefOrder:
    """get_top_k_results no-pref branch: sampled_ids order must be preserved."""

    def test_no_pref_preserves_sample_order(self):
        """
        When no preferences, the returned card sequence matches sampled_ids order,
        NOT the PK/index order that Postgres returns for IN (...) queries.

        Setup:
          - DB has IDs in PK order: bld_001, bld_002, bld_003
          - random.sample yields order: bld_003, bld_001, bld_002  (different from PK)
          - Postgres IN(...) returns rows back in PK order: bld_001, bld_002, bld_003
          - Expected output order: bld_003, bld_001, bld_002  (sample order)
        """
        all_db_ids_pk_order = [('bld_001',), ('bld_002',), ('bld_003',)]
        sample_order = ['bld_003', 'bld_001', 'bld_002']

        # Second query rows come back in PK order from Postgres IN (...)
        rows_pk_order = [
            _build_full_row('bld_001'),
            _build_full_row('bld_002'),
            _build_full_row('bld_003'),
        ]

        mock_conn = _make_cursor_sequence(
            all_db_ids_pk_order,  # first cursor: ID fetch
            rows_pk_order,        # second cursor: full row fetch
        )

        with patch('apps.recommendation.engine.connection', mock_conn), \
             patch('apps.recommendation.engine._get_available_columns',
                   return_value=_ALL_COLS), \
             patch('apps.recommendation.engine.random.sample',
                   return_value=sample_order) as mock_sample:

            result = get_top_k_results(
                pref_vector=None,
                exposed_ids=[],
                k=3,
            )

        # random.sample was called (no-pref path taken)
        mock_sample.assert_called_once()

        # Output order must match sampled_ids, not PK order
        result_ids = [card['canonical_bld_id'] for card in result]
        assert result_ids == sample_order, (
            f'Expected sample order {sample_order}, got {result_ids}. '
            'Postgres IN(...) order leaked through — reorder fix not applied.'
        )

    def test_no_pref_empty_pool(self):
        """Empty DB -> empty result, no crash."""
        mock_conn = _make_cursor_sequence(
            [],  # first cursor: no IDs
        )

        with patch('apps.recommendation.engine.connection', mock_conn), \
             patch('apps.recommendation.engine._get_available_columns',
                   return_value=_ALL_COLS):
            result = get_top_k_results(
                pref_vector=None,
                exposed_ids=[],
                k=5,
            )

        assert result == []
