"""
test_topic_composition.py -- Sprint 4 Topic 02 ∩ 04 Option alpha composition
(RRF fusion + DPP) per Investigation 07 + Investigation 14 §q derivation.

Tests cover:
- Both flags on -> DPP receives RRF-rescaled q (not raw cosine)
- DPP only (rerank off) -> q = max centroid cosine (standalone behaviour preserved)
- Both flags on but rerank returns input order -> DPP uses cosine q (failure cascade)
- Composition q values land in [0.01, 1.0] post-rescale
- fmax == fmin edge case -> all q = 0.5 (no division by zero)
"""
import math
import uuid
import numpy as np
import pytest

DIM = 384


def _unit384(seed_vec):
    """Build a 384-dim unit vector from seed_vec, then L2-normalise."""
    v = np.zeros(DIM)
    v[:len(seed_vec)] = seed_vec
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _make_fake_cards(ids):
    """Minimal card dicts for SessionResultView consumption."""
    return [
        {
            'building_id': bid,
            'name_en': f'Building {bid}',
            'atmosphere': 'calm',
            'material': 'concrete',
            'architect': 'Anon',
            'style': 'Contemporary',
            'program': 'Museum',
        }
        for bid in ids
    ]


def _make_like_vectors(n=2):
    """Return n minimal like_vector dicts."""
    rng = np.random.default_rng(7)
    vecs = []
    for i in range(n):
        v = rng.standard_normal(DIM)
        v = v / np.linalg.norm(v)
        vecs.append({'round': i + 1, 'embedding': v.tolist()})
    return vecs


def _make_session(user_profile, like_vectors=None, like_ids=None):
    """Create a completed AnalysisSession with project for testing."""
    from apps.recommendation.models import Project, AnalysisSession

    if like_ids is None:
        like_ids = [{'id': 'B99999', 'intensity': 1.0}]
    if like_vectors is None:
        like_vectors = _make_like_vectors(2)

    project = Project.objects.create(
        user=user_profile,
        name='Composition Test Project',
        liked_ids=like_ids,
        disliked_ids=[],
    )
    session = AnalysisSession.objects.create(
        session_id=uuid.uuid4(),
        user=user_profile,
        project=project,
        status='completed',
        phase='analyzing',
        preference_vector=[0.0] * DIM,
        like_vectors=like_vectors,
        exposed_ids=[],
        current_round=len(like_vectors),
        convergence_history=[],
    )
    return session


def _expected_rrf_q(ids, cosine_order, rerank_order, K_RRF=60):
    """
    Compute the expected min-max-rescaled RRF q_values for a candidate list.

    cosine_order: list of building_ids in cosine rank order (1-indexed position)
    rerank_order: list of building_ids in rerank order (1-indexed position)
    Returns dict {bid: q_value} in [0.01, 1.0].
    """
    cosine_rank = {bid: i + 1 for i, bid in enumerate(cosine_order)}
    rerank_rank = {bid: i + 1 for i, bid in enumerate(rerank_order)}
    fused = {
        bid: (1.0 / (K_RRF + cosine_rank[bid])) + (1.0 / (K_RRF + rerank_rank[bid]))
        for bid in ids
        if bid in cosine_rank and bid in rerank_rank
    }
    fmin = min(fused.values())
    fmax = max(fused.values())
    if fmax > fmin:
        return {bid: 0.01 + 0.99 * (fused[bid] - fmin) / (fmax - fmin) for bid in fused}
    return {bid: 0.5 for bid in fused}


# ---------------------------------------------------------------------------
# TestTopic02DppComposition
# ---------------------------------------------------------------------------

