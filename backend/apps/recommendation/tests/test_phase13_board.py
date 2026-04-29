"""
test_phase13_board.py — Phase 13 BOARD1: Project visibility + library merge.

Coverage:
  - Project model: visibility default 'private', reaction_count default 0
  - ProjectSerializer: disliked_ids NEVER in response (owner, public, admin)
  - GET /api/v1/projects/{id}/ — own→200, public→200 anon, private non-owner→403
  - PATCH /api/v1/projects/{id}/ — owner updates name+visibility; follower_count/
    disliked_ids silently ignored; non-owner 403
  - GET /api/v1/users/{id}/projects/ — non-owner: public only; owner: all
  - GET /api/v1/users/{id}/ — boards[] field present and correctly hydrated
  - Backward compat smoke tests for existing swipe workflow
"""
import pytest
from unittest.mock import patch
from apps.recommendation.models import Project


# ── TestProjectExtensionModel ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectExtensionModel:

    def test_visibility_default_private(self, user_profile):
        p = Project.objects.create(user=user_profile, name='P1')
        assert p.visibility == 'private'

    def test_reaction_count_default_zero(self, user_profile):
        p = Project.objects.create(user=user_profile, name='P1')
        assert p.reaction_count == 0

    def test_raw_query_default_null(self, user_profile):
        p = Project.objects.create(user=user_profile, name='P1')
        assert p.raw_query is None

    def test_str_unchanged(self, user_profile):
        p = Project.objects.create(user=user_profile, name='MyProject')
        assert 'MyProject' in str(p)

    def test_visibility_choices_valid(self, user_profile):
        p_pub = Project.objects.create(user=user_profile, name='Pub', visibility='public')
        p_prv = Project.objects.create(user=user_profile, name='Prv', visibility='private')
        assert p_pub.visibility == 'public'
        assert p_prv.visibility == 'private'


# ── TestProjectSerializer: disliked_ids absolutely absent ────────────────────

@pytest.mark.django_db
class TestProjectSerializer:

    def _make_project(self, user_profile, **kwargs):
        defaults = dict(
            name='TestBoard',
            liked_ids=[{'id': 'B001', 'intensity': 1.0}],
            disliked_ids=['B999'],
            saved_ids=[{'id': 'B002', 'saved_at': '2026-04-28T00:00:00Z'}],
            visibility='public',
        )
        defaults.update(kwargs)
        return Project.objects.create(user=user_profile, **defaults)

    @pytest.mark.parametrize('context', ['owner', 'public', 'admin'])
    def test_disliked_ids_never_in_response(self, context, auth_client, api_client, user_profile):
        project = self._make_project(user_profile, visibility='public')
        pid = project.project_id

        if context == 'owner':
            resp = auth_client.get(f'/api/v1/projects/{pid}/')
        elif context == 'public':
            resp = api_client.get(f'/api/v1/projects/{pid}/')
        else:  # admin — same shape as owner for now
            resp = auth_client.get(f'/api/v1/projects/{pid}/')

        assert resp.status_code == 200
        data = resp.json()
        assert 'disliked_ids' not in data, (
            f'disliked_ids must NEVER appear in {context} response'
        )

    def test_liked_ids_exposed(self, auth_client, user_profile):
        project = self._make_project(user_profile)
        resp = auth_client.get(f'/api/v1/projects/{project.project_id}/')
        assert resp.status_code == 200
        assert 'liked_ids' in resp.json()

    def test_saved_ids_exposed(self, auth_client, user_profile):
        project = self._make_project(user_profile)
        resp = auth_client.get(f'/api/v1/projects/{project.project_id}/')
        assert resp.status_code == 200
        assert 'saved_ids' in resp.json()

    def test_visibility_and_reaction_count_in_response(self, auth_client, user_profile):
        project = self._make_project(user_profile, visibility='public', reaction_count=0)
        resp = auth_client.get(f'/api/v1/projects/{project.project_id}/')
        data = resp.json()
        assert data['visibility'] == 'public'
        assert data['reaction_count'] == 0

    def test_raw_query_exposed_when_set(self, auth_client, user_profile):
        project = self._make_project(user_profile, raw_query='minimalist concrete')
        resp = auth_client.get(f'/api/v1/projects/{project.project_id}/')
        data = resp.json()
        assert data['raw_query'] == 'minimalist concrete'

    def test_user_nested_shape(self, auth_client, user_profile):
        """user field must be nested {user_id, display_name, avatar_url}."""
        project = self._make_project(user_profile)
        resp = auth_client.get(f'/api/v1/projects/{project.project_id}/')
        data = resp.json()
        assert 'user' in data
        user_data = data['user']
        assert 'user_id' in user_data
        assert 'display_name' in user_data
        assert 'avatar_url' in user_data

    def test_post_response_no_disliked_ids(self, auth_client):
        """POST /projects/ response must also exclude disliked_ids."""
        resp = auth_client.post(
            '/api/v1/projects/',
            {'name': 'NewBoard', 'filters': {}},
            format='json',
        )
        assert resp.status_code == 201
        assert 'disliked_ids' not in resp.json()


