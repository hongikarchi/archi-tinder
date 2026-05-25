"""
test_swipe_goal.py -- product-goal tests for 10-swipe convergence and fast swipe UX.

These tests encode the current product target:
- do not report convergence from a dislike-only analyzing window
- allow stable positive evidence to converge before 10 swipes
- expose the 10-swipe target in progress payloads so the frontend can render it
"""
from types import SimpleNamespace

import numpy as np
import pytest

from apps.recommendation import engine
from apps.recommendation.views._shared import _progress


class TestConvergenceEvidenceUnit:
    def test_convergence_requires_recent_likes(self):
        assert engine.check_convergence(
            [0.0, 0.0, 0.0],
            threshold=0.08,
            window=3,
            recent_actions=['dislike', 'dislike', 'dislike'],
            min_recent_likes=1,
        ) is False

    def test_convergence_allows_stable_positive_window(self):
        assert engine.check_convergence(
            [0.02, 0.03, 0.02],
            threshold=0.08,
            window=3,
            recent_actions=['like', 'dislike', 'like'],
            min_recent_likes=2,
        ) is True

    def test_ten_swipe_declining_delta_window_converges(self):
        assert engine.check_convergence(
            [0.1784, 0.1508, 0.1346, 0.1259, 0.1091],
            threshold=0.13,
            window=3,
            recent_actions=['like', 'like', 'like'],
            min_recent_likes=2,
        ) is True

    def test_confidence_hidden_without_recent_positive_evidence(self):
        assert engine.compute_confidence(
            [0.0, 0.0, 0.0],
            threshold=0.08,
            window=3,
            recent_actions=['dislike', 'dislike', 'dislike'],
            min_recent_likes=1,
        ) is None


class TestProgressContract:
    def test_progress_exposes_ten_swipe_target(self):
        session = SimpleNamespace(
            current_round=6,
            like_vectors=[1, 2, 3, 4],
            phase='analyzing',
            pool_ids=['A', 'B', 'C'],
            exposed_ids=['A'],
        )

        progress = _progress(session)

        assert progress['target_swipes'] == 10
        assert progress['swipe_count'] == 6
        assert progress['swipe_target_remaining'] == 4


class TestFastEarlyCentroid:
    def test_target_window_uses_single_centroid_through_tenth_swipe(self):
        like_vectors = []
        for idx in range(10):
            vec = np.zeros(384)
            vec[idx % 384] = 1.0
            like_vectors.append({'embedding': vec.tolist(), 'round': idx + 1})

        engine.clear_centroid_cache()
        centroids, global_centroid = engine.compute_taste_centroids(like_vectors, round_num=10)
        stats = engine.get_last_clustering_stats()

        assert len(centroids) == 1
        assert stats['cluster_count_used'] == 1
        assert np.linalg.norm(global_centroid) == pytest.approx(1.0)

    def test_nonfinite_embeddings_are_dropped_before_hot_path_math(self):
        valid = np.zeros(384)
        valid[0] = 1.0
        invalid = [float('nan')] * 384
        like_vectors = [
            {'embedding': invalid, 'round': 1},
            {'embedding': valid.tolist(), 'round': 2},
        ]

        engine.clear_centroid_cache()
        centroids, global_centroid = engine.compute_taste_centroids(like_vectors, round_num=2)

        assert len(centroids) == 1
        np.testing.assert_array_almost_equal(centroids[0], valid, decimal=5)
        np.testing.assert_array_almost_equal(global_centroid, valid, decimal=5)
