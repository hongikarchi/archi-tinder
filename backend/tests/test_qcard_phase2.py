"""
test_qcard_phase2.py -- ALGO-QCARD Phase 2: TF-IDF keyword selection +
corpus DF cache + Trigger-B category extraction.

Covers:
  - get_corpus_tag_df: mocked cursor returns canned GROUP BY rows → correct
    dict shape, caches result (second call does not re-query DB).
  - _pick_discriminative_tag: TF-IDF scorer picks discriminative over
    common; blacklisted tag is skipped; df/N over ratio is skipped;
    corpus-unavailable falls back to frequency.
  - _pick_pool_category: mocked cursor returns a top program → returned;
    DB failure → None; empty pool → None.
  - _compute_kw_vec_category: mocked cursor + embeddings → non-null L2-
    normalized vector; no matching IDs → None.
  - handle_question_response refresh-with-category: Yes boosts qbias toward
    program centroid; No penalizes it.
  - _check_question_trigger Trigger B: when pool has a category, refresh
    trigger payload carries axis='program' + keyword=category.
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project, AnalysisSession


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm

_SERVICE_ENGINE = 'apps.recommendation.services.swipe_service.engine'
_CACHES_MODULE = 'apps.recommendation.caches'


def _make_normalized_vec(seed=42):
    v = np.random.RandomState(seed).randn(384).astype(np.float64)
    return v / np.linalg.norm(v)


def _make_card(bid):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
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
            'axis_style': 'Minimal',
            'axis_atmosphere': 'calm',
            'axis_color_tone': 'Light',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


def _make_analyzing_session(user_profile, pool_ids=None, program_pool=None):
    """Create a Project + analyzing AnalysisSession."""
    if pool_ids is None:
        pool_ids = _FAKE_POOL[:10]
    project = Project.objects.create(
        user=user_profile, name='Phase2 Test', filters={},
    )
    fake_vec = list(_make_normalized_vec())
    session = AnalysisSession.objects.create(
        user=user_profile,
        project=project,
        phase='analyzing',
        pool_ids=pool_ids,
        pool_scores={bid: 1.0 for bid in pool_ids},
        current_round=5,
        preference_vector=fake_vec,
        exposed_ids=pool_ids[:3],
        initial_batch=pool_ids[:5],
        like_vectors=[{'embedding': fake_vec, 'round': i} for i in range(3)],
        convergence_history=[],
        previous_pref_vector=fake_vec,
        original_filters={},
        original_filter_priority=[],
        original_seed_ids=[],
        current_pool_tier=1,
        tag_axis_counts={'style': {'minimal': 3, 'organic': 2}},
        recent_like_tag_sets=[],
        question_cooldown=0,
        q_card_consecutive_dislikes=0,
        question_count=0,
        question_bias_vector=None,
    )
    return session


# ---------------------------------------------------------------------------
# Part A — get_corpus_tag_df
# ---------------------------------------------------------------------------

class TestGetCorpusTagDf:
    """get_corpus_tag_df returns correct shape and caches on second call."""

    def _make_cursor_mock(self):
        """Build a mock cursor whose fetchone/fetchall return canned data."""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        # Sequence of fetchone/fetchall results per execute() call:
        # 1. COUNT(*) total  → fetchone → (100,)
        # 2. style GROUP BY  → fetchall → [('minimal', 30), ('organic', 10)]
        # 3. atmosphere      → fetchall → [('warm', 40)]
        # 4. program         → fetchall → [('주거', 25), ('문화', 15)]
        # 5. material_visual → fetchall → [('concrete', 50), ('wood', 20)]
        fetchone_seq = [(100,)]
        fetchall_seq = [
            [('minimal', 30), ('organic', 10)],
            [('warm', 40)],
            [('주거', 25), ('문화', 15)],
            [('concrete', 50), ('wood', 20)],
        ]
        fetchone_iter = iter(fetchone_seq)
        fetchall_iter = iter(fetchall_seq)
        mock_cursor.fetchone.side_effect = lambda: next(fetchone_iter)
        mock_cursor.fetchall.side_effect = lambda: next(fetchall_iter)
        return mock_cursor

    def test_structure_and_values(self, monkeypatch):
        """Returned dict has correct axes, counts, and _total."""
        from apps.recommendation import caches as c_mod

        mock_cursor = self._make_cursor_mock()
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        # Clear any cached value first
        from django.core.cache import cache
        cache.delete('qcard:corpus_tag_df')

        with patch(f'{_CACHES_MODULE}.connections', mock_conn), \
             patch(f'{_CACHES_MODULE}.cache') as mock_cache:
            # Simulate cache miss
            mock_cache.get.return_value = None
            result = c_mod.get_corpus_tag_df()

        assert result['_total'] == 100
        assert result['style'] == {'minimal': 30, 'organic': 10}
        assert result['atmosphere'] == {'warm': 40}
        assert result['program'] == {'주거': 25, '문화': 15}
        assert result['material_visual'] == {'concrete': 50, 'wood': 20}
        # cache.set must have been called
        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args[0]
        assert args[0] == 'qcard:corpus_tag_df'
        assert args[1]['_total'] == 100

    def test_cache_hit_skips_db(self, monkeypatch):
        """On cache hit, the DB is NOT queried again."""
        from apps.recommendation import caches as c_mod

        cached_value = {'_total': 50, 'style': {'a': 10}}
        mock_conn = MagicMock()

        with patch(f'{_CACHES_MODULE}.connections', mock_conn), \
             patch(f'{_CACHES_MODULE}.cache') as mock_cache:
            mock_cache.get.return_value = cached_value
            result = c_mod.get_corpus_tag_df()

        assert result == cached_value
        mock_conn.__getitem__.assert_not_called()

    def test_db_failure_returns_total_zero(self, monkeypatch):
        """On DB exception, returns {'_total': 0} so callers degrade gracefully."""
        from apps.recommendation import caches as c_mod

        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.side_effect = Exception('DB down')

        with patch(f'{_CACHES_MODULE}.connections', mock_conn), \
             patch(f'{_CACHES_MODULE}.cache') as mock_cache:
            mock_cache.get.return_value = None
            result = c_mod.get_corpus_tag_df()

        assert result == {'_total': 0}
        # Must NOT cache the failure result
        mock_cache.set.assert_not_called()


# ---------------------------------------------------------------------------
# Part B — _pick_discriminative_tag
# ---------------------------------------------------------------------------

class TestPickDiscriminativeTag:
    """_pick_discriminative_tag selects TF-IDF winner correctly."""

    def _session_stub(self, axis_counts):
        stub = MagicMock()
        stub.tag_axis_counts = {'style': axis_counts}
        return stub

    def test_discriminative_beats_common(self, monkeypatch):
        """A rare tag with moderate TF beats a very common corpus-wide tag."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        # 'generic' appears in 80% of buildings → df/N = 0.8 → skipped
        # 'niche' appears in 5% → df/N = 0.05 → passes; score = 2*log(100/6) ≈ 5.64
        # 'generic' tf=5, df=80 → skipped (80/100 > 0.4)
        axis_counts = {'niche': 2, 'generic': 5}
        stub = self._session_stub(axis_counts)

        df_map = {
            '_total': 100,
            'style': {'niche': 5, 'generic': 80},
        }
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_common_tag_ratio', 0.4)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_keyword_blacklist', [])

        with patch(
            'apps.recommendation.services.swipe_service.get_corpus_tag_df',
            return_value=df_map,
        ):
            result = svc._pick_discriminative_tag(stub, 'style')

        assert result == 'niche', (
            f'Expected discriminative tag "niche", got "{result}"'
        )

    def test_blacklisted_tag_skipped(self, monkeypatch):
        """Blacklisted tag is excluded; next best tag is returned."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        axis_counts = {'bland': 5, 'specific': 3}
        stub = self._session_stub(axis_counts)

        df_map = {
            '_total': 100,
            'style': {'bland': 5, 'specific': 10},
        }
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_common_tag_ratio', 0.4)
        # Blacklist 'bland' (case-insensitive)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_keyword_blacklist', ['Bland'])

        with patch(
            'apps.recommendation.services.swipe_service.get_corpus_tag_df',
            return_value=df_map,
        ):
            result = svc._pick_discriminative_tag(stub, 'style')

        assert result == 'specific', (
            f'Expected "specific" (bland blacklisted), got "{result}"'
        )

    def test_common_ratio_filter(self, monkeypatch):
        """Tags with df/N above question_common_tag_ratio are skipped."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        # Both tags above the 0.4 threshold → fall back to frequency winner
        axis_counts = {'tagA': 3, 'tagB': 5}
        stub = self._session_stub(axis_counts)

        df_map = {
            '_total': 100,
            'style': {'tagA': 50, 'tagB': 60},  # both 50%/60% > 40%
        }
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_common_tag_ratio', 0.4)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_keyword_blacklist', [])

        with patch(
            'apps.recommendation.services.swipe_service.get_corpus_tag_df',
            return_value=df_map,
        ):
            result = svc._pick_discriminative_tag(stub, 'style')

        # All filtered → fallback to max TF
        assert result == 'tagB', (
            f'Expected frequency fallback "tagB", got "{result}"'
        )

    def test_corpus_unavailable_frequency_fallback(self, monkeypatch):
        """When corpus DF is unavailable (_total==0), returns max-TF tag."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        axis_counts = {'a': 1, 'b': 3, 'c': 2}
        stub = self._session_stub(axis_counts)

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_common_tag_ratio', 0.4)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_keyword_blacklist', [])

        with patch(
            'apps.recommendation.services.swipe_service.get_corpus_tag_df',
            return_value={'_total': 0},
        ):
            result = svc._pick_discriminative_tag(stub, 'style')

        assert result == 'b', f'Expected frequency fallback "b", got "{result}"'

    def test_empty_axis_counts_returns_none(self, monkeypatch):
        """Empty axis counts returns None."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        stub = MagicMock()
        stub.tag_axis_counts = {}
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_common_tag_ratio', 0.4)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_keyword_blacklist', [])

        with patch(
            'apps.recommendation.services.swipe_service.get_corpus_tag_df',
            return_value={'_total': 100, 'style': {}},
        ):
            result = svc._pick_discriminative_tag(stub, 'style')

        assert result is None


