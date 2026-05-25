"""
test_projects.py -- Project CRUD and building batch integration tests.

Migrated from apps/recommendation/tests.py to use pytest fixtures
from conftest.py (SQLite in-memory DB, JWT auth).
"""
import pytest
from unittest.mock import patch
from apps.recommendation.models import Project


MOCK_CARD = {
    'building_id': 'b001',
    'name_en': 'Test Building',
    'project_name': 'Test Project',
    'image_url': 'https://example.com/img.jpg',
    'url': None,
    'gallery': [],
    'metadata': {
        'axis_typology': 'Museum',
        'axis_architects': 'Architect A',
        'axis_country': 'Spain',
        'axis_area_m2': 5000.0,
        'axis_year': 2020,
        'axis_mood': 'Minimalist',
        'axis_material': 'Concrete',
        'axis_tags': [],
    },
}


# -- Project CRUD ----------------------------------------------------------

@pytest.mark.django_db
class TestProjectCRUD:

    def test_create_project(self, auth_client):
        resp = auth_client.post(
            '/api/v1/projects/',
            {'name': 'My Project', 'filters': {}},
            format='json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['name'] == 'My Project'
        assert 'project_id' in data

    def test_list_projects_paginated(self, auth_client, user_profile):
        Project.objects.create(user=user_profile, name='P1')
        Project.objects.create(user=user_profile, name='P2')
        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'results' in data
        assert len(data['results']) == 2
        assert data['has_more'] is False

    def test_list_projects_pagination_controls(self, auth_client, user_profile):
        for i in range(12):
            Project.objects.create(user=user_profile, name=f'P{i}')
        resp = auth_client.get('/api/v1/projects/?page=1&page_size=5')
        data = resp.json()
        assert len(data['results']) == 5
        assert data['has_more'] is True

    def test_delete_project(self, auth_client, user_profile):
        project = Project.objects.create(user=user_profile, name='ToDelete')
        resp = auth_client.delete(f'/api/v1/projects/{project.project_id}/')
        assert resp.status_code == 204
        assert not Project.objects.filter(project_id=project.project_id).exists()

    def test_delete_other_users_project_returns_404(self, auth_client, user_profile):
        """Cannot delete a project belonging to another user — 404 (no row lock granted to non-owner)."""
        from django.contrib.auth.models import User
        from apps.accounts.models import UserProfile
        other_user = User.objects.create_user(
            username='other_user', email='other@test.com',
        )
        other_profile = UserProfile.objects.create(
            user=other_user, display_name='Other User',
        )
        project = Project.objects.create(user=other_profile, name='NotMine')
        resp = auth_client.delete(f'/api/v1/projects/{project.project_id}/')
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self, api_client):
        resp = api_client.get('/api/v1/projects/')
        assert resp.status_code == 401


# -- ProjectDetailView --------------------------------------------------------

@pytest.mark.django_db
class TestProjectDetailView:

    def test_get_private_project_non_owner_returns_403_forbidden_body(
        self, api_client, user_profile,
    ):
        """Private project GET by non-owner returns 403 with body {'detail': 'Forbidden'}."""
        project = Project.objects.create(user=user_profile, name='Private', visibility='private')
        resp = api_client.get(f'/api/v1/projects/{project.project_id}/')
        assert resp.status_code == 403
        assert resp.json() == {'detail': 'Forbidden'}

    def test_patch_updates_updated_at(self, auth_client, user_profile):
        """PATCH refresh_from_db() ensures response reflects DB-set updated_at."""
        project = Project.objects.create(user=user_profile, name='Before')
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'name': 'After'},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['name'] == 'After'
        # updated_at in response must be non-null (DB-set by auto_now=True)
        assert data.get('updated_at') is not None


# -- remove_building_ids PATCH tests ------------------------------------------

