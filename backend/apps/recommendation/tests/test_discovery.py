"""
test_discovery.py — Discovery tab v3.2 endpoint coverage.

Tests cover:
  - DiscoveryFeedView GET (cold Tier-1, warm Tier-2/3, buffer param, 401)
  - DiscoveryFeedbackView POST (like, pass, draft_id in/out, validation errors, 401)
  - DiscoveryPromoteView POST (by draft_id, most-recent fallback, 400 no likes)
  - BoardSurpriseView GET (cold, warm, 401)
  - compute_discovery_tier tier-boundary logic (project_count excludes drafts)
  - create_discovery_draft always creates a new board
  - get_discovery_draft ownership + prefix guard
  - is_discovery_draft_name predicate
  - _interleave_local_global pattern check
  - Profile board list now includes discovery draft boards
"""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project
from apps.recommendation.discovery_feed import (
    DISCOVERY_DRAFT_PREFIX,
    compute_discovery_tier,
    create_discovery_draft,
    get_discovery_draft,
    is_discovery_draft_name,
    _interleave_local_global,
    _greedy_fps,
)

_FAKE_TASTE_VEC = np.array([0.1] * 384, dtype=np.float64)


def _card(building_id):
    return {'canonical_bld_id': building_id}


def _make_cards(building_ids):
    return [_card(bid) for bid in building_ids]


# ── is_discovery_draft_name predicate ─────────────────────────────────────────

def test_is_discovery_draft_name_true():
    assert is_discovery_draft_name('discovery_260604_1430') is True
    assert is_discovery_draft_name('discovery_') is True


def test_is_discovery_draft_name_false():
    assert is_discovery_draft_name('') is False
    assert is_discovery_draft_name(None) is False
    assert is_discovery_draft_name('__discovery_draft__') is False
    assert is_discovery_draft_name('My Board') is False
    assert is_discovery_draft_name('disco') is False


# ── create_discovery_draft ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_discovery_draft_makes_new_board(user_profile):
    """Each call to create_discovery_draft creates a new Project."""
    d1 = create_discovery_draft(user_profile)
    d2 = create_discovery_draft(user_profile)
    assert d1.project_id != d2.project_id
    assert d1.name.startswith(DISCOVERY_DRAFT_PREFIX)
    assert d2.name.startswith(DISCOVERY_DRAFT_PREFIX)
    assert d1.visibility == 'private'
    assert d2.visibility == 'private'
    # Both boards exist in DB
    assert Project.objects.filter(
        user=user_profile, name__startswith=DISCOVERY_DRAFT_PREFIX
    ).count() == 2


@pytest.mark.django_db
def test_create_discovery_draft_name_format(user_profile):
    """Draft name must match 'discovery_YYMMDD_HHMM' format."""
    import re
    draft = create_discovery_draft(user_profile)
    assert re.match(r'^discovery_\d{6}_\d{4}$', draft.name), (
        f"Name '{draft.name}' does not match expected format 'discovery_YYMMDD_HHMM'"
    )


# ── get_discovery_draft ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_get_discovery_draft_returns_owned_draft(user_profile):
    """get_discovery_draft returns a valid draft when given its UUID."""
    draft = create_discovery_draft(user_profile)
    found = get_discovery_draft(user_profile, str(draft.project_id))
    assert found is not None
    assert found.project_id == draft.project_id


@pytest.mark.django_db
def test_get_discovery_draft_rejects_wrong_owner(user_profile, other_profile):
    """get_discovery_draft returns None when draft belongs to a different user."""
    draft = create_discovery_draft(other_profile)
    result = get_discovery_draft(user_profile, str(draft.project_id))
    assert result is None


@pytest.mark.django_db
def test_get_discovery_draft_rejects_non_draft_board(user_profile):
    """get_discovery_draft returns None when the project name is not a draft prefix."""
    board = Project.objects.create(
        user=user_profile, name='My Board', visibility='private',
    )
    result = get_discovery_draft(user_profile, str(board.project_id))
    assert result is None