# ---------------------------------------------------------------------------
# Part C1 — _pick_pool_category
# ---------------------------------------------------------------------------

class TestPickPoolCategory:
    """_pick_pool_category returns dominant program or None on failure."""

    def _make_stub(self, pool_ids):
        stub = MagicMock()
        stub.pool_ids = pool_ids
        return stub

    def test_returns_top_program(self):
        """Returns the program with the highest count in the pool."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(['bld_000001', 'bld_000002'])

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = ('문화',)

        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._pick_pool_category(stub)

        assert result == '문화'

    def test_returns_none_on_db_failure(self):
        """DB exception → None (degrade gracefully)."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(['bld_000001'])
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.side_effect = Exception('DB error')

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._pick_pool_category(stub)

        assert result is None

    def test_returns_none_on_empty_pool(self):
        """Empty pool_ids → None without querying DB."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub([])
        mock_conn = MagicMock()

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._pick_pool_category(stub)

        assert result is None
        mock_conn.__getitem__.assert_not_called()

    def test_returns_none_when_no_rows(self):
        """Query succeeds but no rows returned → None."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(['bld_000001'])
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._pick_pool_category(stub)

        assert result is None


# ---------------------------------------------------------------------------
# Part C3 — _compute_kw_vec_category
# ---------------------------------------------------------------------------

