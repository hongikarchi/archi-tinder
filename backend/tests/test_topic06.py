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
    compute_mmr_next,
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

    def test_adaptive_k_disabled_by_default(self):
        """Default flag=False: k=2 KMeans always used when N>=4."""
        assert settings.RECOMMENDATION.get('adaptive_k_clustering_enabled', False) is False

        likes = [_like_entry(i) for i in range(4)]
        centroids, global_centroid = compute_taste_centroids(likes, round_num=4)
        # Default k_clusters=2 and N=4 >= 2 => two centroids
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
        clear_centroid_cache()

        likes = _two_cluster_likes()  # 8 entries, 2 tight far-apart clusters
        centroids, global_centroid = compute_taste_centroids(likes, round_num=8)

        assert len(centroids) == 2

    def test_adaptive_k_below_min_likes_uses_default_path(self, monkeypatch):
        """Flag on + N=3 (< engine hardcoded >= 4 gate) => falls through to default k=min(2,3)=2 path.

        Note: this tests the ADAPTIVE-K routing gate inside compute_taste_centroids (hardcoded >= 4),
        which is separate from the phase-transition gate min_likes_for_clustering in settings.py.
        Spec v1.8 Topic 06 raised min_likes_for_clustering 3->4 so K-Means is never invoked at
        N=3 from the swipe flow (session stays in exploring phase), but if compute_taste_centroids
        is called directly with N=3 the engine still uses the default k=2 path -- consistent.
        """
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
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

    # -- soft_relevance_enabled flag tests ------------------------------------

    def test_soft_relevance_disabled_by_default(self, monkeypatch):
        """
        Default flag=False: hard-max selects the candidate with the highest
        single-centroid similarity, even when softmax would pick differently.
        """
        assert settings.RECOMMENDATION.get('soft_relevance_enabled', False) is False

        # Construct two orthogonal unit centroids in 2-D embedded in 384-D
        c1 = np.zeros(384)
        c1[0] = 1.0
        c2 = np.zeros(384)
        c2[1] = 1.0

        # candidate_A: high sim to c1 (0.95), strongly negative to c2
        # => hard-max=0.95, softmax-weighted < 0.95
        cand_a = np.zeros(384)
        cand_a[0] = 0.95
        cand_a[1] = -0.90
        norm = np.linalg.norm(cand_a)
        cand_a = cand_a / norm  # normalise

        # candidate_B: equal moderate sim to both centroids
        # => hard-max = sim, softmax-weighted = same sim (equal weights)
        cand_b = np.zeros(384)
        cand_b[0] = 1.0
        cand_b[1] = 1.0
        cand_b = cand_b / np.linalg.norm(cand_b)

        # Verify hard-max picks A, softmax would pick B
        sim_a1 = float(np.dot(cand_a, c1))
        sim_a2 = float(np.dot(cand_a, c2))
        sim_b1 = float(np.dot(cand_b, c1))

        hard_max_a = max(sim_a1, sim_a2)
        hard_max_b = max(sim_b1, float(np.dot(cand_b, c2)))

        sims_a = np.array([sim_a1, sim_a2])
        exp_a = np.exp(sims_a - sims_a.max())
        soft_a = float(np.sum(sims_a * (exp_a / exp_a.sum())))

        assert hard_max_a > hard_max_b, "test setup: hard-max must favour A"
        assert soft_a < hard_max_b, "test setup: softmax must favour B over A"

        # With flag OFF, engine uses hard-max => picks A
        from unittest.mock import patch
        pool_ids = ['A', 'B']
        pool_embeddings = {'A': cand_a, 'B': cand_b}
        like_vectors = [{'embedding': c1.tolist(), 'round': 1}]  # dummy

        with patch('apps.recommendation.engine.compute_taste_centroids',
                   return_value=([c1, c2], c1)):
            result = compute_mmr_next(
                pool_ids, [], pool_embeddings, like_vectors, round_num=1,
            )

        assert result == 'A', f"hard-max (flag off) should pick A; got {result}"

    def test_soft_relevance_enabled_uses_softmax(self, monkeypatch):
        """
        Flag on + 2 centroids: softmax-weighted relevance picks the candidate
        with balanced similarity over both centroids rather than the single-peak
        candidate that hard-max would select.
        """
        monkeypatch.setitem(settings.RECOMMENDATION, 'soft_relevance_enabled', True)

        # Same centroid setup as test above
        c1 = np.zeros(384)
        c1[0] = 1.0
        c2 = np.zeros(384)
        c2[1] = 1.0

        cand_a = np.zeros(384)
        cand_a[0] = 0.95
        cand_a[1] = -0.90
        cand_a = cand_a / np.linalg.norm(cand_a)

        cand_b = np.zeros(384)
        cand_b[0] = 1.0
        cand_b[1] = 1.0
        cand_b = cand_b / np.linalg.norm(cand_b)

        # Verify the discriminator holds
        sim_a1 = float(np.dot(cand_a, c1))
        sim_a2 = float(np.dot(cand_a, c2))
        sims_a = np.array([sim_a1, sim_a2])
        exp_a = np.exp(sims_a - sims_a.max())
        soft_a = float(np.sum(sims_a * (exp_a / exp_a.sum())))

        sim_b1 = float(np.dot(cand_b, c1))
        sim_b2 = float(np.dot(cand_b, c2))
        sims_b = np.array([sim_b1, sim_b2])
        exp_b = np.exp(sims_b - sims_b.max())
        soft_b = float(np.sum(sims_b * (exp_b / exp_b.sum())))

        assert soft_b > soft_a, "test setup: softmax must favour B"

        # With flag ON, engine uses softmax => picks B
        from unittest.mock import patch
        pool_ids = ['A', 'B']
        pool_embeddings = {'A': cand_a, 'B': cand_b}
        like_vectors = [{'embedding': c1.tolist(), 'round': 1}]

        with patch('apps.recommendation.engine.compute_taste_centroids',
                   return_value=([c1, c2], c1)):
            result = compute_mmr_next(
                pool_ids, [], pool_embeddings, like_vectors, round_num=1,
            )

        assert result == 'B', f"softmax (flag on) should pick B; got {result}"

    def test_soft_relevance_single_centroid_equivalent(self, monkeypatch):
        """
        Flag on + len(centroids)==1: soft branch is skipped (len>1 guard).
        Behaviour equals hard max -- both pick the sole candidate.
        """
        monkeypatch.setitem(settings.RECOMMENDATION, 'soft_relevance_enabled', True)

        pole = _unit_vec(5)
        candidate = _unit_vec(6)
        candidate_id = 'B00002'

        pool_ids = [candidate_id]
        exposed_ids = []
        pool_embeddings = {candidate_id: candidate}
        like_vectors = [{'embedding': pole.tolist(), 'round': 1}]

        # Single centroid => soft branch condition `len(centroids) > 1` is False
        # => falls back to hard max => result is still the sole candidate
        result = compute_mmr_next(
            pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num=1,
        )
        assert result == candidate_id
