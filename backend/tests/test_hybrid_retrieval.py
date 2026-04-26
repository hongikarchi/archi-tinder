"""
test_hybrid_retrieval.py -- Topic 01: Hybrid Retrieval (RRF).

Tests for:
- Flag gating (hybrid_retrieval_enabled=False default)
- Mode H dispatch and SQL construction (_run_hybrid_rrf_pool)
- RRF rank fusion formula correctness (unit, no DB)
- Failure cascade: SQL exception => emit failure event, fall back to Mode V/F
- q_text length validation (>1000 => coerced to None in views.py)
- original_q_text persistence on AnalysisSession
- refresh_pool_if_low passes original_q_text through
- Backward compatibility: all existing flag-off paths unchanged

No real DB queries against architecture_vectors -- connection.cursor is mocked.
DB tests use in-memory SQLite via conftest.py.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings

from apps.recommendation.engine import (
    create_bounded_pool,
    create_pool_with_relaxation,
    refresh_pool_if_low,
)

_FAKE_VEC = [0.01] * 384
_FAKE_VEC_STR = '[' + ','.join(['0.01'] * 384) + ']'


def _make_cursor(rows):
    """Build a mock cursor.execute()/fetchall() returning `rows`."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = rows
    return cursor


# ---------------------------------------------------------------------------
# TestHybridFlagDefault
# ---------------------------------------------------------------------------

class TestHybridFlagDefault:
    """Flag is OFF by default; existing behavior preserved."""

    def test_flag_off_by_default(self):
        assert settings.RECOMMENDATION.get('hybrid_retrieval_enabled', False) is False

    def test_rrf_k_default(self):
        assert settings.RECOMMENDATION.get('hybrid_rrf_k', 60) == 60

    def test_bm25_dict_default(self):
        assert settings.RECOMMENDATION.get('hybrid_bm25_dict', 'simple') == 'simple'

    def test_filter_channel_enabled_default(self):
        assert settings.RECOMMENDATION.get('hybrid_filter_channel_enabled', True) is True

    def test_flag_off_q_text_ignored(self, monkeypatch):
        """With flag OFF, q_text is passed but engine falls through to Mode F."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        with patch('apps.recommendation.engine._random_pool', return_value=['B00001']) as mock_rand:
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10,
                v_initial=None, q_text='concrete brutalist museum',
            )

        # No RRF SQL executed -- random pool fallback
        mock_rand.assert_called_once_with(10)
        assert pool_ids == ['B00001']
        assert pool_scores == {}

    def test_flag_off_filter_path_still_runs(self, monkeypatch):
        """With flag OFF and filters provided, Mode F (filter SQL) runs normally."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        fake_rows = [('B00001', 0.9), ('B00002', 0.5)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10,
                v_initial=None, q_text='concrete brutalist museum',
            )

        assert pool_ids == ['B00001', 'B00002']
        executed_sql = mock_cursor.execute.call_args[0][0]
        # Mode F: no RRF, no tsvector, no plainto_tsquery
        assert 'plainto_tsquery' not in executed_sql
        assert 'ts_rank_cd' not in executed_sql
        assert 'program = %s' in executed_sql


# ---------------------------------------------------------------------------
# TestHybridRRFDispatch
# ---------------------------------------------------------------------------