@pytest.mark.django_db
class TestProjectRemoveBuildingIds:

    def test_patch_remove_building_ids_valid(self, auth_client, user_profile):
        """Valid remove_building_ids removes matched items from liked_ids and saved_ids."""
        project = Project.objects.create(
            user=user_profile,
            name='RemoveTest',
            liked_ids=[{'id': 'bld_001'}, {'id': 'bld_002'}, {'id': 'bld_003'}],
            saved_ids=[{'id': 'bld_001', 'saved_at': '2024-01-01T00:00:00Z'}, {'id': 'bld_002', 'saved_at': '2024-01-02T00:00:00Z'}],
        )
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['bld_001', 'bld_003']},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        liked_ids = [item['id'] for item in data['liked_ids']]
        saved_ids = [item['id'] for item in data['saved_ids']]
        assert liked_ids == ['bld_002']
        assert saved_ids == ['bld_002']

    def test_patch_remove_building_ids_invalid_type(self, auth_client, user_profile):
        """Non-list remove_building_ids returns 400 and does not mutate liked_ids."""
        project = Project.objects.create(
            user=user_profile,
            name='InvalidTypeTest',
            liked_ids=[{'id': 'bld_001'}],
            saved_ids=[],
        )

        # string instead of list
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': 'bld_001'},
            format='json',
        )
        assert resp.status_code == 400
        assert 'remove_building_ids' in resp.json()['detail']
        project.refresh_from_db()
        assert len(project.liked_ids) == 1

        # int instead of list
        resp2 = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': 123},
            format='json',
        )
        assert resp2.status_code == 400
        project.refresh_from_db()
        assert len(project.liked_ids) == 1

    def test_patch_remove_building_ids_with_invalid_schema_field_atomic(self, auth_client, user_profile):
        """Atomicity: if schema_data is invalid, the remove_building_ids delete is NOT persisted."""
        project = Project.objects.create(
            user=user_profile,
            name='AtomicTest',
            liked_ids=[{'id': 'bld_001'}, {'id': 'bld_002'}],
            saved_ids=[],
        )
        resp = auth_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'remove_building_ids': ['bld_001'], 'visibility': 'invalid_value'},
            format='json',
        )
        assert resp.status_code == 400
        project.refresh_from_db()
        # delete must NOT have been persisted — liked_ids still has both entries
        assert len(project.liked_ids) == 2
        liked_id_values = [item['id'] for item in project.liked_ids]
        assert 'bld_001' in liked_id_values


# -- UserProjectsListView --------------------------------------------------------

@pytest.mark.django_db
class TestUserProjectsListView:

    def test_page_size_capped_at_50(self, auth_client, user_profile):
        """page_size=999 is clamped to 50; response contains at most 50 results."""
        for i in range(5):
            Project.objects.create(user=user_profile, name=f'P{i}', visibility='public')
        resp = auth_client.get(
            f'/api/v1/users/{user_profile.user.id}/projects/?page_size=999',
        )
        assert resp.status_code == 200
        data = resp.json()
        # page_size=999 is capped to 50; all 5 fit within that cap
        assert len(data['results']) == 5
        # PERF-1: total is now None (deprecated); frontend uses has_more
        assert data['total'] is None
        assert 'page' in data
        assert 'has_more' in data

    def test_no_n_plus_one_select_related(self, auth_client, user_profile, django_assert_num_queries):
        """UserProjectsListView must not issue N per-row FK queries for nested user data.

        With select_related('user__user') the view executes a fixed number of queries
        regardless of project count: auth lookup + profile lookup + one JOIN SELECT.
        Without select_related, each project row would trigger 2 extra FK lookups (N+1).

        PERF-1: COUNT(*) removed (page_size+1 trick) so query count is now 4, not 5.
        """
        for i in range(5):
            Project.objects.create(user=user_profile, name=f'P{i}', visibility='public')
        # 4 queries with PERF-1 optimisation in place:
        #   1. JWT auth lookup (OutstandingToken / auth_user)
        #   2. _get_profile() UserProfile lookup for requester
        #   3. target_profile lookup (get_object_or_404 UserProfile)
        #   4. SELECT with INNER JOINs + Subquery annotations (no COUNT)
        # If select_related is removed, this would grow to 4 + 2×N queries (N=5 → 14).
        with django_assert_num_queries(4):
            resp = auth_client.get(f'/api/v1/users/{user_profile.user.id}/projects/')
        assert resp.status_code == 200
        # total is None after PERF-1 — frontend uses has_more instead
        assert resp.json()['total'] is None

    def test_pagination_returns_page_field(self, auth_client, user_profile):
        """Response shape includes page + has_more (mirrors ProjectListCreateView)."""
        Project.objects.create(user=user_profile, name='P1', visibility='public')
        resp = auth_client.get(f'/api/v1/users/{user_profile.user.id}/projects/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['page'] == 1
        assert data['has_more'] is False


# -- Building Batch --------------------------------------------------------

@pytest.mark.django_db
class TestBuildingBatch:

    @patch('apps.recommendation.views.engine.get_buildings_by_ids')
    def test_batch_fetch(self, mock_batch, auth_client):
        mock_batch.return_value = [MOCK_CARD]
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'building_ids': ['b001']},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['building_id'] == 'b001'

    def test_batch_empty_returns_empty(self, auth_client):
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'building_ids': []},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_batch_nested_list_returns_400(self, auth_client):
        """Nested list element slips past list check without element validation → PG 500.
        Fix: element-type guard must reject non-string elements."""
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': [['bld_000001']]},
            format='json',
        )
        assert resp.status_code == 400
        assert 'non-empty strings' in resp.json().get('detail', '')

    @patch('apps.recommendation.views.engine.get_buildings_by_ids')
    def test_batch_valid_string_ids_returns_200(self, mock_batch, auth_client):
        """Valid list of non-empty strings must reach engine and return 200."""
        mock_batch.return_value = [MOCK_CARD]
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': ['bld_000001']},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_batch_none_and_empty_string_returns_400(self, auth_client):
        """None and empty-string elements must be rejected by element-type guard."""
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': [None, '']},
            format='json',
        )
        assert resp.status_code == 400
        assert 'non-empty strings' in resp.json().get('detail', '')

    def test_batch_integer_element_returns_400(self, auth_client):
        """Integer element must be rejected by element-type guard."""
        resp = auth_client.post(
            '/api/v1/images/batch/',
            {'canonical_bld_ids': [123]},
            format='json',
        )
        assert resp.status_code == 400
        assert 'non-empty strings' in resp.json().get('detail', '')


