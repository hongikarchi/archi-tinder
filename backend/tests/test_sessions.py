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


@pytest.mark.django_db
class TestConvergenceSignalIntegrity:
    """Topic 10 Option A: unconditional convergence signal-integrity fixes.

    Covers two structural bugs in the analyzing-phase Delta-V pipeline:

    Bug 1 -- on exploring -> analyzing, `convergence_history` and
    `previous_pref_vector` must be cleared. Previously the first analyzing
    Delta-V was a cross-metric `||centroid - pref_vector||` (apples to
    oranges: K-Means centroid vs exploring preference vector).

    Bug 2 -- Delta-V append during analyzing was gated by `action == 'like'`,
    so `convergence_window` silently counted likes instead of rounds. After
    the fix, every analyzing swipe (like or dislike) appends one Delta-V
    entry (guarded only by `session.like_vectors` non-empty, since clustering
    needs at least one like).

    See research/spec/requirements.md Section 11 Tier A Topic 10 (binding)
    and research/search/10-convergence-detection.md Option A (reasoning).
    """

    def test_phase_transition_resets_convergence_state(self, auth_client, user_profile):
        """Bug 1: after 3 likes trigger exploring -> analyzing, convergence_history
        and previous_pref_vector must be cleared to the empty list.

        Pre-fix: after 3 exploring likes, convergence_history accumulates 2 entries
        (swipes 2 and 3; swipe 1 sets previous_pref_vector for the first time) and
        previous_pref_vector holds a 384-dim exploring-phase pref_vector. The 4th
        swipe (first analyzing) would then compute a cross-metric Delta-V.

        Post-fix: on the transition, both fields are reset to [], so the first
        analyzing swipe has no previous centroid to compare against yet -- Delta-V
        is deferred to the second analyzing swipe, which is the correct physical
        semantics (centroid vs centroid).
        """
        project = Project.objects.create(
            user=user_profile, name='Convergence Reset Test', filters={},
        )

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
            session_id = resp.json()['session_id']

            # 3 likes = min_likes_for_clustering -> exploring to analyzing
            for i in range(3):
                auth_client.post(
                    f'/api/v1/analysis/sessions/{session_id}/swipes/',
                    {
                        'building_id': f'B{str(i+1).zfill(5)}',
                        'action': 'like',
                        'idempotency_key': f'conv_reset_like_{i}',
                    },
                    format='json',
                )
        finally:
            _stop_patches(patchers)

        session = AnalysisSession.objects.get(session_id=session_id)
        assert session.phase == 'analyzing'
        assert session.convergence_history == [], (
            f'convergence_history should be cleared on phase transition, '
            f'got {session.convergence_history!r}'
        )
        assert session.previous_pref_vector == [], (
            f'previous_pref_vector should be cleared on phase transition, '
            f'got len={len(session.previous_pref_vector)}'
        )

    def test_analyzing_dislike_appends_delta_v(self, auth_client, user_profile):
        """Bug 2: in analyzing phase, a dislike swipe must append exactly one
        entry to convergence_history.

        Pre-fix: the `action == 'like'` gate blocked the append entirely on
        dislikes, so convergence_window=3 counted likes, not rounds.

        Setup: directly seed an analyzing-phase session with
        like_vectors=[{...}] (clustering needs >=1 like), previous_pref_vector
        as a valid 384-dim centroid from a prior round, and convergence_history=[].
        Post one dislike. The mocked compute_convergence returns 0.05, so after
        the fix we expect convergence_history == [0.05].
        """
        project = Project.objects.create(
            user=user_profile, name='Dislike Delta-V Test', filters={},
        )

        # Seed an analyzing-phase session directly (avoids driving the full
        # exploring -> analyzing transition, which adds dependency on swipe order).
        prev_centroid = (np.random.RandomState(7).randn(384)).tolist()
        seed_like_embedding = _FAKE_EMBEDDINGS['B00001'].tolist()
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='analyzing',
            status='active',
            pool_ids=list(_FAKE_POOL),
            pool_scores=dict(_FAKE_SCORES),
            exposed_ids=['B00001'],  # already-seen seed-like card
            initial_batch=list(_FAKE_POOL[:5]),
            like_vectors=[{'embedding': seed_like_embedding, 'round': 0}],
            convergence_history=[],
            previous_pref_vector=prev_centroid,
            current_round=1,
        )

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {
                    'building_id': 'B00002',
                    'action': 'dislike',
                    'idempotency_key': 'analyzing_dislike_delta_v',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200

        session.refresh_from_db()
        # Post-fix: dislike during analyzing appends exactly one Delta-V entry
        # (the mock returns 0.05). Pre-fix: history remained empty due to the
        # action == 'like' gate.
        assert len(session.convergence_history) == 1, (
            f'analyzing-phase dislike should append exactly 1 Delta-V entry, '
            f'got {session.convergence_history!r}'
        )
        assert session.convergence_history[0] == 0.05


@pytest.mark.django_db
class TestClientBufferMerge:
    """Verify client_buffer_ids merges into exposed_ids, preventing queue drift."""

    def _create_session(self, auth_client, user_profile):
        """Helper: create a project + session, return session_id."""
        project = Project.objects.create(
            user=user_profile, name='Buffer Test', filters={},
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
        return resp.json()['session_id']

    def test_client_buffer_ids_merged_into_exposed(self, auth_client, user_profile):
        """client_buffer_ids must be added to exposed_ids so subsequent selections skip them."""
        session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'buffer_test_1',
                    'client_buffer_ids': ['B00002', 'B00003'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200

        # Verify exposed_ids includes all buffered cards
        session = AnalysisSession.objects.get(session_id=session_id)
        assert 'B00002' in session.exposed_ids
        assert 'B00003' in session.exposed_ids

    def test_invalid_buffer_ids_ignored(self, auth_client, user_profile):
        """Non-list or invalid entries in client_buffer_ids must be ignored safely."""
        session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'buffer_invalid_1',
                    'client_buffer_ids': 'not a list',  # invalid shape
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200

    def test_action_card_marker_filtered_from_buffer(self, auth_client, user_profile):
        """__action_card__ entries must NOT be added to exposed_ids."""
        session_id = self._create_session(auth_client, user_profile)

        patchers = _apply_patches()
        try:
            auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'buffer_action_1',
                    'client_buffer_ids': ['B00002', '__action_card__', 'B00003'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        session = AnalysisSession.objects.get(session_id=session_id)
        assert '__action_card__' not in session.exposed_ids
        assert 'B00002' in session.exposed_ids
        assert 'B00003' in session.exposed_ids


@pytest.mark.django_db
class TestSessionStateResume:
    """Verify SessionStateView returns current session state without creating a new one."""

    def test_resume_returns_current_state(self, auth_client, user_profile):
        """GET /analysis/sessions/<id>/state/ returns the current card and progress."""
        project = Project.objects.create(
            user=user_profile, name='Resume Test', filters={},
        )

        patchers = _apply_patches()
        try:
            # Create a session and swipe a few cards
            create_resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
            session_id = create_resp.json()['session_id']
            original_round = create_resp.json()['progress']['current_round']

            # Swipe 2 cards
            auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {'building_id': 'B00001', 'action': 'like', 'idempotency_key': 'resume_1'},
                format='json',
            )
            auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {'building_id': 'B00002', 'action': 'dislike', 'idempotency_key': 'resume_2'},
                format='json',
            )

            # Call the resume endpoint
            resume_resp = auth_client.get(
                f'/api/v1/analysis/sessions/{session_id}/state/',
            )
        finally:
            _stop_patches(patchers)

        assert resume_resp.status_code == 200
        data = resume_resp.json()
        assert data['session_id'] == session_id
        assert data['next_image'] is not None
        # Progress should reflect the 2 completed swipes, not reset to 0
        assert data['progress']['current_round'] == original_round + 2
        assert data['progress']['like_count'] == 1
        assert data['progress']['dislike_count'] == 1
        # No new session created
        assert AnalysisSession.objects.filter(project=project).count() == 1

    def test_resume_404_for_missing_session(self, auth_client, user_profile):
        """Resume endpoint returns 404 for a non-existent session."""
        import uuid
        fake_id = uuid.uuid4()
        resp = auth_client.get(f'/api/v1/analysis/sessions/{fake_id}/state/')
        assert resp.status_code == 404

    def test_resume_completed_session_returns_analysis_completed(self, auth_client, user_profile):
        """Resuming a completed session returns is_analysis_completed=True."""
        project = Project.objects.create(
            user=user_profile, name='Completed Test', filters={},
        )
        session = AnalysisSession.objects.create(
            user=user_profile, project=project,
            phase='completed', status='completed',
            pool_ids=['B00001'], pool_scores={}, exposed_ids=['B00001'],
            initial_batch=['B00001'], like_vectors=[], convergence_history=[],
        )

        resp = auth_client.get(f'/api/v1/analysis/sessions/{session.session_id}/state/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['is_analysis_completed'] is True
        assert data['next_image'] is None


class TestPoolScoreNormalization:
    """Topic 12: `_build_score_cases` / `create_bounded_pool` normalize to [0,1]."""

    def test_build_score_cases_returns_total_weight(self):
        """`_build_score_cases` reports the sum of weights for branches that fired."""
        from apps.recommendation import engine

        # 3 priority entries, but only 2 filters actively set.
        filters = {'program': 'Museum', 'style': 'Brutalist'}
        weights = {'program': 3, 'style': 2, 'material': 1}

        cases, params, total_weight = engine._build_score_cases(filters, weights)

        # Two active branches (program + style); material inactive -> not counted.
        assert len(cases) == 2
        assert total_weight == 5  # 3 (program) + 2 (style)
        # Params interleave: [program_value, style_pattern]
        assert params == ['Museum', '%Brutalist%']

    def test_build_score_cases_returns_zero_when_no_filters_fire(self):
        """Empty filters -> empty cases and zero total_weight."""
        from apps.recommendation import engine

        cases, params, total_weight = engine._build_score_cases({}, {'program': 3})

        assert cases == []
        assert params == []
        assert total_weight == 0


@pytest.mark.django_db
class TestProjectSchemaA3:
    """Sprint 0 A3: liked_ids {id, intensity} shape + saved_ids field."""

    def _create_session(self, auth_client, user_profile, project):
        """Helper: create a session for the given project."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'project_id': str(project.project_id), 'filters': {}},
                format='json',
            )
        finally:
            _stop_patches(patchers)
        return resp.json()['session_id']

    def test_like_writes_intensity_dict(self, auth_client, user_profile):
        """A like swipe appends `{id, intensity: 1.0}` to project.liked_ids (new shape)."""
        project = Project.objects.create(user=user_profile, name='A3 Like Shape Test')
        session_id = self._create_session(auth_client, user_profile, project)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'a3_like_intensity_1',
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        project.refresh_from_db()
        assert len(project.liked_ids) == 1
        assert project.liked_ids[0] == {'id': 'B00001', 'intensity': 1.0}

    def test_like_with_explicit_intensity(self, auth_client, user_profile):
        """Forward-compat: request can carry `intensity` to override 1.0 (Sprint 3 A-1 prep)."""
        project = Project.objects.create(user=user_profile, name='A3 Explicit Intensity Test')
        session_id = self._create_session(auth_client, user_profile, project)

        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'a3_explicit_intensity_1',
                    'intensity': 1.8,
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        project.refresh_from_db()
        assert len(project.liked_ids) == 1
        assert project.liked_ids[0]['intensity'] == 1.8

    def test_intensity_clamped(self, auth_client, user_profile):
        """Out-of-range intensity is clamped to [0, 2], not rejected."""
        project = Project.objects.create(user=user_profile, name='A3 Clamp Test')
        session_id = self._create_session(auth_client, user_profile, project)

        # Test upper clamp: intensity=5.0 -> 2.0
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00001',
                    'action': 'like',
                    'idempotency_key': 'a3_clamp_high',
                    'intensity': 5.0,
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.liked_ids[0]['intensity'] == 2.0

        # Test lower clamp: intensity=-1.0 -> 0.0
        # Use a different building_id to avoid duplicate-like guard
        patchers = _apply_patches()
        try:
            resp2 = auth_client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {
                    'building_id': 'B00002',
                    'action': 'like',
                    'idempotency_key': 'a3_clamp_low',
                    'intensity': -1.0,
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp2.status_code == 200
        project.refresh_from_db()
        low_entry = next((e for e in project.liked_ids if e['id'] == 'B00002'), None)
        assert low_entry is not None
        assert low_entry['intensity'] == 0.0

    def test_liked_id_only_helper_handles_both_shapes(self):
        """Helper extracts ID strings from both legacy list[str] and new list[dict]."""
        from apps.recommendation.views import _liked_id_only
        assert _liked_id_only([]) == []
        assert _liked_id_only(['B1', 'B2']) == ['B1', 'B2']
        assert _liked_id_only([{'id': 'B1', 'intensity': 1.0}, {'id': 'B2', 'intensity': 1.8}]) == ['B1', 'B2']
        assert _liked_id_only([{'id': 'B1', 'intensity': 1.0}, 'B2']) == ['B1', 'B2']  # mixed
        assert _liked_id_only(None) == []  # defensive

    def test_saved_ids_default_empty(self, user_profile):
        """New `saved_ids` field defaults to empty list on project creation."""
        p = Project.objects.create(user=user_profile, name='A3 SavedIds Default Test')
        assert p.saved_ids == []

    def test_saved_ids_serialized_on_response(self, auth_client, user_profile):
        """`saved_ids` field appears in project list/detail responses."""
        Project.objects.create(user=user_profile, name='A3 SavedIds Serialized Test')
        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'results' in data
        assert len(data['results']) >= 1
        project_data = data['results'][0]
        assert 'saved_ids' in project_data
        assert project_data['saved_ids'] == []


class TestFarthestPointFromPool:
    """IMP-1 (spec v1.1 §11.1, investigation 02): max-min correctness + vectorization."""

    def test_selects_max_min_diverse_candidate(self):
        """Regression against pre-fix max-max bug.

        Pool = {X, Y}, exposed = {A, B}. Embeddings crafted so that:
        - X is a near-duplicate of A (cos(X,A)=0.99, cos(X,B)=0.141)
        - Y is equidistant from both (cos(Y,A)=cos(Y,B)=0.5)
        - A and B are orthogonal

        Pre-fix max-max code picks X (X's farthest exposed = B is very far,
        max_distance=1-0.141=0.859). Correct max-min code picks Y (Y's
        nearest exposed has similarity 0.5 < X's nearest 0.99).
        """
        from apps.recommendation import engine

        def unit(v):
            v = np.asarray(v, dtype=float)
            return v / np.linalg.norm(v)

        pool_embeddings = {
            'A': unit([1.0, 0.0, 0.0]),
            'B': unit([0.0, 1.0, 0.0]),                  # orthogonal to A
            'X': unit([0.99, 0.141, 0.0]),               # cos(X,A)=0.99, cos(X,B)=0.141
            'Y': unit([0.5, 0.5, np.sqrt(0.5)]),         # cos(Y,A)=cos(Y,B)=0.5
        }
        result = engine.farthest_point_from_pool(['X', 'Y'], ['A', 'B'], pool_embeddings)
        assert result == 'Y', (
            f"Expected Y (max-min farthest from nearest-exposed); "
            f"got {result} -- indicates max-max bug from pre-fix code"
        )

    def test_returns_none_when_no_unexposed_candidates(self):
        """Pool entirely exposed -> None."""
        from apps.recommendation import engine
        pool_embeddings = {'A': np.array([1.0, 0.0]), 'B': np.array([0.0, 1.0])}
        result = engine.farthest_point_from_pool(['A', 'B'], ['A', 'B'], pool_embeddings)
        assert result is None

    def test_returns_random_candidate_when_no_exposed(self):
        """No anchor -> random candidate (deterministically, one of the candidates)."""
        from apps.recommendation import engine
        pool_embeddings = {'X': np.array([1.0, 0.0]), 'Y': np.array([0.0, 1.0])}
        result = engine.farthest_point_from_pool(['X', 'Y'], [], pool_embeddings)
        assert result in {'X', 'Y'}

    def test_skips_candidates_missing_from_embeddings(self):
        """Defensive: candidates missing from pool_embeddings are silently skipped."""
        from apps.recommendation import engine
        pool_embeddings = {'X': np.array([1.0, 0.0])}  # Y missing
        result = engine.farthest_point_from_pool(['X', 'Y'], [], pool_embeddings)
        assert result == 'X'  # Y is skipped, X is the only valid candidate

    def test_returns_random_when_all_exposed_missing_from_embeddings(self):
        """Exposed list non-empty but every entry missing from pool_embeddings -> random."""
        from apps.recommendation import engine
        pool_embeddings = {'X': np.array([1.0, 0.0]), 'Y': np.array([0.0, 1.0])}
        # exposed has IDs not in pool_embeddings
        result = engine.farthest_point_from_pool(['X', 'Y'], ['Z'], pool_embeddings)
        assert result in {'X', 'Y'}