# ── TestProjectDetailView ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectDetailView:

    def test_owner_gets_own_private_project(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='Mine', visibility='private')
        resp = auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200

    def test_anon_gets_public_project(self, api_client, user_profile):
        p = Project.objects.create(user=user_profile, name='PublicP', visibility='public')
        resp = api_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 200

    def test_non_owner_blocked_on_private(self, other_auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='Private', visibility='private')
        resp = other_auth_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 403

    def test_anon_blocked_on_private(self, api_client, user_profile):
        p = Project.objects.create(user=user_profile, name='PrivAnon', visibility='private')
        resp = api_client.get(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 403

    def test_404_on_nonexistent(self, api_client):
        import uuid
        resp = api_client.get(f'/api/v1/projects/{uuid.uuid4()}/')
        assert resp.status_code == 404


# ── TestProjectSelfUpdateView ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestProjectSelfUpdateView:

    def test_owner_can_update_name(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='OldName')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'name': 'NewName'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.json()['name'] == 'NewName'

    def test_owner_can_update_visibility(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='P1', visibility='private')
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'visibility': 'public'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.json()['visibility'] == 'public'

    def test_patch_ignores_disliked_ids(self, auth_client, user_profile):
        """Attempting to PATCH disliked_ids must not change or expose them."""
        p = Project.objects.create(user=user_profile, name='P1', disliked_ids=['B999'])
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'disliked_ids': ['HACKED'], 'name': 'Updated'},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'disliked_ids' not in data
        p.refresh_from_db()
        assert p.disliked_ids == ['B999'], 'disliked_ids must not be mutated by PATCH'

    def test_patch_ignores_reaction_count(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='P1', reaction_count=0)
        resp = auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'reaction_count': 9999, 'name': 'P1'},
            format='json',
        )
        assert resp.status_code == 200
        p.refresh_from_db()
        assert p.reaction_count == 0

    def test_non_owner_patch_returns_403(self, other_auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='NotMine')
        resp = other_auth_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'name': 'Hacked'},
            format='json',
        )
        assert resp.status_code == 403

    def test_unauthenticated_patch_returns_401(self, api_client, user_profile):
        p = Project.objects.create(user=user_profile, name='P1')
        resp = api_client.patch(
            f'/api/v1/projects/{p.project_id}/',
            {'name': 'Anon'},
            format='json',
        )
        assert resp.status_code == 401


# ── TestUserProjectsListView ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserProjectsListView:

    def test_non_owner_sees_public_only(self, other_auth_client, user_profile):
        Project.objects.create(user=user_profile, name='Pub', visibility='public')
        Project.objects.create(user=user_profile, name='Priv', visibility='private')
        uid = user_profile.user.id
        resp = other_auth_client.get(f'/api/v1/users/{uid}/projects/')
        assert resp.status_code == 200
        data = resp.json()
        names = [p['name'] for p in data['results']]
        assert 'Pub' in names
        assert 'Priv' not in names

    def test_owner_sees_all(self, auth_client, user_profile):
        Project.objects.create(user=user_profile, name='Pub', visibility='public')
        Project.objects.create(user=user_profile, name='Priv', visibility='private')
        uid = user_profile.user.id
        resp = auth_client.get(f'/api/v1/users/{uid}/projects/')
        assert resp.status_code == 200
        data = resp.json()
        names = [p['name'] for p in data['results']]
        assert 'Pub' in names
        assert 'Priv' in names

    def test_anon_sees_public_only(self, api_client, user_profile):
        Project.objects.create(user=user_profile, name='PubA', visibility='public')
        Project.objects.create(user=user_profile, name='PrivA', visibility='private')
        uid = user_profile.user.id
        resp = api_client.get(f'/api/v1/users/{uid}/projects/')
        assert resp.status_code == 200
        names = [p['name'] for p in resp.json()['results']]
        assert 'PubA' in names
        assert 'PrivA' not in names

    def test_disliked_ids_absent_in_list(self, api_client, user_profile):
        Project.objects.create(
            user=user_profile, name='PubB', visibility='public', disliked_ids=['B999'],
        )
        uid = user_profile.user.id
        resp = api_client.get(f'/api/v1/users/{uid}/projects/')
        for item in resp.json()['results']:
            assert 'disliked_ids' not in item

    def test_user_not_found_returns_404(self, api_client):
        resp = api_client.get('/api/v1/users/99999/projects/')
        assert resp.status_code == 404