class TestTopic02DppComposition:
    """Sprint 4 Topic 02 ∩ 04 Option alpha composition (Investigation 07)."""

    @pytest.mark.django_db
    def test_composition_uses_rrf_q_when_both_flags_on(self, user_profile, auth_client, monkeypatch):
        """Both flags on -> DPP receives RRF-rescaled q_override (not raw cosine)."""
        from django.conf import settings
        from apps.recommendation import engine, services

        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 5)

        ids = [f'B{i:05d}' for i in range(5)]
        # Rerank returns a distinct order (reversed)
        reversed_ids = list(reversed(ids))
        fake_cards = _make_fake_cards(ids)

        # Capture the q_override argument passed to compute_dpp_topk
        captured = {}

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_rerank(candidates, liked_summary):
            return reversed_ids

        def _fake_liked_summary(liked_ids):
            return 'liked summary'

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            captured['q_override'] = q_override
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(services, 'rerank_candidates', _fake_rerank)
        monkeypatch.setattr(services, '_liked_summary_for_rerank', _fake_liked_summary)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        like_vectors = _make_like_vectors(2)
        session = _make_session(user_profile, like_vectors=like_vectors)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200

        # DPP must have been called with q_override (not None)
        assert 'q_override' in captured, "compute_dpp_topk was not called"
        q_override = captured['q_override']
        assert q_override is not None, "q_override should be set when both flags are on"

        # Verify q_override matches expected RRF-rescaled values
        expected_q = _expected_rrf_q(ids, cosine_order=ids, rerank_order=reversed_ids)
        for bid in ids:
            assert bid in q_override, f"q_override missing bid {bid}"
            assert abs(q_override[bid] - expected_q[bid]) < 1e-9, (
                f"q_override[{bid}]={q_override[bid]} expected={expected_q[bid]}"
            )

    @pytest.mark.django_db
    def test_composition_falls_back_to_cosine_q_when_rerank_off(self, user_profile, auth_client, monkeypatch):
        """DPP only (rerank off) -> q_override=None, standalone cosine q path used."""
        from django.conf import settings
        from apps.recommendation import engine, services

        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 5)

        ids = [f'B{i:05d}' for i in range(5)]
        fake_cards = _make_fake_cards(ids)
        captured = {}

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            captured['q_override'] = q_override
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        # Ensure rerank_candidates is NOT called
        rerank_called = []
        monkeypatch.setattr(services, 'rerank_candidates', lambda *a, **kw: rerank_called.append(1) or [])

        like_vectors = _make_like_vectors(2)
        session = _make_session(user_profile, like_vectors=like_vectors)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200

        assert not rerank_called, "rerank_candidates should not be called when flag is off"
        assert 'q_override' in captured, "compute_dpp_topk was not called"
        assert captured['q_override'] is None, (
            "q_override should be None when only DPP flag is on (cosine q path)"
        )

    @pytest.mark.django_db
    def test_composition_falls_back_to_cosine_q_when_rerank_returns_input_order(
        self, user_profile, auth_client, monkeypatch
    ):
        """Rerank returns input order (failure indicator) -> DPP uses cosine q (q_override=None)."""
        from django.conf import settings
        from apps.recommendation import engine, services

        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 5)

        ids = [f'B{i:05d}' for i in range(5)]
        fake_cards = _make_fake_cards(ids)
        captured = {}

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        # Rerank returns SAME ORDER as input — sentinel: no real reorder
        def _fake_rerank(candidates, liked_summary):
            return list(ids)  # same order as cosine

        def _fake_liked_summary(liked_ids):
            return 'liked summary'

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            captured['q_override'] = q_override
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(services, 'rerank_candidates', _fake_rerank)
        monkeypatch.setattr(services, '_liked_summary_for_rerank', _fake_liked_summary)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        like_vectors = _make_like_vectors(2)
        session = _make_session(user_profile, like_vectors=like_vectors)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200

        assert 'q_override' in captured, "compute_dpp_topk was not called"
        assert captured['q_override'] is None, (
            "q_override must be None when rerank returned input order (failure sentinel)"
        )

    @pytest.mark.django_db
    def test_composition_q_in_unit_interval(self, user_profile, auth_client, monkeypatch):
        """Composition q values land in [0.01, 1.0] post-rescale."""
        from django.conf import settings
        from apps.recommendation import engine, services

        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 5)

        ids = [f'B{i:05d}' for i in range(5)]
        # Use a distinct rerank order (not identical to cosine order)
        rerank_order = [ids[2], ids[4], ids[0], ids[3], ids[1]]
        fake_cards = _make_fake_cards(ids)
        captured = {}

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_rerank(candidates, liked_summary):
            return rerank_order

        def _fake_liked_summary(liked_ids):
            return 'liked summary'

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            captured['q_override'] = q_override
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(services, 'rerank_candidates', _fake_rerank)
        monkeypatch.setattr(services, '_liked_summary_for_rerank', _fake_liked_summary)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        like_vectors = _make_like_vectors(2)
        session = _make_session(user_profile, like_vectors=like_vectors)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200

        q_override = captured.get('q_override')
        assert q_override is not None, "q_override should be set when rerank returned distinct order"
        for bid, val in q_override.items():
            assert 0.01 <= val <= 1.0, (
                f"q_override[{bid}]={val} outside [0.01, 1.0]"
            )
        # Verify top item is exactly 1.0 and bottom item is exactly 0.01
        values = list(q_override.values())
        assert math.isclose(max(values), 1.0, rel_tol=1e-9), "max q should be 1.0"
        assert math.isclose(min(values), 0.01, rel_tol=1e-9), "min q should be 0.01"

    @pytest.mark.django_db
    def test_composition_handles_all_equal_fused_relevance(self, user_profile, auth_client, monkeypatch):
        """fmax == fmin edge -> all q = 0.5 (no division by zero)."""
        from django.conf import settings
        from apps.recommendation import engine, services

        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', 2)

        # Use 2 candidates with the same cosine rank and rerank rank -> equal fused score.
        # We achieve this by having only 1 candidate (trivially all-equal edge case
        # never reaches the fmax > fmin branch), but per code the dpp gate requires >= 2.
        # Instead: two candidates with symmetric RRF — cosine 1→2 / rerank 2→1 and
        # cosine 2→1 / rerank 1→2 — this gives equal fused scores.
        ids = ['B00001', 'B00002']
        # cosine order: [B00001, B00002], rerank_order: [B00002, B00001]
        # cosine_rank: B00001=1, B00002=2  |  rerank_rank: B00002=1, B00001=2
        # fused(B00001) = 1/(60+1) + 1/(60+2) = 1/61 + 1/62
        # fused(B00002) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61  (same!)
        rerank_order = list(reversed(ids))
        fake_cards = _make_fake_cards(ids)
        captured = {}

        def _fake_top_k_mmr(*a, **kw):
            return list(fake_cards)

        def _fake_rerank(candidates, liked_summary):
            return rerank_order

        def _fake_liked_summary(liked_ids):
            return 'liked summary'

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            captured['q_override'] = q_override
            return [c['building_id'] for c in cards[:k]]

        monkeypatch.setattr(engine, 'get_top_k_mmr', _fake_top_k_mmr)
        monkeypatch.setattr(services, 'rerank_candidates', _fake_rerank)
        monkeypatch.setattr(services, '_liked_summary_for_rerank', _fake_liked_summary)
        monkeypatch.setattr(engine, 'compute_dpp_topk', _fake_dpp)

        like_vectors = _make_like_vectors(2)
        session = _make_session(user_profile, like_vectors=like_vectors)

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/result/')
        assert resp.status_code == 200

        q_override = captured.get('q_override')
        # rerank_order != cosine_order so rerank_rank_by_id is set -> composition path runs
        assert q_override is not None, "q_override should be set"
        # All values should be 0.5 (all-equal edge case)
        for bid, val in q_override.items():
            assert math.isclose(val, 0.5, rel_tol=1e-9), (
                f"Expected all q=0.5 for equal fused relevance, got q[{bid}]={val}"
            )
