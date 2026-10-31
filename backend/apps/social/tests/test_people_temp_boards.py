"""
Unconfirmed (is_temp=True) boards must not surface to non-owners, and the feed
reports the requester's own discoverability (me_discoverable / me_hint).

Project.visibility defaults to 'public' (FULL-MESSAGING-5), so an in-progress
temp board is public by default. These tests pin that such a board never
leaks before the save-confirm step, while the owner still sees it.
"""
import pytest

from apps.recommendation.models import Project
from apps.social.tests.test_board_feed import _board, _client, _ids, _person

FEED = '/api/v1/people/'


def _img_url(project):
    return f'/api/v1/people/boards/{project.pk}/report-image/'


@pytest.mark.django_db
class TestTempBoardNotShared:
    def test_new_board_defaults_public(self):
        _, p = _person('b')
        assert Project.objects.create(user=p, name='x').visibility == 'public'

    def test_temp_board_not_in_feed(self):
        au, _ = _person('a')
        _, pb = _person('b')
        _board(pb, is_temp=True)
        assert _ids(_client(au).get(FEED)) == []

    def test_confirmed_board_in_feed(self):
        au, _ = _person('a')
        _, pb = _person('b')
        b = _board(pb)
        assert _ids(_client(au).get(FEED)) == [str(b.pk)]

    def test_board_report_image_404_for_temp(self):
        au, _ = _person('a')
        _, pb = _person('b')
        assert _client(au).get(_img_url(_board(pb, is_temp=True))).status_code == 404

    def test_board_report_image_served_for_confirmed(self):
        au, _ = _person('a')
        _, pb = _person('b')
        assert _client(au).get(_img_url(_board(pb))).status_code == 200

    def test_project_report_image_non_owner_404_for_temp(self):
        au, _ = _person('a')
        _, pb = _person('b')
        t = _board(pb, is_temp=True)
        assert _client(au).get(f'/api/v1/projects/{t.pk}/report-image/').status_code == 404

    def test_project_report_image_owner_reads_own_temp(self):
        bu, pb = _person('b')
        t = _board(pb, is_temp=True)
        assert _client(bu).get(f'/api/v1/projects/{t.pk}/report-image/').status_code == 200


@pytest.mark.django_db
class TestTempBoardPerObjectGates:
    def test_detail_non_owner_denied_like_private(self):
        au, _ = _person('a')
        _, pb = _person('b')
        temp = _board(pb, is_temp=True)
        private = _board(pb, visibility='private')
        c = _client(au)
        r_temp = c.get(f'/api/v1/projects/{temp.pk}/')
        r_priv = c.get(f'/api/v1/projects/{private.pk}/')
        assert r_temp.status_code == r_priv.status_code == 403
        assert r_temp.json() == r_priv.json()

    def test_detail_owner_ok(self):
        bu, pb = _person('b')
        temp = _board(pb, is_temp=True)
        assert _client(bu).get(f'/api/v1/projects/{temp.pk}/').status_code == 200

    def test_recommendations_non_owner_denied_preexisting(self):
        au, _ = _person('a')
        _, pb = _person('b')
        temp = _board(pb, is_temp=True)
        assert _client(au).get(f'/api/v1/projects/{temp.pk}/recommendations/').status_code == 403

    def test_reaction_post_non_owner_denied(self):
        au, _ = _person('a')
        _, pb = _person('b')
        temp = _board(pb, is_temp=True)
        assert _client(au).post(f'/api/v1/projects/{temp.pk}/react/').status_code == 403

    def test_reactors_list_non_owner_denied_owner_ok(self):
        au, _ = _person('a')
        bu, pb = _person('b')
        temp = _board(pb, is_temp=True)
        url = f'/api/v1/projects/{temp.pk}/reactors/'
        assert _client(au).get(url).status_code == 403
        assert _client(bu).get(url).status_code == 200

    def test_profile_board_list_hides_temp_from_non_owner(self):
        au, _ = _person('a')
        bu, pb = _person('b')
        conf = _board(pb, 'conf')
        temp = _board(pb, 'temp', is_temp=True)

        def ids(client):
            r = client.get(f'/api/v1/users/{bu.id}/')
            assert r.status_code == 200, r.content
            return {b['project_id'] for b in r.json()['boards']['items']}

        assert ids(_client(au)) == {str(conf.pk)}
        assert ids(_client(bu)) == {str(conf.pk), str(temp.pk)}


@pytest.mark.django_db
class TestMeDiscoverable:
    @staticmethod
    def _me(client, **params):
        resp = client.get(FEED, params)
        assert resp.status_code == 200, resp.content
        return resp.json()['me_discoverable'], resp.json()['me_hint']

    def test_public_saved_board_with_image(self):
        u, p = _person('a')
        _board(p)
        assert self._me(_client(u)) == (True, None)

    def test_no_board_at_all(self):
        u, _ = _person('a')
        assert self._me(_client(u)) == (False, 'no_public_report_image')

    def test_only_private_board_image(self):
        u, p = _person('a')
        _board(p, visibility='private')
        assert self._me(_client(u)) == (False, 'no_public_report_image')

    def test_only_temp_public_board_image(self):
        u, p = _person('a')
        _board(p, is_temp=True)
        assert self._me(_client(u)) == (False, 'unsaved_board')

    def test_temp_plus_confirmed_is_discoverable(self):
        u, p = _person('a')
        _board(p, is_temp=True)
        _board(p, 'ok')
        assert self._me(_client(u)) == (True, None)

    def test_opted_out(self):
        u, p = _person('a', opt_in=False)
        _board(p)
        assert self._me(_client(u)) == (False, 'opted_out')

    def test_independent_of_filter_and_cursor(self):
        u, p = _person('a', type_code='CLON')
        _board(p)
        body = _client(u).get(FEED, {'filter': 'RSDT'}).json()
        assert body['results'] == []
        assert (body['me_discoverable'], body['me_hint']) == (True, None)
        body = _client(u).get(FEED, {'filter': 'inspired'}).json()
        assert body['results'] == []
        assert body['me_discoverable'] is True

    def test_me_fields_present_on_cursor_page(self):
        u, p = _person('a', type_code='CLON')
        _board(p)
        _, pb = _person('b', type_code='CLON')
        _board(pb, 'b1', age_min=1)
        _board(pb, 'b2', age_min=2)
        c = _client(u)
        first = c.get(FEED, {'page_size': 1}).json()
        assert first['next_cursor']
        second = c.get(FEED, {'page_size': 1, 'cursor': first['next_cursor']}).json()
        assert (second['me_discoverable'], second['me_hint']) == (True, None)
