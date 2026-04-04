"""
test_sessions.py -- Swipe session lifecycle integration tests.

All engine.py functions that perform raw SQL against architecture_vectors
are mocked, since that table is owned by Make DB and not available in
the SQLite test database.
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from apps.recommendation.models import Project, AnalysisSession, SwipeEvent


# -- Helpers -----------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]  # B00001..B00015
_FAKE_SCORES = {bid: 15 - i for i, bid in enumerate(_FAKE_POOL)}
_FAKE_EMBEDDINGS = {bid: np.random.RandomState(i).randn(384).astype(np.float64) for i, bid in enumerate(_FAKE_POOL)}

# Normalize fake embeddings
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm


def _make_card(bid):
    """Create a fake building card dict."""
    return {
        'building_id': bid,
        'name_en': f'Building {bid}',
        'project_name': f'Project {bid}',
        'image_url': f'https://example.com/{bid}/photo.jpg',
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Housing',
            'axis_architects': 'Test Architect',
            'axis_country': 'Korea',
            'axis_area_m2': 100.0,
            'axis_year': 2020,
            'axis_style': 'Contemporary',
            'axis_atmosphere': 'calm',
            'axis_color_tone': 'Cool White',
            'axis_material': 'concrete',
            'axis_material_visual': [],
            'axis_tags': [],
        },
    }


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    """Return first pool_id not in exposed_ids."""
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_get_card(bid):
    """Return fake card or None."""
    if bid is None:
        return None
    return _make_card(bid)


def _mock_get_embedding(bid):
    """Return fake 384-dim embedding as list."""
    if bid in _FAKE_EMBEDDINGS:
        return _FAKE_EMBEDDINGS[bid].tolist()
    return list(np.random.randn(384))


def _mock_update_pref(pref_vector, embedding, action):
    """Return a fake preference vector."""
    return list(np.random.RandomState(42).randn(384))


def _mock_compute_centroids(like_vectors, round_num):
    """Return fake centroids."""
    c = np.random.RandomState(42).randn(384)
    c = c / np.linalg.norm(c)
    return ([c], c)


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num):
    """Return first available building_id."""
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_build_action_card():
    """Return action card dict."""
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
        'action_card_message': 'We\'ve analyzed your preferences.',
        'action_card_subtitle': 'Swipe right to see results.',
    }


# Shared patch decorator for engine functions used in session creation
_ENGINE = 'apps.recommendation.views.engine'

_SESSION_PATCHES = {
    f'{_ENGINE}.create_bounded_pool': lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES)),
    f'{_ENGINE}.get_pool_embeddings': lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids},
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': _mock_get_card,
    f'{_ENGINE}.get_building_embedding': _mock_get_embedding,
    f'{_ENGINE}.update_preference_vector': _mock_update_pref,
    f'{_ENGINE}.compute_taste_centroids': _mock_compute_centroids,
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a: False,
    f'{_ENGINE}.build_action_card': _mock_build_action_card,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
}


def _apply_patches():
    """Return a list of started mock patchers."""
    patchers = []
    for target, side_effect in _SESSION_PATCHES.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    """Stop all patchers."""
    for p in patchers:
        p.stop()


# -- Tests -------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionCreation:

    def test_create_session_returns_next_image(self, auth_client, user_profile):
        """POST /analysis/sessions/ creates a session with next_image."""
        project = Project.objects.create(
            user=user_profile, name='Test Project', filters={},
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
        data = resp.json()
        assert 'session_id' in data
        assert data['next_image'] is not None
        assert data['next_image']['building_id'] in _FAKE_POOL
        assert 'progress' in data
        assert data['progress']['phase'] == 'exploring'

    def test_create_session_with_no_project_creates_one(self, auth_client, user_profile):
        """If project_id is not found, a new project is auto-created."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'filters': {'program': 'Museum'}},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        data = resp.json()
        assert 'project_id' in data
        # Project was created
        assert Project.objects.filter(project_id=data['project_id']).exists()


@pytest.mark.django_db
class TestSwipeRecording:

    def _create_session(self, auth_client, user_profile):
        """Helper: create a project + session, return (project, session_id)."""
        project = Project.objects.create(
            user=user_profile, name='Swipe Test', filters={},
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
        return project, resp.json()['session_id']

    def test_record_swipe_like(self, auth_client, user_profile):
        """Record a like swipe, get next_image back."""
        project, session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'test_swipe_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        data = resp.json()
        assert data['accepted'] is True
        assert 'progress' in data

    def test_record_swipe_dislike(self, auth_client, user_profile):
        """Record a dislike swipe."""
        project, session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'dislike',
                    'idempotency_key': 'test_swipe_dislike_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        assert resp.json()['accepted'] is True

    def test_idempotent_swipe(self, auth_client, user_profile):
        """Same idempotency_key returns duplicate without re-processing."""
        project, session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            # First swipe
            resp1 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'idem_key_123',
                },
                format='json',
            )
            assert resp1.status_code == 200

            # Duplicate swipe with same key
            resp2 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'idem_key_123',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp2.status_code == 200
        assert resp2.json()['detail'] == 'duplicate'

    def test_invalid_action_rejected(self, auth_client, user_profile):
        """Invalid action value returns 400."""
        project, session_id = self._create_session(auth_client, user_profile)

        resp = auth_client.post(
            f'/api/v1/analysis/sessions/{session_id}/swipes/',
            {
                'building_id': 'B00001',
                'action': 'superlike',
                'idempotency_key': 'test_invalid_action',
            },
            format='json',
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPhaseTransitions:

    def test_exploring_to_analyzing(self, auth_client, user_profile):
        """After min_likes_for_clustering likes, phase becomes analyzing."""
        project = Project.objects.create(
            user=user_profile, name='Phase Test', filters={},
        )

        patchers = _apply_patches()
        try:
            # Create session
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
            session_id = resp.json()['session_id']

            # Record 3 likes (min_likes_for_clustering = 3)
            last_resp = None
            for i in range(3):
                last_resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session_id}/swipes/',
                    {
                        'building_id': f'B{str(i+1).zfill(5)}',
                        'action': 'like',
                        'idempotency_key': f'phase_test_like_{i}',
                    },
                    format='json',
                )
        finally:
            _stop_patches(patchers)

        assert last_resp.status_code == 200
        # After 3 likes, phase should be 'analyzing'
        assert last_resp.json()['progress']['phase'] == 'analyzing'

    def test_analyzing_to_converged(self, auth_client, user_profile):
        """When check_convergence returns True, phase becomes converged."""
        project = Project.objects.create(
            user=user_profile, name='Converge Test', filters={},
        )

        # Override check_convergence to return True after some swipes
        call_count = [0]

        def mock_check_convergence_dynamic(*args):
            call_count[0] += 1
            return call_count[0] >= 2  # converge after 2 checks

        custom_patches = dict(_SESSION_PATCHES)
        custom_patches[f'{_ENGINE}.check_convergence'] = mock_check_convergence_dynamic

        patchers = []
        for target, side_effect in custom_patches.items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
            session_id = resp.json()['session_id']

            # Record enough likes to enter analyzing, then converge
            last_resp = None
            for i in range(6):
                last_resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session_id}/swipes/',
                    {
                        'building_id': f'B{str(i+1).zfill(5)}',
                        'action': 'like',
                        'idempotency_key': f'converge_test_{i}',
                    },
                    format='json',
                )
                if last_resp.json().get('progress', {}).get('phase') == 'converged':
                    break
        finally:
            for p in patchers:
                p.stop()

        assert last_resp.json()['progress']['phase'] == 'converged'
