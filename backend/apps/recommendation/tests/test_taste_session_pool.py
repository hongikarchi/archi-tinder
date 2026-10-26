"""Taste-start step 3-2: session_pool (pool build, refresh, off-tag, stored tags). DB-free."""
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from apps.recommendation.taste_start import session_pool as sp
from apps.recommendation.taste_start.recognizer import make_tag

WANT = [make_tag('country', 'Japan')]
EXCL_ONLY = [make_tag('material', 'wood', 'exclude')]


@pytest.fixture
def m():
    with mock.patch.object(sp, 'matching') as matching, mock.patch.object(sp, 'engine') as engine:
        matching.ranked_pool.return_value = []
        matching.score_ids.return_value = {}
        engine._random_pool.return_value = []
        yield SimpleNamespace(matching=matching, engine=engine)


def ranked(*pairs):
    return [{'canonical_bld_id': b, 'score': s} for b, s in pairs]


def session(pool, exposed, tags=WANT, tier=1, extra=None):
    filters = {'selector': 'taste_v2', 'taste_tags': [t.to_dict() for t in tags]}
    filters.update(extra or {})
    return SimpleNamespace(
        pool_ids=list(pool), exposed_ids=list(exposed), pool_scores={p: 1.0 for p in pool},
        current_pool_tier=tier, original_filters=filters, current_round=3,
        multimodal_floor=None, session_id='s1')


# -- is_v2 / stored_tags ---------------------------------------------------------
def test_is_v2():
    assert sp.is_v2(SimpleNamespace(original_filters={'selector': 'taste_v2'}))
    assert not sp.is_v2(SimpleNamespace(original_filters={'selector': 'x'}))
    assert not sp.is_v2(SimpleNamespace(original_filters={}))
    assert not sp.is_v2(SimpleNamespace(original_filters=None))


def test_stored_tags_skips_invalid_and_ignores_forged_match():
    good = WANT[0].to_dict()
    forged = dict(good, match={'location_country': ['Evil']})
    items = [good, {'axis': 'country', 'value': 'Atlantis'}, 'junk', {'axis': 'nope'}, forged]
    tags = sp.stored_tags(SimpleNamespace(original_filters={'taste_tags': items}))
    assert len(tags) == 2
    assert all(t.match == WANT[0].match for t in tags)


def test_stored_tags_for_project_and_missing():
    proj = SimpleNamespace(filters={'taste_tags': [WANT[0].to_dict()], 'style': 'x'})
    assert [t.key for t in sp.stored_tags(proj)] == [WANT[0].key]
    assert sp.stored_tags(SimpleNamespace(filters=None)) == []
    assert sp.stored_tags(SimpleNamespace(original_filters={'taste_tags': 'bad'})) == []


# -- build_pool ------------------------------------------------------------------
def test_build_pool_start_first_and_exclude_passthrough(m):
    m.matching.ranked_pool.return_value = ranked(('b', 3.0), ('c', 2.0), ('a', 1.0))
    m.matching.score_ids.return_value = {'a': 3.0, 's2': 0.0}
    pool, scores = sp.build_pool(WANT, ['a', 's2'], ['x', 'y'])
    assert pool == ['a', 's2', 'b', 'c']          # start ids first, no duplicate 'a'
    assert scores['a'] == 3.0 and scores['b'] == 3.0
    kw = m.matching.ranked_pool.call_args.kwargs
    assert kw['exclude_ids'] == ['a', 's2', 'x', 'y']
    assert kw['limit'] == 150


def test_build_pool_no_want_tags_uses_diverse_scored(m):
    m.engine._random_pool.return_value = ['z', 'q', 'x', 's1']
    m.matching.score_ids.side_effect = lambda tags, ids: {i: -2.0 for i in ids if i == 'q'}
    pool, scores = sp.build_pool(EXCL_ONLY, ['s1'], ['x'])
    assert pool == ['s1', 'q', 'z']                # sorted, excluded x/s1 removed, start first
    assert scores['q'] == -2.0 and scores['z'] == 0.0 and scores['s1'] == 0.0


# -- refresh_if_low --------------------------------------------------------------
def test_refresh_noop_when_enough_remaining(m):
    pool = [f'p{i}' for i in range(30)]
    s = session(pool, ['p0'])
    assert sp.refresh_if_low(s, []) is False
    m.matching.ranked_pool.assert_not_called()
    assert s.pool_ids == pool


def test_refresh_appends_next_page_excluding_pool_and_exposed(m):
    pool = [f'p{i}' for i in range(10)]
    s = session(pool, ['p0', 'e1'])
    m.matching.ranked_pool.return_value = ranked(('n1', 2.0), ('p3', 2.0), ('n2', 1.0))
    assert sp.refresh_if_low(s, []) is True
    assert m.matching.ranked_pool.call_args.kwargs['exclude_ids'] == pool + ['e1']
    assert s.pool_ids == pool + ['n1', 'n2']       # p3 (dup) dropped, unique
    assert s.pool_scores['n1'] == 2.0
    assert s.current_pool_tier == 2
    assert 'off_tag' not in s.original_filters


def test_refresh_off_tag_uses_like_centroid(m):
    pool = [f'p{i}' for i in range(5)]
    s = session(pool, ['p0'])
    m.matching.ranked_pool.return_value = []
    centroid = np.ones(4)
    m.engine.compute_taste_centroids.return_value = ([centroid], centroid)
    m.engine.taste_ranked_page.return_value = [
        {'canonical_bld_id': 'o1'}, {'canonical_bld_id': 'p1'}, {'canonical_bld_id': 'o2'},
        {'canonical_bld_id': 'o1'}]
    m.matching.score_ids.return_value = {'o2': -1.0}
    likes = [{'embedding': [0.1] * 4, 'round': 1}]
    assert sp.refresh_if_low(s, likes) is True
    args = m.engine.taste_ranked_page.call_args.args
    assert args[0] is centroid and set(args[1]) == set(pool) and args[3] == 0
    assert s.pool_ids == pool + ['o1', 'o2']
    assert len(set(s.pool_ids)) == len(s.pool_ids)
    assert s.pool_scores['o1'] == 0.0 and s.pool_scores['o2'] == -1.0
    assert s.original_filters['off_tag'] is True
    assert s.original_filters['selector'] == 'taste_v2'
    assert s.current_pool_tier == 2


def test_refresh_off_tag_without_likes_uses_diverse(m):
    pool = ['p0', 'p1']
    s = session(pool, ['p0'])
    m.engine._random_pool.return_value = ['p1', 'r2', 'r1']
    assert sp.refresh_if_low(s, []) is True
    m.engine.taste_ranked_page.assert_not_called()
    assert s.pool_ids == ['p0', 'p1', 'r1', 'r2']
    assert s.original_filters['off_tag'] is True


def test_refresh_off_tag_falls_back_when_centroid_page_empty(m):
    s = session(['p0'], ['p0'])
    m.engine.compute_taste_centroids.return_value = ([np.ones(2)], np.ones(2))
    m.engine.taste_ranked_page.return_value = []
    m.engine._random_pool.return_value = ['r1']
    assert sp.refresh_if_low(s, [{'embedding': [0.1, 0.1], 'round': 1}]) is True
    assert s.pool_ids == ['p0', 'r1']


def test_refresh_returns_false_when_db_fully_used(m):
    s = session(['p0'], ['p0'])
    m.engine._random_pool.return_value = ['p0']
    assert sp.refresh_if_low(s, []) is False
    assert s.pool_ids == ['p0']
    assert 'off_tag' not in s.original_filters
