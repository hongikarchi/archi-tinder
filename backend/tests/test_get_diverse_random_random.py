"""
test_get_diverse_random_random.py -- Unit tests for get_diverse_random two-query pattern.

Verifies that the function no longer uses ORDER BY RANDOM() on the full corpus and
instead uses Python random.sample + a second targeted fetch, with proper ordering.

No real DB: connection.cursor is mocked.
"""
from unittest.mock import patch, MagicMock

from apps.recommendation.engine import get_diverse_random

# Column set that _get_available_columns() would return from a real DB probe.
_ALL_COLS = frozenset([
    'canonical_bld_id', 'name', 'architect_names', 'architects_text',
    'location_country', 'location_city', 'project_year',
    'program', 'style', 'atmosphere', 'color_tone', 'material_visual',
    'visual_description', 'covers_by_type', 'all_images', 'display_cover_url',
    'cover_image_url_default', 'source_urls',
])

_FULL_ROW_COLS = [
    'canonical_bld_id', 'name', 'architect_names', 'architects_text',
    'location_country', 'location_city', 'project_year',
    'program', 'style', 'atmosphere', 'color_tone', 'material_visual',
    'visual_description', 'covers_by_type', 'all_images', 'display_cover_url',
    'cover_image_url_default', 'source_urls',
    'embedding',
]


def _make_cursor_sequence(*fetchall_returns):
    """
    Return a context-manager-compatible cursor mock that yields successive
    fetchall() return values on each use (one per `with connection.cursor() as cur`).
    """
    cursors = []
    for i, rows in enumerate(fetchall_returns):
        cur = MagicMock()
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        cur.fetchall.return_value = rows
        if i == 0:
            # First cursor: ID-only fetch — no description needed (not _dictfetchall)
            cur.description = [('canonical_bld_id',)]
        else:
            # Second cursor: full row fetch — description used by _dictfetchall
            cur.description = [(col,) for col in _FULL_ROW_COLS]
        cursors.append(cur)

    conn = MagicMock()
    conn.cursor.side_effect = cursors
    return conn


def _build_full_row(canonical_bld_id):
    """Minimal DB row that _row_to_card won't blow up on. Embedding is a 3-dim unit vector."""
    vec = '[1.0,0.0,0.0]'
    return (
        canonical_bld_id,   # canonical_bld_id
        f'Building {canonical_bld_id}',  # name
        None, None, None, None, None,    # architect_names, architects_text, location_country, location_city, project_year
        None, None, None, None, None,    # program, style, atmosphere, color_tone, material_visual
        None, None, None, None, None,    # visual_description, covers_by_type, all_images, display_cover_url, cover_image_url_default
        None,                            # source_urls
        vec,                             # embedding::text
    )