@pytest.mark.django_db
def test_get_discovery_draft_none_id_returns_none(user_profile):
    """get_discovery_draft returns None when draft_id is None or empty."""
    assert get_discovery_draft(user_profile, None) is None
    assert get_discovery_draft(user_profile, '') is None


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
def test_tier3_at_4_projects(user_profile):
    """4 real projects → Tier 3 (multi). DISCOVERY-PERF-3: threshold raised 2→4."""
    for b in range(4):
        Project.objects.create(
            user=user_profile, name=f'Board {b}',
            liked_ids=[{'id': f'bld_{b}{i:05d}', 'intensity': 1.0} for i in range(5)],
        )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 3
    assert info['n_local'] == 4
    assert info['n_global'] == 6
    assert info['project_count'] == 4


@pytest.mark.django_db
def test_tier2_at_2_projects(user_profile):
    """2 projects (<4) with >=10 likes → Tier 2. DISCOVERY-PERF-3: 2<tier3_min(4)."""
    Project.objects.create(
        user=user_profile, name='Board A',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)],
    )
    Project.objects.create(
        user=user_profile, name='Board B',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(100, 110)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 2
    assert info['project_count'] == 2


@pytest.mark.django_db
def test_tier3_at_50_likes_single_project(user_profile):
    """50 likes with 1 project → Tier 3 (>=50 cumulative likes)."""
    Project.objects.create(
        user=user_profile, name='Board A',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(50)],
    )
    info = compute_discovery_tier(user_profile)
    assert info['tier'] == 3
    assert info['project_count'] == 1


@pytest.mark.django_db
def test_draft_included_in_project_count_and_likes(user_profile):
    """DISCOVERY-PERF-2: draft boards ARE counted in project_count, and draft
    likes also contribute to cumulative_likes."""
    # Create a draft board with 1 like
    draft = create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    draft.save(update_fields=['liked_ids'])
    # Create a real board with 10 likes
    Project.objects.create(
        user=user_profile, name='Real Board',
        liked_ids=[{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10, 20)],
    )
    info = compute_discovery_tier(user_profile)
    # project_count = 2 (draft + real, both counted)
    assert info['project_count'] == 2
    # 2 projects < tier3_min(4), 11 likes >= 10 → Tier 2
    assert info['tier'] == 2
    # draft likes DO count toward cumulative (1 draft + 10 real = 11)
    assert info['cumulative_likes'] == 11


@pytest.mark.django_db
def test_two_drafts_included_in_project_count(user_profile):
    """DISCOVERY-PERF-2: draft boards count toward project_count."""
    draft1 = create_discovery_draft(user_profile)
    draft1.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    draft1.save(update_fields=['liked_ids'])
    draft2 = create_discovery_draft(user_profile)
    draft2.liked_ids = [{'id': 'bld_000002', 'intensity': 1.0}]
    draft2.save(update_fields=['liked_ids'])
    # Only 1 real board
    Project.objects.create(
        user=user_profile, name='My Board',
        liked_ids=[{'id': 'bld_000010', 'intensity': 1.0} for _ in range(10)],
    )
    info = compute_discovery_tier(user_profile)
    # 2 drafts + 1 real, all counted
    assert info['project_count'] == 3
    # cumulative = 10 (real) + 1 (draft1) + 1 (draft2) = 12
    assert info['cumulative_likes'] == 12


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
    # No cursor fields in v3.1+ response
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
def test_feedback_without_draft_id_creates_new_draft(auth_client, user_profile):
    """POST feedback without draft_id creates a new draft and returns draft_id."""
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
    assert 'draft_id' in payload
    assert 'draft_like_count' in payload
    assert 'draft_pass_count' in payload
    assert payload['draft_like_count'] == 1
    assert payload['draft_pass_count'] == 0

    # A draft board must have been created
    draft_id = payload['draft_id']
    draft = Project.objects.get(project_id=draft_id, user=user_profile)
    assert draft.name.startswith(DISCOVERY_DRAFT_PREFIX)
    liked_ids = [e['id'] if isinstance(e, dict) else e for e in draft.liked_ids]
    assert 'bld_000001' in liked_ids


