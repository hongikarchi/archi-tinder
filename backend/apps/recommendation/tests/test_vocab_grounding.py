"""
test_vocab_grounding.py -- BACK-PARSER-VOCAB-1: DB-grounded vocab + snap tests.

Covers:
  - get_axis_vocab: DB-failure -> snapshot fallback (mock connections['buildings']
    cursor to raise).
  - engine_filters: architectural_elements filter produces the EXISTS unnest SQL
    fragment + '%Courtyard%' param in the IDF score cases.
"""
from unittest.mock import MagicMock, patch

import pytest

from apps.recommendation.services.vocab import _VOCAB_SNAPSHOT, get_axis_vocab


# ---------------------------------------------------------------------------
# get_axis_vocab: DB failure -> snapshot fallback
# ---------------------------------------------------------------------------

class TestGetAxisVocabFallback:

    def test_full_connection_failure_falls_back_to_snapshot(self):
        """connections['buildings'] raising entirely -> full snapshot fallback."""
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.side_effect = RuntimeError('DB unreachable')
                result = get_axis_vocab()

        for axis, values in _VOCAB_SNAPSHOT.items():
            assert result[axis] == values

    def test_per_axis_query_failure_falls_back_per_axis(self):
        """One axis's cursor.execute raises -> that axis falls back to snapshot,
        other axes still come from the (mocked) live query."""
        mock_cursor = MagicMock()

        call_log = {'n': 0}

        def _execute(sql, *a, **kw):
            call_log['n'] += 1
            if 'style' in sql:
                raise RuntimeError('style column query failed')

        mock_cursor.execute.side_effect = _execute
        mock_cursor.fetchall.return_value = [('Custom Value',)]

        mock_cm = MagicMock()
        mock_cm.__enter__ = lambda s: mock_cursor
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.return_value.cursor.return_value = mock_cm
                result = get_axis_vocab()

        # style failed -> snapshot fallback for style specifically
        assert result['style'] == _VOCAB_SNAPSHOT['style']
        # other axes succeeded via the (mocked) live query
        assert result['atmosphere'] == ['Custom Value']

    def test_empty_axis_result_falls_back_to_snapshot(self):
        """Live query succeeds but returns zero rows for an axis -> snapshot fallback
        for that axis (per spec: 'any axis coming back empty' triggers fallback)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_cm = MagicMock()
        mock_cm.__enter__ = lambda s: mock_cursor
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.return_value.cursor.return_value = mock_cm
                result = get_axis_vocab()

        for axis, values in _VOCAB_SNAPSHOT.items():
            assert result[axis] == values

    def test_never_raises(self):
        """get_axis_vocab must never propagate an exception to the caller."""
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.side_effect = RuntimeError('cache backend down')
            # Should not raise even when the cache backend itself is broken.
            try:
                result = get_axis_vocab()
            except Exception as e:  # noqa: BLE001
                pytest.fail(f'get_axis_vocab raised: {e}')
            assert isinstance(result, dict)

    def test_cache_hit_returns_cached_value_without_db_call(self):
        cached_value = {'style': ['CachedStyle']}
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = cached_value
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                result = get_axis_vocab()
                mock_conns.__getitem__.assert_not_called()
        assert result == cached_value


# ---------------------------------------------------------------------------
# engine_filters: architectural_elements EXISTS/unnest scoring
# ---------------------------------------------------------------------------

class TestEngineFiltersArchitecturalElements:

    def test_architectural_elements_produces_exists_unnest_case(self):
        from apps.recommendation.engine_filters import _build_idf_score_cases

        base_weights = {
            'architectural_elements': 4.0,
            '_idf_ceiling': 3.0, '_priority_boost': 0.25,
        }
        cases, params, total = _build_idf_score_cases(
            {'architectural_elements': 'Courtyard'}, base_weights, {'_total': 0}, [],
        )
        assert len(cases) == 1
        assert 'EXISTS' in cases[0]
        assert 'unnest(architectural_elements)' in cases[0]
        assert 'ILIKE %s' in cases[0]
        assert '%Courtyard%' in params
        assert total > 0

    def test_architectural_elements_in_idf_score_axes_allowlist(self):
        from apps.recommendation.engine_filters import _IDF_SCORE_AXES
        assert 'architectural_elements' in _IDF_SCORE_AXES

    def test_architectural_elements_not_in_required_slate(self):
        """architectural_elements must NOT be added to the required-slate set."""
        from apps.recommendation.engine_filters import _REQUIRED_SLATE_FIELDS_SET
        assert 'architectural_elements' not in _REQUIRED_SLATE_FIELDS_SET
        assert len(_REQUIRED_SLATE_FIELDS_SET) == 4

    def test_none_value_produces_no_case(self):
        from apps.recommendation.engine_filters import _build_idf_score_cases
        base_weights = {'architectural_elements': 4.0, '_idf_ceiling': 3.0, '_priority_boost': 0.25}
        cases, params, total = _build_idf_score_cases(
            {'architectural_elements': None}, base_weights, {'_total': 0}, [],
        )
        assert cases == []
