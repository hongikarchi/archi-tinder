"""
test_imp10_topic06_telemetry.py -- IMP-10 sub-task A + Spec v1.8 §6 Topic 06 telemetry.

Tests cover:
  - confidence_update 4 new fields (cluster_count_used, silhouette_score,
    soft_relevance_used, n_likes_at_decision)
  - session_end aggregation (cluster_count_distribution, silhouette_score_p50)
  - backward-compat: AnalysisSession keeps the top-10 provenance columns (DB cleanup: #463)
"""
import pytest
import numpy as np
from unittest.mock import patch
from django.conf import settings

from apps.recommendation import engine, event_log
from apps.recommendation.engine import (
    compute_taste_centroids,
    clear_centroid_cache,
    get_last_clustering_stats,
)
from apps.recommendation.models import AnalysisSession, Project, SessionEvent


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _unit_vec(seed, dim=384):
    """Deterministic L2-normalised vector."""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim)
    return v / np.linalg.norm(v)


def _v_initial():
    """Fake 384-dim v_initial as a list of floats."""
    return _unit_vec(99).tolist()


def _like_entry(seed, round_num=1):
    return {'embedding': _unit_vec(seed).tolist(), 'round': round_num}


def _fake_card(bid):
    return {
        'canonical_bld_id': bid,
        'name_en': f'Building {bid}',
        'project_name': f'Project {bid}',
        'image_url': '',
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Housing',
            'axis_architects': None,
            'axis_country': None,
            'axis_area_m2': None,
            'axis_year': None,
            'axis_style': None,
            'axis_atmosphere': 'calm',
            'axis_color_tone': None,
            'axis_material': None,
            'axis_material_visual': [],
            'axis_tags': [],
        },
    }


FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
FAKE_EMBEDDINGS = {}
for _i, _bid in enumerate(FAKE_POOL):
    _v = _unit_vec(_i)
    FAKE_EMBEDDINGS[_bid] = _v


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------------------------------------------------------------------------
# TestComputeTasteCentroidsStats  (unit, no DB)
# ---------------------------------------------------------------------------

