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
        """Cannot delete a project belonging to another user."""
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
