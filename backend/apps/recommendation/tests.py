"""
Integration tests for the recommendation app.

Engine functions that query architecture_vectors are mocked because that table
is owned by Make DB and does not exist in the test database.
"""
import uuid
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserProfile
from .models import Project, AnalysisSession, SwipeEvent

# ── Helpers ───────────────────────────────────────────────────────────────────

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

MOCK_EMBEDDING = [0.1] * 384


def _make_user(username='testuser'):
    user = User.objects.create_user(username=username, email=f'{username}@test.com')
    profile = UserProfile.objects.create(user=user, display_name=username)
    return profile


def _auth_client(profile):
    client = APIClient()
    refresh = RefreshToken.for_user(profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(refresh.access_token)}')
    return client


# ── Project CRUD ──────────────────────────────────────────────────────────────

class TestProjectCRUD(TestCase):

    def setUp(self):
        self.profile = _make_user('proj_user')
        self.client  = _auth_client(self.profile)

    def test_create_project(self):
        res = self.client.post('/api/v1/projects/', {'name': 'My Project', 'filters': {}}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['name'], 'My Project')
        self.assertIn('project_id', res.data)

    def test_list_projects_paginated(self):
        Project.objects.create(user=self.profile, name='P1')
        Project.objects.create(user=self.profile, name='P2')
        res = self.client.get('/api/v1/projects/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('results', res.data)
        self.assertEqual(len(res.data['results']), 2)
        self.assertFalse(res.data['has_more'])

    def test_list_projects_pagination_controls(self):
        for i in range(12):
            Project.objects.create(user=self.profile, name=f'P{i}')
        res = self.client.get('/api/v1/projects/?page=1&page_size=5')
        self.assertEqual(len(res.data['results']), 5)
        self.assertTrue(res.data['has_more'])

    def test_delete_project(self):
        project = Project.objects.create(user=self.profile, name='ToDelete')
        res = self.client.delete(f'/api/v1/projects/{project.project_id}/')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Project.objects.filter(project_id=project.project_id).exists())

    def test_delete_other_users_project_returns_404(self):
        other = _make_user('other_user')
        project = Project.objects.create(user=other, name='NotMine')
        res = self.client.delete(f'/api/v1/projects/{project.project_id}/')
        self.assertEqual(res.status_code, 404)

    def test_unauthenticated_returns_401(self):
        res = APIClient().get('/api/v1/projects/')
        self.assertEqual(res.status_code, 401)


# ── Session flow ──────────────────────────────────────────────────────────────

