"""
test_topic06.py -- Sprint 4 Topic 06: adaptive-k clustering + soft-assignment relevance.

Tests are unit-level (no DB required) -- they call engine functions directly with
synthetic embeddings. RC flags are toggled via monkeypatch on settings.RECOMMENDATION.
The centroid cache is cleared before each test to prevent cross-contamination when
the same like_vectors signature is reused with different flag states.
"""
import numpy as np
from django.conf import settings

from apps.recommendation.engine import (
    compute_taste_centroids,
    clear_centroid_cache,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unit_vec(seed, dim=384):
    """Return a deterministic L2-normalised vector."""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return v / np.linalg.norm(v)


def _like_entry(seed, round_num=1):
    """Build a like_vectors entry dict with a normalised embedding."""
    return {'embedding': _unit_vec(seed).tolist(), 'round': round_num}


def _two_cluster_likes():
    """
    8 like entries that form two well-separated clusters (seeds 0-3 near pole A,
    seeds 100-103 near pole B).  Silhouette(k=2) should be >> 0.15.
    """
    pole_a = _unit_vec(0)
    pole_b = -pole_a  # maximally antipodal
    entries = []
    rng_a = np.random.RandomState(7)
    rng_b = np.random.RandomState(8)
    for _ in range(4):
        noise = rng_a.randn(384) * 0.05
        v = pole_a + noise
        entries.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
    for _ in range(4):
        noise = rng_b.randn(384) * 0.05
        v = pole_b + noise
        entries.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
    return entries


def _tight_cluster_likes():
    """
    8 like entries clustered tightly around a single pole -- sil(k=2) << 0.15.
    """
    pole = _unit_vec(42)
    entries = []
    rng = np.random.RandomState(13)
    for _ in range(8):
        noise = rng.randn(384) * 0.005  # very small perturbations
        v = pole + noise
        entries.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
    return entries


# ---------------------------------------------------------------------------
# TestTopic06AdaptiveK
# ---------------------------------------------------------------------------

class TestTopic06AdaptiveK:
    """Sprint 4 Topic 06: silhouette-based adaptive k {1,2} + soft-assignment relevance."""

    def setup_method(self):
        """Clear centroid cache before each test."""
        clear_centroid_cache()

    # -- adaptive_k_clustering_enabled flag tests ----------------------------

    def test_adaptive_k_disabled_by_default(self, monkeypatch):
        """Default flag=False: once multimodal routing is allowed, k=2 KMeans is used."""
        assert settings.RECOMMENDATION.get('adaptive_k_clustering_enabled', False) is False
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 4)
        clear_centroid_cache()

        likes = [_like_entry(i) for i in range(4)]
        centroids, global_centroid = compute_taste_centroids(likes, round_num=4)
        # Default k_clusters=2 and N=4 >= min_likes_for_multimodal => two centroids.
        assert len(centroids) == 2

    def test_adaptive_k_picks_k1_on_low_silhouette(self, monkeypatch):
        """Flag on + tight cluster (sil(k=2) < 0.15) => k=1, single global centroid."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        clear_centroid_cache()

        likes = _tight_cluster_likes()  # 8 tightly-clustered entries
        centroids, global_centroid = compute_taste_centroids(likes, round_num=8)

        assert len(centroids) == 1
        # The single centroid must equal the global centroid (same object or numerically equal)
        np.testing.assert_array_almost_equal(centroids[0], global_centroid, decimal=5)

    def test_adaptive_k_picks_k2_on_high_silhouette(self, monkeypatch):
        """Flag on + two well-separated clusters (sil(k=2) >= 0.15) => k=2."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 8)
        clear_centroid_cache()

        likes = _two_cluster_likes()  # 8 entries, 2 tight far-apart clusters
        centroids, global_centroid = compute_taste_centroids(likes, round_num=8)

        assert len(centroids) == 2

    def test_adaptive_k_below_min_likes_uses_default_path(self, monkeypatch):
        """Flag on + N=3 (< adaptive KMeans gate) falls through to the default k=2 path.

        Note: this tests the ADAPTIVE-K routing gate inside compute_taste_centroids (hardcoded >= 4),
        which is separate from the target-window multimodal gate. The test lowers the multimodal
        gate so it can exercise the old adaptive-k boundary directly.
        """
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 3)
        clear_centroid_cache()

        likes = [_like_entry(i) for i in range(3)]  # exactly 3 < engine adaptive gate (4)
        centroids, global_centroid = compute_taste_centroids(likes, round_num=3)
        # Default path: k=min(k_clusters=2, N=3)=2
        assert len(centroids) == 2

    def test_adaptive_k_n_equals_4_boundary(self, monkeypatch):
        """N=4 is the minimum for the adaptive branch (boundary condition)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        clear_centroid_cache()

        likes = _tight_cluster_likes()[:4]  # exactly 4 tight entries
        centroids, _ = compute_taste_centroids(likes, round_num=4)
        # Tight cluster => silhouette < 0.15 => k=1
        assert len(centroids) == 1

    def test_adaptive_k_n_equals_1_uses_early_return(self, monkeypatch):
        """N=1: existing early-return fires before any k-selection logic."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        clear_centroid_cache()

        likes = [_like_entry(0)]
        centroids, global_centroid = compute_taste_centroids(likes, round_num=1)
        assert len(centroids) == 1