class TestGetDiverseRandomNoOrderByRandom:
    """Regression guard: get_diverse_random must NOT emit ORDER BY RANDOM in SQL."""

    def test_no_order_by_random_in_sql(self):
        """SQL strings captured from cursor.execute must not contain ORDER BY RANDOM."""
        captured_sqls = []

        # Cursor 1: ID-only fetch
        cur1 = MagicMock()
        cur1.__enter__ = lambda s: s
        cur1.__exit__ = MagicMock(return_value=False)
        cur1.fetchall.return_value = [('bld_001',), ('bld_002',), ('bld_003',)]
        cur1.description = [('canonical_bld_id',)]

        def capture_execute_1(sql, params=None):
            captured_sqls.append(sql)
        cur1.execute.side_effect = capture_execute_1

        # Cursor 2: full row fetch
        cur2 = MagicMock()
        cur2.__enter__ = lambda s: s
        cur2.__exit__ = MagicMock(return_value=False)
        cur2.fetchall.return_value = [_build_full_row('bld_001'), _build_full_row('bld_002'), _build_full_row('bld_003')]
        cur2.description = [(col,) for col in _FULL_ROW_COLS]

        def capture_execute_2(sql, params=None):
            captured_sqls.append(sql)
        cur2.execute.side_effect = capture_execute_2

        conn = MagicMock()
        conn.cursor.side_effect = [cur1, cur2]

        with patch('apps.recommendation.engine.connection', conn), \
             patch('apps.recommendation.engine._get_available_columns', return_value=_ALL_COLS), \
             patch('apps.recommendation.engine.random.sample',
                   return_value=['bld_001', 'bld_002', 'bld_003']):
            get_diverse_random(n=2, filters=None)

        assert len(captured_sqls) >= 1, 'Expected at least one SQL to be captured'
        for sql in captured_sqls:
            assert 'ORDER BY RANDOM' not in sql.upper(), (
                f'ORDER BY RANDOM found in SQL — full corpus sort not eliminated:\n{sql}'
            )

    def test_sample_order_preserved_through_pk_reorder(self):
        """
        When Postgres ANY(...) returns rows in PK order, the output must still
        match the random.sample order, not PK order.

        Setup:
          - DB has IDs in PK order: bld_001, bld_002, bld_003
          - random.sample yields order: bld_003, bld_001, bld_002  (different from PK)
          - Postgres ANY(...) returns rows back in PK order: bld_001, bld_002, bld_003
          - Expected output order: bld_003, bld_001, bld_002  (sample order)
        """
        all_db_ids_pk_order = [('bld_001',), ('bld_002',), ('bld_003',)]
        sample_order = ['bld_003', 'bld_001', 'bld_002']

        # Second query rows come back in PK order from Postgres ANY(...)
        rows_pk_order = [
            _build_full_row('bld_001'),
            _build_full_row('bld_002'),
            _build_full_row('bld_003'),
        ]

        mock_conn = _make_cursor_sequence(
            all_db_ids_pk_order,  # first cursor: ID-only fetch
            rows_pk_order,        # second cursor: full row fetch
        )

        with patch('apps.recommendation.engine.connection', mock_conn), \
             patch('apps.recommendation.engine._get_available_columns', return_value=_ALL_COLS), \
             patch('apps.recommendation.engine.random.sample',
                   return_value=sample_order) as mock_sample:
            result = get_diverse_random(n=3, filters=None)

        # random.sample was called (two-query path taken)
        mock_sample.assert_called_once()

        # get_diverse_random applies greedy farthest-point; with identical unit
        # vectors [1,0,0] all cosine distances are 0 — so output order depends
        # solely on the pool order coming into the greedy loop, which must be
        # sample_order (not PK order).
        result_ids = [card['canonical_bld_id'] for card in result]
        # With identical unit vectors [1,0,0] the cosine distance between any pair
        # is 0, so the greedy loop never advances the best candidate — it always
        # picks remaining[0] in pool order.  The pool order is the sample_order
        # (after PK reorder); so the full output order must be sample_order.
        assert result_ids == sample_order, (
            f'Expected sample order {sample_order}, got {result_ids}. '
            'Postgres PK order may have leaked through the rows_by_id reorder.'
        )

    def test_empty_pool_returns_empty(self):
        """Empty first query (no matching buildings) returns [] without a second query."""
        cur1 = MagicMock()
        cur1.__enter__ = lambda s: s
        cur1.__exit__ = MagicMock(return_value=False)
        cur1.fetchall.return_value = []
        cur1.description = [('canonical_bld_id',)]

        conn = MagicMock()
        conn.cursor.return_value = cur1

        with patch('apps.recommendation.engine.connection', conn), \
             patch('apps.recommendation.engine._get_available_columns', return_value=_ALL_COLS):
            result = get_diverse_random(n=5, filters=None)

        assert result == [], f'Expected empty list, got {result}'
        # Should only have called cursor once (ID fetch), not twice
        assert conn.cursor.call_count == 1, (
            'Expected only one cursor call for empty pool, '
            f'got {conn.cursor.call_count}'
        )