@pytest.mark.django_db
def test_feedback_with_valid_draft_id_appends_to_same_draft(auth_client, user_profile):
    """POST feedback with draft_id appends to the same board (count increments)."""
    # Create a draft explicitly first
    existing_draft = create_discovery_draft(user_profile)
    draft_id_str = str(existing_draft.project_id)

    def _mock_cursor():
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        return mock_cursor

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_conns.__getitem__.return_value.cursor.return_value = _mock_cursor()
        resp1 = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like', 'draft_id': draft_id_str},
            format='json',
        )

    assert resp1.status_code == 200
    assert resp1.json()['draft_id'] == draft_id_str
    assert resp1.json()['draft_like_count'] == 1

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_conns.__getitem__.return_value.cursor.return_value = _mock_cursor()
        resp2 = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000002', 'action': 'like', 'draft_id': draft_id_str},
            format='json',
        )

    assert resp2.status_code == 200
    # Same draft_id returned, count is now 2
    assert resp2.json()['draft_id'] == draft_id_str
    assert resp2.json()['draft_like_count'] == 2

    # Only 1 draft board was created (not 2)
    assert Project.objects.filter(
        user=user_profile, name__startswith=DISCOVERY_DRAFT_PREFIX
    ).count() == 1


@pytest.mark.django_db
def test_feedback_invalid_draft_id_creates_new_draft(auth_client, user_profile):
    """POST feedback with invalid/non-existent draft_id falls back to new draft."""
    fake_uuid = '00000000-0000-0000-0000-000000000000'
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like', 'draft_id': fake_uuid},
            format='json',
        )

    assert resp.status_code == 200
    payload = resp.json()
    # A new draft was created (different from the fake UUID)
    assert payload['draft_id'] != fake_uuid
    # One draft board exists
    assert Project.objects.filter(
        user=user_profile, name__startswith=DISCOVERY_DRAFT_PREFIX
    ).count() == 1


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
    payload = resp.json()
    assert payload['draft_pass_count'] == 1

    draft = Project.objects.get(project_id=payload['draft_id'], user=user_profile)
    assert 'bld_000002' in draft.disliked_ids


@pytest.mark.django_db
def test_feedback_deduplication(auth_client, user_profile):
    """Posting the same like twice to the same draft does not duplicate the entry."""
    # Pre-create draft with the id already in liked_ids
    existing_draft = create_discovery_draft(user_profile)
    existing_draft.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    existing_draft.save(update_fields=['liked_ids'])
    draft_id_str = str(existing_draft.project_id)

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like', 'draft_id': draft_id_str},
            format='json',
        )

    assert resp.status_code == 200
    existing_draft.refresh_from_db()
    liked_ids = [e['id'] if isinstance(e, dict) else e for e in existing_draft.liked_ids]
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


# ── DiscoveryPromoteView integration tests ─────────────────────────────────────

