"""Feedback endpoints: validation, upsert, cancel, auth. Buildings DB fetch is mocked."""
from unittest import mock

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.accounts.models import UserProfile
from apps.feedback.models import CardReport, QueryReport

CARD = '/api/v1/feedback/card-reports/'
CARD_CANCEL = '/api/v1/feedback/card-reports/cancel/'
QUERY = '/api/v1/feedback/query-reports/'
QUERY_CANCEL = '/api/v1/feedback/query-reports/cancel/'
FETCH = 'apps.feedback.views._fetch_building'

ROW = {
    'program': 'Housing', 'typology_primary': 'Apartment', 'style': 'Modernism',
    'atmosphere': 'Warm', 'color_tone': 'Warm', 'location_country': 'Japan',
    'location_city': 'Tokyo', 'project_year': 2005, 'material_visual': ['Wood'],
    'architectural_elements': ['Garden'],
    'visual_description': 'Units are separated by a shared garden and a path.',
}

TAGS = [
    {'axis': 'country', 'value': 'Japan', 'prob': 0.9},
    {'axis': 'style', 'value': 'Brutalist', 'prob': 7},
    {'axis': 'element', 'value': 'Garden', 'prob': 'x'},
]


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache
    cache.clear()


@pytest.fixture
def client(db):
    user = User.objects.create_user('fb-user', password='x')
    UserProfile.objects.create(user=user, display_name='FB')
    c = APIClient()
    c.force_authenticate(user=user)
    c.profile = user.profile
    return c


def card_body(**over):
    body = {
        'round_key': 'r1760340000000', 'query_text': 'warm japan house', 'tags': TAGS,
        'source': 'jev', 'language': 'ko', 'canonical_bld_id': 'bld_000344',
        'card_rank': 1, 'hit': 2, 'total': 3, 'reason': 'tag', 'sub_reasons': [],
        'wrong_tags': [{'axis': 'element', 'value': 'Garden'}], 'comment': '',
    }
    body.update(over)
    return body


def query_body(**over):
    body = {
        'round_key': 'r1760340000001', 'query_text': 'q', 'tags': TAGS, 'source': 'dictionary',
        'language': 'en', 'wrong_tags': [{'axis': 'country', 'value': 'Japan'}], 'comment': '',
    }
    body.update(over)
    return body


# -- auth ---------------------------------------------------------------------
@pytest.mark.parametrize('url', [CARD, CARD_CANCEL, QUERY, QUERY_CANCEL])
def test_unauthenticated(url):
    assert APIClient().post(url, {}, format='json').status_code in (401, 403)


# -- card report: validation --------------------------------------------------
@pytest.mark.parametrize('over', [
    {'reason': None, 'wrong_tags': [], 'comment': '  '},           # neither reason nor comment
    {'reason': 'photo', 'sub_reasons': ['country'], 'wrong_tags': []},   # sub_reason of another reason
    {'reason': 'photo', 'sub_reasons': ['bogus'], 'wrong_tags': []},
    {'reason': 'tag', 'sub_reasons': ['not_visible']},
    {'reason': 'nope'},
    {'wrong_tags': [{'axis': 'style', 'value': 'Wood'}]},          # not among tags
    {'reason': 'info', 'sub_reasons': ['year']},                   # wrong_tags only with reason tag
    {'card_rank': 0}, {'card_rank': 4}, {'card_rank': True},
    {'hit': -1}, {'total': 31},
    {'round_key': ''}, {'round_key': 'x' * 65}, {'round_key': 'abc'}, {'round_key': 'r12'},
    {'sub_reasons': ['photo'] * 31},
    {'wrong_tags': [{'axis': 'element', 'value': 'Garden'}] * 31},
    {'wrong_tags': [{'axis': ['x'], 'value': 'Garden'}]},
    {'wrong_tags': [{'axis': 'element', 'value': {'a': 1}}]},
    {'wrong_tags': [{'axis': 'element', 'value': [1]}]}, {'wrong_tags': ['x']},
    {'canonical_bld_id': ''}, {'canonical_bld_id': 'b' * 21},
    {'source': 'gpt'}, {'language': 'fr'},
    {'comment': 'c' * 501}, {'query_text': 'q' * 501},
    {'tags': [{'axis': 'country', 'value': 'Atlantis'}]},
    {'tags': 'nope'},
])
def test_card_report_400(client, over):
    with mock.patch(FETCH, return_value=dict(ROW)):
        r = client.post(CARD, card_body(**over), format='json')
    assert r.status_code == 400 and 'detail' in r.json()
    assert CardReport.objects.count() == 0


def test_card_report_unknown_building(client):
    with mock.patch(FETCH, return_value=None):
        r = client.post(CARD, card_body(), format='json')
    assert r.status_code == 400 and r.json()['detail'] == 'unknown building'


