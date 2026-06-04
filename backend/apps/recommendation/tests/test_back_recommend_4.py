"""
test_back_recommend_4.py — BACK-RECOMMEND-4: Discovery-mode likes feed into
taste vector + exclude-set + cache eviction.

Coverage:
  (1) Discovery-only profile → taste vector non-None  (cold→warm path)
  (2) exclude-set includes a liked_building_id in DiscoveryFeedView
  (3) exclude-set includes a liked_building_id in BoardSurpriseView
  (4) LikedBuildingsView POST evicts taste + discovery-feed caches

Discriminating setup for (1): profile has ZERO Project.liked_ids so the vector
is non-None ONLY because of liked_building_ids — not a pre-existing Project path.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# (1) Discovery-only profile → taste vector non-None
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_discovery_only_profile_yields_taste_vector(user_profile):
    """A profile with zero Project likes but non-empty liked_building_ids
    must return a non-None taste vector (proves the Discovery path is wired in).
    """
    from apps.recommendation.engine import compute_user_taste_vector

    # ZERO Project liked_ids — profile is cold via that path
    assert user_profile.liked_building_ids == [] or not user_profile.liked_building_ids

    # Add a Discovery like directly on the profile
    user_profile.liked_building_ids = ['bld_000001']
    user_profile.save(update_fields=['liked_building_ids'])

    fake_embedding = np.ones(384, dtype=np.float64)
    with patch(
        'apps.recommendation.engine.get_pool_embeddings',
        return_value={'bld_000001': fake_embedding},
    ):
        vec = compute_user_taste_vector(user_profile)

    assert vec is not None, (
        "Expected non-None taste vector for Discovery-only profile; "
        "liked_building_ids not being injected into all_likes."
    )
    assert vec.shape == (384,)


@pytest.mark.django_db
def test_zero_liked_building_ids_still_returns_none(user_profile):
    """Baseline: a truly cold profile (no Project likes, no Discovery likes)
    must still return None. Guards against accidentally caching a zero vector.
    """
    from apps.recommendation.engine import compute_user_taste_vector

    user_profile.liked_building_ids = []
    user_profile.save(update_fields=['liked_building_ids'])

    with patch('apps.recommendation.engine.get_pool_embeddings', return_value={}):
        vec = compute_user_taste_vector(user_profile)

    assert vec is None


# ---------------------------------------------------------------------------
# (2) DiscoveryFeedView exclude-set includes liked_building_ids
# ---------------------------------------------------------------------------

_FAKE_TASTE_VEC = np.array([0.1] * 384, dtype=np.float64)


def _make_cards(ids):
    return [{'canonical_bld_id': bid} for bid in ids]


@pytest.mark.django_db
def test_discovery_feed_excludes_liked_building_ids(auth_client, user_profile):
    """liked_building_ids entries must appear in exclude_ids passed to
    taste_ranked_page so already-liked buildings don't re-surface in the feed.
    """
    user_profile.liked_building_ids = ['bld_d001', 'bld_d002']
    user_profile.save(update_fields=['liked_building_ids'])

    cards = _make_cards([f'R{i:03d}' for i in range(12)])
    with patch(
        'apps.recommendation.views.discovery.engine.compute_user_taste_vector',
        return_value=_FAKE_TASTE_VEC,
    ), patch(
        'apps.recommendation.views.discovery.engine.taste_ranked_page',
    ) as mocked_trp:
        mocked_trp.return_value = cards
        resp = auth_client.get('/api/v1/discovery/', {'cursor': 0, 'limit': 12})

    assert resp.status_code == 200
    exclude_ids = list(mocked_trp.call_args.args[1])
    assert 'bld_d001' in exclude_ids, "bld_d001 must be in exclude_ids for DiscoveryFeedView"
    assert 'bld_d002' in exclude_ids, "bld_d002 must be in exclude_ids for DiscoveryFeedView"


@pytest.mark.django_db
def test_discovery_feed_cold_path_excludes_liked_building_ids(auth_client, user_profile):
    """Even on the cold path (no taste vector), liked_building_ids are excluded
    from the cards returned to the client.
    """
    user_profile.liked_building_ids = ['bld_already_liked']
    user_profile.save(update_fields=['liked_building_ids'])

    # Cold-path: get_diverse_random includes the already-liked building
    raw_cards = _make_cards(['bld_already_liked', 'bld_new_001', 'bld_new_002'])
    with patch(
        'apps.recommendation.views.discovery.engine.get_diverse_random',
        return_value=raw_cards,
    ):
        resp = auth_client.get('/api/v1/discovery/', {'cursor': 0, 'limit': 12})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['taste_state'] == 'cold'
    returned_ids = {c['canonical_bld_id'] for c in payload['cards']}
    assert 'bld_already_liked' not in returned_ids, (
        "Cold path must exclude liked_building_ids from returned cards."
    )


# ---------------------------------------------------------------------------
# (3) BoardSurpriseView exclude-set includes liked_building_ids
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_board_surprise_excludes_liked_building_ids(auth_client, user_profile):
    """liked_building_ids must be in exclude_ids passed to taste_ranked_page
    in BoardSurpriseView so they don't reappear in the Surprise board.
    """
    user_profile.liked_building_ids = ['bld_s001', 'bld_s002']
    user_profile.save(update_fields=['liked_building_ids'])

    cards = _make_cards([f'R{i:03d}' for i in range(10)])
    with patch(
        'apps.recommendation.views.discovery.engine.compute_user_taste_vector',
        return_value=_FAKE_TASTE_VEC,
    ), patch(
        'apps.recommendation.views.discovery.engine.taste_ranked_page',
    ) as mocked_trp:
        mocked_trp.return_value = cards
        resp = auth_client.get('/api/v1/recommendations/board-surprise/')

    assert resp.status_code == 200
    exclude_ids = list(mocked_trp.call_args.args[1])
    assert 'bld_s001' in exclude_ids, "bld_s001 must be in exclude_ids for BoardSurpriseView"
    assert 'bld_s002' in exclude_ids, "bld_s002 must be in exclude_ids for BoardSurpriseView"


# ---------------------------------------------------------------------------
# (4) LikedBuildingsView POST evicts taste + discovery-feed caches
# ---------------------------------------------------------------------------

def _make_buildings_cursor_mock(exists=True):
    cur = MagicMock()
    cur.fetchone.return_value = (1,) if exists else None
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cur)
    cm.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cm
    return conn


@pytest.fixture
def lb_user_and_profile(db):
    from django.contrib.auth.models import User
    from apps.accounts.models import UserProfile
    user = User.objects.create_user(
        username='lb4user', email='lb4@example.com', password='pass123',
    )
    profile = UserProfile.objects.create(user=user, display_name='LB4 User')
    return user, profile


@pytest.fixture
def lb_auth_client(lb_user_and_profile):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    user, _ = lb_user_and_profile
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
def test_post_like_evicts_taste_and_discovery_feed_cache(lb_user_and_profile, lb_auth_client):
    """POST to /liked-buildings/ must call evict_taste and evict_discovery_feed
    when a new building is actually added (i.e. not a duplicate).
    """
    _, profile = lb_user_and_profile
    conn_mock = _make_buildings_cursor_mock(exists=True)

    with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}), \
         patch('apps.recommendation.caches.evict_taste') as mock_evict_taste, \
         patch('apps.recommendation.caches.evict_discovery_feed') as mock_evict_feed:
        resp = lb_auth_client.post(
            '/api/v1/liked-buildings/',
            {'canonical_bld_id': 'bld_000999'},
            format='json',
        )

    assert resp.status_code == 200
    mock_evict_taste.assert_called_once_with(profile.id)
    mock_evict_feed.assert_called_once_with(profile.id)


@pytest.mark.django_db
def test_post_duplicate_does_not_evict_cache(lb_user_and_profile, lb_auth_client):
    """POSTing a duplicate bld_id (already in liked_building_ids) must NOT
    call evict_taste or evict_discovery_feed — no write, no eviction.
    """
    _, profile = lb_user_and_profile
    profile.liked_building_ids = ['bld_000999']
    profile.save(update_fields=['liked_building_ids'])

    conn_mock = _make_buildings_cursor_mock(exists=True)
    with patch('apps.accounts.views.profile._dj_connections', {'buildings': conn_mock}), \
         patch('apps.recommendation.caches.evict_taste') as mock_evict_taste, \
         patch('apps.recommendation.caches.evict_discovery_feed') as mock_evict_feed:
        resp = lb_auth_client.post(
            '/api/v1/liked-buildings/',
            {'canonical_bld_id': 'bld_000999'},
            format='json',
        )

    assert resp.status_code == 200
    mock_evict_taste.assert_not_called()
    mock_evict_feed.assert_not_called()
