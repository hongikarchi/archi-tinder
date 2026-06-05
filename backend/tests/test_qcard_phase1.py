"""
test_qcard_phase1.py -- ALGO-QCARD Phase 1: soft-vector bias integration tests.

Covers:
  - Yes on refine: session.question_bias_vector becomes non-null, magnitude
    reflects +2.0 * kw_vec direction.
  - No on refine: qbias delta is in negative direction.
  - Cooldown/cap: after question_max_per_session (2) triggered questions,
    _check_question_trigger returns None.
  - question_cooldown is set to question_cooldown_swipes (15) on trigger.
  - skip: no qbias change, flush_prefetch False.
  - Response shape: flush_prefetch True + next_image present on A/B.

Engine functions that require DB access are mocked throughout.
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project, AnalysisSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm

_ENGINE = 'apps.recommendation.views.engine'
_SERVICE_ENGINE = 'apps.recommendation.services.swipe_service.engine'


def _make_card(bid):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'image_url': '',
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
            'axis_style': 'Minimal',
            'axis_atmosphere': 'calm',
            'axis_color_tone': 'Light',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


def _fake_pool_embeddings(ids):
    return {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in ids}


def _make_normalized_vec():
    """Return a deterministic normalized 384-d vector."""
    v = np.random.RandomState(99).randn(384).astype(np.float64)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# Unit tests: _check_question_trigger cap/cooldown behaviour
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCheckQuestionTriggerCap:
    """_check_question_trigger respects question_count cap and cooldown_n."""

    def _make_session(self, user_profile, question_count=0, question_cooldown=0):
        project = Project.objects.create(user=user_profile, name='QCard Test', filters={})
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='analyzing',
            pool_ids=_FAKE_POOL[:5],
            pool_scores={bid: 1.0 for bid in _FAKE_POOL[:5]},
            current_round=5,
            preference_vector=[0.1] * 384,
            exposed_ids=_FAKE_POOL[:3],
            initial_batch=_FAKE_POOL[:5],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            # Set up tag state for 70% condition to trigger
            tag_axis_counts={'style': {'minimal': 5}},
            recent_like_tag_sets=[],
            question_cooldown=question_cooldown,
            q_card_consecutive_dislikes=0,
            question_count=question_count,
            question_bias_vector=None,
        )
        return session

    def test_cap_at_2_no_trigger(self, user_profile):
        """After 2 questions triggered, _check_question_trigger returns None."""
        from apps.recommendation.services import swipe_service as svc
        session = self._make_session(user_profile, question_count=2)
        result = svc._check_question_trigger(session, 'like')
        assert result is None, (
            f'Expected None when question_count=2 (cap), got: {result}'
        )

    def test_cap_at_1_still_triggers(self, user_profile, monkeypatch):
        """At question_count=1, next trigger should still fire (below cap=2)."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc
        # Make sure cap is 2
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)
        session = self._make_session(user_profile, question_count=1)
        # tag_axis_counts has 'minimal' at 5 counts = 100% (>70%) → should trigger
        result = svc._check_question_trigger(session, 'like')
        assert result is not None, 'Expected trigger at question_count=1 (< cap=2)'
        assert result['type'] == 'refine'
        assert result['keyword'] == 'minimal'

    def test_cooldown_uses_question_cooldown_swipes(self, user_profile, monkeypatch):
        """When a trigger fires, question_cooldown is set to question_cooldown_swipes (15)."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)
        session = self._make_session(user_profile, question_count=0)
        result = svc._check_question_trigger(session, 'like')
        assert result is not None, 'Expected trigger'
        assert session.question_cooldown == 15, (
            f'Expected question_cooldown=15, got {session.question_cooldown}'
        )

    def test_trigger_increments_question_count(self, user_profile, monkeypatch):
        """Firing a trigger increments session.question_count by 1."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)
        session = self._make_session(user_profile, question_count=0)
        result = svc._check_question_trigger(session, 'like')
        assert result is not None
        assert session.question_count == 1

    def test_refresh_trigger_includes_keyword_none(self, user_profile, monkeypatch):
        """Refresh trigger (4+ consecutive dislikes) has keyword=None."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        session = self._make_session(user_profile, question_count=0)
        session.q_card_consecutive_dislikes = 4
        result = svc._check_question_trigger(session, 'dislike')
        assert result is not None
        assert result['type'] == 'refresh'
        assert result['keyword'] is None

    def test_refine_trigger_carries_keyword(self, user_profile, monkeypatch):
        """Refine trigger payload includes 'keyword' field."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        session = self._make_session(user_profile, question_count=0)
        result = svc._check_question_trigger(session, 'like')
        assert result is not None
        assert 'keyword' in result
        assert result['keyword'] == 'minimal'


