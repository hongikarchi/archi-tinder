"""
Unconfirmed (is_temp=True) boards must not surface through people discovery.

Project.visibility now defaults to 'public' (FULL-MESSAGING-5), so an
in-progress temp board is public by default. These tests pin that such a board
neither makes its owner eligible for the people feed nor is served by the
report-image endpoints before the save-confirm step.
"""
import pytest

from apps.accounts.models import PersonalityProfile
from apps.recommendation.models import Project


def _personality(profile, axis=0.1):
    return PersonalityProfile.objects.create(
        user=profile,
        axis_1=axis, axis_2=axis, axis_3=axis, axis_4=axis, axis_5=axis,
        type_code='ABCD',
        discovery_opt_in=True,
    )


def _board(profile, **kwargs):
    return Project.objects.create(
        user=profile,
        name='b',
        report_image='aGVsbG8=',
        report_image_mime='image/png',
        **kwargs,
    )


def _feed_user_ids(client):
    resp = client.get('/api/v1/people/')
    assert resp.status_code == 200, resp.content
    return {r['user_id'] for r in resp.json()['results']}


@pytest.mark.django_db
class TestTempBoardNotDiscoverable:
    def test_new_board_defaults_public(self, user_b):
        _, profile_b = user_b
        assert _board(profile_b).visibility == 'public'

    def test_temp_board_owner_not_in_feed(self, user_a, user_b, auth_client_a):
        _, profile_a = user_a
        user_b_obj, profile_b = user_b
        _personality(profile_a)
        _personality(profile_b)
        _board(profile_b, is_temp=True)
        assert user_b_obj.id not in _feed_user_ids(auth_client_a)

    def test_confirmed_board_owner_in_feed(self, user_a, user_b, auth_client_a):
        _, profile_a = user_a
        user_b_obj, profile_b = user_b
        _personality(profile_a)
        _personality(profile_b)
        _board(profile_b, is_temp=False)
        assert user_b_obj.id in _feed_user_ids(auth_client_a)

    def test_people_report_image_404_for_temp_board(self, user_b, auth_client_a):
        user_b_obj, profile_b = user_b
        _board(profile_b, is_temp=True)
        resp = auth_client_a.get(f'/api/v1/people/{user_b_obj.id}/report-image/')
        assert resp.status_code == 404

    def test_people_report_image_served_for_confirmed_board(self, user_b, auth_client_a):
        user_b_obj, profile_b = user_b
        _board(profile_b, is_temp=False)
        resp = auth_client_a.get(f'/api/v1/people/{user_b_obj.id}/report-image/')
        assert resp.status_code == 200

    def test_project_report_image_non_owner_404_for_temp_board(self, user_b, auth_client_a):
        _, profile_b = user_b
        project = _board(profile_b, is_temp=True)
        resp = auth_client_a.get(f'/api/v1/projects/{project.project_id}/report-image/')
        assert resp.status_code == 404

    def test_project_report_image_owner_can_read_own_temp_board(self, user_b, auth_client_b):
        _, profile_b = user_b
        project = _board(profile_b, is_temp=True)
        resp = auth_client_b.get(f'/api/v1/projects/{project.project_id}/report-image/')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTempBoardPerObjectGates:
    def test_detail_non_owner_denied_like_private(self, user_b, auth_client_a):
        _, profile_b = user_b
        temp = _board(profile_b, is_temp=True)
        private = _board(profile_b, visibility='private')
        r_temp = auth_client_a.get(f'/api/v1/projects/{temp.project_id}/')
        r_priv = auth_client_a.get(f'/api/v1/projects/{private.project_id}/')
        assert r_temp.status_code == r_priv.status_code == 403
        assert r_temp.json() == r_priv.json()

    def test_detail_owner_ok(self, user_b, auth_client_b):
        _, profile_b = user_b
        temp = _board(profile_b, is_temp=True)
        assert auth_client_b.get(f'/api/v1/projects/{temp.project_id}/').status_code == 200

    def test_recommendations_non_owner_denied(self, user_b, auth_client_a):
        _, profile_b = user_b
        temp = _board(profile_b, is_temp=True)
        resp = auth_client_a.get(f'/api/v1/projects/{temp.project_id}/recommendations/')
        assert resp.status_code == 403

    def test_reaction_post_non_owner_denied(self, user_b, auth_client_a):
        _, profile_b = user_b
        temp = _board(profile_b, is_temp=True)
        resp = auth_client_a.post(f'/api/v1/projects/{temp.project_id}/react/')
        assert resp.status_code == 403


@pytest.mark.django_db
class TestMeDiscoverable:
    def _me(self, client):
        resp = client.get('/api/v1/people/')
        assert resp.status_code == 200, resp.content
        body = resp.json()
        return body['me_discoverable'], body['me_hint']

    def test_public_saved_board_with_image(self, user_a, auth_client_a):
        _, profile_a = user_a
        _personality(profile_a)
        _board(profile_a, is_temp=False)
        assert self._me(auth_client_a) == (True, None)

    def test_only_private_board_image(self, user_a, auth_client_a):
        _, profile_a = user_a
        _personality(profile_a)
        _board(profile_a, visibility='private', is_temp=False)
        assert self._me(auth_client_a) == (False, 'no_public_report_image')

    def test_only_temp_public_board_image(self, user_a, auth_client_a):
        _, profile_a = user_a
        _personality(profile_a)
        _board(profile_a, is_temp=True)
        assert self._me(auth_client_a) == (False, 'no_public_report_image')

    def test_opted_out(self, user_a, auth_client_a):
        _, profile_a = user_a
        p = _personality(profile_a)
        p.discovery_opt_in = False
        p.save()
        _board(profile_a, is_temp=False)
        assert self._me(auth_client_a) == (False, 'opted_out')

    def test_type_code_filter_excluding_me_still_true(self, user_a, auth_client_a):
        _, profile_a = user_a
        _personality(profile_a)  # type_code 'ABCD'
        _board(profile_a, is_temp=False)
        resp = auth_client_a.get('/api/v1/people/?filter=CLON')
        assert resp.status_code == 200
        body = resp.json()
        assert body['results'] == []
        assert body['me_discoverable'] is True
        assert body['me_hint'] is None
