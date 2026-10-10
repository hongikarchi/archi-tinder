"""Taste-start views: client tags are REBUILT server-side (match/labels/prob never trusted)."""
from unittest import mock

import pytest
from django.conf import settings

from apps.recommendation.taste_start import RecognitionResult
from apps.recommendation.taste_start.recognizer import make_tag
from apps.recommendation.tests.test_taste_start_matching import (  # noqa: F401  (fixtures)
    CARDS, RECOGNIZE, api_client, auth_client,
)

V = 'apps.recommendation.views.taste_start.'


@pytest.mark.parametrize('tag', [
    {'axis': 'year', 'value': [1500, 2000]}, {'axis': 'year', 'value': [2000]},
    {'axis': 'year', 'value': 'x'}, {'axis': 'year', 'value': [None, None]},
    {'axis': 'year', 'value': ['a', 2000]}, {'axis': 'year', 'value': [2000, 1990]},
    {'axis': 'year', 'value': [True, 2000]}, {'axis': 'year', 'value': [2000, 2200]},
    {'axis': 'nope', 'value': 'x'}, {'axis': 'era', 'value': 'recent'},
    {'axis': 'country', 'value': 'Atlantis'}, {'axis': 'country', 'value': ['Japan']},
    {'axis': 'use', 'value': 'Nonsense'},
    {'axis': 'material', 'value': 'wood', 'polarity': 'maybe'},
])
def test_invalid_tags_400_not_500(auth_client, tag):  # noqa: F811
    assert auth_client.post(CARDS, {'tags': [tag]}, format='json').status_code == 400
    with mock.patch(V + 'recognize_tags') as rec:
        r = auth_client.post(RECOGNIZE, {'text': 'a', 'prev_tags': [tag]}, format='json')
    assert r.status_code == 400
    rec.assert_not_called()


def test_forged_match_is_rebuilt(auth_client):  # noqa: F811
    forged = {
        'axis': 'country', 'value': 'Japan', 'polarity': 'want', 'label_ko': 'HACK',
        'prob': 99,
        'match': {'location_country': ['x%d' % i for i in range(5000)],
                  'evil_column; DROP TABLE': ['y']},
    }
    seen = {}

    def fake_top(tags, exclude_ids=(), limit=3):
        seen['tags'] = tags
        return []

    with mock.patch(V + 'matching.top_matches', side_effect=fake_top), \
            mock.patch(V + 'engine.get_buildings_by_ids', return_value=[]):
        r = auth_client.post(CARDS, {'tags': [forged]}, format='json')
    assert r.status_code == 200
    tag = seen['tags'][0]
    assert tag.match == make_tag('country', 'Japan').match
    assert tag.label_ko != 'HACK' and tag.prob is None


def test_forged_match_ignored_for_prev_tags(auth_client):  # noqa: F811
    forged = {'axis': 'style', 'value': 'Minimalist',
              'match': {'bad_col': ['z'], 'style': ['q'] * 5000}}
    captured = {}

    def fake_rec(text, prev):
        captured['prev'] = prev
        return RecognitionResult(tags=[], source='dictionary')

    with mock.patch(V + 'recognize_tags', side_effect=fake_rec), \
            mock.patch(V + 'engine.get_diverse_random', return_value=[]):
        r = auth_client.post(RECOGNIZE, {'text': 'a', 'prev_tags': [forged]}, format='json')
    assert r.status_code == 200
    assert captured['prev'][0].match == make_tag('style', 'Minimalist').match


def test_typology_use_tag_kept_and_year_roundtrip(auth_client):  # noqa: F811
    seen = {}

    def fake_top(tags, exclude_ids=(), limit=3):
        seen['tags'] = tags
        return []

    body = [make_tag('use', 'Housing', kind='typology').to_dict(),
            make_tag('year', (2000, None)).to_dict()]
    with mock.patch(V + 'matching.top_matches', side_effect=fake_top), \
            mock.patch(V + 'engine.get_buildings_by_ids', return_value=[]):
        r = auth_client.post(CARDS, {'tags': body}, format='json')
    assert r.status_code == 200
    assert 'typology_primary' in seen['tags'][0].match
    assert seen['tags'][1].match == {'year_min': 2000, 'year_max': None}


def test_cards_throttle_is_normal_user_throttle():
    from rest_framework.throttling import UserRateThrottle
    from apps.recommendation.views.taste_start import TasteCardsView
    assert TasteCardsView.throttle_classes == [UserRateThrottle]
    assert 'user' in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