@pytest.mark.django_db
def test_promote_with_draft_id_uses_that_draft(auth_client, user_profile):
    """promote-to-taste with draft_id uses that draft's likes."""
    draft = create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]
    draft.save(update_fields=['liked_ids'])
    draft_id_str = str(draft.project_id)

    mock_emb = np.array([0.1] * 384, dtype=np.float64)
    emb_map = {f'bld_{i:06d}': mock_emb for i in range(10)}

    with patch('apps.recommendation.views.discovery.engine.get_pool_embeddings', return_value=emb_map), \
         patch('apps.recommendation.views.discovery.engine.update_preference_vector',
               side_effect=lambda pv, emb, a: emb), \
         patch('apps.recommendation.views.discovery.engine.create_pool_with_relaxation',
               return_value=(['bld_000010', 'bld_000011'], {}, 1)), \
         patch('apps.recommendation.views.discovery.engine.get_pool_embeddings',
               return_value=emb_map), \
         patch('apps.recommendation.views.discovery.engine.farthest_point_from_pool',
               return_value=None), \
         patch('apps.recommendation.views.discovery.engine.get_buildings_by_ids',
               return_value=[_card('bld_000010')]):
        resp = auth_client.post(
            '/api/v1/discovery/promote-to-taste/',
            {'draft_id': draft_id_str},
            format='json',
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert 'session_id' in payload
    assert 'project_id' in payload


@pytest.mark.django_db
def test_promote_without_draft_id_uses_most_recent(auth_client, user_profile):
    """promote-to-taste without draft_id falls back to the most-recent draft."""
    # Create two drafts; second is more recent (relies on auto_now updated_at).
    # draft1 exists but has no likes — draft2 has likes and is more recent.
    create_discovery_draft(user_profile)
    draft2 = create_discovery_draft(user_profile)
    draft2.liked_ids = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]
    draft2.save(update_fields=['liked_ids'])

    mock_emb = np.array([0.1] * 384, dtype=np.float64)
    emb_map = {f'bld_{i:06d}': mock_emb for i in range(10)}

    with patch('apps.recommendation.views.discovery.engine.get_pool_embeddings', return_value=emb_map), \
         patch('apps.recommendation.views.discovery.engine.update_preference_vector',
               side_effect=lambda pv, emb, a: emb), \
         patch('apps.recommendation.views.discovery.engine.create_pool_with_relaxation',
               return_value=(['bld_000010'], {}, 1)), \
         patch('apps.recommendation.views.discovery.engine.farthest_point_from_pool',
               return_value=None), \
         patch('apps.recommendation.views.discovery.engine.get_buildings_by_ids',
               return_value=[_card('bld_000010')]):
        resp = auth_client.post(
            '/api/v1/discovery/promote-to-taste/',
            {},
            format='json',
        )

    # draft2 had likes → should succeed
    assert resp.status_code == 201


@pytest.mark.django_db
def test_promote_returns_400_when_no_likes(auth_client, user_profile):
    """promote-to-taste returns 400 not_enough_likes when draft has no likes."""
    draft = create_discovery_draft(user_profile)
    # draft has no liked_ids

    resp = auth_client.post(
        '/api/v1/discovery/promote-to-taste/',
        {'draft_id': str(draft.project_id)},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json().get('detail') == 'not_enough_likes'


@pytest.mark.django_db
def test_promote_returns_400_when_no_draft_exists(auth_client):
    """promote-to-taste returns 400 not_enough_likes when user has no drafts at all."""
    resp = auth_client.post(
        '/api/v1/discovery/promote-to-taste/',
        {},
        format='json',
    )
    assert resp.status_code == 400
    assert resp.json().get('detail') == 'not_enough_likes'


# ── BoardSurpriseView tests (preserved) ───────────────────────────────────────

@pytest.mark.django_db
def test_surprise_cold_start_returns_random(auth_client):
    """Zero likes → cold start; title must contain 'Discover'.

    get_or_build_taste must be mocked to None to guarantee the cold branch
    runs regardless of LocMemCache state from previous tests in the same
    pytest session (LocMemCache does not reset between tests).
    """
    with patch('apps.recommendation.views.discovery.get_or_build_taste', return_value=None), \
         patch('apps.recommendation.views.discovery.engine.get_diverse_random') as mocked:
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


# ── Draft cap tests ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_feedback_liked_ids_hard_capped_at_50(auth_client, user_profile):
    """draft.liked_ids is hard-capped at 50 entries (discovery_like_hard_cap).

    New likes are blocked once the draft has reached the cap — the list never
    grows past 50 distinct entries.  The 51st distinct like returns
    like_cap_reached=True and does NOT grow the list.
    """
    from django.conf import settings
    hard_cap = settings.RECOMMENDATION.get('discovery_like_hard_cap', 50)

    # Pre-fill draft with exactly (hard_cap - 1) distinct likes
    existing_draft = create_discovery_draft(user_profile)
    existing_draft.liked_ids = [
        {'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(hard_cap - 1)
    ]
    existing_draft.save(update_fields=['liked_ids'])
    draft_id_str = str(existing_draft.project_id)

    def _mock_cursor():
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        return mock_cursor

    # The hard_cap-th like fills the list to exactly the cap
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_conns.__getitem__.return_value.cursor.return_value = _mock_cursor()
        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': f'bld_{hard_cap - 1:06d}', 'action': 'like', 'draft_id': draft_id_str},
            format='json',
        )
    assert resp.status_code == 200
    existing_draft.refresh_from_db()
    assert len(existing_draft.liked_ids) == hard_cap

    # The (hard_cap + 1)-th distinct like must NOT grow the list
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_conns.__getitem__.return_value.cursor.return_value = _mock_cursor()
        resp_over = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': f'bld_{hard_cap + 999:06d}', 'action': 'like', 'draft_id': draft_id_str},
            format='json',
        )
    assert resp_over.status_code == 200
    payload = resp_over.json()
    # Hard cap: the list must not exceed hard_cap
    existing_draft.refresh_from_db()
    assert len(existing_draft.liked_ids) == hard_cap, (
        f'liked_ids must stay at {hard_cap} after hard cap reached, '
        f'got {len(existing_draft.liked_ids)}'
    )
    # like_cap_reached must be True when the draft is at or past the cap
    assert payload.get('like_cap_reached') is True, (
        f'Expected like_cap_reached=True once cap is reached, got {payload}'
    )


