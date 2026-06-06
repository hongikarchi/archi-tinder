"""
test_swipe.py -- Codex audit finding #1.2 + #1.3 regression tests.

Tests:
  - #1.2(a): duplicate swipe returns full payload shape (not minimal {accepted, detail})
  - #1.2(b): IntegrityError on SwipeEvent.create returns idempotent 200 (not 500)
  - #1.3: duplicate like yields single project entry (dedup guard holds)
"""
import pytest
import numpy as np
from unittest.mock import patch
from django.db import IntegrityError

from apps.recommendation.models import Project


# ---------------------------------------------------------------------------
# Shared test infrastructure (mirrors test_sessions.py)
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]  # B00001..B00015
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


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_get_card(bid, image_focus=None):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'image_url': f'https://example.com/{bid}/photo.jpg',
        'covers_by_type': {},
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Housing',
            'axis_architects': 'Test Architect',
            'axis_country': 'Korea',
            'axis_city': None,
            'axis_year': 2020,
            'axis_style': 'Contemporary',
            'axis_atmosphere': 'calm',
            'axis_color_tone': 'Cool White',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


def _mock_get_embedding(bid):
    if bid in _FAKE_EMBEDDINGS:
        return _FAKE_EMBEDDINGS[bid].tolist()
    return list(np.random.randn(384))


def _mock_update_pref(pref_vector, embedding, action):
    return list(np.random.RandomState(42).randn(384))


def _mock_compute_centroids(like_vectors, round_num, multimodal_floor=None):
    c = np.random.RandomState(42).randn(384)
    c = c / np.linalg.norm(c)
    return ([c], c)


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num, **kwargs):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


_ENGINE = 'apps.recommendation.views.engine'
_SWIPE_VIEW = 'apps.recommendation.views.swipe'


class _SyncThread:
    """Run telemetry synchronously while suppressing async prefetch in tests."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **kw):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if getattr(self._target, '__name__', '') == '_async_prefetch_thread':
            return
        if self._target:
            self._target(*self._args, **self._kwargs)


def _sync_emit_telemetry(swipe_kwargs, confidence_kwargs):
    from apps.recommendation import event_log
    event_log.emit_swipe_event(**swipe_kwargs)
    if confidence_kwargs is not None:
        event_log.emit_event('confidence_update', **confidence_kwargs)


_SESSION_PATCHES = {
    f'{_ENGINE}.create_bounded_pool': lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES)),
    f'{_ENGINE}.get_pool_embeddings': (
        lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}
    ),
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': _mock_get_card,
    f'{_ENGINE}.get_building_embedding': _mock_get_embedding,
    f'{_ENGINE}.update_preference_vector': _mock_update_pref,
    f'{_ENGINE}.compute_taste_centroids': _mock_compute_centroids,
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a: False,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
    f'{_SWIPE_VIEW}.threading.Thread': _SyncThread,
    f'{_SWIPE_VIEW}._emit_telemetry_thread': _sync_emit_telemetry,
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
# Helpers
# ---------------------------------------------------------------------------

def _create_session(auth_client, user_profile, name='Swipe Fix Test'):
    """Create a Project + AnalysisSession via the API. Return (project, session_id)."""
    project = Project.objects.create(user=user_profile, name=name, filters={})
    patchers = _apply_patches()
    try:
        resp = auth_client.post(
            '/api/v1/analysis/sessions/',
            {'project_id': str(project.project_id), 'filters': {}},
            format='json',
        )
    finally:
        _stop_patches(patchers)
    assert resp.status_code == 201, f'Session create failed: {resp.json()}'
    return project, resp.json()['session_id']


_FULL_PAYLOAD_KEYS = {
    'accepted', 'session_status', 'progress', 'next_image',
    'is_analysis_completed', 'can_continue',
}


# ---------------------------------------------------------------------------
# Tests: Codex finding #1.2 — swipe idempotency response shape + race window
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwipeIdempotencyResponseShape:
    """Finding #1.2(a): duplicate swipe must return full payload, not minimal {accepted, detail}."""

    def test_duplicate_swipe_returns_full_payload_shape(self, auth_client, user_profile):
        """Second POST with same idempotency_key returns full response shape."""
        project, session_id = _create_session(auth_client, user_profile)

        payload = {
            'canonical_bld_id': 'B00001',
            'action': 'like',
            'idempotency_key': 'idem_full_shape_1',
        }

        patchers = _apply_patches()
        try:
            resp1 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
            assert resp1.status_code == 200

            resp2 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp2.status_code == 200
        data = resp2.json()
        # Must carry full state-machine fields
        missing = _FULL_PAYLOAD_KEYS - set(data.keys())
        assert not missing, (
            f'Duplicate swipe response missing keys: {missing}. '
            f'Got: {set(data.keys())}'
        )
        # Must still signal duplicate
        assert data.get('detail') == 'duplicate'
        assert data['accepted'] is True
        # progress sub-object must have required keys
        progress = data.get('progress', {})
        for key in ('current_round', 'like_count', 'phase', 'pool_remaining'):
            assert key in progress, f'progress missing key: {key}'

    def test_duplicate_swipe_status_200(self, auth_client, user_profile):
        """Duplicate swipe returns HTTP 200, not 4xx."""
        project, session_id = _create_session(auth_client, user_profile, 'Dup Status Test')

        payload = {
            'canonical_bld_id': 'B00002',
            'action': 'dislike',
            'idempotency_key': 'idem_status_200_1',
        }

        patchers = _apply_patches()
        try:
            auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
            resp2 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp2.status_code == 200


