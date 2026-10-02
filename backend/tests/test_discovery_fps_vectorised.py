"""PERF-MISC-1 (e): numpy-vectorised Discovery FPS / local-global split.

The pure-Python originals are copied here verbatim and the production numpy
implementations must pick the SAME rows in the SAME order (incl. tie-breaks).
Exact-arithmetic inputs (dyadic rationals, duplicate rows) make both paths
bit-identical so ties are real ties; Gaussian inputs additionally exercise the
generic path.
"""
import random

import numpy as np
import pytest

from apps.recommendation.discovery_feed import _greedy_fps, _split_local_global


# --- old implementations, copied verbatim from the pre-PERF-MISC-1 source ----

def _old_greedy_fps(rows, n):
    if not rows:
        return []
    if n <= 0:
        return []
    if len(rows) <= n:
        return list(rows)

    selected = [rows[0]]
    remaining = list(rows[1:])
    while len(selected) < n and remaining:
        best_idx, best_dist = 0, -1.0
        for i, r in enumerate(remaining):
            min_sim = min(
                sum(a * b for a, b in zip(r['_vec'], s['_vec']))
                for s in selected
            )
            dist = 1.0 - min_sim  # cosine distance
            if dist > best_dist:
                best_idx, best_dist = i, dist
        selected.append(remaining.pop(best_idx))
    return selected


def _old_split(parsed_rows, centroid_vecs, local_sim_radius):
    local_pool, global_pool = [], []
    for row in parsed_rows:
        v = row['_vec']
        max_sim = max(
            sum(a * b for a, b in zip(v, cv))
            for cv in centroid_vecs
        )
        if max_sim >= local_sim_radius:
            local_pool.append(row)
        else:
            global_pool.append(row)
    return local_pool, global_pool


def _ids(rows):
    return [r['canonical_bld_id'] for r in rows]


def _dyadic_rows(rng, n, dim, levels=4, dup_prob=0.3):
    """Rows whose components are multiples of 1/8 -> all dot products exact in float64."""
    rows = []
    for i in range(n):
        if rows and rng.random() < dup_prob:
            vec = list(rng.choice(rows)['_vec'])  # exact duplicate -> real ties
        else:
            vec = [rng.randint(-levels, levels) / 8.0 for _ in range(dim)]
        rows.append({'canonical_bld_id': f'bld_{i:04d}', '_vec': vec})
    return rows


def _gauss_rows(seed, n, dim):
    g = np.random.default_rng(seed)
    out = []
    for i in range(n):
        v = g.normal(size=dim)
        v = v / np.linalg.norm(v)
        out.append({'canonical_bld_id': f'bld_{i:04d}', '_vec': v.tolist()})
    return out


class TestGreedyFpsEquivalence:

    @pytest.mark.parametrize('seed', range(40))
    def test_dyadic_with_duplicates_same_order(self, seed):
        rng = random.Random(seed)
        n_rows = rng.randint(2, 40)
        rows = _dyadic_rows(rng, n_rows, dim=rng.randint(1, 6))
        for n in (1, 2, 4, 6, n_rows - 1, n_rows, n_rows + 3):
            assert _ids(_greedy_fps(rows, n)) == _ids(_old_greedy_fps(rows, n)), (seed, n)

    @pytest.mark.parametrize('seed', range(8))
    def test_gaussian_unit_vectors_same_order(self, seed):
        rows = _gauss_rows(seed, n=120, dim=32)
        for n in (4, 6, 10):
            assert _ids(_greedy_fps(rows, n)) == _ids(_old_greedy_fps(rows, n))

    def test_all_identical_rows_tie_break_is_list_order(self):
        rows = [{'canonical_bld_id': f'b{i}', '_vec': [0.5, 0.5, 0.5, 0.5]} for i in range(8)]
        assert _ids(_greedy_fps(rows, 5)) == _ids(_old_greedy_fps(rows, 5)) == ['b0', 'b1', 'b2', 'b3', 'b4']

    def test_non_unit_vectors_hit_best_dist_floor(self):
        """Large-norm vectors push min_sim >= 2 (dist <= -1): the old code's
        best_dist=-1.0 init then picks remaining[0]; the numpy path must too."""
        rows = [{'canonical_bld_id': f'b{i}', '_vec': [2.0 + i, 2.0 + i]} for i in range(6)]
        assert _ids(_greedy_fps(rows, 4)) == _ids(_old_greedy_fps(rows, 4))

    def test_edge_cases(self):
        assert _greedy_fps([], 3) == []
        assert _greedy_fps(_gauss_rows(0, 3, 4), 0) == []
        rows = _gauss_rows(1, 3, 4)
        assert _greedy_fps(rows, 5) == rows == _old_greedy_fps(rows, 5)
        assert _greedy_fps(rows, 3) is not rows  # copy, input not aliased

    def test_does_not_mutate_input(self):
        rows = _gauss_rows(2, 20, 8)
        before = list(rows)
        _greedy_fps(rows, 6)
        assert rows == before

    def test_returns_original_row_objects(self):
        rows = _gauss_rows(3, 20, 8)
        out = _greedy_fps(rows, 5)
        assert all(any(o is r for r in rows) for o in out)


class TestSplitLocalGlobalEquivalence:

    @pytest.mark.parametrize('seed', range(30))
    def test_dyadic_split_matches(self, seed):
        rng = random.Random(1000 + seed)
        dim = rng.randint(1, 6)
        rows = _dyadic_rows(rng, rng.randint(1, 40), dim)
        cents = [[rng.randint(-4, 4) / 8.0 for _ in range(dim)] for _ in range(rng.randint(1, 4))]
        # radius chosen from the data so rows sit exactly ON the threshold (>= edge)
        sims = sorted(sum(a * b for a, b in zip(r['_vec'], cents[0])) for r in rows)
        for radius in (sims[len(sims) // 2], sims[0], sims[-1] + 1.0, 0.0):
            new_l, new_g = _split_local_global(rows, cents, radius)
            old_l, old_g = _old_split(rows, cents, radius)
            assert _ids(new_l) == _ids(old_l)
            assert _ids(new_g) == _ids(old_g)

    def test_gaussian_split_matches_and_preserves_order(self):
        rows = _gauss_rows(7, 200, 64)
        cents = [r['_vec'] for r in rows[:3]]
        new_l, new_g = _split_local_global(rows, cents, 0.2)
        old_l, old_g = _old_split(rows, cents, 0.2)
        assert _ids(new_l) == _ids(old_l)
        assert _ids(new_g) == _ids(old_g)
        assert len(new_l) + len(new_g) == len(rows)

    def test_empty_rows(self):
        assert _split_local_global([], [[1.0, 0.0]], 0.5) == ([], [])
