"""
test_dpp_overfetch.py -- Codex audit #1.4: DPP over-fetch fix.

Verifies that when dpp_topk_enabled=True the SessionResultView re-fetches
a larger candidate window (top_k_results * dpp_overfetch_multiplier) so
DPP MAP can actually narrow, and that the response is still exactly
top_k_results items in DPP-determined order.
"""
import numpy as np
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helpers shared with test_topic04.py
# ---------------------------------------------------------------------------

DIM = 384


def _make_card(bid):
    """Minimal card dict matching v2 schema."""
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'image_url': f'https://example.com/{bid}.jpg',
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
            'axis_style': 'Modern',
            'axis_atmosphere': 'bold',
            'axis_color_tone': 'Dark',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


_ENGINE = 'apps.recommendation.views.engine'


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDppOverfetch:
    """Codex audit #1.4: DPP over-fetch candidate window."""

    def _make_session(self, user_profile):
        """Seed a minimal session with like_vectors set."""
        from apps.recommendation.models import Project, AnalysisSession
        fake_vec = list(np.random.RandomState(7).randn(DIM))
        project = Project.objects.create(
            user=user_profile,
            name='DPP Overfetch Test',
            liked_ids=[{'id': 'B00001', 'intensity': 1.0}],
        )
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            status='completed',
            phase='converged',
            preference_vector=fake_vec,
            like_vectors=[{'round': 1, 'embedding': fake_vec}],
            pool_ids=[f'B{i:05d}' for i in range(60)],
            exposed_ids=[f'B{i:05d}' for i in range(60)],
            pool_scores={f'B{i:05d}': 1.0 for i in range(60)},
            current_round=20,
            current_pool_tier=1,
        )
        return session

    def test_dpp_disabled_no_overfetch(self, user_profile, auth_client, monkeypatch):
        """Flag OFF: get_top_k_mmr called with k == top_k_results (no over-fetch)."""
        from django.conf import settings

        top_k = 5
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', top_k)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_overfetch_multiplier', 3)

        session = self._make_session(user_profile)

        k_calls = []

        def _fake_mmr(like_vectors, exposed_ids, k, round_num=None):
            k_calls.append(k)
            return [_make_card(f'B{i:05d}') for i in range(k)]

        with patch(f'{_ENGINE}.get_buildings_by_ids', return_value=[]):
            with patch(f'{_ENGINE}.get_top_k_mmr', side_effect=_fake_mmr):
                resp = auth_client.get(
                    f'/api/v1/analysis/sessions/{session.session_id}/result/'
                )

        assert resp.status_code == 200
        # Flag OFF: only the baseline fetch with k=top_k_results (no second call)
        assert k_calls == [top_k], (
            f"Expected single fetch with k={top_k}, got k_calls={k_calls}"
        )

    def test_dpp_enabled_overfetches_3x(self, user_profile, auth_client, monkeypatch):
        """Flag ON: the second get_top_k_mmr call uses k = top_k_results * multiplier."""
        from django.conf import settings

        top_k = 5
        mult = 3
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', top_k)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_overfetch_multiplier', mult)

        session = self._make_session(user_profile)

        k_calls = []

        def _fake_mmr(like_vectors, exposed_ids, k, round_num=None):
            k_calls.append(k)
            return [_make_card(f'B{i:05d}') for i in range(k)]

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            return [c['canonical_bld_id'] for c in cards[:k]]

        with patch(f'{_ENGINE}.get_buildings_by_ids', return_value=[]):
            with patch(f'{_ENGINE}.get_top_k_mmr', side_effect=_fake_mmr):
                with patch(f'{_ENGINE}.compute_dpp_topk', side_effect=_fake_dpp):
                    resp = auth_client.get(
                        f'/api/v1/analysis/sessions/{session.session_id}/result/'
                    )

        assert resp.status_code == 200
        # First call: baseline k=5; second call: over-fetch k=15
        assert top_k * mult in k_calls, (
            f"Expected a call with k={top_k * mult}; got k_calls={k_calls}"
        )

    def test_dpp_narrows_back_to_top_k(self, user_profile, auth_client, monkeypatch):
        """Flag ON: response predicted_images length == top_k_results and order follows DPP."""
        from django.conf import settings

        top_k = 5
        mult = 3
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', top_k)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_overfetch_multiplier', mult)

        session = self._make_session(user_profile)

        # Over-fetched set: 15 cards in original MMR order
        overfetch_ids = [f'B{i:05d}' for i in range(top_k * mult)]

        def _fake_mmr(like_vectors, exposed_ids, k, round_num=None):
            return [_make_card(oid) for oid in overfetch_ids[:k]]

        # DPP narrows to top_k in reversed order
        dpp_result = list(reversed(overfetch_ids[:top_k]))

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            return dpp_result[:k]

        with patch(f'{_ENGINE}.get_buildings_by_ids', return_value=[]):
            with patch(f'{_ENGINE}.get_top_k_mmr', side_effect=_fake_mmr):
                with patch(f'{_ENGINE}.compute_dpp_topk', side_effect=_fake_dpp):
                    resp = auth_client.get(
                        f'/api/v1/analysis/sessions/{session.session_id}/result/'
                    )

        assert resp.status_code == 200
        data = resp.json()
        predicted = data['predicted_images']
        returned_ids = [c['canonical_bld_id'] for c in predicted]

        # Exactly top_k_results items returned
        assert len(returned_ids) == top_k, (
            f"Expected {top_k} items, got {len(returned_ids)}"
        )
        # Order follows DPP output
        assert returned_ids == dpp_result[:top_k], (
            f"DPP order not respected: got {returned_ids}, want {dpp_result[:top_k]}"
        )

    def test_dpp_provenance_top10_stable(self, user_profile, auth_client, monkeypatch):
        """Flag ON: session.cosine_top10_ids == first 10 ids of the over-fetched cosine result."""
        from django.conf import settings

        top_k = 5
        mult = 3
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_topk_enabled', True)
        monkeypatch.setitem(settings.RECOMMENDATION, 'gemini_rerank_enabled', False)
        monkeypatch.setitem(settings.RECOMMENDATION, 'top_k_results', top_k)
        monkeypatch.setitem(settings.RECOMMENDATION, 'dpp_overfetch_multiplier', mult)

        session = self._make_session(user_profile)

        overfetch_ids = [f'B{i:05d}' for i in range(top_k * mult)]

        def _fake_mmr(like_vectors, exposed_ids, k, round_num=None):
            return [_make_card(oid) for oid in overfetch_ids[:k]]

        def _fake_dpp(cards, like_vectors, k, q_override=None):
            return [c['canonical_bld_id'] for c in cards[:k]]

        with patch(f'{_ENGINE}.get_buildings_by_ids', return_value=[]):
            with patch(f'{_ENGINE}.get_top_k_mmr', side_effect=_fake_mmr):
                with patch(f'{_ENGINE}.compute_dpp_topk', side_effect=_fake_dpp):
                    resp = auth_client.get(
                        f'/api/v1/analysis/sessions/{session.session_id}/result/'
                    )

        assert resp.status_code == 200
        session.refresh_from_db()

        # cosine_top10 must reflect the over-fetched cosine order sliced to min(10, n)
        expected_cosine_top10 = overfetch_ids[:min(10, top_k * mult)]
        assert session.cosine_top10_ids == expected_cosine_top10, (
            f"cosine_top10_ids mismatch: got {session.cosine_top10_ids}, "
            f"want {expected_cosine_top10}"
        )
