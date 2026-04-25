"""
test_confidence.py -- Sprint 3 C-1: engine.compute_confidence + SwipeView response
+ confidence_update event.

Covers:
  - Pure-Python unit tests for engine.compute_confidence (no DB required)
  - Integration tests: SwipeView response includes 'confidence' key
  - Integration tests: confidence_update SessionEvent emitted with action field
"""
import pytest
import numpy as np
from unittest.mock import patch
from apps.recommendation.models import Project, AnalysisSession


# ---------------------------------------------------------------------------
# Helpers (mirrors test_sessions.py setup so we can seed analyzing state)
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
_FAKE_SCORES = {bid: 15 - i for i, bid in enumerate(_FAKE_POOL)}
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm


def _make_card(bid):
    if bid is None:
        return None
    return {
        'building_id': bid,
        'name_en': f'Building {bid}',
        'project_name': f'Project {bid}',
        'image_url': '',
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Museum',
            'axis_architects': 'Test Arch',
            'axis_country': 'Korea',
            'axis_area_m2': 200.0,
            'axis_year': 2022,
            'axis_style': 'Brutalist',
            'axis_atmosphere': 'bold',
            'axis_color_tone': 'Dark',
            'axis_material': 'concrete',
            'axis_material_visual': [],
            'axis_tags': [],
        },
    }


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_compute_centroids(like_vectors, round_num):
    c = np.random.RandomState(42).randn(384)
    c = c / np.linalg.norm(c)
    return ([c], c)


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_build_action_card():
    return {
        'building_id': '__action_card__',
        'card_type': 'action',
        'name_en': 'Your Taste is Found!',
        'project_name': '',
        'image_url': '',
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {},
        'action_card_message': "We've analyzed your preferences.",
        'action_card_subtitle': 'Swipe right to see results.',
    }


_ENGINE = 'apps.recommendation.views.engine'

_SESSION_PATCHES = {
    f'{_ENGINE}.create_bounded_pool': lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES)),
    f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {
        bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids
    },
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': _make_card,
    f'{_ENGINE}.get_building_embedding': lambda bid: list(
        _FAKE_EMBEDDINGS.get(bid, np.random.randn(384))
    ),
    f'{_ENGINE}.update_preference_vector': lambda pv, emb, act: list(
        np.random.RandomState(42).randn(384)
    ),
    f'{_ENGINE}.compute_taste_centroids': _mock_compute_centroids,
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a: False,
    f'{_ENGINE}.build_action_card': _mock_build_action_card,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
}


def _apply_patches():
    patchers = []
    for target, side_effect in _SESSION_PATCHES.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# Pure unit tests -- no DB needed
# ---------------------------------------------------------------------------

class TestComputeConfidenceUnit:
    """Sprint 3 C-1: engine.compute_confidence pure-Python edge cases."""

    def test_returns_none_below_window_empty(self):
        """n=0 < window(3) -> None (hide-bar semantic per Investigation 13)."""
        from apps.recommendation import engine
        assert engine.compute_confidence([], 0.08) is None

    def test_returns_none_below_window_one(self):
        """n=1 < window(3) -> None."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.04], 0.08) is None

    def test_returns_none_below_window_two(self):
        """n=2 < window(3) -> None."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.04, 0.02], 0.08) is None

    def test_formula_all_zero_returns_one(self):
        """avg=0 -> 1.0 (all Δv zero, vanishingly rare in practice)."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.0, 0.0, 0.0], 0.08) == 1.0

    def test_formula_avg_half_threshold(self):
        """avg=0.04 (= threshold/2) -> 0.5 per Investigation 13 §Formula breakdown."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.04, 0.04, 0.04], 0.08) == pytest.approx(0.5)

    def test_formula_avg_quarter_threshold(self):
        """avg=0.02 (= threshold/4) -> 0.75."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.02, 0.02, 0.02], 0.08) == pytest.approx(0.75)

    def test_formula_avg_equals_threshold(self):
        """avg=0.08 (= threshold) -> 0.0 (floor)."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.08, 0.08, 0.08], 0.08) == pytest.approx(0.0)

    def test_formula_avg_exceeds_threshold_clamped(self):
        """avg > threshold -> clamped to 0.0 (max(0, ...) guard)."""
        from apps.recommendation import engine
        assert engine.compute_confidence([0.20, 0.04, 0.04], 0.08) == pytest.approx(0.0)

    def test_uses_only_last_window(self):
        """Stale history beyond window doesn't affect output -- only last 3 matter."""
        from apps.recommendation import engine
        # history=[0.50, 0.0, 0.0, 0.0]: last 3 = [0.0, 0.0, 0.0] -> avg=0 -> 1.0
        assert engine.compute_confidence([0.50, 0.0, 0.0, 0.0], 0.08) == 1.0

    def test_threshold_zero_guard(self):
        """threshold=0 is defended via 1e-6 floor -- no ZeroDivisionError."""
        from apps.recommendation import engine
        # avg=0.04 >> safe_threshold=1e-6 -> deeply negative, clamped to 0.0
        result = engine.compute_confidence([0.04, 0.04, 0.04], 0.0)
        assert result == 0.0

    def test_result_in_range(self):
        """All valid inputs produce output in [0, 1]."""
        from apps.recommendation import engine
        for avg in [0.0, 0.01, 0.04, 0.07, 0.08, 0.15, 0.30]:
            history = [avg, avg, avg]
            result = engine.compute_confidence(history, 0.08)
            assert 0.0 <= result <= 1.0, f'Out of range for avg={avg}: {result}'