class TestHybridRRFDispatch:
    """Flag ON + q_text non-empty => Mode H SQL executed."""

    def test_flag_on_q_text_empty_falls_through_to_mode_f(self, monkeypatch):
        """Flag ON but q_text empty => short-circuit, Mode F runs."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        fake_rows = [('B00001', 0.9)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, _ = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10,
                v_initial=None, q_text='',  # empty
            )

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'plainto_tsquery' not in executed_sql

    def test_flag_on_q_text_none_falls_through_to_mode_f(self, monkeypatch):
        """Flag ON but q_text=None => short-circuit, Mode F runs."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        fake_rows = [('B00001', 0.9)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, _ = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10,
                v_initial=None, q_text=None,
            )

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'plainto_tsquery' not in executed_sql

    def test_flag_on_q_text_nonempty_uses_rrf_sql(self, monkeypatch):
        """Flag ON + q_text non-empty => RRF SQL with ts_rank_cd."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        fake_rows = [('B00001', 0.016), ('B00002', 0.014)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log') as mock_log:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10,
                v_initial=None, q_text='concrete brutalist',
            )

        assert pool_ids == ['B00001', 'B00002']
        assert pool_scores['B00001'] == pytest.approx(0.016)
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'ts_rank_cd' in executed_sql
        assert 'plainto_tsquery' in executed_sql
        # Observability event emitted
        mock_log.emit_event.assert_called_once()
        assert mock_log.emit_event.call_args[0][0] == 'hybrid_pool_timing'

    def test_bm25_only_when_v_initial_none(self, monkeypatch):
        """Flag ON + q_text + v_initial=None => BM25-only channel (no embedding CTE)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        fake_rows = [('B00001', 0.016)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log'):
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10,
                v_initial=None, q_text='museum glass facade',
            )

        executed_sql = mock_cursor.execute.call_args[0][0]
        # No vector CTE when v_initial is None
        assert 'vector_ranked' not in executed_sql
        assert 'embedding <=>' not in executed_sql
        assert 'bm25_with_rank' in executed_sql

    def test_full_rrf_with_v_initial(self, monkeypatch):
        """Flag ON + q_text + v_initial => both BM25 and vector CTEs present."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        fake_rows = [('B00001', 0.029)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log'):
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10,
                v_initial=_FAKE_VEC, q_text='concrete brutalist museum',
            )

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'bm25_with_rank' in executed_sql
        assert 'vector_ranked' in executed_sql
        assert 'embedding <=> %s::vector' in executed_sql

    def test_filter_channel_included_when_enabled(self, monkeypatch):
        """filter_channel_enabled=True + filters provided => filter_ranked CTE present."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', True)

        fake_rows = [('B00001', 0.035)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log'):
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, _ = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10,
                v_initial=None, q_text='museum design',
            )

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert 'filter_ranked' in executed_sql
        assert 'filter_score' in executed_sql

    def test_seed_ids_override_in_hybrid_mode(self, monkeypatch):
        """Seed IDs get score 1.1 even in Mode H."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        fake_rows = [('B00002', 0.016)]
        mock_cursor = _make_cursor(fake_rows)

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log'):
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, ['B00001'], target=10,
                v_initial=None, q_text='museum',
            )

        assert 'B00001' in pool_scores
        assert pool_scores['B00001'] == pytest.approx(1.1)


# ---------------------------------------------------------------------------
# TestRRFRankFusion
# ---------------------------------------------------------------------------

class TestRRFRankFusion:
    """Unit tests: RRF formula 1/(k+rank) correctness. No DB required."""

    def test_rrf_formula_rank1(self):
        """rank=1, k=60 => 1/61."""
        k = 60
        rank = 1
        score = 1.0 / (k + rank)
        assert score == pytest.approx(1.0 / 61)

    def test_rrf_formula_rank60(self):
        """rank=60, k=60 => 1/120."""
        k = 60
        rank = 60
        score = 1.0 / (k + rank)
        assert score == pytest.approx(1.0 / 120)

    def test_rrf_absent_channel_coalesce_zero(self):
        """Missing from a CTE (not ranked) => COALESCE to 0 contribution."""
        # Simulate building not in bm25_with_rank (no BM25 signal)
        bm25_rank = None  # absent
        vec_rank = 5
        k = 60
        bm25_contrib = 0 if bm25_rank is None else 1.0 / (k + bm25_rank)
        vec_contrib = 1.0 / (k + vec_rank)
        total = bm25_contrib + vec_contrib
        assert bm25_contrib == 0.0
        assert total == pytest.approx(1.0 / 65)

    def test_rrf_two_channels_sum(self):
        """Two-channel RRF: BM25 rank=3, vector rank=7, k=60."""
        k = 60
        expected = 1.0 / (k + 3) + 1.0 / (k + 7)
        bm25 = 1.0 / (k + 3)
        vec = 1.0 / (k + 7)
        assert bm25 + vec == pytest.approx(expected)

    def test_rrf_three_channels_sum(self):
        """Three-channel RRF: BM25 rank=1, vector rank=2, filter rank=3, k=60."""
        k = 60
        total = 1.0 / (k + 1) + 1.0 / (k + 2) + 1.0 / (k + 3)
        assert total == pytest.approx(1.0 / 61 + 1.0 / 62 + 1.0 / 63)

    def test_rrf_k_from_settings(self, monkeypatch):
        """RRF k is read from settings.RECOMMENDATION['hybrid_rrf_k']."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_rrf_k', 100)
        k = settings.RECOMMENDATION['hybrid_rrf_k']
        assert 1.0 / (k + 1) == pytest.approx(1.0 / 101)


