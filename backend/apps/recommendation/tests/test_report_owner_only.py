"""
test_report_owner_only.py -- persona report TEXT is owner-only.

Non-owners (incl. anonymous on a public board) get final_report /
analysis_report / axis_scores = null and report_stale = False from every
Project serializer; structural fields and the report IMAGE stay public.
"""
import pytest
from django.core.cache import cache

from apps.recommendation.models import Project

_REPORT = {'one_liner': 'secret taste', 'source_signature': 'stale-on-purpose'}
_AXES = {'a': 1}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _board(profile, visibility='public'):
    return Project.objects.create(
        user=profile, name='B', visibility=visibility,
        liked_ids=[{'id': 'bld_000001', 'intensity': 1.0}],
        final_report=_REPORT, axis_scores=_AXES, analysis_report={'x': 1},
        report_image='IMG', report_image_mime='image/png',
    )


def _detail(pk):
    return f'/api/v1/projects/{pk}/'


@pytest.mark.django_db
class TestDetailOwnerOnlyReport:

    def test_owner_sees_report(self, auth_client, user_profile):
        data = auth_client.get(_detail(_board(user_profile).project_id)).json()
        assert data['final_report'] == _REPORT
        assert data['axis_scores'] == _AXES
        assert data['analysis_report'] == {'x': 1}

    def test_non_owner_report_null_structure_kept(self, other_auth_client, user_profile):
        project = _board(user_profile)
        resp = other_auth_client.get(_detail(project.project_id))
        assert resp.status_code == 200
        data = resp.json()
        assert data['final_report'] is None
        assert data['axis_scores'] is None
        assert data['analysis_report'] is None
        assert data['report_stale'] is False
        assert 'conversation_history' not in data
        assert data['name'] == 'B'
        assert data['visibility'] == 'public'
        assert data['liked_ids'] == project.liked_ids
        assert data['report_image'] == 'IMG'
        assert data['report_image_mime'] == 'image/png'
        assert data['latest_session_id'] is None

    def test_anonymous_public_report_null(self, api_client, user_profile):
        data = api_client.get(_detail(_board(user_profile).project_id)).json()
        assert data['final_report'] is None
        assert data['axis_scores'] is None
        assert data['report_image'] == 'IMG'

    def test_private_board_still_403_for_non_owner(self, other_auth_client, user_profile):
        project = _board(user_profile, visibility='private')
        resp = other_auth_client.get(_detail(project.project_id))
        assert resp.status_code == 403
        assert resp.json() == {'detail': 'Forbidden'}

    def test_cache_isolation_between_owner_and_non_owner(
        self, auth_client, other_auth_client, api_client, user_profile,
    ):
        pk = _board(user_profile).project_id
        # non-owner / anonymous first (warm their cache entries) ...
        assert other_auth_client.get(_detail(pk)).json()['final_report'] is None
        assert api_client.get(_detail(pk)).json()['final_report'] is None
        # ... owner must still get the report ...
        assert auth_client.get(_detail(pk)).json()['final_report'] == _REPORT
        # ... and the owner's cached payload must not leak back.
        assert other_auth_client.get(_detail(pk)).json()['final_report'] is None
        assert api_client.get(_detail(pk)).json()['final_report'] is None
        assert auth_client.get(_detail(pk)).json()['final_report'] == _REPORT


@pytest.mark.django_db
class TestUserProjectsListOwnerOnlyReport:

    def _url(self, profile):
        return f'/api/v1/users/{profile.user.id}/projects/'

    def test_non_owner_list_report_null(self, other_auth_client, user_profile):
        _board(user_profile)
        result = other_auth_client.get(self._url(user_profile)).json()['results'][0]
        assert result['final_report'] is None
        assert result['report_stale'] is False
        assert 'axis_scores' not in result

    def test_anonymous_list_report_null(self, api_client, user_profile):
        _board(user_profile)
        result = api_client.get(self._url(user_profile)).json()['results'][0]
        assert result['final_report'] is None

    def test_owner_list_keeps_report(self, auth_client, user_profile):
        _board(user_profile)
        result = auth_client.get(self._url(user_profile)).json()['results'][0]
        assert result['final_report'] == _REPORT


@pytest.mark.django_db
class TestRecommendationsOwnerOnly:

    def test_anonymous_recommendations_401(self, api_client, user_profile):
        project = _board(user_profile)
        resp = api_client.get(f'/api/v1/projects/{project.project_id}/recommendations/')
        assert resp.status_code == 401