# ---------------------------------------------------------------------------
# Integration tests -- require DB
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestConfidenceBarIntegration:
    """Sprint 3 C-1 integration: SwipeView response + confidence_update event."""

    def _create_session_in_analyzing(self, auth_client, user_profile, history):
        """
        Create a session and directly seed it into 'analyzing' phase with the
        given convergence_history. Returns (session_id, session).

        Direct DB seeding avoids driving many API swipes through a mocked
        engine, which is brittle and slow.
        """
        project = Project.objects.create(
            user=user_profile, name='Confidence Test', filters={},
        )
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        session_id = resp.json()['session_id']
        session = AnalysisSession.objects.get(session_id=session_id)

        # Seed analyzing state directly
        fake_emb = list(np.random.RandomState(1).randn(384))
        session.phase = 'analyzing'
        session.like_vectors = [{'embedding': fake_emb, 'round': 0}]
        session.previous_pref_vector = list(np.random.RandomState(2).randn(384))
        session.convergence_history = list(history)
        session.preference_vector = list(np.random.RandomState(3).randn(384))
        session.current_round = max(3, len(history))
        session.save()

        return session_id, session

    def test_swipe_response_includes_confidence_key(self, auth_client, user_profile):
        """SwipeView POST response must contain 'confidence' key (float or null)."""
        session_id, _ = self._create_session_in_analyzing(
            auth_client, user_profile, history=[0.04, 0.04, 0.04]
        )

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'conf_response_test_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'confidence' in data, f"'confidence' key missing from swipe response: {data.keys()}"
        conf = data['confidence']
        # confidence is float in [0,1] when history >= window
        assert conf is not None
        assert 0.0 <= conf <= 1.0, f'Confidence out of range: {conf}'

    def test_swipe_response_confidence_null_when_history_short(self, auth_client, user_profile):
        """confidence is null when convergence_history < window after swipe."""
        project = Project.objects.create(
            user=user_profile, name='Null Confidence Test', filters={},
        )
        patchers = _apply_patches()
        try:
            create_resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
            session_id = create_resp.json()['session_id']

            # Swipe 1 -- exploring phase, history stays short
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'conf_null_test_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'confidence' in data, f"'confidence' key missing: {data.keys()}"
        # In exploring phase with 1 swipe, history is very short -> confidence=None
        assert data['confidence'] is None, (
            f"Expected null confidence on first swipe, got {data['confidence']!r}"
        )

    def test_swipe_emits_confidence_update_event_with_action(self, auth_client, user_profile):
        """When confidence is not None, a confidence_update SessionEvent is emitted
        with the action field ('like' or 'dislike') per Spec v1.2 dislike-bias telemetry."""
        from apps.recommendation.models import SessionEvent

        session_id, _ = self._create_session_in_analyzing(
            auth_client, user_profile, history=[0.04, 0.04, 0.04]
        )

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00002',
                    'action': 'dislike',
                    'idempotency_key': 'conf_event_action_test_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        conf_events = SessionEvent.objects.filter(
            session__session_id=session_id,
            event_type='confidence_update',
        )
        assert conf_events.exists(), 'No confidence_update SessionEvent found'
        evt = conf_events.order_by('-id').first()
        assert 'action' in evt.payload, f"'action' missing from confidence_update payload: {evt.payload}"
        assert evt.payload['action'] in ('like', 'dislike'), (
            f"action must be 'like' or 'dislike', got {evt.payload['action']!r}"
        )
        assert evt.payload['action'] == 'dislike', (
            f"Expected 'dislike', got {evt.payload['action']!r}"
        )
        assert 'confidence' in evt.payload, f"'confidence' missing from payload: {evt.payload}"
        assert 0.0 <= evt.payload['confidence'] <= 1.0

    def test_action_card_reset_response_has_null_confidence(self, auth_client, user_profile):
        """Action-card 'Reset and keep going' (dislike) response confidence is null."""
        session_id, session = self._create_session_in_analyzing(
            auth_client, user_profile, history=[0.04, 0.04, 0.04]
        )
        # Manually set phase to 'converged' so the action card fires
        session.phase = 'converged'
        session.save(update_fields=['phase'])

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': '__action_card__',
                    'action': 'dislike',  # "Reset and keep going"
                    'idempotency_key': 'conf_action_reset_test_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'confidence' in data, f"'confidence' key missing from reset response: {data.keys()}"
        assert data['confidence'] is None, (
            f"Expected null confidence after reset (history cleared), got {data['confidence']!r}"
        )

    def test_action_card_complete_response_has_confidence_key(self, auth_client, user_profile):
        """Action-card 'like' (complete / view results) path response must include 'confidence' key (null).

        AC #3: both action-card paths (reset+dislike and complete+like) must expose 'confidence'.
        Session terminates on this path; no convergence history to compute over, so null is correct.
        """
        session_id, session = self._create_session_in_analyzing(
            auth_client, user_profile, history=[0.04, 0.04, 0.04]
        )
        # Manually set phase to 'converged' so the action card fires
        session.phase = 'converged'
        session.save(update_fields=['phase'])

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': '__action_card__',
                    'action': 'like',  # "View results" -- complete branch
                    'idempotency_key': 'conf_action_complete_test_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert 'confidence' in data, f"'confidence' key missing from complete response: {data.keys()}"
        assert data['confidence'] is None, (
            f"Expected null confidence on session complete (no live history), got {data['confidence']!r}"
        )
        assert data.get('is_analysis_completed') is True, (
            f"Expected is_analysis_completed=True on complete path, got {data.get('is_analysis_completed')!r}"
        )
