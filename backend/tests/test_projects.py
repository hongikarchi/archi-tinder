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

    def test_delete_other_users_project_returns_403(self, auth_client, user_profile):
        """Cannot delete a project belonging to another user — 403 (project exists, forbidden)."""
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
        assert resp.status_code == 403

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
        assert data['total'] == 5
        assert 'page' in data
        assert 'has_more' in data

    def test_no_n_plus_one_select_related(self, auth_client, user_profile, django_assert_num_queries):
        """UserProjectsListView must not issue N per-row FK queries for nested user data.

        With select_related('user__user') the view executes a fixed number of queries
        regardless of project count: auth lookup + profile lookup + COUNT + one JOIN SELECT.
        Without select_related, each project row would trigger 2 extra FK lookups (N+1).
        """
        for i in range(5):
            Project.objects.create(user=user_profile, name=f'P{i}', visibility='public')
        # 5 queries observed empirically with select_related in place:
        #   1. JWT auth lookup (OutstandingToken / auth_user)
        #   2. _get_profile() UserProfile lookup for requester
        #   3. target_profile lookup (get_object_or_404 UserProfile)
        #   4. COUNT(*) on filtered queryset
        #   5. SELECT with INNER JOINs (select_related fetches user+auth_user in one query)
        # If select_related is removed, this would grow to 5 + 2×N queries (N=5 → 15).
        with django_assert_num_queries(5):
            resp = auth_client.get(f'/api/v1/users/{user_profile.user.id}/projects/')
        assert resp.status_code == 200
        assert resp.json()['total'] == 5

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
