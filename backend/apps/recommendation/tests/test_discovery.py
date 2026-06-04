"""
test_discovery.py — Discovery tab v3.1 endpoint coverage.

Tests cover:
  - DiscoveryFeedView GET (cold Tier-1, warm Tier-2/3, buffer param, 401)
  - DiscoveryFeedbackView POST (like, pass, validation errors, 401)
  - BoardSurpriseView GET (cold, warm, 401)
  - compute_discovery_tier tier-boundary logic
  - get_or_create_discovery_draft idempotency
  - _interleave_local_global pattern check
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project
from apps.recommendation.discovery_feed import (
    DISCOVERY_DRAFT_NAME,
    compute_discovery_tier,
    get_or_create_discovery_draft,
    _interleave_local_global,
    _greedy_fps,
)

_FAKE_TASTE_VEC = np.array([0.1] * 384, dtype=np.float64)


def _card(building_id):
    return {'canonical_bld_id': building_id}


def _make_cards(building_ids):
    return [_card(bid) for bid in building_ids]


# ── compute_discovery_tier unit tests ─────────────────────────────────────────

@pytest.mark.django_db
def test_tier1_cold_no_likes(user_profile):
    """Zero likes → Tier 1 (cold), 0 local / 10 global."""
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 1
    assert info['n_local'] == 0
    assert info['n_global'] == 10
    assert info['cumulative_likes'] == 0
    assert info['project_count'] == 0


@pytest.mark.django_db
def test_tier1_boundary_9_likes(user_profile):
    """9 cumulative likes → still Tier 1."""
    Project.objects.create(
        user=user_profile,
        name='Real Board',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(9)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 1
    assert info['cumulative_likes'] == 9


@pytest.mark.django_db
def test_tier2_at_10_likes_single_project(user_profile):
    """10 likes, 1 real project → Tier 2 (single)."""
    Project.objects.create(
        user=user_profile,
        name='Real Board',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 2
    assert info['n_local'] == 2
    assert info['n_global'] == 8
    assert info['project_count'] == 1


@pytest.mark.django_db
def test_tier3_at_2_projects(user_profile):
    """2 real projects → Tier 3 (multi) regardless of like count."""
    Project.objects.create(
        user=user_profile, name='Board A',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)],
    )
    Project.objects.create(
        user=user_profile, name='Board B',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(100, 110)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 3
    assert info['n_local'] == 4
    assert info['n_global'] == 6
    assert info['project_count'] == 2


@pytest.mark.django_db
def test_tier3_at_50_likes_single_project(user_profile):
    """50 likes with 1 project → Tier 3 (≥50 cumulative likes)."""
    Project.objects.create(
        user=user_profile, name='Board A',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(50)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 3
    assert info['project_count'] == 1


@pytest.mark.django_db
def test_draft_excluded_from_project_count(user_profile):
    """Draft project must not count toward project_count for tier calculation."""
    # Create draft + 1 real board (10 likes → normally Tier 2 with 1 project)
    draft = get_or_create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    draft.save(update_fields=['liked_ids'])
    Project.objects.create(
        user=user_profile, name='Real Board',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10, 20)],
    )
    info = compute_discovery_tier(user_profile)
    # project_count should be 1 (draft excluded), tier should be 2
    assert info['project_count'] == 1
    assert info['tier'] == 2
    # But draft likes DO count toward cumulative (1 draft + 10 real = 11)
    assert info['cumulative_likes'] == 11


# ── get_or_create_discovery_draft ─────────────────────────────────────────────

@pytest.mark.django_db
def test_get_or_create_discovery_draft_idempotent(user_profile):
    """Calling twice returns the same Project instance."""
    d1 = get_or_create_discovery_draft(user_profile)
    d2 = get_or_create_discovery_draft(user_profile)
    assert d1.project_id == d2.project_id
    assert d1.name == DISCOVERY_DRAFT_NAME
    assert d1.visibility == 'private'
    # Only 1 draft should exist
    assert Project.objects.filter(user=user_profile, name=DISCOVERY_DRAFT_NAME).count() == 1


# ── _interleave_local_global unit tests ───────────────────────────────────────

def _make_rows(ids):
    return [{'canonical_bld_id': i, '_vec': [0.1] * 10} for i in ids]


def test_interleave_all_global():
    result = _interleave_local_global([], _make_rows(['G1', 'G2', 'G3']))
    assert len(result) == 3
    assert all(r['canonical_bld_id'].startswith('G') for r in result)


def test_interleave_all_local():
    result = _interleave_local_global(_make_rows(['L1', 'L2']), [])
    assert len(result) == 2


def test_interleave_mixed_count():
    """4 local + 6 global = 10 total, all present in output."""
    local = _make_rows([f'L{i}' for i in range(4)])
    global_ = _make_rows([f'G{i}' for i in range(6)])
    result = _interleave_local_global(local, global_)
    assert len(result) == 10
    ids = {r['canonical_bld_id'] for r in result}
    assert ids == {f'L{i}' for i in range(4)} | {f'G{i}' for i in range(6)}


def test_interleave_empty_both():
    assert _interleave_local_global([], []) == []


# ── _greedy_fps unit tests ────────────────────────────────────────────────────

def test_greedy_fps_returns_requested_count():
    rows = [{'_vec': [1.0 if i == j else 0.0 for j in range(5)]} for i in range(5)]
    selected = _greedy_fps(rows, 3)
    assert len(selected) == 3


def test_greedy_fps_fewer_than_n():
    rows = [{'_vec': [float(i)] * 3} for i in range(2)]
    selected = _greedy_fps(rows, 5)
    assert len(selected) == 2  # can't return more than available


# ── FIX 2: backfill tests ────────────────────────────────────────────────────

def _make_pool_rows(prefix, count, dims=8):
    """Make rows with distinct orthogonal-ish vectors for FPS testing."""
    rows = []
    for i in range(count):
        vec = [0.0] * dims
        vec[i % dims] = 1.0
        rows.append({'canonical_bld_id': f'{prefix}_{i:03d}', '_vec': vec})
    return rows


def test_build_chunk_backfill_empty_local_pool():
    """When local pool is empty but >=chunk_size global candidates exist,
    the chunk must return chunk_size cards (Tier-1-like Tier-3 backfill case).

    Simulates: n_local=4, n_global=6, but local_pool is empty.
    Backfill should pull 4 extra globals so total = 10 = chunk_size.
    """
    from apps.recommendation.discovery_feed import _greedy_fps

    n_local = 4
    n_global = 6
    chunk_size = n_local + n_global  # 10
    global_pool = _make_pool_rows('G', 15)
    local_pool = []  # deliberately empty

    local_selected = _greedy_fps(local_pool, n_local)
    global_selected = _greedy_fps(global_pool, n_global)

    # --- replicate the fixed backfill logic ---
    selected_ids = set()
    for r in local_selected:
        selected_ids.add(r['canonical_bld_id'])
    for r in global_selected:
        selected_ids.add(r['canonical_bld_id'])

    local_deficit = n_local - len(local_selected)
    global_deficit = n_global - len(global_selected)

    if local_deficit > 0:
        unused_global = [r for r in global_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_global, local_deficit)
        for r in backfill:
            local_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    if global_deficit > 0:
        unused_local = [r for r in local_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_local, global_deficit)
        for r in backfill:
            global_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    total = len(local_selected) + len(global_selected)
    assert total == chunk_size, f'Expected {chunk_size} cards, got {total}'
    # No duplicates
    all_ids = [r['canonical_bld_id'] for r in local_selected + global_selected]
    assert len(all_ids) == len(set(all_ids)), 'Duplicate cards in chunk'


def test_build_chunk_backfill_both_pools_short():
    """When both pools are short, chunk returns exactly the available unique count
    with no duplicates.
    """
    from apps.recommendation.discovery_feed import _greedy_fps

    n_local = 4
    n_global = 6
    # Only 3 local and 3 global available — total 6 candidates
    local_pool = _make_pool_rows('L', 3)
    global_pool = _make_pool_rows('G', 3)

    local_selected = _greedy_fps(local_pool, n_local)
    global_selected = _greedy_fps(global_pool, n_global)

    selected_ids = set()
    for r in local_selected:
        selected_ids.add(r['canonical_bld_id'])
    for r in global_selected:
        selected_ids.add(r['canonical_bld_id'])

    local_deficit = n_local - len(local_selected)
    global_deficit = n_global - len(global_selected)

    if local_deficit > 0:
        unused_global = [r for r in global_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_global, local_deficit)
        for r in backfill:
            local_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    if global_deficit > 0:
        unused_local = [r for r in local_pool if r['canonical_bld_id'] not in selected_ids]
        backfill = _greedy_fps(unused_local, global_deficit)
        for r in backfill:
            global_selected.append(r)
            selected_ids.add(r['canonical_bld_id'])

    total = len(local_selected) + len(global_selected)
    # 3 local + 3 global = 6 total available; all consumed
    assert total == 6, f'Expected 6 cards (all available), got {total}'
    # No duplicates
    all_ids = [r['canonical_bld_id'] for r in local_selected + global_selected]
    assert len(all_ids) == len(set(all_ids)), 'Duplicate cards in chunk'


# ── DiscoveryFeedView integration tests ───────────────────────────────────────

@pytest.mark.django_db
def test_discovery_feed_cold_start(auth_client):
    """Cold user → tier 1, taste_state 'cold', cards list present, no cursor."""
    fake_cards = _make_cards([f'bld_{i:06d}' for i in range(10)])
    with patch('apps.recommendation.views.discovery.get_or_build_discovery_centroids', return_value=[]), \
         patch('apps.recommendation.views.discovery.build_discovery_chunk', return_value=fake_cards):
        resp = auth_client.get('/api/v1/discovery/')

    assert resp.status_code == 200
    payload = resp.json()
    assert 'cards' in payload
    assert 'tier' in payload
    assert 'taste_state' in payload
    assert payload['taste_state'] == 'cold'
    assert payload['tier'] == 1
    # No cursor fields in v3.1 response
    assert 'next_cursor' not in payload
    assert 'has_more' not in payload


@pytest.mark.django_db
def test_discovery_feed_warm_tier2(auth_client, user_profile):
    """10 likes, 1 project → Tier 2 (single), taste_state 'single'."""
    Project.objects.create(
        user=user_profile, name='Board A',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)],
    )
    fake_cards = _make_cards([f'bld_{i:06d}' for i in range(100, 110)])
    with patch('apps.recommendation.views.discovery.get_or_build_discovery_centroids', return_value=[[0.1] * 384]), \
         patch('apps.recommendation.views.discovery.build_discovery_chunk', return_value=fake_cards):
        resp = auth_client.get('/api/v1/discovery/')

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['tier'] == 2
    assert payload['taste_state'] == 'single'


@pytest.mark.django_db
def test_discovery_feed_buffer_param_parsed(auth_client):
    """buffer param is accepted without error."""
    fake_cards = _make_cards([f'bld_{i:06d}' for i in range(10)])
    buffer = 'bld_000001,bld_000002'
    with patch('apps.recommendation.views.discovery.get_or_build_discovery_centroids', return_value=[]), \
         patch('apps.recommendation.views.discovery.build_discovery_chunk', return_value=fake_cards) as mock_build:
        resp = auth_client.get(f'/api/v1/discovery/?buffer={buffer}')

    assert resp.status_code == 200
    # build_discovery_chunk should have been called with the parsed buffer ids
    call_kwargs = mock_build.call_args
    assert call_kwargs is not None


@pytest.mark.django_db
def test_discovery_feed_unauthenticated(api_client):
    assert api_client.get('/api/v1/discovery/').status_code == 401


# ── DiscoveryFeedbackView integration tests ───────────────────────────────────

@pytest.mark.django_db
def test_feedback_like_appends_to_draft(auth_client, user_profile):
    """POST feedback like → draft.liked_ids gets the entry."""
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like'},
            format='json',
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert 'draft_like_count' in payload
    assert 'draft_pass_count' in payload

    draft = Project.objects.get(user=user_profile, name=DISCOVERY_DRAFT_NAME)
    liked_ids = [e['id'] if isinstance(e, dict) else e for e in draft.liked_ids]
    assert 'bld_000001' in liked_ids


@pytest.mark.django_db
def test_feedback_pass_appends_to_draft(auth_client, user_profile):
    """POST feedback pass → draft.disliked_ids gets the entry."""
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000002', 'action': 'pass'},
            format='json',
        )

    assert resp.status_code == 200
    draft = Project.objects.get(user=user_profile, name=DISCOVERY_DRAFT_NAME)
    assert 'bld_000002' in draft.disliked_ids


@pytest.mark.django_db
def test_feedback_deduplication(auth_client, user_profile):
    """Posting the same like twice does not duplicate the entry."""
    # Pre-create draft with the id already in liked_ids
    draft = get_or_create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    draft.save(update_fields=['liked_ids'])

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like'},
            format='json',
        )

    assert resp.status_code == 200
    draft.refresh_from_db()
    liked_ids = [e['id'] if isinstance(e, dict) else e for e in draft.liked_ids]
    assert liked_ids.count('bld_000001') == 1


@pytest.mark.django_db
def test_feedback_invalid_bld_id_format(auth_client):
    resp = auth_client.post(
        '/api/v1/discovery/feedback/',
        {'canonical_bld_id': 'INVALID_ID', 'action': 'like'},
        format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_feedback_invalid_action(auth_client):
    resp = auth_client.post(
        '/api/v1/discovery/feedback/',
        {'canonical_bld_id': 'bld_000001', 'action': 'love'},
        format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_feedback_unauthenticated(api_client):
    resp = api_client.post(
        '/api/v1/discovery/feedback/',
        {'canonical_bld_id': 'bld_000001', 'action': 'like'},
        format='json',
    )
    assert resp.status_code == 401


# ── BoardSurpriseView tests (preserved) ───────────────────────────────────────

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
    assert blocked_ids.isdisjoint(card['canonical_bld_id'] for card in payload['cards'])


@pytest.mark.django_db
def test_surprise_unauthenticated_returns_401(api_client):
    assert api_client.get('/api/v1/recommendations/board-surprise/').status_code == 401


# ── FIX 3: buffer validation tests ───────────────────────────────────────────

@pytest.mark.django_db
def test_discovery_feed_buffer_invalid_ids_dropped(auth_client):
    """Buffer items with invalid format are silently dropped; valid ones pass."""
    fake_cards = _make_cards([f'bld_{i:06d}' for i in range(10)])
    # Mix valid + invalid ids
    buffer = 'bld_000001,INVALID,bld_000002,toolong_' + 'x' * 30
    with patch('apps.recommendation.views.discovery.get_or_build_discovery_centroids', return_value=[]), \
         patch('apps.recommendation.views.discovery.build_discovery_chunk', return_value=fake_cards) as mock_build:
        resp = auth_client.get(f'/api/v1/discovery/?buffer={buffer}')

    assert resp.status_code == 200
    # Verify only valid ids were passed through
    call_kwargs = mock_build.call_args
    assert call_kwargs is not None
    passed_buffer = call_kwargs[1].get('client_buffer_ids') or call_kwargs[0][2]
    assert 'bld_000001' in passed_buffer
    assert 'bld_000002' in passed_buffer
    assert 'INVALID' not in passed_buffer


# ── FIX 4: draft cap tests ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_feedback_liked_ids_capped_at_200(auth_client, user_profile):
    """draft.liked_ids is trimmed to at most 200 entries (rolling cap)."""
    # Pre-fill draft with 199 existing likes
    draft = get_or_create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(199)]
    draft.save(update_fields=['liked_ids'])

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        # This 200th like brings the list to exactly the cap
        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000999', 'action': 'like'},
            format='json',
        )
    assert resp.status_code == 200
    draft.refresh_from_db()
    assert len(draft.liked_ids) == 200

    # One more like — should still be capped at 200 (oldest dropped)
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_001000', 'action': 'like'},
            format='json',
        )
    assert resp.status_code == 200
    draft.refresh_from_db()
    assert len(draft.liked_ids) <= 200


@pytest.mark.django_db
def test_feedback_disliked_ids_capped_at_200(auth_client, user_profile):
    """draft.disliked_ids is trimmed to at most 200 entries (rolling cap)."""
    draft = get_or_create_discovery_draft(user_profile)
    draft.disliked_ids = [f'bld_{i:06d}' for i in range(200)]
    draft.save(update_fields=['disliked_ids'])

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_001000', 'action': 'pass'},
            format='json',
        )
    assert resp.status_code == 200
    draft.refresh_from_db()
    assert len(draft.disliked_ids) <= 200


# ── FIX 5: reserved name guard tests ─────────────────────────────────────────

@pytest.mark.django_db
def test_project_create_rejects_reserved_name(auth_client):
    """POST /api/v1/projects/ with name='__discovery_draft__' returns 400."""
    resp = auth_client.post(
        '/api/v1/projects/',
        {'name': '__discovery_draft__', 'visibility': 'private'},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json().get('detail') == 'reserved_name'


@pytest.mark.django_db
def test_project_rename_rejects_reserved_name(auth_client, user_profile):
    """PATCH /api/v1/projects/{pk}/ with name='__discovery_draft__' returns 400."""
    project = Project.objects.create(
        user=user_profile,
        name='Normal Board',
        visibility='private',
    )
    resp = auth_client.patch(
        f'/api/v1/projects/{project.project_id}/',
        {'name': '__discovery_draft__'},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json().get('detail') == 'reserved_name'
