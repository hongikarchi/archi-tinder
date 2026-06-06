"""
test_qcard_phase3.py -- ALGO-QCARD Phase 3: swipe-latency capture +
hyper-positive Trigger A (fast + mostly-like detection).

Covers:
  - handle_swipe_normal stores latency: latency_ms appended and capped.
  - Invalid / absent / absurd latency_ms values are silently ignored.
  - _check_question_trigger hyper-positive Trigger A:
      - fires when last-10 actions >= 8 likes AND avg latency < 1500.
      - does NOT fire when avg latency >= 1500.
      - does NOT fire when likes < 8.
      - does NOT fire when latency sample count below threshold.
      - does NOT fire when cooldown > 0 / question_count >= max.
      - does NOT fire when tag_axis_counts is empty (no keyword available).
      - payload is a refine trigger with a non-null keyword.

Threading note (TestLatencyCapture):
  SwipeView spawns two background threads (_async_prefetch_thread and
  _emit_telemetry_thread) both of which call connections.close_all() in
  their finally blocks.  That closes the shared test DB connection and
  causes InterfaceError on subsequent ORM calls (e.g. session.refresh_from_db).
  Fix: patch 'apps.recommendation.views.threading.Thread' with _NoopThread
  (imported from test_imp8_async_prefetch) so threads are constructed but
  never executed.  The latency value is written inside handle_swipe_normal
  (main request thread) so assertions on recent_latencies still exercise
  the real production path.
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project, AnalysisSession

# _NoopThread: non-executing threading.Thread shim.  Prevents background
# threads from calling connections.close_all() on the test DB connection.
# Imported from the test that first introduced this pattern (IMP-8 prefetch).
from tests.test_imp8_async_prefetch import _NoopThread  # noqa: F401


# ---------------------------------------------------------------------------
# Shared helpers (mirror phase1/phase2 conventions)
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    _v = _FAKE_EMBEDDINGS[bid]
    _norm = np.linalg.norm(_v)
    if _norm > 0:
        _FAKE_EMBEDDINGS[bid] = _v / _norm

_SERVICE_ENGINE = 'apps.recommendation.services.swipe_service.engine'
_VIEW_ENGINE = 'apps.recommendation.views.engine'


def _mock_buildings_by_ids(ids):
    """Minimal get_buildings_by_ids mock: returns a bare card dict for each id."""
    return [_make_card(bid) for bid in (ids or []) if bid is not None]


def _make_normalized_vec(seed=55):
    v = np.random.RandomState(seed).randn(384).astype(np.float64)
    return v / np.linalg.norm(v)


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


def _make_session(user_profile, question_count=0, question_cooldown=0,
                  tag_axis_counts=None, recent_latencies=None):
    """Create a minimal Project + AnalysisSession for testing."""
    project = Project.objects.create(user=user_profile, name='Phase3 Test', filters={})
    fake_vec = list(_make_normalized_vec())
    if tag_axis_counts is None:
        tag_axis_counts = {'style': {'minimal': 5}}
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
        tag_axis_counts=tag_axis_counts,
        recent_like_tag_sets=[],
        question_cooldown=question_cooldown,
        q_card_consecutive_dislikes=0,
        question_count=question_count,
        question_bias_vector=None,
        recent_latencies=list(recent_latencies) if recent_latencies else [],
    )
    return session


# ---------------------------------------------------------------------------
# Unit tests: _check_question_trigger hyper-positive (Trigger A)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHyperpositiveTrigger:
    """_check_question_trigger fires / does not fire based on Phase 3 conditions."""

    def _session_with_latencies(self, user_profile, latencies, like_count=8, window=10):
        """Build a session where the last `window` recent swipes contain `like_count`
        likes (padded with dislikes), and recent_latencies = latencies."""
        session = _make_session(
            user_profile,
            question_count=0,
            question_cooldown=0,
            tag_axis_counts={'style': {'niche': 4, 'rare': 2}},
            recent_latencies=latencies,
        )
        return session

    def test_fires_when_fast_and_high_likes(self, user_profile, monkeypatch):
        """Trigger A fires: 8+ likes in window + avg latency < 1500ms."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        # 5 samples well below 1500ms → avg = 800ms
        latencies = [800.0] * 5
        session = self._session_with_latencies(user_profile, latencies)

        # Mock _recent_actions to return 8 likes + 2 dislikes in last 10
        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 100, 'style': {'niche': 5, 'rare': 10}}):
            result = svc._check_question_trigger(session, 'like')

        assert result is not None, 'Expected trigger to fire, got None'
        assert result['type'] == 'refine'
        assert result['keyword'] is not None, 'Hyper-positive trigger must carry a keyword'

    def test_does_not_fire_when_latency_too_slow(self, user_profile, monkeypatch):
        """Trigger A does NOT fire when avg latency >= 1500ms."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        # avg = 3000ms → above threshold
        latencies = [3000.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        # Clear existing tags so existing refine conditions A/B cannot fire
        session.tag_axis_counts = {'style': {'niche': 1}}
        session.recent_like_tag_sets = []

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 100, 'style': {'niche': 5}}):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when avg latency >= 1500ms, got: {result}'
        )

    def test_does_not_fire_when_likes_below_min(self, user_profile, monkeypatch):
        """Trigger A does NOT fire when like count < min_likes (8)."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        latencies = [500.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        # Clear so existing refine A/B cannot fire
        session.tag_axis_counts = {'style': {'niche': 1}}
        session.recent_like_tag_sets = []

        # Only 7 likes — below the min of 8
        recent_10 = ['like'] * 7 + ['dislike'] * 3
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 100, 'style': {'niche': 5}}):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when like count < 8, got: {result}'
        )

    def test_does_not_fire_when_latency_samples_too_few(self, user_profile, monkeypatch):
        """Trigger A does NOT fire when latency sample count < min_samples (window//2)."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        # Only 2 samples — below window//2 = 5
        latencies = [400.0, 600.0]
        session = self._session_with_latencies(user_profile, latencies)
        # Clear so existing refine A/B cannot fire
        session.tag_axis_counts = {'style': {'niche': 1}}
        session.recent_like_tag_sets = []

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 100, 'style': {'niche': 5}}):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when latency sample count too few, got: {result}'
        )

    def test_does_not_fire_when_cooldown_active(self, user_profile, monkeypatch):
        """Trigger A does NOT fire when question_cooldown > 0."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        latencies = [300.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        session.question_cooldown = 5  # active cooldown

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when cooldown > 0, got: {result}'
        )

    def test_does_not_fire_when_question_count_at_cap(self, user_profile, monkeypatch):
        """Trigger A does NOT fire when question_count >= question_max_per_session."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        latencies = [300.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        session.question_count = 2  # at cap

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when question_count >= cap, got: {result}'
        )

    def test_does_not_fire_when_tag_axis_counts_empty(self, user_profile, monkeypatch):
        """Trigger A skips gracefully (returns None) when tag_axis_counts is empty."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        latencies = [300.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        session.tag_axis_counts = {}   # empty — no axis data
        session.recent_like_tag_sets = []

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10):
            result = svc._check_question_trigger(session, 'like')

        assert result is None, (
            f'Expected None when tag_axis_counts is empty, got: {result}'
        )

    def test_fires_increments_question_count_and_sets_cooldown(
        self, user_profile, monkeypatch
    ):
        """Firing Trigger A increments question_count and sets question_cooldown."""
        from django.conf import settings
        from apps.recommendation.services import swipe_service as svc

        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_window', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_hyperpositive_min_likes', 8)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_fast_swipe_ms', 1500)
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_cooldown_swipes', 15)
        monkeypatch.setitem(settings.RECOMMENDATION, 'question_max_per_session', 2)

        latencies = [600.0] * 5
        session = self._session_with_latencies(user_profile, latencies)
        # Use tag state that avoids refine A/B (no intersection, no 70% tag)
        session.tag_axis_counts = {'style': {'niche': 1, 'rare': 1}}
        session.recent_like_tag_sets = []
        assert session.question_count == 0

        recent_10 = ['like'] * 8 + ['dislike'] * 2
        with patch('apps.recommendation.services.swipe_service._recent_actions',
                   return_value=recent_10), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 100, 'style': {'niche': 5, 'rare': 8}}):
            result = svc._check_question_trigger(session, 'like')

        assert result is not None
        assert session.question_count == 1, (
            f'Expected question_count=1 after trigger, got {session.question_count}'
        )
        assert session.question_cooldown == 15, (
            f'Expected question_cooldown=15, got {session.question_cooldown}'
        )