# -- ProjectSerializer.latest_session_meta ------------------------------------

def _make_owner_request(user):
    """Build a minimal DRF-compatible request stub with the given authenticated user.

    Creates a DRF Request from an APIRequestFactory GET, then assigns the user
    directly to Request.user (the DRF setter propagates to both internal _user
    and the underlying HttpRequest).  This bypasses the authentication backend
    pipeline while still satisfying the serializer's `request.user.is_authenticated`
    and `request.user == obj.user.user` checks.
    """
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request
    factory = APIRequestFactory()
    raw = factory.get('/')
    req = Request(raw)
    req.user = user  # DRF Request.user setter sets both req._user and raw.user
    return req


@pytest.mark.django_db
class TestProjectSerializerLatestSessionMeta:
    """Verify ProjectSerializer exposes latest_session_meta with correct shape.

    Tests run against the serializer directly (not via HTTP) to stay isolated
    from view-layer annotation logic.  The serializer's fallback path
    (obj.sessions.order_by('-created_at').first()) is exercised here.

    All owner-path tests pass context={'request': <owner_request>} so the
    ownership gate is satisfied.  Non-owner / no-context paths are tested
    separately (IDOR guard tests).
    """

    def test_latest_session_meta_is_none_when_no_session(self, user_profile):
        """Project with no sessions → latest_session_meta is null (owner caller)."""
        from apps.recommendation.serializers import ProjectSerializer
        project = Project.objects.create(user=user_profile, name='No Session')
        req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': req}).data
        assert data['latest_session_meta'] is None

    def test_latest_session_meta_returns_correct_shape(self, user_profile):
        """Project with a session returns id, like_count, created_at (owner caller)."""
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        project = Project.objects.create(user=user_profile, name='Has Session')
        n_likes = 3
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            like_vectors=[{'embedding': [0.1] * 5, 'round': i} for i in range(n_likes)],
        )

        req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': req}).data
        meta = data['latest_session_meta']

        assert meta is not None
        assert meta['id'] == str(session.session_id)
        assert meta['like_count'] == n_likes
        assert 'created_at' in meta
        # created_at must be a non-empty ISO string
        assert isinstance(meta['created_at'], str) and meta['created_at']

    def test_latest_session_meta_like_count_matches_like_vectors_length(self, user_profile):
        """like_count is len(like_vectors), not a separate column (owner caller)."""
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        project = Project.objects.create(user=user_profile, name='Like Count Test')
        AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            like_vectors=[{'embedding': [0.0] * 5, 'round': i} for i in range(7)],
        )

        req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': req}).data
        assert data['latest_session_meta']['like_count'] == 7

    def test_latest_session_meta_uses_most_recent_session(self, user_profile):
        """When multiple sessions exist, meta reflects the most recently created (owner caller)."""
        import time
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        project = Project.objects.create(user=user_profile, name='Multi Session')
        AnalysisSession.objects.create(
            user=user_profile, project=project,
            like_vectors=[{'embedding': [0.0] * 5, 'round': 0}],
        )
        # Small sleep to ensure created_at ordering is deterministic on SQLite
        time.sleep(0.01)
        newer_session = AnalysisSession.objects.create(
            user=user_profile, project=project,
            like_vectors=[{'embedding': [0.0] * 5, 'round': i} for i in range(5)],
        )

        req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': req}).data
        meta = data['latest_session_meta']
        assert meta['id'] == str(newer_session.session_id)
        assert meta['like_count'] == 5

    def test_latest_session_id_and_meta_consistent(self, user_profile):
        """latest_session_id and latest_session_meta['id'] must refer to the same session (owner caller)."""
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        project = Project.objects.create(user=user_profile, name='Consistency Test')
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            like_vectors=[],
        )

        req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': req}).data
        assert data['latest_session_id'] == str(session.session_id)
        assert data['latest_session_meta']['id'] == str(session.session_id)

    # -- IDOR guard: Defect 1 regression tests --------------------------------

    def test_latest_session_meta_hidden_from_non_owner(self, user_profile):
        """Non-owner viewing another user's public project gets latest_session_meta=None.

        Regression guard for IDOR: viewer A queries owner B's public project.
        Even when B has an in-progress session, A must receive null for both
        latest_session_meta and latest_session_id.
        """
        from django.contrib.auth.models import User
        from apps.accounts.models import UserProfile
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        # Owner B has a public project with an active session
        owner_user = User.objects.create_user(
            username='owner_b', email='owner_b@test.com',
        )
        owner_profile = UserProfile.objects.create(
            user=owner_user, display_name='Owner B',
        )
        project = Project.objects.create(
            user=owner_profile, name='Public Board', visibility='public',
        )
        AnalysisSession.objects.create(
            user=owner_profile,
            project=project,
            like_vectors=[{'embedding': [0.1] * 5, 'round': 0}],
        )

        # Viewer A is a different authenticated user
        viewer_req = _make_owner_request(user_profile.user)
        data = ProjectSerializer(project, context={'request': viewer_req}).data

        assert data['latest_session_meta'] is None, (
            'Non-owner must not receive session meta — IDOR leak'
        )
        assert data['latest_session_id'] is None, (
            'Non-owner must not receive session_id — IDOR leak'
        )

    def test_latest_session_meta_hidden_when_no_context(self, user_profile):
        """Serializer called without request context returns null conservatively."""
        from apps.recommendation.models import AnalysisSession
        from apps.recommendation.serializers import ProjectSerializer

        project = Project.objects.create(user=user_profile, name='No Context')
        AnalysisSession.objects.create(
            user=user_profile, project=project, like_vectors=[],
        )
        # No context passed — conservative fallback must be null
        data = ProjectSerializer(project).data
        assert data['latest_session_meta'] is None
        assert data['latest_session_id'] is None