# ── TestUserProfileBoardsField ────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserProfileBoardsField:

    def test_boards_field_present(self, api_client, user_profile):
        uid = user_profile.user.id
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            resp = api_client.get(f'/api/v1/users/{uid}/')
        assert resp.status_code == 200
        assert 'boards' in resp.json()

    def test_boards_empty_when_no_projects(self, api_client, user_profile):
        uid = user_profile.user.id
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            resp = api_client.get(f'/api/v1/users/{uid}/')
        assert resp.json()['boards'] == []

    def test_boards_non_owner_sees_public_only(self, api_client, user_profile):
        Project.objects.create(user=user_profile, name='PubBoard', visibility='public')
        Project.objects.create(user=user_profile, name='PrivBoard', visibility='private')
        uid = user_profile.user.id
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            resp = api_client.get(f'/api/v1/users/{uid}/')
        boards = resp.json()['boards']
        names = [b['name'] for b in boards]
        assert 'PubBoard' in names
        assert 'PrivBoard' not in names

    def test_boards_owner_sees_all(self, auth_client, user_profile):
        Project.objects.create(user=user_profile, name='PubO', visibility='public')
        Project.objects.create(user=user_profile, name='PrivO', visibility='private')
        uid = user_profile.user.id
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            resp = auth_client.get(f'/api/v1/users/{uid}/')
        boards = resp.json()['boards']
        names = [b['name'] for b in boards]
        assert 'PubO' in names
        assert 'PrivO' in names

    def test_boards_card_shape(self, api_client, user_profile):
        """Each board card must have the required fields."""
        Project.objects.create(
            user=user_profile, name='ShapeTest', visibility='public',
            liked_ids=[{'id': 'B001', 'intensity': 1.0}],
        )
        uid = user_profile.user.id
        mock_card = {'building_id': 'B001', 'image_url': 'https://cdn.example.com/B001/photo.jpg'}
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[mock_card]):
            resp = api_client.get(f'/api/v1/users/{uid}/')
        boards = resp.json()['boards']
        assert len(boards) == 1
        card = boards[0]
        required_fields = {
            'project_id', 'name', 'date', 'visibility',
            'building_count', 'cover_image_url', 'thumbnails',
        }
        assert required_fields.issubset(card.keys())
        assert card['cover_image_url'] == 'https://cdn.example.com/B001/photo.jpg'
        assert card['visibility'] == 'public'

    def test_boards_building_count_correct(self, api_client, user_profile):
        Project.objects.create(
            user=user_profile, name='CountTest', visibility='public',
            liked_ids=[{'id': 'B001', 'intensity': 1.0}, {'id': 'B002', 'intensity': 1.0}],
            saved_ids=[{'id': 'B003', 'saved_at': '2026-04-28T00:00:00Z'}],
        )
        uid = user_profile.user.id
        with patch('apps.recommendation.engine.get_buildings_by_ids', return_value=[]):
            resp = api_client.get(f'/api/v1/users/{uid}/')
        card = resp.json()['boards'][0]
        assert card['building_count'] == 3  # 2 liked + 1 saved


# ── Backward Compat Smoke Tests ───────────────────────────────────────────────

@pytest.mark.django_db
class TestBackwardCompatSmoke:

    def test_project_list_still_works(self, auth_client, user_profile):
        Project.objects.create(user=user_profile, name='Smoke1')
        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        assert 'results' in resp.json()

    def test_project_create_still_works(self, auth_client):
        resp = auth_client.post(
            '/api/v1/projects/',
            {'name': 'SmokePrj', 'filters': {}},
            format='json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['name'] == 'SmokePrj'
        assert 'project_id' in data
        # New fields present with safe defaults
        assert data['visibility'] == 'private'
        assert data['reaction_count'] == 0

    def test_project_delete_still_works(self, auth_client, user_profile):
        p = Project.objects.create(user=user_profile, name='DelSmoke')
        resp = auth_client.delete(f'/api/v1/projects/{p.project_id}/')
        assert resp.status_code == 204
        assert not Project.objects.filter(project_id=p.project_id).exists()