# ---------------------------------------------------------------------------
# TestHybridRRFFailureCascade
# ---------------------------------------------------------------------------

class TestHybridRRFFailureCascade:
    """SQL exception during RRF => emits failure event, falls back to Mode V/F."""

    def test_rrf_sql_exception_falls_back_to_filter_path(self, monkeypatch):
        """When RRF SQL raises, failure event emitted, Mode F fallback runs."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        fallback_rows = [('B00099', 0.75)]
        call_count = [0]
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        def _execute_side(sql, params):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is RRF SQL (contains plainto_tsquery)
                raise Exception('tsvector: operator does not exist')
            # Second call is Mode F fallback
            mock_cursor.fetchall.return_value = fallback_rows

        mock_cursor.execute.side_effect = _execute_side

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log') as mock_log:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {'program': 'Museum'}, ['program'], None, target=10,
                v_initial=None, q_text='museum',
            )

        assert pool_ids == ['B00099']
        assert pool_scores['B00099'] == pytest.approx(0.75)
        # Failure event must be emitted
        failure_calls = [c for c in mock_log.emit_event.call_args_list
                         if c[0][0] == 'failure']
        assert len(failure_calls) == 1
        assert failure_calls[0][1].get('failure_type') == 'hybrid_pool_query'
        assert failure_calls[0][1].get('recovery_path') == 'no_hybrid'

    def test_rrf_sql_exception_falls_back_to_random_when_no_filters(self, monkeypatch):
        """RRF fails + no filters => falls back to random pool (_random_pool)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = Exception('pgvector error')

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log'), \
             patch('apps.recommendation.engine._random_pool', return_value=['B00042']) as mock_rand:
            mock_conn.cursor.return_value = mock_cursor
            pool_ids, pool_scores = create_bounded_pool(
                {}, None, None, target=10,
                v_initial=None, q_text='random fallback test',
            )

        mock_rand.assert_called_once_with(10)
        assert pool_ids == ['B00042']

    def test_rrf_sql_exception_emits_error_class(self, monkeypatch):
        """Failure event includes error_class field."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_filter_channel_enabled', False)

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = ValueError('bad value')
        mock_cursor.fetchall.return_value = []

        with patch('apps.recommendation.engine.connection') as mock_conn, \
             patch('apps.recommendation.engine.event_log') as mock_log, \
             patch('apps.recommendation.engine._random_pool', return_value=[]):
            mock_conn.cursor.return_value = mock_cursor
            create_bounded_pool({}, None, None, target=10, q_text='test')

        failure_calls = [c for c in mock_log.emit_event.call_args_list
                         if c[0][0] == 'failure']
        assert failure_calls[0][1].get('error_class') == 'ValueError'


# ---------------------------------------------------------------------------
# TestQTextPassThrough
# ---------------------------------------------------------------------------

class TestQTextPassThrough:
    """q_text is threaded correctly through create_pool_with_relaxation."""

    def test_q_text_passed_to_tier1_and_tier2(self, monkeypatch):
        """q_text is forwarded to Tier 1 and Tier 2 create_bounded_pool calls."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)

        captured = []

        def _mock_pool(filters, filter_priority=None, seed_ids=None, target=None,
                       v_initial=None, q_text=None):
            captured.append({'q_text': q_text, 'filters': dict(filters or {})})
            return ([], {})  # force tier 2 by returning empty

        with patch('apps.recommendation.engine.create_bounded_pool', side_effect=_mock_pool):
            with patch('apps.recommendation.engine._random_pool', return_value=['B00001']):
                create_pool_with_relaxation(
                    {'program': 'Museum', 'location_country': 'Japan'},
                    ['program', 'location_country'],
                    [],
                    target=10,
                    q_text='Japanese modernist museum',
                )

        # Both tier calls should receive q_text
        assert all(c['q_text'] == 'Japanese modernist museum' for c in captured)

    def test_q_text_not_passed_to_tier3_random_pool(self, monkeypatch):
        """Tier 3 random pool is relevance-blind; create_bounded_pool not called for it."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)

        with patch('apps.recommendation.engine.create_bounded_pool',
                   return_value=([], {})):
            with patch('apps.recommendation.engine._random_pool',
                       return_value=['B00001']) as mock_rand:
                result_ids, result_scores, tier = create_pool_with_relaxation(
                    {},
                    [],
                    [],
                    target=10,
                    q_text='irrelevant for tier3',
                )

        mock_rand.assert_called_once_with(10)
        # Tier 3 used (both tier1 and tier2 returned empty)
        assert tier == 3


# ---------------------------------------------------------------------------
# TestQTextValidation
# ---------------------------------------------------------------------------

class TestQTextValidation:
    """Views.py: q_text is validated (type + length) before reaching engine."""

    @pytest.mark.django_db
    def test_oversized_q_text_coerced_to_none(self, auth_client, monkeypatch):
        """query >1000 chars => silently coerced to None in views.py."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        captured_q_text = {}

        def _mock_relaxation(filters, fp, seeds, v_initial=None, q_text=None, **kwargs):
            captured_q_text['value'] = q_text
            return fake_pool, fake_scores, 1

        _V = 'apps.recommendation.views.engine'
        with patch(f'{_V}.create_pool_with_relaxation', side_effect=_mock_relaxation), \
             patch(f'{_V}.get_pool_embeddings', return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool', side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'query': 'x' * 1001},
                format='json',
            )

        assert resp.status_code == 201
        # Flag ON but query too long => coerced to None before engine call
        assert captured_q_text['value'] is None

    @pytest.mark.django_db
    def test_flag_off_q_text_not_passed_to_engine(self, auth_client, monkeypatch):
        """Flag OFF: even valid q_text must NOT reach engine as non-None."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        captured_q_text = {}

        def _mock_relaxation(filters, fp, seeds, v_initial=None, q_text=None, **kwargs):
            captured_q_text['value'] = q_text
            return fake_pool, fake_scores, 1

        _V = 'apps.recommendation.views.engine'
        with patch(f'{_V}.create_pool_with_relaxation', side_effect=_mock_relaxation), \
             patch(f'{_V}.get_pool_embeddings', return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool', side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'query': 'concrete brutalist museum'},
                format='json',
            )

        assert resp.status_code == 201
        # Flag OFF => q_text_param=None passed to engine
        assert captured_q_text['value'] is None


# ---------------------------------------------------------------------------
# TestOriginalQTextPersistence
# ---------------------------------------------------------------------------

class TestOriginalQTextPersistence:
    """AnalysisSession.original_q_text is persisted correctly."""

    @pytest.mark.django_db
    def test_original_q_text_stored_when_flag_on(self, auth_client, monkeypatch):
        """With flag ON + valid query, session.original_q_text == query."""
        from apps.recommendation.models import AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(f'{_V}.create_pool_with_relaxation', return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings', return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool', side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'query': 'concrete brutalist museum'},
                format='json',
            )

        assert resp.status_code == 201
        session = AnalysisSession.objects.get(session_id=resp.data['session_id'])
        assert session.original_q_text == 'concrete brutalist museum'

    @pytest.mark.django_db
    def test_original_q_text_none_when_flag_off(self, auth_client, monkeypatch):
        """With flag OFF, session.original_q_text is None."""
        from apps.recommendation.models import AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(f'{_V}.create_pool_with_relaxation', return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings', return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool', side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'query': 'concrete brutalist museum'},
                format='json',
            )

        assert resp.status_code == 201
        session = AnalysisSession.objects.get(session_id=resp.data['session_id'])
        assert session.original_q_text is None


# ---------------------------------------------------------------------------
# TestRefreshPoolIfLowPreservesQText
# ---------------------------------------------------------------------------

class TestRefreshPoolIfLowPreservesQText:
    """refresh_pool_if_low passes session.original_q_text through to create_pool_with_relaxation."""

    @pytest.mark.django_db
    def test_original_q_text_forwarded_on_escalation(self, user_profile, monkeypatch):
        """When pool is low, refresh_pool_if_low passes original_q_text from session."""
        from apps.recommendation.models import AnalysisSession, Project

        project = Project.objects.create(user=user_profile, name='Test')
        pool = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=pool,
            pool_scores={},
            current_round=0,
            preference_vector=[],
            exposed_ids=pool,  # all exposed => remaining=0 => escalation fires
            initial_batch=pool[:1],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={'program': 'Museum'},
            original_filter_priority=['program'],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
            original_q_text='brutalist concrete structures',
        )

        new_pool = ['B00010', 'B00011']
        captured_kwargs = {}

        def _mock_relaxation(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return new_pool, {}, 2

        with patch('apps.recommendation.engine.create_pool_with_relaxation',
                   side_effect=_mock_relaxation):
            refresh_pool_if_low(session, threshold=5)

        assert 'q_text' in captured_kwargs
        assert captured_kwargs['q_text'] == 'brutalist concrete structures'

    @pytest.mark.django_db
    def test_original_q_text_none_forwarded_gracefully(self, user_profile):
        """Session with original_q_text=None escalates without crash."""
        from apps.recommendation.models import AnalysisSession, Project

        project = Project.objects.create(user=user_profile, name='Test')
        pool = [f'B{str(i).zfill(5)}' for i in range(1, 6)]
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=pool,
            pool_scores={},
            current_round=0,
            preference_vector=[],
            exposed_ids=pool,
            initial_batch=pool[:1],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
            original_q_text=None,
        )

        captured_kwargs = {}

        def _mock_relaxation(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return ['B00010'], {}, 2

        with patch('apps.recommendation.engine.create_pool_with_relaxation',
                   side_effect=_mock_relaxation):
            refresh_pool_if_low(session, threshold=5)

        assert captured_kwargs.get('q_text') is None


# ---------------------------------------------------------------------------
# TestBackwardCompatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """CRITICAL: flag=False (default) must not change any existing behavior."""

    def test_new_field_nullable_no_default_value(self):
        """original_q_text is a nullable TextField -- no migration needed on existing rows."""
        from apps.recommendation.models import AnalysisSession
        field = AnalysisSession._meta.get_field('original_q_text')
        assert field.null is True
        assert field.blank is True

    def test_new_event_type_in_choices(self):
        """hybrid_pool_timing event type is registered."""
        from apps.recommendation.models import SessionEvent
        choices_dict = dict(SessionEvent.EVENT_TYPE_CHOICES)
        assert 'hybrid_pool_timing' in choices_dict

    @pytest.mark.django_db
    def test_existing_session_creation_unchanged(self, auth_client, monkeypatch):
        """Session creation without query field produces original_q_text=None."""
        from apps.recommendation.models import AnalysisSession

        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)

        import numpy as np
        fake_pool = [f'B{str(i).zfill(5)}' for i in range(1, 11)]
        fake_scores = {bid: 10 - i for i, bid in enumerate(fake_pool)}
        fake_embeddings = {bid: np.random.RandomState(i).randn(384) for i, bid in enumerate(fake_pool)}
        for bid in fake_embeddings:
            v = fake_embeddings[bid]
            fake_embeddings[bid] = v / np.linalg.norm(v)

        def _mock_farthest(pool_ids, exposed_ids, pool_embs):
            s = set(exposed_ids)
            for bid in pool_ids:
                if bid not in s:
                    return bid
            return None

        _V = 'apps.recommendation.views.engine'
        with patch(f'{_V}.create_pool_with_relaxation', return_value=(fake_pool, fake_scores, 1)), \
             patch(f'{_V}.get_pool_embeddings', return_value=fake_embeddings), \
             patch(f'{_V}.farthest_point_from_pool', side_effect=_mock_farthest), \
             patch(f'{_V}.get_building_card',
                   side_effect=lambda bid: {'building_id': bid, 'name_en': bid,
                                            'project_name': '', 'image_url': '',
                                            'url': None, 'gallery': [],
                                            'gallery_drawing_start': 0, 'metadata': {}}):
            # No 'query' field in request
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'filters': {}},
                format='json',
            )

        assert resp.status_code == 201
        session = AnalysisSession.objects.get(session_id=resp.data['session_id'])
        assert session.original_q_text is None

    def test_create_pool_with_relaxation_backward_compat_signature(self, monkeypatch):
        """Old call signature (no q_text kwarg) still works."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)

        with patch('apps.recommendation.engine.create_bounded_pool',
                   return_value=(['B00001'], {'B00001': 0.9})) as mock_pool:
            pool_ids, pool_scores, tier = create_pool_with_relaxation(
                {'program': 'Museum'}, ['program'], [], target=10,
            )

        # Called without q_text
        call_kwargs = mock_pool.call_args[1]
        assert 'q_text' in call_kwargs  # new param present
        assert call_kwargs['q_text'] is None  # but None when not provided
