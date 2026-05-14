"""
test_discovery.py — Discovery tab feed endpoint and taste helpers coverage.
"""
import numpy as np
import pytest
from unittest.mock import patch

from apps.recommendation.models import Project

_FAKE_TASTE_VEC = np.array([0.1] * 384, dtype=np.float64)


def _card(building_id):
    return {'building_id': building_id}


def _make_cards(building_ids):
    return [_card(bid) for bid in building_ids]


@pytest.mark.django_db
def test_cold_start_returns_random(auth_client):
    with patch('apps.recommendation.views.discovery.engine.get_diverse_random') as mocked:
        mocked.return_value = _make_cards(['B001', 'B002', 'B003'])
        resp = auth_client.get('/api/v1/discovery/', {'cursor': 0, 'limit': 5})
        payload = resp.json()

    assert resp.status_code == 200
    assert payload['taste_state'] == 'cold'
    assert len(payload['cards']) <= 5
    assert payload['has_more'] is False
    assert payload['next_cursor'] is None


@pytest.mark.django_db
def test_warm_returns_taste_ordered(auth_client, user_profile):
    Project.objects.create(
        user=user_profile,
        name='Discovery Project',
        liked_ids=[
            {'id': 'L001', 'intensity': 1.0},
            {'id': 'L002', 'intensity': 1.0},
        ],
        disliked_ids=['D001'],
        saved_ids=[{'id': 'S001', 'saved_at': '2026-05-14T00:00:00Z'}],
    )

    cards = _make_cards(['R001', 'R002', 'R003', 'R004', 'R005', 'R006', 'R007', 'R008', 'R009', 'R010', 'R011', 'R012'])
    with patch('apps.recommendation.views.discovery.engine.compute_user_taste_vector',
               return_value=_FAKE_TASTE_VEC), \
         patch('apps.recommendation.views.discovery.engine.taste_ranked_page') as mocked:
        mocked.return_value = cards
        resp = auth_client.get('/api/v1/discovery/', {'cursor': 0, 'limit': 12})
        payload = resp.json()

    assert resp.status_code == 200
    assert payload['taste_state'] == 'warm'
    assert len(payload['cards']) == 12
    assert payload['cards'][0]['building_id'] == 'R001'
    assert payload['next_cursor'] == 12
    assert payload['has_more'] is True
    assert list(mocked.call_args.args[1]) == ['L001', 'L002', 'D001', 'S001']
    blocked_ids = {'L001', 'L002', 'D001', 'S001'}
    assert blocked_ids.isdisjoint(card['building_id'] for card in payload['cards'])


@pytest.mark.django_db
def test_pagination_cursor_advances(auth_client, user_profile):
    Project.objects.create(user=user_profile, liked_ids=[{'id': 'L001', 'intensity': 1.0}], name='Discovery Project')
    all_cards = _make_cards([f'B{i:03d}' for i in range(30)])

    def _taste_ranked_page(v_taste, exclude_ids, limit, offset):
        start = int(offset)
        return all_cards[start:start + int(limit)]

    with patch('apps.recommendation.views.discovery.engine.compute_user_taste_vector',
               return_value=_FAKE_TASTE_VEC), \
         patch('apps.recommendation.views.discovery.engine.taste_ranked_page', side_effect=_taste_ranked_page) as mocked:
        first = auth_client.get('/api/v1/discovery/?cursor=0&limit=12')
        second = auth_client.get('/api/v1/discovery/?cursor=12&limit=12')
        payload_1 = first.json()
        payload_2 = second.json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert payload_1['taste_state'] == 'warm'
    assert payload_2['taste_state'] == 'warm'
    assert payload_1['next_cursor'] == 12
    assert payload_1['cards'][0]['building_id'] == 'B000'
    assert payload_2['cards'][0]['building_id'] == 'B012'
    first_ids = {card['building_id'] for card in payload_1['cards']}
    second_ids = {card['building_id'] for card in payload_2['cards']}
    assert first_ids.isdisjoint(second_ids)
    assert mocked.call_count == 2


@pytest.mark.django_db
def test_invalid_params_return_400(auth_client):
    assert auth_client.get('/api/v1/discovery/?cursor=-1').status_code == 400
    assert auth_client.get('/api/v1/discovery/?limit=999').status_code == 400
    assert auth_client.get('/api/v1/discovery/?limit=abc').status_code == 400


@pytest.mark.django_db
def test_unauthenticated_returns_401(api_client):
    assert api_client.get('/api/v1/discovery/').status_code == 401


# ---------------------------------------------------------------------------
# BoardSurpriseView tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_surprise_cold_start_returns_random(auth_client):
    """Zero likes → cold start; title must contain 'Discover'."""
    with patch('apps.recommendation.views.discovery.engine.get_diverse_random') as mocked:
        mocked.return_value = _make_cards([f'B{i:03d}' for i in range(10)])
        resp = auth_client.get('/api/v1/recommendations/board-surprise/')
        payload = resp.json()

    assert resp.status_code == 200
    assert 'Discover' in payload['title']
    assert len(payload['cards']) == 10
    assert 'rationale' in payload


@pytest.mark.django_db
def test_surprise_warm_returns_taste_ranked(auth_client, user_profile):
    """At least one like → warm path; title contains 'Curated'; excluded IDs absent from cards."""
    Project.objects.create(
        user=user_profile,
        name='Surprise Project',
        liked_ids=[
            {'id': 'L001', 'intensity': 1.0},
            {'id': 'L002', 'intensity': 1.0},
        ],
        disliked_ids=['D001'],
        saved_ids=[{'id': 'S001', 'saved_at': '2026-05-14T00:00:00Z'}],
    )

    cards = _make_cards(['R001', 'R002', 'R003', 'R004', 'R005',
                         'R006', 'R007', 'R008', 'R009', 'R010'])
    with patch('apps.recommendation.views.discovery.engine.compute_user_taste_vector',
               return_value=_FAKE_TASTE_VEC), \
         patch('apps.recommendation.views.discovery.engine.taste_ranked_page') as mocked:
        mocked.return_value = cards
        resp = auth_client.get('/api/v1/recommendations/board-surprise/')
        payload = resp.json()

    assert resp.status_code == 200
    assert 'Curated' in payload['title']
    assert len(payload['cards']) == 10
    blocked_ids = {'L001', 'L002', 'D001', 'S001'}
    assert blocked_ids.isdisjoint(card['building_id'] for card in payload['cards'])
    # Verify exclude_ids ordering: liked → disliked → saved
    assert list(mocked.call_args.args[1]) == ['L001', 'L002', 'D001', 'S001']


@pytest.mark.django_db
def test_surprise_unauthenticated_returns_401(api_client):
    assert api_client.get('/api/v1/recommendations/board-surprise/').status_code == 401