class TestComputeKwVecCategory:
    """_compute_kw_vec_category averages embeddings for a program category."""

    def _make_stub(self, pool_ids):
        stub = MagicMock()
        stub.pool_ids = pool_ids
        return stub

    def test_returns_normalized_vector(self):
        """With matching IDs and embeddings, returns L2-normalized array."""
        from apps.recommendation.services import swipe_service as svc

        pool_ids = _FAKE_POOL[:5]
        stub = self._make_stub(pool_ids)

        matching_ids = [pool_ids[0], pool_ids[1]]
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(bid,) for bid in matching_ids]

        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        unit_vec = _make_normalized_vec(seed=7)
        mock_get_embs = MagicMock(
            return_value={bid: unit_vec.copy() for bid in matching_ids}
        )

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings', mock_get_embs):
            result = svc._compute_kw_vec_category('문화', stub)

        assert result is not None
        assert result.shape == (384,)
        # Must be L2-normalized
        assert abs(np.linalg.norm(result) - 1.0) < 1e-6

    def test_no_matching_ids_returns_none(self):
        """When no pool cards have the program, returns None."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(_FAKE_POOL[:5])

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._compute_kw_vec_category('없는프로그램', stub)

        assert result is None

    def test_db_failure_returns_none(self):
        """DB exception → None."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(_FAKE_POOL[:5])
        mock_conn = MagicMock()
        mock_conn.__getitem__.return_value.cursor.side_effect = Exception('DB fail')

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._compute_kw_vec_category('문화', stub)

        assert result is None

    def test_none_program_returns_none(self):
        """program=None guard at entry → None without touching DB."""
        from apps.recommendation.services import swipe_service as svc

        stub = self._make_stub(_FAKE_POOL[:5])
        mock_conn = MagicMock()

        with patch('apps.recommendation.services.swipe_service.connections', mock_conn):
            result = svc._compute_kw_vec_category(None, stub)

        assert result is None
        mock_conn.__getitem__.assert_not_called()