def test_card_report_comment_only_ok(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        r = client.post(CARD, card_body(reason=None, wrong_tags=[], comment='photo is odd'),
                        format='json')
    assert r.status_code == 201
    assert CardReport.objects.get().reason is None


# -- card report: storage + upsert --------------------------------------------
def test_card_report_stores_snapshot_explained_tags_and_clamped_prob(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        r = client.post(CARD, card_body(wrong_tags=[
            {'axis': 'element', 'value': 'Garden'}, {'axis': 'style', 'value': 'Brutalist'}]),
            format='json')
    assert r.status_code == 201 and r.json()['status'] == 'unreviewed'
    obj = CardReport.objects.get()
    assert obj.user == client.profile
    assert obj.building_snapshot['location_city'] == 'Tokyo'
    assert 'visual_description' not in obj.building_snapshot
    assert [t['prob'] for t in obj.tags] == [0.9, 1.0, None]   # 7 clamped, 'x' -> None
    assert obj.tags[0]['label_en']                              # canonical, rebuilt server-side
    garden, brut = obj.wrong_tags
    assert garden['matched'] is True and garden['direction'] == 'not_actually_present'
    assert {'column': 'architectural_elements', 'value': 'Garden'} in garden['matched_via']
    assert any(v['column'] == 'visual_description' and 'separated' in v['excerpt']
               for v in garden['matched_via'])
    assert brut['matched'] is False and brut['direction'] == 'actually_present'


def test_card_report_upsert_edits_same_row_and_resets_status(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        first = client.post(CARD, card_body(), format='json')
        CardReport.objects.update(status='fixed')
        second = client.post(CARD, card_body(reason='etc', wrong_tags=[], comment='changed'),
                             format='json')
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()['id'] == second.json()['id']
    assert CardReport.objects.count() == 1
    obj = CardReport.objects.get()
    assert obj.reason == 'etc' and obj.comment == 'changed' and obj.status == 'unreviewed'


def test_card_cancel_keeps_row(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        client.post(CARD, card_body(), format='json')
    r = client.post(CARD_CANCEL, {'round_key': 'r1760340000000', 'canonical_bld_id': 'bld_000344'},
                    format='json')
    assert r.status_code == 204
    assert CardReport.objects.get().status == 'user_canceled'


def test_card_cancel_404(client):
    r = client.post(CARD_CANCEL, {'round_key': 'r1760340000099', 'canonical_bld_id': 'x'}, format='json')
    assert r.status_code == 404


# -- query report ---------------------------------------------------------------
@pytest.mark.parametrize('over', [
    {'wrong_tags': [], 'comment': ''},
    {'wrong_tags': [], 'comment': '   '},
    {'wrong_tags': [{'axis': 'style', 'value': 'Wood'}]},
    {'wrong_tags': 'x'}, {'round_key': 'bad'}, {'wrong_tags': [{'axis': [], 'value': 'x'}]},
    {'source': 'x'}, {'language': 'x'}, {'round_key': ''}, {'comment': 'c' * 501},
])
def test_query_report_400(client, over):
    assert client.post(QUERY, query_body(**over), format='json').status_code == 400
    assert QueryReport.objects.count() == 0


def test_query_report_upsert_and_cancel(client):
    a = client.post(QUERY, query_body(), format='json')
    assert a.status_code == 201
    QueryReport.objects.update(status='not_fixed')
    b = client.post(QUERY, query_body(wrong_tags=[], comment='mis-read'), format='json')
    assert b.status_code == 200 and a.json()['id'] == b.json()['id']
    obj = QueryReport.objects.get()
    assert obj.status == 'unreviewed' and obj.comment == 'mis-read' and obj.wrong_tags == []
    assert obj.tags[0]['prob'] == 0.9

    assert client.post(QUERY_CANCEL, {'round_key': 'r1760340000001'}, format='json').status_code == 204
    assert QueryReport.objects.get().status == 'user_canceled'
    assert client.post(QUERY_CANCEL, {'round_key': 'r1760340000099'}, format='json').status_code == 404


def test_reports_are_per_user(client):
    other = User.objects.create_user('fb-other', password='x')
    UserProfile.objects.create(user=other, display_name='O')
    client.post(QUERY, query_body(), format='json')
    c2 = APIClient()
    c2.force_authenticate(user=other)
    assert c2.post(QUERY_CANCEL, {'round_key': 'r1760340000001'}, format='json').status_code == 404
    assert QueryReport.objects.get().status == 'unreviewed'


# -- status handling ------------------------------------------------------------
def test_card_resend_identical_keeps_verdict(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        client.post(CARD, card_body(), format='json')
        CardReport.objects.update(status='fixed')
        r = client.post(CARD, card_body(), format='json')
    assert r.status_code == 200 and r.json()['status'] == 'fixed'
    assert CardReport.objects.get().status == 'fixed'


def test_card_resend_after_cancel_reopens(client):
    with mock.patch(FETCH, return_value=dict(ROW)):
        client.post(CARD, card_body(), format='json')
        CardReport.objects.update(status='user_canceled')
        r = client.post(CARD, card_body(), format='json')
    assert r.json()['status'] == 'unreviewed'


def test_query_resend_identical_keeps_verdict(client):
    client.post(QUERY, query_body(), format='json')
    QueryReport.objects.update(status='not_fixed')
    assert client.post(QUERY, query_body(), format='json').json()['status'] == 'not_fixed'
    QueryReport.objects.update(status='user_canceled')
    assert client.post(QUERY, query_body(), format='json').json()['status'] == 'unreviewed'


def test_wrong_tag_stores_polarity(client):
    tags = [{'axis': 'element', 'value': 'Garden', 'polarity': 'exclude'}]
    with mock.patch(FETCH, return_value=dict(ROW)):
        client.post(CARD, card_body(tags=tags, wrong_tags=[{'axis': 'element', 'value': 'Garden'}]),
                    format='json')
    assert CardReport.objects.get().wrong_tags[0]['polarity'] == 'exclude'