# ---------------------------------------------------------------------------
# Integration tests: handle_question_response soft-vector mutations
# ---------------------------------------------------------------------------

def _make_analyzing_session(user_profile):
    """Create a Project + analyzing AnalysisSession with some like_vectors."""
    project = Project.objects.create(
        user=user_profile, name='QBias Integration Test', filters={},
    )
    fake_vec = list(_make_normalized_vec())
    session = AnalysisSession.objects.create(
        user=user_profile,
        project=project,
        phase='analyzing',
        pool_ids=_FAKE_POOL[:10],
        pool_scores={bid: 1.0 for bid in _FAKE_POOL[:10]},
        current_round=5,
        preference_vector=fake_vec,
        exposed_ids=_FAKE_POOL[:3],
        initial_batch=_FAKE_POOL[:5],
        like_vectors=[{'embedding': fake_vec, 'round': i} for i in range(3)],
        convergence_history=[],
        previous_pref_vector=fake_vec,
        original_filters={},
        original_filter_priority=[],
        original_seed_ids=[],
        current_pool_tier=1,
        tag_axis_counts={'style': {'minimal': 3}},
        recent_like_tag_sets=[],
        question_cooldown=0,
        q_card_consecutive_dislikes=2,
        question_count=0,
        question_bias_vector=None,
    )
    return session


def _base_patches(pool_ids, kw_vec=None):
    """Build engine mock dict for question-response tests.

    kw_vec: if provided, get_pool_embeddings returns a uniform dict so
    _compute_kw_vec_refine can average them to get a stable vector.
    """
    if kw_vec is None:
        kw_vec_arr = _make_normalized_vec()
    else:
        kw_vec_arr = kw_vec

    def _fake_get_pool_embs(ids):
        return {bid: kw_vec_arr.copy() for bid in ids}

    return {
        f'{_SERVICE_ENGINE}.get_pool_embeddings': _fake_get_pool_embs,
        f'{_SERVICE_ENGINE}.compute_mmr_next': lambda *a, **kw: pool_ids[3],
        f'{_SERVICE_ENGINE}.farthest_point_from_pool': lambda *a, **kw: pool_ids[3],
        f'{_SERVICE_ENGINE}.get_buildings_by_ids': lambda ids, **kw: [_make_card(bid) for bid in ids],
    }


def _apply_patches(patches):
    patchers = []
    for target, side_effect in patches.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