@pytest.mark.django_db
def test_feedback_disliked_ids_capped_at_200(auth_client, user_profile):
    """draft.disliked_ids is trimmed to at most 200 entries (rolling cap)."""
    existing_draft = create_discovery_draft(user_profile)
    existing_draft.disliked_ids = [f'bld_{i:06d}' for i in range(200)]
    existing_draft.save(update_fields=['disliked_ids'])
    draft_id_str = str(existing_draft.project_id)

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_001000', 'action': 'pass', 'draft_id': draft_id_str},
            format='json',
        )
    assert resp.status_code == 200
    existing_draft.refresh_from_db()
    assert len(existing_draft.disliked_ids) <= 200


# ── Profile board list includes discovery drafts (v3.2) ───────────────────────

@pytest.mark.django_db
def test_profile_boards_includes_discovery_draft(auth_client, user_profile):
    """v3.2: Discovery draft boards appear in the user's profile board list."""
    from apps.accounts.views.profile import _build_boards_field

    draft = create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': 'bld_000001', 'intensity': 1.0}]
    draft.save(update_fields=['liked_ids'])

    # Mock the buildings DB thumbnail fetch (not available in test environment).
    # engine is imported locally inside _build_boards_field, so patch at the source.
    with patch('apps.recommendation.engine.get_building_thumbnails', return_value=[]):
        boards = _build_boards_field(user_profile, is_owner=True, page=1, page_size=50)

    board_names = [b['name'] for b in boards['items']]
    assert draft.name in board_names, (
        f"Expected draft '{draft.name}' in board list, got: {board_names}"
    )
    assert boards['total_count'] >= 1


@pytest.mark.django_db
def test_profile_board_count_includes_discovery_draft(auth_client, user_profile):
    """v3.2: total_count in boards includes discovery draft boards."""
    from apps.accounts.views.profile import _build_boards_field

    # One regular board + one draft
    Project.objects.create(user=user_profile, name='Normal Board')
    create_discovery_draft(user_profile)

    boards = _build_boards_field(user_profile, is_owner=True, page=1, page_size=50)
    assert boards['total_count'] == 2


# ── No reserved-name guard in projects API (v3.2) ────────────────────────────

@pytest.mark.django_db
def test_project_create_does_not_reject_discovery_prefix(auth_client):
    """POST /api/v1/projects/ with name starting 'discovery_' is now allowed (no reserved guard)."""
    resp = auth_client.post(
        '/api/v1/projects/',
        {'name': 'discovery_260604_1430', 'visibility': 'private'},
        format='json',
    )
    # Should succeed (201) — no reserved_name guard for this prefix
    assert resp.status_code == 201


# ── FIX 1: malformed draft_id regression tests ────────────────────────────────

@pytest.mark.django_db
def test_get_discovery_draft_malformed_uuid_returns_none(user_profile):
    """FIX 1: get_discovery_draft with a non-UUID string must return None, not raise."""
    result = get_discovery_draft(user_profile, 'not-a-uuid')
    assert result is None