# ---------------------------------------------------------------------------
# Unit tests: latency capture in handle_swipe_normal
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLatencyCapture:
    """handle_swipe_normal stores latency_ms into session.recent_latencies."""

    def _minimal_swipe_mocks(self, session):
        """Return a dict of all patches needed to run handle_swipe_normal
        without hitting real buildings DB or engine compute paths."""
        fake_vec = list(_make_normalized_vec())

        def _fake_emb(bid):
            return fake_vec

        def _fake_pool_embs(ids):
            return {bid: np.array(fake_vec) for bid in ids}

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # is_publishable check returns a row (building found)
        mock_cursor.fetchone.return_value = (1,)
        # tag fetch returns (None, None, None) — no tag update
        mock_cursor.fetchone.side_effect = [(1,), None]
        mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

        return {
            'conn': mock_conn,
            'fake_emb': _fake_emb,
            'fake_pool_embs': _fake_pool_embs,
        }

    def _run_swipe(self, auth_client, session, latency_ms=None):
        """POST a swipe via the HTTP endpoint (goes through handle_swipe_normal)."""
        body = {
            'canonical_bld_id': session.pool_ids[0],
            'action': 'like',
            'idempotency_key': f'test-lat-{id(session)}-{latency_ms}',
        }
        if latency_ms is not None:
            body['latency_ms'] = latency_ms
        return auth_client.post(
            f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
            body,
            format='json',
        )

    def test_valid_latency_appended(self, auth_client, user_profile, monkeypatch):
        """Posting latency_ms=900 appends 900.0 to session.recent_latencies."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)

        session = _make_session(user_profile, recent_latencies=[])
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms=900)

        assert resp.status_code == 200, (
            f'Expected 200, got {resp.status_code}: {resp.json()}'
        )
        session.refresh_from_db()
        assert 900.0 in session.recent_latencies, (
            f'Expected 900.0 in recent_latencies, got: {session.recent_latencies}'
        )

    def test_absent_latency_no_append(self, auth_client, user_profile, monkeypatch):
        """Not sending latency_ms leaves recent_latencies unchanged."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)

        session = _make_session(user_profile, recent_latencies=[])
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms=None)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.recent_latencies == [], (
            f'Expected empty recent_latencies, got: {session.recent_latencies}'
        )

    def test_invalid_latency_string_ignored(self, auth_client, user_profile, monkeypatch):
        """latency_ms='not-a-number' is silently ignored, no error."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)

        session = _make_session(user_profile, recent_latencies=[])
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms='not-a-number')

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.recent_latencies == [], (
            f'Expected empty recent_latencies after invalid string, got: {session.recent_latencies}'
        )

    def test_absurd_positive_latency_ignored(self, auth_client, user_profile, monkeypatch):
        """latency_ms > 120000 (>2 min) is ignored as an absurd value."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)

        session = _make_session(user_profile, recent_latencies=[])
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms=999999)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.recent_latencies == [], (
            f'Expected empty recent_latencies for absurd latency, got: {session.recent_latencies}'
        )

    def test_non_positive_latency_ignored(self, auth_client, user_profile, monkeypatch):
        """latency_ms <= 0 is ignored."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 10)

        session = _make_session(user_profile, recent_latencies=[])
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms=-100)

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.recent_latencies == [], (
            f'Expected empty recent_latencies for non-positive latency, got: {session.recent_latencies}'
        )

    def test_latency_list_capped_at_recent_latencies_cap(
        self, auth_client, user_profile, monkeypatch
    ):
        """When list exceeds cap, oldest entries are dropped."""
        from django.conf import settings
        monkeypatch.setitem(settings.RECOMMENDATION, 'recent_latencies_cap', 3)

        # Start with a full window of 3
        initial_latencies = [1000.0, 1100.0, 1200.0]
        session = _make_session(user_profile, recent_latencies=initial_latencies)
        mocks = self._minimal_swipe_mocks(session)

        with patch('apps.recommendation.services.swipe_service.connections', mocks['conn']), \
             patch(f'{_SERVICE_ENGINE}.get_building_embedding',
                   side_effect=mocks['fake_emb']), \
             patch(f'{_SERVICE_ENGINE}.get_pool_embeddings',
                   side_effect=mocks['fake_pool_embs']), \
             patch(f'{_SERVICE_ENGINE}.update_preference_vector',
                   return_value=[0.1] * 384), \
             patch(f'{_SERVICE_ENGINE}.compute_taste_centroids',
                   return_value=([None], np.array([0.1] * 384))), \
             patch(f'{_SERVICE_ENGINE}.compute_convergence', return_value=0.05), \
             patch(f'{_SERVICE_ENGINE}.check_convergence', return_value=False), \
             patch(f'{_SERVICE_ENGINE}.refresh_pool_if_low'), \
             patch(f'{_SERVICE_ENGINE}.compute_mmr_next',
                   return_value=session.pool_ids[1]), \
             patch(f'{_SERVICE_ENGINE}.get_last_embedding_call_stats',
                   return_value={'cache_misses': 0}), \
             patch('apps.recommendation.services.swipe_service.get_corpus_tag_df',
                   return_value={'_total': 0}), \
             patch(f'{_VIEW_ENGINE}.get_buildings_by_ids',
                   side_effect=_mock_buildings_by_ids), \
             patch('apps.recommendation.views.threading.Thread',
                   side_effect=lambda *a, **kw: _NoopThread(*a, **kw)):
            resp = self._run_swipe(auth_client, session, latency_ms=500)

        assert resp.status_code == 200
        session.refresh_from_db()
        lats = session.recent_latencies
        assert len(lats) == 3, f'Expected cap=3, got len={len(lats)}: {lats}'
        # Oldest (1000.0) was evicted; newest (500.0) appended
        assert 500.0 in lats, f'Expected 500.0 in capped list, got: {lats}'
        assert 1000.0 not in lats, f'Expected 1000.0 evicted, still in: {lats}'