@pytest.mark.django_db
class TestQuestionResponseSoftVector:
    """handle_question_response mutates question_bias_vector correctly."""

    def test_yes_refine_boosts_qbias(self, auth_client, user_profile, monkeypatch):
        """A=Yes on refine sets a non-null question_bias_vector in +boost direction."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_boost_weight', 2.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        kw_vec = _make_normalized_vec()
        session = _make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        # Mock the buildings DB cursor to return matching IDs for the keyword query
        from unittest.mock import MagicMock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # Return first 2 pool IDs as matching the keyword
        mock_cursor.fetchall.return_value = [(pool_ids[0],), (pool_ids[1],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        patches = _base_patches(pool_ids, kw_vec=kw_vec)

        patchers = _apply_patches(patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refine',
                    'axis': 'style',
                    'keyword': 'minimal',
                    'selected_option': 'A',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.json()}'
        data = resp.json()
        assert data['accepted'] is True
        assert data['flush_prefetch'] is True
        assert data.get('next_image') is not None

        session.refresh_from_db()
        assert session.question_bias_vector is not None, (
            'question_bias_vector should be non-null after Yes/refine answer'
        )
        assert len(session.question_bias_vector) == 384
        # The bias vector should be in the +kw_vec direction (all components ~2.0*kw_vec)
        qb = np.array(session.question_bias_vector)
        dot = float(np.dot(qb / np.linalg.norm(qb), kw_vec))
        assert dot > 0.9, (
            f'Bias direction should align strongly with kw_vec (dot={dot:.3f}), '
            f'expected > 0.9'
        )

    def test_no_refine_penalizes_qbias(self, auth_client, user_profile, monkeypatch):
        """B=No on refine sets a negative-direction question_bias_vector."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_penalty_weight', 1.0)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        kw_vec = _make_normalized_vec()
        session = _make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        patches = _base_patches(pool_ids, kw_vec=kw_vec)
        patchers = _apply_patches(patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refine',
                    'axis': 'style',
                    'keyword': 'minimal',
                    'selected_option': 'B',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.question_bias_vector is not None
        qb = np.array(session.question_bias_vector)
        # B=No → delta = -penalty*kw_vec → bias should align negatively with kw_vec
        dot = float(np.dot(qb / np.linalg.norm(qb), kw_vec))
        assert dot < -0.9, (
            f'Bias direction should be ANTI-aligned with kw_vec (dot={dot:.3f}), '
            f'expected < -0.9'
        )

    def test_skip_no_qbias_change(self, auth_client, user_profile, monkeypatch):
        """skip answer does NOT change question_bias_vector, flush_prefetch=False."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        session = _make_analyzing_session(user_profile)
        original_bias = session.question_bias_vector  # None

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refine',
                    'axis': 'style',
                    'keyword': 'minimal',
                    'selected_option': 'skip',
                },
                format='json',
            )
        finally:
            conn_patcher.stop()

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        assert data['flush_prefetch'] is False

        session.refresh_from_db()
        assert session.question_bias_vector == original_bias, (
            'question_bias_vector must not change on skip'
        )

    def test_response_shape_on_answer(self, auth_client, user_profile, monkeypatch):
        """A/B answer returns flush_prefetch=True with next_image + prefetch cards."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        kw_vec = _make_normalized_vec()
        session = _make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        patches = _base_patches(pool_ids, kw_vec=kw_vec)
        patchers = _apply_patches(patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refine',
                    'axis': 'style',
                    'keyword': 'minimal',
                    'selected_option': 'A',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['flush_prefetch'] is True
        assert 'next_image' in data
        assert 'prefetch_image' in data
        assert 'prefetch_image_2' in data
        assert 'progress' in data

    def test_cooldown_reset_after_answer(self, auth_client, user_profile, monkeypatch):
        """After A/B answer, question_cooldown is set to question_cooldown_swipes."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)

        kw_vec = _make_normalized_vec()
        session = _make_analyzing_session(user_profile)
        pool_ids = session.pool_ids

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [(pool_ids[0],)]
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        patches = _base_patches(pool_ids, kw_vec=kw_vec)
        patchers = _apply_patches(patches)
        conn_patcher = patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn
        )
        conn_patcher.start()
        patchers.append(conn_patcher)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/question-responses/',
                {
                    'question_type': 'refine',
                    'axis': 'style',
                    'keyword': 'minimal',
                    'selected_option': 'A',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.question_cooldown == 15, (
            f'Expected question_cooldown=15 after answer, got {session.question_cooldown}'
        )
        assert session.q_card_consecutive_dislikes == 0