@pytest.mark.django_db
def test_get_discovery_draft_malformed_uuid_variants(user_profile):
    """FIX 1: various malformed draft_id values all return None without exception."""
    bad_ids = ['', 'abc', '123', 'not-a-uuid', 'x' * 100, '!!!', '0']
    for bad_id in bad_ids:
        result = get_discovery_draft(user_profile, bad_id)
        assert result is None, f'Expected None for draft_id={bad_id!r}, got {result}'


@pytest.mark.django_db
def test_feedback_malformed_draft_id_creates_new_draft_not_500(auth_client, user_profile):
    """FIX 1: POST /discovery/feedback/ with draft_id='not-a-uuid' must return 200
    (creates a new draft) and not raise a 500.
    """
    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like', 'draft_id': 'not-a-uuid'},
            format='json',
        )

    assert resp.status_code == 200, (
        f'Expected 200, got {resp.status_code}; body: {resp.content}'
    )
    payload = resp.json()
    assert 'draft_id' in payload
    # A new draft board was created (graceful fallback on malformed draft_id)
    assert Project.objects.filter(
        user=user_profile, name__startswith=DISCOVERY_DRAFT_PREFIX
    ).count() == 1


# ── Security: guest board-limit gate (fix ⑤ guest-cap) ──────────────────────