@pytest.mark.django_db
class TestSwipeIntegrityErrorHandler:
    """Finding #1.2(b): IntegrityError on SwipeEvent.create returns 200, not 500."""

    def test_swipe_event_integrity_error_returns_idempotent(self, auth_client, user_profile):
        """Mock SwipeEvent.create to raise IntegrityError once; assert 200 + full shape."""
        project, session_id = _create_session(auth_client, user_profile, 'IntError Test')

        _swipe_view_create = 'apps.recommendation.models.SwipeEvent.objects.create'

        patchers = _apply_patches()
        try:
            with patch(_swipe_view_create, side_effect=IntegrityError('duplicate key')):
                resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session_id}/swipes/',
                    {
                        'canonical_bld_id': 'B00003',
                        'action': 'like',
                        'idempotency_key': 'idem_integrity_err_1',
                    },
                    format='json',
                )
        finally:
            _stop_patches(patchers)

        # Must return 200, not 500
        assert resp.status_code == 200, (
            f'Expected 200 on IntegrityError, got {resp.status_code}: {resp.json()}'
        )
        data = resp.json()
        # Must return full idempotent payload
        missing = _FULL_PAYLOAD_KEYS - set(data.keys())
        assert not missing, (
            f'IntegrityError response missing keys: {missing}. Got: {set(data.keys())}'
        )
        assert data['accepted'] is True
        assert data.get('detail') == 'duplicate'


# ---------------------------------------------------------------------------
# Tests: Codex finding #1.3 — duplicate like yields single project entry
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDuplicateLikeDedup:
    """Finding #1.3 + #1.2 combined: duplicate like must not double-append to liked_ids."""

    def test_duplicate_like_yields_single_project_entry(self, auth_client, user_profile):
        """POST same like twice (same idempotency_key) -> liked_ids has exactly 1 entry."""
        project, session_id = _create_session(auth_client, user_profile, 'Dup Like Test')

        payload = {
            'canonical_bld_id': 'B00004',
            'action': 'like',
            'idempotency_key': 'idem_dup_like_1',
        }

        patchers = _apply_patches()
        try:
            resp1 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
            assert resp1.status_code == 200

            resp2 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                payload,
                format='json',
            )
            assert resp2.status_code == 200
        finally:
            _stop_patches(patchers)

        project.refresh_from_db()
        liked_ids_for_bid = [
            entry for entry in project.liked_ids
            if (isinstance(entry, dict) and entry.get('id') == 'B00004')
            or entry == 'B00004'
        ]
        assert len(liked_ids_for_bid) == 1, (
            f'Expected exactly 1 liked_ids entry for B00004, '
            f'got {len(liked_ids_for_bid)}: {project.liked_ids}'
        )

    def test_first_swipe_like_not_tagged_duplicate(self, auth_client, user_profile):
        """First (unique) like must NOT have detail=duplicate in response."""
        project, session_id = _create_session(auth_client, user_profile, 'First Like Test')

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'canonical_bld_id': 'B00005',
                    'action': 'like',
                    'idempotency_key': 'idem_first_like_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        assert data.get('detail') != 'duplicate'
        # Full payload without duplicate tag
        assert 'progress' in data
