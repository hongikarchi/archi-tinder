"""
test_project_recommendations.py -- FULL-REPORT-UI-1 (WP5):
GET /api/v1/projects/<pk>/recommendations/ shows a board's recommended
buildings to the owner AND to non-owners of a public board.

Also pins ProjectReportImageView: a failed regeneration keeps the stored image.
"""
import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.recommendation.models import AnalysisSession, Project

_BUILD = 'apps.recommendation.views.projects.session_service.build_predicted_cards'
_CARDS = [{'canonical_bld_id': 'bld_000001'}, {'canonical_bld_id': 'bld_000002'}]


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _project(profile, visibility='private'):
    return Project.objects.create(user=profile, name='B', visibility=visibility)


def _session(project, profile, like_vectors=None):
    return AnalysisSession.objects.create(
        user=profile, project=project,
        like_vectors=[{'embedding_id': 'bld_000001', 'round': 1}] if like_vectors is None else like_vectors,
    )


def _url(pk):
    return f'/api/v1/projects/{pk}/recommendations/'


@pytest.mark.django_db
class TestProjectRecommendations:

    def test_owner_gets_cards(self, auth_client, user_profile):
        project = _project(user_profile)
        _session(project, user_profile)
        with patch(_BUILD, return_value=(_CARDS, [], None, None)):
            resp = auth_client.get(_url(project.project_id))
        assert resp.status_code == 200
        assert resp.json() == {'predicted_like_images': _CARDS}
        assert 'latest_session_id' not in resp.json()

    def test_non_owner_public_board_200(self, other_auth_client, user_profile):
        project = _project(user_profile, visibility='public')
        _session(project, user_profile)
        with patch(_BUILD, return_value=(_CARDS, [], None, None)):
            resp = other_auth_client.get(_url(project.project_id))
        assert resp.status_code == 200
        assert resp.json()['predicted_like_images'] == _CARDS

    def test_non_owner_private_board_403(self, other_auth_client, user_profile):
        project = _project(user_profile, visibility='private')
        _session(project, user_profile)
        with patch(_BUILD) as build:
            resp = other_auth_client.get(_url(project.project_id))
        assert resp.status_code == 403
        assert resp.json() == {'detail': 'Forbidden'}
        build.assert_not_called()

    def test_anonymous_401(self, api_client, user_profile):
        project = _project(user_profile, visibility='public')
        resp = api_client.get(_url(project.project_id))
        assert resp.status_code == 401

    def test_unknown_project_404(self, auth_client):
        resp = auth_client.get(_url(uuid.uuid4()))
        assert resp.status_code == 404

    def test_no_session_returns_empty_list(self, auth_client, user_profile):
        project = _project(user_profile)
        with patch(_BUILD) as build:
            resp = auth_client.get(_url(project.project_id))
        assert resp.status_code == 200
        assert resp.json() == {'predicted_like_images': []}
        build.assert_not_called()

    def test_session_without_like_vectors_returns_empty_list(self, auth_client, user_profile):
        project = _project(user_profile)
        _session(project, user_profile, like_vectors=[])
        with patch(_BUILD) as build:
            resp = auth_client.get(_url(project.project_id))
        assert resp.status_code == 200
        assert resp.json() == {'predicted_like_images': []}
        build.assert_not_called()

    def test_cache_hit_does_not_rerun_engine(self, auth_client, other_auth_client, user_profile):
        project = _project(user_profile, visibility='public')
        _session(project, user_profile)
        with patch(_BUILD, return_value=(_CARDS, [], None, None)) as build:
            first = auth_client.get(_url(project.project_id))
            second = other_auth_client.get(_url(project.project_id))
        assert first.json() == second.json() == {'predicted_like_images': _CARDS}
        assert build.call_count == 1

    def test_evict_project_detail_invalidates_cache(self, auth_client, user_profile):
        from apps.recommendation.caches import evict_project_detail
        project = _project(user_profile)
        _session(project, user_profile)
        with patch(_BUILD, return_value=(_CARDS, [], None, None)) as build:
            auth_client.get(_url(project.project_id))
            evict_project_detail(str(project.project_id))
            auth_client.get(_url(project.project_id))
        assert build.call_count == 2


@pytest.mark.django_db
def test_failed_image_regeneration_keeps_stored_image(auth_client, user_profile):
    project = Project.objects.create(
        user=user_profile, name='Img',
        liked_ids=[{'id': 'L1', 'intensity': 1.0}],
        report_image='OLDIMG', report_image_mime='image/png',
        final_report={'one_liner': 'x'},
    )
    with patch('apps.recommendation.services.generate_persona_image', return_value=None):
        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/report/generate-image/',
            {'regenerate': True}, format='json',
        )
    assert resp.status_code == 500
    project.refresh_from_db()
    assert project.report_image == 'OLDIMG'
    assert project.report_image_mime == 'image/png'
