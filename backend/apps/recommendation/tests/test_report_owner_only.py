"""
test_report_owner_only.py -- persona report visibility.

Detail GET: non-owners (incl. anonymous) of a PUBLIC board get final_report +
axis_scores read-only; analysis_report stays owner-only; report_stale is always
False for them. Private boards stay 403. List serializers never expose report
text to non-owners.
"""
import pytest
from django.core.cache import cache

from apps.recommendation.models import Project

_REPORT = {
    'one_liner': 'secret taste',
    'source_signature': 'stale-on-purpose',
    'source_count': 3,
    'generation_id': 'gen-1',
}
_VIEWER_REPORT = {'one_liner': 'secret taste'}
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

    def test_non_owner_public_sees_report_structure_kept(self, other_auth_client, user_profile):
        project = _board(user_profile)
        resp = other_auth_client.get(_detail(project.project_id))
        assert resp.status_code == 200
        data = resp.json()
        assert data['final_report'] == _VIEWER_REPORT
        assert data['axis_scores'] == _AXES
        assert 'disliked_ids' not in data
        assert data['analysis_report'] is None
        assert data['report_stale'] is False
        assert 'conversation_history' not in data
        assert data['name'] == 'B'
        assert data['visibility'] == 'public'
        assert data['liked_ids'] == project.liked_ids
        assert data['report_image'] == 'IMG'
        assert data['report_image_mime'] == 'image/png'
        assert data['latest_session_id'] is None

    def test_viewer_payload_strips_internal_keys_owner_keeps(
        self, auth_client, other_auth_client, api_client, user_profile,
    ):
        pk = _board(user_profile).project_id
        for client in (other_auth_client, api_client):
            report = client.get(_detail(pk)).json()['final_report']
            for key in ('source_signature', 'source_count', 'generation_id'):
                assert key not in report
        owner = auth_client.get(_detail(pk)).json()['final_report']
        for key in ('source_signature', 'source_count', 'generation_id'):
            assert key in owner
        # stored dict untouched
        assert Project.objects.get(project_id=pk).final_report == _REPORT

    def test_anonymous_public_sees_report(self, api_client, user_profile):
        data = api_client.get(_detail(_board(user_profile).project_id)).json()
        assert data['final_report'] == _VIEWER_REPORT
        assert data['axis_scores'] == _AXES
        assert data['analysis_report'] is None
        assert data['report_stale'] is False
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
        # Owner sees stale flag + analysis_report; viewers never do, in any order.
        for _ in range(2):
            viewer = other_auth_client.get(_detail(pk)).json()
            assert viewer['report_stale'] is False and viewer['analysis_report'] is None
            anon = api_client.get(_detail(pk)).json()
            assert anon['report_stale'] is False and anon['analysis_report'] is None
            owner = auth_client.get(_detail(pk)).json()
            assert owner['report_stale'] is True and owner['analysis_report'] == {'x': 1}

    def test_temp_public_board_403_for_non_owner(self, other_auth_client, user_profile):
        project = _board(user_profile)
        Project.objects.filter(pk=project.pk).update(is_temp=True)
        assert other_auth_client.get(_detail(project.project_id)).status_code == 403

    def test_visibility_flip_to_private_hides_report(
        self, auth_client, other_auth_client, user_profile,
    ):
        pk = _board(user_profile).project_id
        assert other_auth_client.get(_detail(pk)).json()['final_report'] == _VIEWER_REPORT  # warm cache
        auth_client.patch(_detail(pk), {'visibility': 'private'}, format='json')
        assert other_auth_client.get(_detail(pk)).status_code == 403


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
class TestViewerEndpoints:

    def test_anonymous_private_recommendations_404(self, api_client, user_profile):
        project = _board(user_profile, visibility='private')
        resp = api_client.get(f'/api/v1/projects/{project.project_id}/recommendations/')
        assert resp.status_code == 404

    def test_anonymous_public_recommendations_200(self, api_client, user_profile):
        project = _board(user_profile)
        resp = api_client.get(f'/api/v1/projects/{project.project_id}/recommendations/')
        assert resp.status_code == 200
        assert resp.json() == {'predicted_like_images': []}

    def test_architects_public_non_owner_and_anon_200(
        self, other_auth_client, api_client, user_profile,
    ):
        from unittest.mock import MagicMock, patch
        project = _board(user_profile)
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        url = f'/api/v1/projects/{project.project_id}/recommended_architects/'
        with patch('apps.recommendation.views.office_recommendation.connections',
                   {'buildings': conn}):
            assert other_auth_client.get(url).status_code == 200
            assert api_client.get(url).status_code == 200

    def test_architects_private_non_owner_and_anon_404(
        self, other_auth_client, api_client, user_profile,
    ):
        project = _board(user_profile, visibility='private')
        url = f'/api/v1/projects/{project.project_id}/recommended_architects/'
        assert other_auth_client.get(url).status_code == 404
        assert api_client.get(url).status_code == 404

    def test_anonymous_private_temp_unknown_identical_404(self, api_client, user_profile):
        import uuid
        private = _board(user_profile, visibility='private')
        temp = _board(user_profile)
        Project.objects.filter(pk=temp.pk).update(is_temp=True)
        for suffix in ('recommendations', 'recommended_architects'):
            resps = [
                api_client.get(f'/api/v1/projects/{pk}/{suffix}/')
                for pk in (private.project_id, temp.project_id, uuid.uuid4())
            ]
            assert [r.status_code for r in resps] == [404, 404, 404], suffix
            assert resps[0].json() == resps[1].json() == resps[2].json(), suffix

    def test_architects_endpoint_throttled_429(self, api_client, user_profile):
        from apps.recommendation.throttles import ArchitectRecommendationsThrottle
        project = _board(user_profile, visibility='private')
        url = f'/api/v1/projects/{project.project_id}/recommended_architects/'
        limit = int(ArchitectRecommendationsThrottle.rate.split('/')[0])
        for _ in range(limit):
            assert api_client.get(url).status_code == 404
        assert api_client.get(url).status_code == 429

    def test_writes_stay_owner_only(self, other_auth_client, api_client, user_profile):
        pk = _board(user_profile).project_id
        base = f'/api/v1/projects/{pk}/'
        assert other_auth_client.patch(base, {'visibility': 'private'}, format='json').status_code == 404
        assert other_auth_client.delete(base).status_code == 404
        assert api_client.patch(base, {'visibility': 'private'}, format='json').status_code == 401
        assert api_client.delete(base).status_code == 401
        for suffix in ('report/generate/', 'report/generate-image/'):
            r = other_auth_client.post(base + suffix, {}, format='json')
            assert r.status_code in (403, 404), (suffix, r.status_code)
            assert api_client.post(base + suffix, {}, format='json').status_code == 401
        assert Project.objects.get(project_id=pk).visibility == 'public'
