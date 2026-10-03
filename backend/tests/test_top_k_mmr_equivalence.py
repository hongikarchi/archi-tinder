"""
PERF-ROUND2 item 2 -- vectorised get_top_k_mmr must select the SAME ids in the SAME
order as the previous pure-Python per-pair np.dot MMR loop.

No DB: engine.connection is replaced by a fake whose cursor returns synthetic rows
(including the embedding::text column). The reference implementation below is the
pre-optimisation loop, copied verbatim, and is run on the same rows.
"""
import numpy as np
import pytest
from unittest.mock import patch

import apps.recommendation.views  # noqa: F401 -- import-order guard (services<->views cycle when run alone)
from apps.recommendation import engine

DIM = 384


def _unit(rng, n):
    v = rng.normal(size=(n, DIM))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _vec_text(vec):
    # pgvector text form: '[a,b,c]' with float4-shortest style numbers.
    return '[' + ','.join(f'{float(np.float32(x)):.9g}' for x in vec) + ']'


def _make_rows(rng, n, n_duplicates=0, n_anti=0):
    vecs = _unit(rng, n)
    # Exact duplicates -> exact score ties -> tie-break (first index wins) is exercised.
    for i in range(n_duplicates):
        vecs[n - 1 - i] = vecs[i]
    return [(f'B{i:05d}', f'Building {i}', _vec_text(vecs[i])) for i in range(n)], vecs


class _Cursor:
    description = [('canonical_bld_id',), ('name',), ('embedding',)]

    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _Cursor(self._rows)


def _reference_ids(rows, centroids, k, penalty):
    """Pre-optimisation get_top_k_mmr selection loop, verbatim (ids only)."""
    parsed = []
    for cid, _name, emb in rows:
        parsed.append({'id': cid, '_vec': np.array([float(x) for x in emb.strip('[]').split(',')])})
    selected = []
    remaining = parsed.copy()
    if remaining:
        best_idx = 0
        best_relevance = -1
        for i, row in enumerate(remaining):
            relevance = max(np.dot(row['_vec'], c) for c in centroids)
            if relevance > best_relevance:
                best_relevance = relevance
                best_idx = i
        selected.append(remaining.pop(best_idx))
    while len(selected) < k and remaining:
        best_idx = 0
        best_score = -float('inf')
        for i, row in enumerate(remaining):
            candidate_emb = row['_vec']
            relevance = max(np.dot(candidate_emb, c) for c in centroids)
            redundancy = 0
            for sel in selected:
                redundancy = max(redundancy, np.dot(candidate_emb, sel['_vec']))
            mmr_score = relevance - penalty * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = i
        selected.append(remaining.pop(best_idx))
    return [r['id'] for r in selected]


def _run_new(rows, k, centroids=None, like_vectors=None):
    like_vectors = like_vectors or [{'embedding': rows and [0.0] * DIM, 'round': 1}]
    with patch.object(engine, 'connection', _Conn(rows)), \
            patch.object(engine, '_get_available_columns', return_value=None):
        if centroids is not None:
            with patch.object(engine, 'compute_taste_centroids',
                              return_value=(centroids, centroids[0])):
                cards = engine.get_top_k_mmr(like_vectors, [], k=k, round_num=5)
        else:
            cards = engine.get_top_k_mmr(like_vectors, [], k=k)
    return [c['canonical_bld_id'] for c in cards]


@pytest.mark.parametrize('seed', [0, 1, 2, 3, 4])
@pytest.mark.parametrize('n_rows,k', [(60, 20), (12, 20), (90, 20), (60, 1), (40, 40), (3, 20)])
def test_single_centroid_identical_order(seed, n_rows, k):
    rng = np.random.default_rng(seed)
    rows, vecs = _make_rows(rng, n_rows, n_duplicates=min(3, n_rows // 2))
    # No-round_num path: centroid = normalised mean of like embeddings.
    likes = _unit(rng, 4)
    like_vectors = [{'embedding': likes[i].tolist(), 'round': i} for i in range(4)]
    centroid = np.mean([np.array(lv['embedding']) for lv in like_vectors], axis=0)
    centroid = centroid / np.linalg.norm(centroid)
    penalty = engine.RC['mmr_penalty']

    expected = _reference_ids(rows, [centroid], k, penalty)
    got = _run_new(rows, k, like_vectors=like_vectors)
    assert got == expected
    assert len(got) == min(k, n_rows)


@pytest.mark.parametrize('seed', [10, 11, 12])
@pytest.mark.parametrize('penalty', [0.0, 0.3, 0.9])
def test_multi_centroid_identical_order(seed, penalty):
    rng = np.random.default_rng(seed)
    rows, _ = _make_rows(rng, 60, n_duplicates=4)
    centroids = list(_unit(rng, 2))
    with patch.dict(engine.RC, {'mmr_penalty': penalty}):
        expected = _reference_ids(rows, centroids, 20, penalty)
        got = _run_new(rows, 20, centroids=centroids)
    assert got == expected


def test_clamped_redundancy_and_all_negative_relevance():
    """Candidates anti-aligned with the centroid (relevance < 0) and mutually
    negative similarity: exercises the redundancy floor of 0 and the first-pick
    'best_relevance = -1' scan."""
    rng = np.random.default_rng(99)
    centroid = _unit(rng, 1)[0]
    vecs = _unit(rng, 30)
    vecs = np.where((vecs @ centroid)[:, None] > 0, -vecs, vecs)   # all relevance <= 0
    rows = [(f'B{i:05d}', f'n{i}', _vec_text(vecs[i])) for i in range(30)]
    expected = _reference_ids(rows, [centroid], 20, engine.RC['mmr_penalty'])
    got = _run_new(rows, 20, centroids=[centroid])
    assert got == expected


def test_empty_candidates_returns_empty():
    assert _run_new([], 20, like_vectors=[{'embedding': [0.1] * DIM, 'round': 1}]) == []


def test_no_python_float_parse_loop_on_result_path():
    """Guard: the parse is np.fromstring-based, not a per-element float() list comp."""
    import inspect
    src = inspect.getsource(engine.get_top_k_mmr)
    assert 'float(x) for x' not in src
    assert 'np.fromstring' in src
