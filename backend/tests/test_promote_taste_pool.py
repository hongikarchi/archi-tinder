"""
test_promote_taste_pool.py -- BACK-PROMOTE-1.

promote-to-taste used to build its pool with
create_pool_with_relaxation({}, [], seeds, v_initial=pref). With empty filters
and hyde_vinitial_enabled=False that returned a uniformly random pool BEFORE
seed injection, so the Discovery preference vector and the liked seeds were
ignored. engine.create_taste_seeded_pool now builds the pool from pgvector HNSW
neighbours of the preference vector, MMR-diversified.

No real DB: engine.connection is mocked. The regression tests prove the regular
(empty-filter, no v_initial) path is unchanged.
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from django.conf import settings

from apps.recommendation import engine
from apps.recommendation.services import session_service  # noqa: F401  (import order: avoids swipe_service circular import in the autouse conftest patch)
from apps.recommendation.engine import (
    _mmr_downsample,
    create_bounded_pool,
    create_pool_with_relaxation,
    create_taste_seeded_pool,
)

DIM = 384


def _unit(vec):
    vec = np.asarray(vec, dtype=np.float64)
    return vec / np.linalg.norm(vec)


def _emb_text(vec):
    return '[' + ','.join(repr(float(x)) for x in vec) + ']'


def _make_cursor(rows):
    cursor = MagicMock()
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchall.return_value = rows
    return cursor


def _pref():
    v = np.zeros(DIM)
    v[0] = 1.0
    return v.tolist()


def _rows(n, *, clustered_head=0, seed=0):
    """n rows (bld_id, emb_text, relevance), ordered by descending relevance.

    The first `clustered_head` rows are near-duplicates of one direction (the
    nearest neighbours of the pref vector all look alike); the rest are spread.
    """
    rng = np.random.default_rng(seed)
    rows = []
    base = _unit(rng.standard_normal(DIM))
    for i in range(n):
        if i < clustered_head:
            vec = _unit(base + 0.01 * rng.standard_normal(DIM))
        else:
            vec = _unit(rng.standard_normal(DIM))
        rows.append((f'bld_{i + 100:06d}', _emb_text(vec), 1.0 - i * 0.001))
    return rows


def _fake_random_pool(n):
    return [f'rnd_{i:05d}' for i in range(n)]


@pytest.fixture(autouse=True)
def _clean_caches(monkeypatch):
    engine.clear_pool_embedding_cache()
    # Exploration slice draws from the cached random-id list: never hit a DB here.
    monkeypatch.setattr(engine, '_random_pool', _fake_random_pool)
    yield
    engine.clear_pool_embedding_cache()


# ---------------------------------------------------------------------------
# New path: HNSW query
# ---------------------------------------------------------------------------

class TestTasteSeededPoolQuery:

    def _run(self, rows, **kw):
        cursor = _make_cursor(rows)
        with patch('apps.recommendation.engine.connection') as conn:
            conn.cursor.return_value = cursor
            result = create_taste_seeded_pool(_pref(), **kw)
        return result, cursor

    def test_issues_hnsw_order_by_query_not_random_pool(self, monkeypatch):
        monkeypatch.setitem(settings.RECOMMENDATION, 'taste_pool_random_fraction', 0.0)
        with patch('apps.recommendation.engine._random_pool') as rand:
            (pool_ids, scores), cursor = self._run(
                _rows(60), seed_ids=[], exclude_ids=[], target=20,
            )
        rand.assert_not_called()
        sql = cursor.execute.call_args[0][0]
        assert 'ORDER BY embedding <=> %s::vector' in sql
        assert 'is_publishable = true' in sql
        assert len(pool_ids) == 20
        assert all(b.startswith('bld_') for b in pool_ids)

    def test_default_pool_is_mostly_neighbours_plus_small_random_slice(self):
        (pool_ids, scores), _ = self._run(
            _rows(200), seed_ids=[], exclude_ids=[], target=50,
        )
        rnd = [b for b in pool_ids if b.startswith('rnd_')]
        assert len(pool_ids) == 50
        assert len(rnd) == 10                     # 20% exploration slice
        assert all(b not in scores for b in rnd)  # random ids carry no relevance score

    def test_random_slice_excludes_excluded_ids(self):
        taken = _fake_random_pool(5)
        (pool_ids, _), _ = self._run(
            _rows(200), seed_ids=[], exclude_ids=taken, target=50,
        )
        assert not set(taken) & set(pool_ids)

    def test_random_slice_shortfall_filled_with_neighbours(self, monkeypatch):
        monkeypatch.setattr(engine, '_random_pool', lambda n: [])
        (pool_ids, _), _ = self._run(
            _rows(200), seed_ids=[], exclude_ids=[], target=50,
        )
        assert len(pool_ids) == 50
        assert all(b.startswith('bld_') for b in pool_ids)

    def test_no_usable_neighbours_raises_for_caller_fallback(self):
        with pytest.raises(RuntimeError):
            self._run([], seed_ids=[], exclude_ids=[], target=20)

    def test_overfetch_limit_is_multiplier_times_target(self, monkeypatch):
        monkeypatch.setitem(settings.RECOMMENDATION, 'taste_pool_overfetch', 3)
        _, cursor = self._run(_rows(10), seed_ids=[], exclude_ids=[], target=20)
        params = cursor.execute.call_args[0][1]
        assert params[-1] == 60            # LIMIT = 3 * target

    def test_excludes_seeds_and_disliked_ids_in_sql(self):
        seeds = ['bld_000001', 'bld_000002']
        disliked = ['bld_000003']
        _, cursor = self._run(
            _rows(30), seed_ids=seeds, exclude_ids=disliked, target=10,
        )
        sql, params = cursor.execute.call_args[0]
        assert '<> ALL(%s::text[])' in sql
        excluded = next(p for p in params if isinstance(p, list))
        assert set(excluded) == {'bld_000001', 'bld_000002', 'bld_000003'}

    def test_no_exclusion_clause_when_nothing_to_exclude(self):
        _, cursor = self._run(_rows(30), seed_ids=[], exclude_ids=[], target=10)
        assert '<> ALL' not in cursor.execute.call_args[0][0]

    def test_pool_size_respects_target_including_seeds(self):
        seeds = [f'bld_{i:06d}' for i in range(12)]
        (pool_ids, scores), _ = self._run(
            _rows(200), seed_ids=seeds, exclude_ids=[], target=50,
        )
        assert len(pool_ids) == 50
        assert len(set(pool_ids)) == 50
        # seeds injected first at score 1.1 (create_bounded_pool semantics)
        assert pool_ids[:12] == seeds
        assert all(scores[s] == 1.1 for s in seeds)
        # neighbour scores are cosine relevance floats
        assert all(0 < scores[b] <= 1.0 for b in pool_ids[12:] if b.startswith('bld_'))

    def test_pool_never_contains_excluded_ids_beyond_seeds(self):
        # The DB applies the exclusion; the function must not re-add them.
        (pool_ids, _), _ = self._run(
            _rows(80), seed_ids=['bld_000001'], exclude_ids=['bld_000002'], target=30,
        )
        assert 'bld_000002' not in pool_ids

    def test_fewer_rows_than_target_returns_what_exists(self, monkeypatch):
        monkeypatch.setitem(settings.RECOMMENDATION, 'taste_pool_random_fraction', 0.0)
        (pool_ids, _), _ = self._run(_rows(5), seed_ids=[], exclude_ids=[], target=30)
        assert len(pool_ids) == 5

    def test_neighbour_embeddings_populate_cache(self):
        (pool_ids, _), _ = self._run(_rows(40), seed_ids=[], exclude_ids=[], target=10)
        near = [b for b in pool_ids if b.startswith('bld_')]
        assert near and all(bid in engine._building_embedding_cache for bid in near)

    def test_sql_failure_propagates_for_caller_fallback(self):
        cursor = _make_cursor([])
        cursor.execute.side_effect = RuntimeError('db down')
        with patch('apps.recommendation.engine.connection') as conn:
            conn.cursor.return_value = cursor
            with pytest.raises(RuntimeError):
                create_taste_seeded_pool(_pref(), [], target=10)

    def test_rejects_wrong_dimension_vector(self):
        with pytest.raises(ValueError):
            create_taste_seeded_pool([0.1] * 10, [], target=10)


# ---------------------------------------------------------------------------
# Diversity step
# ---------------------------------------------------------------------------

class TestDiversityStep:

    def test_mmr_selection_differs_from_plain_top_k_when_head_is_clustered(self, monkeypatch):
        monkeypatch.setitem(settings.RECOMMENDATION, 'taste_pool_random_fraction', 0.0)
        # Top-30 nearest are near-duplicates; the tail is spread out.
        rows = _rows(90, clustered_head=30)
        cursor = _make_cursor(rows)
        with patch('apps.recommendation.engine.connection') as conn:
            conn.cursor.return_value = cursor
            pool_ids, _ = create_taste_seeded_pool(
                _pref(), [], exclude_ids=[], target=30,
            )
        plain_top = [r[0] for r in rows[:30]]
        assert pool_ids != plain_top
        # at least some of the diverse tail made it in
        tail_ids = {r[0] for r in rows[30:]}
        assert len(tail_ids & set(pool_ids)) >= 5

    def test_mmr_keeps_highest_relevance_first(self):
        rel = [0.9, 0.8, 0.7]
        embs = np.stack([_unit(np.eye(DIM)[i]) for i in range(3)])
        assert _mmr_downsample(rel, embs, 3, 0.3)[0] == 0

    def test_mmr_penalises_near_duplicate_of_selected(self):
        a = np.eye(DIM)[0]
        a_dup = _unit(a + 0.001 * np.eye(DIM)[1])
        b = np.eye(DIM)[2]
        embs = np.stack([a, a_dup, b])
        rel = [0.90, 0.89, 0.60]
        # second pick: duplicate scores 0.89-0.3*~1 = 0.59 < 0.60 -> picks b
        assert _mmr_downsample(rel, embs, 2, 0.3) == [0, 2]

    def test_mmr_k_larger_than_candidates(self):
        embs = np.stack([np.eye(DIM)[0], np.eye(DIM)[1]])
        assert sorted(_mmr_downsample([0.5, 0.4], embs, 10, 0.3)) == [0, 1]


# ---------------------------------------------------------------------------
# Regression: regular empty-filter path is unchanged
# ---------------------------------------------------------------------------

class TestRegularPathUnchanged:

    def test_empty_filters_no_v_initial_still_uses_random_pool(self, monkeypatch):
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)
        with patch('apps.recommendation.engine._random_pool', return_value=['b1', 'b2']) as rand, \
             patch('apps.recommendation.engine.create_taste_seeded_pool') as taste, \
             patch('apps.recommendation.engine.connection') as conn:
            pool_ids, scores = create_bounded_pool({}, None, None, target=10)
        rand.assert_called_once_with(10)
        taste.assert_not_called()
        conn.cursor.assert_not_called()      # no <=> SQL
        assert (pool_ids, scores) == (['b1', 'b2'], {})

    def test_relaxation_with_empty_filters_still_random_even_with_v_initial(self, monkeypatch):
        """The global hyde flag is untouched: with it OFF, create_pool_with_relaxation
        keeps returning the random pool (promote no longer relies on this)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'hyde_vinitial_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'hybrid_retrieval_enabled', False)
        assert settings.RECOMMENDATION['hyde_vinitial_enabled'] is False
        with patch('apps.recommendation.engine._random_pool', return_value=['b1']) as rand, \
             patch('apps.recommendation.engine.create_taste_seeded_pool') as taste, \
             patch('apps.recommendation.engine.cache') as fake_cache:
            fake_cache.get.return_value = None
            ids, scores, tier = create_pool_with_relaxation(
                {}, [], ['s1'], target=10, v_initial=_pref(),
            )
        rand.assert_called()
        taste.assert_not_called()
        assert ids == ['b1'] and tier == 1

    def test_global_hyde_flag_default_still_off(self):
        assert settings.RECOMMENDATION.get('hyde_vinitial_enabled', False) is False