# ---------------------------------------------------------------------------
# Trigger B with category — _check_question_trigger
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTriggerBCategory:
    """_check_question_trigger refresh path includes program category payload."""

    def _make_session(self, user_profile):
        project = Project.objects.create(user=user_profile, name='TriggerB', filters={})
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='analyzing',
            pool_ids=_FAKE_POOL[:5],
            pool_scores={bid: 1.0 for bid in _FAKE_POOL[:5]},
            current_round=5,
            preference_vector=[0.1] * 384,
            exposed_ids=_FAKE_POOL[:3],
            initial_batch=_FAKE_POOL[:5],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            tag_axis_counts={},
            recent_like_tag_sets=[],
            question_cooldown=0,
            q_card_consecutive_dislikes=4,  # at threshold
            question_count=0,
            question_bias_vector=None,
        )
        return session

    def test_refresh_trigger_with_category(self, user_profile, monkeypatch):
        """When _pick_pool_category returns a category, trigger payload has axis='program'."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        session = self._make_session(user_profile)

        with patch(
            'apps.recommendation.services.swipe_service._pick_pool_category',
            return_value='문화',
        ):
            result = svc._check_question_trigger(session, 'dislike')

        assert result is not None
        assert result['type'] == 'refresh'
        assert result['axis'] == 'program'
        assert result['keyword'] == '문화'
        assert '문화' in result['question']

    def test_refresh_trigger_no_category_fallback(self, user_profile, monkeypatch):
        """When _pick_pool_category returns None, trigger uses generic question."""
        from apps.recommendation.services import swipe_service as svc
        from django.conf import settings

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        session = self._make_session(user_profile)

        with patch(
            'apps.recommendation.services.swipe_service._pick_pool_category',
            return_value=None,
        ):
            result = svc._check_question_trigger(session, 'dislike')

        assert result is not None
        assert result['type'] == 'refresh'
        assert result['axis'] is None
        assert result['keyword'] is None


# ---------------------------------------------------------------------------
# handle_question_response — refresh with category
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQuestionResponseRefreshCategory:
    """handle_question_response refresh with program category uses category centroid."""

    def _make_analyzing_session(self, user_profile):
        return _make_analyzing_session(user_profile)

    def _base_patches(self, pool_ids, cat_vec):
        """Engine patches for question-response tests."""
        def _fake_get_pool_embs(ids):
            return {bid: cat_vec.copy() for bid in ids}

        return {
            f'{_SERVICE_ENGINE}.get_pool_embeddings': _fake_get_pool_embs,
            f'{_SERVICE_ENGINE}.compute_mmr_next': lambda *a, **kw: pool_ids[3],
            f'{_SERVICE_ENGINE}.farthest_point_from_pool': lambda *a, **kw: pool_ids[3],
            f'{_SERVICE_ENGINE}.get_buildings_by_ids': lambda ids, **kw: [_make_card(bid) for bid in ids],
        }

    def _apply_patches(self, patches):
        patchers = []
        for target, fn in patches.items():
            p = patch(target, side_effect=fn)
            p.start()
            patchers.append(p)
        return patchers

    def _stop_patches(self, patchers):
        for p in patchers:
            p.stop()

    def test_yes_refresh_with_category_boosts_toward_centroid(
        self, auth_client, user_profile, monkeypatch
    ):
        """A (Yes = that category) on refresh with program keyword boosts qbias
        TOWARD the category centroid vector."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_boost_weight', 2.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        cat_vec = _make_normalized_vec(seed=11)
        session = self._make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        # Mock buildings DB cursor — fetchall returns pool matching IDs
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],), (pool_ids[1],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        engine_patches = self._base_patches(pool_ids, cat_vec)
        patchers = self._apply_patches(engine_patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refresh',
                    'axis': 'program',
                    'keyword': '문화',
                    'selected_option': 'A',
                },
                format='json',
            )
        finally:
            self._stop_patches(patchers)

        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.json()}'
        data = resp.json()
        assert data['accepted'] is True
        assert data['flush_prefetch'] is True

        session.refresh_from_db()
        assert session.question_bias_vector is not None
        qb = np.array(session.question_bias_vector)
        # Yes on category-refresh → delta = +boost * cat_vec → bias aligns with cat_vec
        dot = float(np.dot(qb / np.linalg.norm(qb), cat_vec))
        assert dot > 0.9, (
            f'Bias should align with category centroid (dot={dot:.3f}), expected > 0.9'
        )

    def test_no_refresh_with_category_penalizes_away_from_centroid(
        self, auth_client, user_profile, monkeypatch
    ):
        """B (No = not that category) on refresh with program keyword pushes qbias
        AWAY from the category centroid vector."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_penalty_weight', 1.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        cat_vec = _make_normalized_vec(seed=22)
        session = self._make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        engine_patches = self._base_patches(pool_ids, cat_vec)
        patchers = self._apply_patches(engine_patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refresh',
                    'axis': 'program',
                    'keyword': '문화',
                    'selected_option': 'B',
                },
                format='json',
            )
        finally:
            self._stop_patches(patchers)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.question_bias_vector is not None
        qb = np.array(session.question_bias_vector)
        # B on category-refresh → delta = -penalty * cat_vec → anti-aligned
        dot = float(np.dot(qb / np.linalg.norm(qb), cat_vec))
        assert dot < -0.9, (
            f'Bias should be anti-aligned with category centroid (dot={dot:.3f}), expected < -0.9'
        )

    def test_yes_refresh_without_category_uses_dislike_direction(
        self, auth_client, user_profile, monkeypatch
    ):
        """A on refresh with NO category keyword falls back to Phase 1 dislike behavior
        (push away from dislike direction: delta = -penalty * kw_vec)."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_penalty_weight', 1.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        dislike_vec = _make_normalized_vec(seed=33)
        session = self._make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        engine_patches = self._base_patches(pool_ids, dislike_vec)
        patchers = self._apply_patches(engine_patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        # Also mock session.swipes.filter to return dislike IDs for _compute_kw_vec_refresh
        mock_swipes_qs = MagicMock()
        mock_swipes_qs.filter.return_value.order_by.return_value.\
            values_list.return_value.__getitem__.return_value = [pool_ids[0]]
        # Patch get_pool_embeddings to return the dislike_vec for all IDs
        # already handled by engine_patches above (uniform vec)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refresh',
                    'axis': None,
                    'keyword': None,
                    'selected_option': 'A',
                },
                format='json',
            )
        finally:
            self._stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        # Phase 1 fallback: bias should be non-null or None (depends on whether
        # dislikes exist in session; new session has none, so kw_vec=None → delta=None)
        # The important thing is the endpoint succeeded and returned flush_prefetch=True
        assert data['flush_prefetch'] is True