class TestSessionFlow(TestCase):

    def setUp(self):
        self.profile = _make_user('session_user')
        self.client  = _auth_client(self.profile)

    @patch('apps.recommendation.views.engine.get_diverse_random')
    def test_create_session(self, mock_diverse):
        mock_diverse.return_value = [MOCK_CARD] * 10
        res = self.client.post('/api/v1/analysis/sessions/', {}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('session_id', res.data)
        self.assertIn('project_id', res.data)
        self.assertEqual(res.data['next_image']['building_id'], 'b001')

    @patch('apps.recommendation.views.engine.get_diverse_random')
    def test_create_session_no_buildings_returns_404(self, mock_diverse):
        mock_diverse.return_value = []
        res = self.client.post('/api/v1/analysis/sessions/', {}, format='json')
        self.assertEqual(res.status_code, 404)

    @patch('apps.recommendation.views.engine.get_building_card')
    @patch('apps.recommendation.views.engine.farthest_point_from_pool')
    @patch('apps.recommendation.views.engine.get_pool_embeddings')
    @patch('apps.recommendation.views.engine.create_bounded_pool')
    @patch('apps.recommendation.views.engine.get_building_embedding')
    @patch('apps.recommendation.views.engine.get_diverse_random')
    def test_swipe_like(self, mock_diverse, mock_emb, mock_pool, mock_pool_emb, mock_farthest, mock_card):
        mock_diverse.return_value    = [MOCK_CARD] * 10
        mock_emb.return_value        = MOCK_EMBEDDING
        mock_pool.return_value       = (['b001', 'b002'], {})
        mock_pool_emb.return_value   = {}
        mock_farthest.return_value   = 'b002'
        mock_card.return_value       = {**MOCK_CARD, 'building_id': 'b002'}

        create = self.client.post('/api/v1/analysis/sessions/', {}, format='json')
        session_id = create.data['session_id']

        res = self.client.post(
            f'/api/v1/analysis/sessions/{session_id}/swipes/',
            {'building_id': 'b001', 'action': 'like', 'idempotency_key': 'swp_1'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['accepted'])
        self.assertEqual(res.data['next_image']['building_id'], 'b002')

        # Liked building recorded on project
        session = AnalysisSession.objects.get(session_id=session_id)
        self.assertIn('b001', session.project.liked_ids)

    @patch('apps.recommendation.views.engine.get_building_card')
    @patch('apps.recommendation.views.engine.farthest_point_from_pool')
    @patch('apps.recommendation.views.engine.get_pool_embeddings')
    @patch('apps.recommendation.views.engine.create_bounded_pool')
    @patch('apps.recommendation.views.engine.get_building_embedding')
    @patch('apps.recommendation.views.engine.get_diverse_random')
    def test_duplicate_swipe_accepted(self, mock_diverse, mock_emb, mock_pool, mock_pool_emb, mock_farthest, mock_card):
        mock_diverse.return_value    = [MOCK_CARD] * 10
        mock_emb.return_value        = MOCK_EMBEDDING
        mock_pool.return_value       = (['b001', 'b002'], {})
        mock_pool_emb.return_value   = {}
        mock_farthest.return_value   = 'b001'
        mock_card.return_value       = MOCK_CARD

        create = self.client.post('/api/v1/analysis/sessions/', {}, format='json')
        session_id = create.data['session_id']

        payload = {'building_id': 'b001', 'action': 'like', 'idempotency_key': 'swp_dup'}
        self.client.post(f'/api/v1/analysis/sessions/{session_id}/swipes/', payload, format='json')
        res = self.client.post(f'/api/v1/analysis/sessions/{session_id}/swipes/', payload, format='json')
        # Duplicate should return accepted=True (not an error)
        self.assertTrue(res.data['accepted'])

    @patch('apps.recommendation.views.engine.get_top_k_results')
    @patch('apps.recommendation.views.engine.get_building_card')
    @patch('apps.recommendation.views.engine.farthest_point_from_pool')
    @patch('apps.recommendation.views.engine.get_pool_embeddings')
    @patch('apps.recommendation.views.engine.create_bounded_pool')
    @patch('apps.recommendation.views.engine.get_building_embedding')
    @patch('apps.recommendation.views.engine.get_diverse_random')
    def test_full_session_completes(self, mock_diverse, mock_emb, mock_pool, mock_pool_emb, mock_farthest, mock_card, mock_topk):
        cards = [{**MOCK_CARD, 'building_id': f'b{i:03d}'} for i in range(8)]
        mock_diverse.return_value  = cards
        mock_emb.return_value      = MOCK_EMBEDDING
        mock_pool.return_value     = ([c['building_id'] for c in cards], {})
        mock_pool_emb.return_value = {}
        mock_farthest.return_value = 'b001'
        mock_card.return_value     = MOCK_CARD
        mock_topk.return_value     = [MOCK_CARD]

        create = self.client.post('/api/v1/analysis/sessions/', {}, format='json')
        self.assertEqual(create.status_code, 201)
        session_id = create.data['session_id']

        for i in range(3):
            res = self.client.post(
                f'/api/v1/analysis/sessions/{session_id}/swipes/',
                {'building_id': f'b{i:03d}', 'action': 'like', 'idempotency_key': f'swp_{i}'},
                format='json',
            )
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.data['accepted'])
            self.assertIn('progress', res.data)
            self.assertIn('next_image', res.data)

        result = self.client.get(f'/api/v1/analysis/sessions/{session_id}/result/')
        self.assertEqual(result.status_code, 200)
        self.assertIn('liked_images', result.data)
        self.assertIn('predicted_images', result.data)


# ── Buildings batch ───────────────────────────────────────────────────────────

class TestBuildingBatch(TestCase):

    def setUp(self):
        self.profile = _make_user('batch_user')
        self.client  = _auth_client(self.profile)

    @patch('apps.recommendation.views.engine.get_buildings_by_ids')
    def test_batch_fetch(self, mock_batch):
        mock_batch.return_value = [MOCK_CARD]
        res = self.client.post('/api/v1/images/batch/', {'building_ids': ['b001']}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['building_id'], 'b001')

    def test_batch_empty_returns_empty(self):
        res = self.client.post('/api/v1/images/batch/', {'building_ids': []}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])