@pytest.mark.django_db
def test_guest_feedback_blocked_at_board_limit(user_profile):
    """Guest with 3 existing Projects → POST /discovery/feedback/ (no draft_id)
    → 403 board_limit_reached (existence check passes; board cap fires).
    """
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    user_profile.is_guest = True
    user_profile.save(update_fields=['is_guest'])

    for i in range(3):
        Project.objects.create(user=user_profile, name=f'Board {i}')

    client = APIClient()
    refresh = RefreshToken.for_user(user_profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    with patch('apps.recommendation.views.discovery._dj_connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (1,)  # building exists
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = client.post(
            '/api/v1/discovery/feedback/',
            {'canonical_bld_id': 'bld_000001', 'action': 'like'},
            format='json',
        )

    assert resp.status_code == 403
    data = resp.json()
    assert data.get('detail') == 'verify_required'
    assert data.get('reason') == 'board_limit_reached'


@pytest.mark.django_db
def test_guest_promote_blocked_at_board_limit(user_profile):
    """Guest with 3 existing Projects and a 10-like draft → promote-to-taste
    → 403 board_limit_reached (checked after seed validation).
    """
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    user_profile.is_guest = True
    user_profile.save(update_fields=['is_guest'])

    # 3 real boards to hit the cap
    for i in range(3):
        Project.objects.create(user=user_profile, name=f'Board {i}')

    # A draft with exactly 10 likes (promote_threshold)
    draft = create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]
    draft.save(update_fields=['liked_ids'])

    client = APIClient()
    refresh = RefreshToken.for_user(user_profile.user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    mock_emb = np.array([0.1] * 384, dtype=np.float64)
    emb_map = {f'bld_{i:06d}': mock_emb for i in range(10)}

    with patch('apps.recommendation.views.discovery.engine.get_pool_embeddings', return_value=emb_map), \
         patch('apps.recommendation.views.discovery.engine.update_preference_vector',
               side_effect=lambda pv, emb, a: emb):
        resp = client.post(
            '/api/v1/discovery/promote-to-taste/',
            {'draft_id': str(draft.project_id)},
            format='json',
        )

    assert resp.status_code == 403
    data = resp.json()
    assert data.get('detail') == 'verify_required'
    assert data.get('reason') == 'board_limit_reached'


# ── Security: swipe/bookmark non-existent building → 404 (fix ②) ────────────

@pytest.mark.django_db
def test_swipe_nonexistent_building_returns_404(auth_client, user_profile):
    """Swipe with a canonical_bld_id that does not exist in buildings DB → 404."""
    from apps.recommendation.models import Project, AnalysisSession

    project = Project.objects.create(user=user_profile, name='SwipeProject')
    session = AnalysisSession.objects.create(
        user=user_profile,
        project=project,
        phase='exploring',
        pool_ids=['bld_999999'],
        pool_scores={'bld_999999': 1.0},
        current_round=0,
        preference_vector=[],
        exposed_ids=[],
        initial_batch=['bld_999999'],
        like_vectors=[],
        convergence_history=[],
        previous_pref_vector=[],
        original_filters={},
        original_filter_priority=[],
        original_seed_ids=[],
        current_pool_tier=1,
        v_initial=None,
    )

    with patch('apps.recommendation.services.swipe_service.connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None  # building not found
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
            {
                'canonical_bld_id': 'bld_999999',
                'action': 'like',
                'idempotency_key': 'test-idem-1',
            },
            format='json',
        )

    assert resp.status_code == 404
    assert resp.json().get('detail') == 'building not found'


@pytest.mark.django_db
def test_bookmark_nonexistent_building_returns_404(auth_client, user_profile):
    """Bookmark with a card_id that does not exist in buildings DB → 404."""
    from apps.recommendation.models import Project

    project = Project.objects.create(user=user_profile, name='BookmarkProject')

    with patch('apps.recommendation.services.swipe_service.connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = None  # building not found
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post(
            f'/api/v1/projects/{project.project_id}/bookmark/',
            {
                'card_id': 'bld_999999',
                'action': 'save',
                'rank': 5,
            },
            format='json',
        )

    assert resp.status_code == 404
    assert resp.json().get('detail') == 'building not found'


# ── Security: architect follow non-existent architect → 404 (fix ③) ─────────

@pytest.mark.django_db
def test_architect_follow_nonexistent_returns_404(auth_client):
    """POST follow on an architect that has no publishable buildings → 404."""
    with patch('apps.recommendation.views.office_recommendation.connections') as mock_conns:
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchone.return_value = (0,)  # COUNT(*) = 0 → not found
        mock_conns.__getitem__.return_value.cursor.return_value = mock_cursor

        resp = auth_client.post('/api/v1/architects/arch_999999/follow/')

    assert resp.status_code == 404
    assert resp.json().get('detail') == 'Architect not found'


# ── FIX 2: promote next_image card shape regression test ─────────────────────

@pytest.mark.django_db
def test_promote_next_image_contains_image_url(auth_client, user_profile):
    """FIX 2: promote-to-taste response next_image must contain 'image_url' key
    (same card shape as SessionCreateView, built via engine.get_buildings_by_ids
    which calls _row_to_card).
    """
    draft = create_discovery_draft(user_profile)
    draft.liked_ids = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]
    draft.save(update_fields=['liked_ids'])
    draft_id_str = str(draft.project_id)

    mock_emb = np.array([0.1] * 384, dtype=np.float64)
    emb_map = {f'bld_{i:06d}': mock_emb for i in range(10)}

    # Card dict that mirrors what engine.get_buildings_by_ids/_row_to_card returns.
    normalized_card = {
        'canonical_bld_id': 'bld_000010',
        'image_url': 'https://example.com/cover.jpg',
        'name': 'Test Building',
        'metadata': {},
    }

    with patch('apps.recommendation.views.discovery.engine.get_pool_embeddings', return_value=emb_map), \
         patch('apps.recommendation.views.discovery.engine.update_preference_vector',
               side_effect=lambda pv, emb, a: emb), \
         patch('apps.recommendation.views.discovery.engine.create_pool_with_relaxation',
               return_value=(['bld_000010', 'bld_000011'], {}, 1)), \
         patch('apps.recommendation.views.discovery.engine.farthest_point_from_pool',
               return_value=None), \
         patch('apps.recommendation.views.discovery.engine.get_buildings_by_ids',
               return_value=[normalized_card]):
        resp = auth_client.post(
            '/api/v1/discovery/promote-to-taste/',
            {'draft_id': draft_id_str},
            format='json',
        )

    assert resp.status_code == 201
    payload = resp.json()
    next_image = payload.get('next_image')
    assert next_image is not None, 'next_image must not be None'
    assert 'image_url' in next_image, (
        f'next_image must contain image_url key; got keys: {list(next_image.keys())}'
    )