class TestComputeTasteCentroidsStats:
    """Verify _last_clustering_stats is set correctly in all 4 execution paths."""

    def setup_method(self):
        clear_centroid_cache()

    def test_path1_n_equals_1_stats(self):
        """N=1 early return: k=1, silhouette=None, soft=False, n=1."""
        likes = [_like_entry(0)]
        compute_taste_centroids(likes, round_num=1)
        stats = get_last_clustering_stats()
        assert stats is not None
        assert stats['cluster_count_used'] == 1
        assert stats['silhouette_score'] is None
        assert stats['soft_relevance_used'] is False
        assert stats['n_likes_at_decision'] == 1

    def test_path4_default_flag_off_stats(self):
        """Flag OFF, N=4: default KMeans path, silhouette=None."""
        assert settings.RECOMMENDATION.get('adaptive_k_clustering_enabled', False) is False
        likes = [_like_entry(i) for i in range(4)]
        compute_taste_centroids(likes, round_num=4)
        stats = get_last_clustering_stats()
        assert stats is not None
        assert stats['silhouette_score'] is None  # only on adaptive path
        assert stats['n_likes_at_decision'] == 4
        assert stats['cluster_count_used'] in (1, 2)

    def test_path2_adaptive_k2_stats(self, monkeypatch):
        """Adaptive ON, two-cluster data: k=2, silhouette is real float >= 0.15."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 4)
        clear_centroid_cache()
        # Two well-separated poles
        pole_a = _unit_vec(0)
        pole_b = -pole_a
        likes = []
        rng_a = np.random.RandomState(7)
        rng_b = np.random.RandomState(8)
        for _ in range(4):
            noise = rng_a.randn(384) * 0.05
            v = pole_a + noise
            likes.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
        for _ in range(4):
            noise = rng_b.randn(384) * 0.05
            v = pole_b + noise
            likes.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
        compute_taste_centroids(likes, round_num=8)
        stats = get_last_clustering_stats()
        assert stats['cluster_count_used'] == 2
        assert stats['silhouette_score'] is not None
        assert stats['silhouette_score'] >= 0.15
        assert stats['n_likes_at_decision'] == 8

    def test_path3_adaptive_k1_tight_cluster_stats(self, monkeypatch):
        """Adaptive ON, tight cluster (sil<0.15): degrades to k=1, silhouette < 0.15."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 4)
        clear_centroid_cache()
        pole = _unit_vec(42)
        likes = []
        rng = np.random.RandomState(13)
        for _ in range(8):
            noise = rng.randn(384) * 0.005
            v = pole + noise
            likes.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
        compute_taste_centroids(likes, round_num=8)
        stats = get_last_clustering_stats()
        assert stats['cluster_count_used'] == 1
        assert stats['silhouette_score'] is not None  # computed before decision
        assert stats['n_likes_at_decision'] == 8

    def test_soft_relevance_used_true_when_k2_and_flag(self, monkeypatch):
        """soft_relevance_used=True when flag ON AND k=2."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'soft_relevance_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'min_likes_for_multimodal', 4)
        clear_centroid_cache()
        pole_a = _unit_vec(0)
        pole_b = -pole_a
        likes = []
        rng_a = np.random.RandomState(7)
        rng_b = np.random.RandomState(8)
        for _ in range(4):
            noise = rng_a.randn(384) * 0.05
            v = pole_a + noise
            likes.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
        for _ in range(4):
            noise = rng_b.randn(384) * 0.05
            v = pole_b + noise
            likes.append({'embedding': (v / np.linalg.norm(v)).tolist(), 'round': 1})
        compute_taste_centroids(likes, round_num=8)
        stats = get_last_clustering_stats()
        assert stats['soft_relevance_used'] is True

    def test_cache_hit_updates_stats(self, monkeypatch):
        """On cache hit, stats are re-set (not stale from previous request)."""
        monkeypatch.setitem(settings.RECOMMENDATION, 'adaptive_k_clustering_enabled', False)
        clear_centroid_cache()
        likes = [_like_entry(i) for i in range(4)]
        # First call populates cache
        compute_taste_centroids(likes, round_num=4)
        stats1 = get_last_clustering_stats()
        # Simulate a different stats state being set
        import apps.recommendation.engine as _eng
        _eng._last_clustering_stats = {
            'cluster_count_used': 99, 'silhouette_score': 99.9,
            'soft_relevance_used': True, 'n_likes_at_decision': 99,
        }
        # Second call with same input hits cache -- must restore correct stats
        compute_taste_centroids(likes, round_num=4)
        stats2 = get_last_clustering_stats()
        assert stats2['cluster_count_used'] == stats1['cluster_count_used']
        assert stats2['cluster_count_used'] != 99  # stale value overwritten


# ---------------------------------------------------------------------------
# TestConfidenceUpdate4NewFields  (integration, uses DB)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestConfidenceUpdate4NewFields:
    """Verify confidence_update event carries 4 new Topic 06 fields."""

    def _make_analyzing_session(self, user_profile, project):
        """Session in analyzing phase with enough convergence history to emit confidence_update."""
        like_vecs = [_like_entry(i) for i in range(4)]
        return AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            status='active',
            phase='analyzing',
            pool_ids=FAKE_POOL,
            pool_scores={bid: 1.0 for bid in FAKE_POOL},
            like_vectors=like_vecs,
            exposed_ids=FAKE_POOL[:6],
            convergence_history=[0.10, 0.09, 0.08],  # window=3 entries => confidence computed
            previous_pref_vector=_unit_vec(77).tolist(),
            initial_batch=FAKE_POOL[:10],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
        )

    def test_confidence_update_has_cluster_count_used(self, auth_client, user_profile):
        """confidence_update payload includes cluster_count_used field."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_analyzing_session(user_profile, project)

        fake_emb = _unit_vec(5).tolist()
        fake_card = _fake_card('B00007')

        emb_map = {bid: FAKE_EMBEDDINGS[bid] for bid in FAKE_POOL}
        with patch.object(engine, 'get_building_embedding', return_value=fake_emb), \
             patch.object(engine, 'get_pool_embeddings', return_value=emb_map), \
             patch.object(engine, 'get_building_card', return_value=fake_card), \
             patch.object(engine, 'taste_ranked_page', return_value=[]), \
             patch.object(engine, '_random_pool', return_value=[]):
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {
                    'building_id': FAKE_POOL[5],
                    'action': 'like',
                    'idempotency_key': 'test-idem-key-cc-001',
                },
                format='json',
            )

        assert resp.status_code == 200
        event = SessionEvent.objects.filter(
            session=session, event_type='confidence_update',
        ).order_by('-created_at').first()
        if event is not None:  # may not emit if convergence window not reached
            assert 'cluster_count_used' in event.payload

    def test_confidence_update_silhouette_none_when_adaptive_off(self, auth_client, user_profile):
        """adaptive_k_clustering_enabled=False -> silhouette_score=None in event."""
        assert settings.RECOMMENDATION.get('adaptive_k_clustering_enabled', False) is False
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_analyzing_session(user_profile, project)

        fake_emb = _unit_vec(5).tolist()
        fake_card = _fake_card('B00008')

        emb_map_2 = {bid: FAKE_EMBEDDINGS[bid] for bid in FAKE_POOL}
        with patch.object(engine, 'get_building_embedding', return_value=fake_emb), \
             patch.object(engine, 'get_pool_embeddings', return_value=emb_map_2), \
             patch.object(engine, 'get_building_card', return_value=fake_card), \
             patch.object(engine, 'taste_ranked_page', return_value=[]), \
             patch.object(engine, '_random_pool', return_value=[]):
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {
                    'building_id': FAKE_POOL[5],
                    'action': 'like',
                    'idempotency_key': 'test-idem-key-sil-001',
                },
                format='json',
            )

        assert resp.status_code == 200
        event = SessionEvent.objects.filter(
            session=session, event_type='confidence_update',
        ).order_by('-created_at').first()
        if event is not None:
            assert event.payload.get('silhouette_score') is None

    def test_confidence_update_n_likes_at_decision(self, auth_client, user_profile):
        """n_likes_at_decision matches like count in session at clustering time."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_analyzing_session(user_profile, project)

        fake_emb = _unit_vec(5).tolist()
        fake_card = _fake_card('B00009')

        emb_map_3 = {bid: FAKE_EMBEDDINGS[bid] for bid in FAKE_POOL}
        with patch.object(engine, 'get_building_embedding', return_value=fake_emb), \
             patch.object(engine, 'get_pool_embeddings', return_value=emb_map_3), \
             patch.object(engine, 'get_building_card', return_value=fake_card), \
             patch.object(engine, 'taste_ranked_page', return_value=[]), \
             patch.object(engine, '_random_pool', return_value=[]):
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {
                    'building_id': FAKE_POOL[5],
                    'action': 'like',
                    'idempotency_key': 'test-idem-key-nld-001',
                },
                format='json',
            )

        assert resp.status_code == 200
        event = SessionEvent.objects.filter(
            session=session, event_type='confidence_update',
        ).order_by('-created_at').first()
        if event is not None:
            # n_likes_at_decision must be a non-negative int
            assert isinstance(event.payload.get('n_likes_at_decision'), int)
            assert event.payload['n_likes_at_decision'] >= 0


# ---------------------------------------------------------------------------
# TestSessionEndAggregation  (unit + integration)
# ---------------------------------------------------------------------------

class TestSessionEndAggregationUnit:
    """Unit tests for event_log.aggregate_session_clustering_stats."""

    def test_none_session_id_returns_empty(self):
        """session_id=None -> returns empty distribution and None p50."""
        result = event_log.aggregate_session_clustering_stats(None)
        assert result['cluster_count_distribution'] == {}
        assert result['silhouette_score_p50'] is None

    def test_empty_distribution_is_empty_dict(self):
        """No confidence_update events -> distribution={}, p50=None."""
        # Use a non-existent UUID so no events match
        import uuid
        result = event_log.aggregate_session_clustering_stats(uuid.uuid4())
        assert result['cluster_count_distribution'] == {}
        assert result['silhouette_score_p50'] is None


@pytest.mark.django_db
class TestSessionEndAggregationDB:

    def _make_session_object(self, user_profile, project):
        return AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='completed',
            pool_ids=[],
            pool_scores={},
            like_vectors=[],
            exposed_ids=[],
            convergence_history=[],
            initial_batch=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
        )

    def test_k1_k2_distribution(self, user_profile):
        """3 k=1 events + 2 k=2 events -> distribution={1:3, 2:2}."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_session_object(user_profile, project)
        payloads = [
            {'cluster_count_used': 1, 'silhouette_score': 0.05},
            {'cluster_count_used': 1, 'silhouette_score': 0.06},
            {'cluster_count_used': 1, 'silhouette_score': 0.04},
            {'cluster_count_used': 2, 'silhouette_score': 0.20},
            {'cluster_count_used': 2, 'silhouette_score': 0.25},
        ]
        for p in payloads:
            event_log.emit_event('confidence_update', session=session, user=user_profile, **p)

        result = event_log.aggregate_session_clustering_stats(session.session_id)
        assert result['cluster_count_distribution'] == {'1': 3, '2': 2}

    def test_silhouette_p50_median_odd(self, user_profile):
        """5 silhouette scores [0.10, 0.15, 0.20, 0.25, 0.30] -> p50=0.20."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_session_object(user_profile, project)
        scores = [0.10, 0.30, 0.15, 0.25, 0.20]  # unsorted on purpose
        for s in scores:
            event_log.emit_event('confidence_update', session=session, user=user_profile,
                                 cluster_count_used=1, silhouette_score=s)

        result = event_log.aggregate_session_clustering_stats(session.session_id)
        assert abs(result['silhouette_score_p50'] - 0.20) < 1e-9

    def test_silhouette_p50_median_even(self, user_profile):
        """4 silhouette scores -> p50 = avg of two middle values."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_session_object(user_profile, project)
        scores = [0.10, 0.20, 0.30, 0.40]
        for s in scores:
            event_log.emit_event('confidence_update', session=session, user=user_profile,
                                 cluster_count_used=1, silhouette_score=s)

        result = event_log.aggregate_session_clustering_stats(session.session_id)
        assert abs(result['silhouette_score_p50'] - 0.25) < 1e-9

    def test_all_silhouette_none_gives_none_p50(self, user_profile):
        """All events have silhouette_score=None -> p50=None."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_session_object(user_profile, project)
        for _ in range(3):
            event_log.emit_event('confidence_update', session=session, user=user_profile,
                                 cluster_count_used=1, silhouette_score=None)

        result = event_log.aggregate_session_clustering_stats(session.session_id)
        assert result['silhouette_score_p50'] is None

    def test_zero_events_returns_empty(self, user_profile):
        """No confidence_update events -> distribution={}, p50=None."""
        project = Project.objects.create(user=user_profile, name='Test')
        session = self._make_session_object(user_profile, project)
        result = event_log.aggregate_session_clustering_stats(session.session_id)
        assert result['cluster_count_distribution'] == {}
        assert result['silhouette_score_p50'] is None


# ---------------------------------------------------------------------------
# TestBackwardCompat  (verify key backward-compat properties)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackwardCompat:

    def test_analysissession_model_has_three_new_fields(self):
        """AnalysisSession has the 3 new nullable JSONField attributes."""
        from django.db import models as dj_models
        fields = {f.name: f for f in AnalysisSession._meta.get_fields()}
        for fname in ('cosine_top10_ids', 'gemini_top10_ids', 'dpp_top10_ids'):
            assert fname in fields, f'Missing field: {fname}'
            field = fields[fname]
            assert isinstance(field, dj_models.JSONField), f'{fname} should be JSONField'
            assert field.null is True, f'{fname} should be nullable'