# -- TOCTOU / ownership tests (Defect 3) -------------------------------------

@pytest.mark.django_db
class TestProjectPatchOwnership:
    """Verify PATCH /projects/{pk}/ returns 404 for non-owner cross-user requests.

    Regression guard for Defect 3: ownership is now folded into the
    select_for_update().filter(user=profile) queryset so a non-owner request
    never acquires a row lock and receives 404 (not 403).
    """

    def _make_other_client(self):
        """Create a second user + JWT client."""
        from django.contrib.auth.models import User
        from apps.accounts.models import UserProfile
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        other_user = User.objects.create_user(
            username='attacker', email='attacker@test.com',
        )
        UserProfile.objects.create(user=other_user, display_name='Attacker')
        client = APIClient()
        refresh = RefreshToken.for_user(other_user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return client

    def test_project_patch_returns_404_for_non_owner_cross_user(self, user_profile):
        """User A tries to PATCH user B's project → 404 (no lock granted to non-owner)."""
        project = Project.objects.create(user=user_profile, name='Victim Project')
        attacker_client = self._make_other_client()
        resp = attacker_client.patch(
            f'/api/v1/projects/{project.project_id}/',
            {'name': 'Hijacked'},
            format='json',
        )
        assert resp.status_code == 404
        # Project must be unchanged
        project.refresh_from_db()
        assert project.name == 'Victim Project'
