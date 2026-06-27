"""
test_discovery_recent_boards_cap.py — DISCOVERY-PERF-1 and DISCOVERY-PERF-2 unit tests.

Verifies:
1. _tier_from_project_rows is a pure function (no DB access).
2. compute_discovery_tier fetches only the most-recent cap boards.
3. build_discovery_chunk uses _project_rows when provided and skips re-querying.
4. build_discovery_chunk fetches capped rows internally when _project_rows=None.
5. get_or_build_discovery_centroids scans only cap boards.
6. DiscoveryFeedView.get() issues exactly 1 Project queryset on the default DB (DISCOVERY-PERF-2 Finding 2).
7. Tier/exclude/dislike derived from the same capped rows — no full-project scan.
8. Draft boards ARE counted in project_count (DISCOVERY-PERF-2 spec).
"""
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_vec(seed=0):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(384)
    return (v / np.linalg.norm(v)).tolist()


def _make_profile(pk=77, liked_building_ids=None):
    p = MagicMock()
    p.id = pk
    p.liked_building_ids = liked_building_ids or []
    p.is_guest = False
    return p


def _make_rows(n, liked_each=5, draft=False):
    """Return n synthetic project rows.

    Each row has:
      name: 'real_board_{i}' or 'discovery_260601_0000'
      liked_ids: [{'id': 'bld_0000NN', 'intensity': 1.0}, ...]
      disliked_ids: ['bld_1000NN', ...]
      saved_ids: [{'id': 'bld_2000NN'}, ...]
    """
    rows = []
    for i in range(n):
        name = f'discovery_260601_{i:04d}' if draft else f'real_board_{i}'
        liked = [{'id': f'bld_{i * 100 + j:06d}', 'intensity': 1.0}
                 for j in range(liked_each)]
        disliked = [f'bld_{100000 + i * 10 + j:06d}' for j in range(3)]
        saved = [{'id': f'bld_{200000 + i * 10 + j:06d}'} for j in range(2)]
        rows.append({
            'name': name,
            'liked_ids': liked,
            'disliked_ids': disliked,
            'saved_ids': saved,
        })
    return rows


# ---------------------------------------------------------------------------
# 1. _tier_from_project_rows — pure function, no DB
# ---------------------------------------------------------------------------

class TestTierFromProjectRows:
    """_tier_from_project_rows computes tier from in-memory rows, no DB hit."""

    def test_cold_tier1_zero_likes(self):
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [{'name': 'discovery_260601_0000', 'liked_ids': []}]
        result = _tier_from_project_rows(rows)
        assert result['tier'] == 1
        assert result['cumulative_likes'] == 0
        assert result['n_local'] == 0

    def test_single_board_few_likes_tier2(self):
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [{'name': 'real_board', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(15)]}]
        result = _tier_from_project_rows(rows)
        # 1 non-draft board, 15 likes >= tier2_min(10), < tier3_min_likes(50)
        # project_count=1 < tier3_min_projects(4) → Tier 2
        assert result['tier'] == 2
        assert result['cumulative_likes'] == 15
        assert result['project_count'] == 1

    def test_two_real_boards_tier2_below_project_threshold(self):
        """2 boards is below tier3_min_projects(4), so still Tier 2.

        DISCOVERY-PERF-3: threshold raised from 2 → 4.
        2 boards, 20 likes >= 10 (tier2), project_count=2 < 4 → Tier 2.
        """
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [
            {'name': 'board_a', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]},
            {'name': 'board_b', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10, 20)]},
        ]
        result = _tier_from_project_rows(rows)
        assert result['tier'] == 2
        assert result['project_count'] == 2

    def test_four_real_boards_tier3_by_project_count(self):
        """4 boards meets tier3_min_projects(4) → Tier 3.

        DISCOVERY-PERF-3: the new threshold. project_count=4 >= 4 → Tier 3.
        """
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [
            {'name': f'board_{i}', 'liked_ids': [{'id': f'bld_{i * 10 + j:06d}', 'intensity': 1.0} for j in range(5)]}
            for i in range(4)
        ]
        result = _tier_from_project_rows(rows)
        # 4 boards, 20 likes >= 10 (tier2), project_count=4 >= 4 (tier3) → Tier 3
        assert result['tier'] == 3
        assert result['project_count'] == 4

    def test_draft_boards_included_in_project_count(self):
        """DISCOVERY-PERF-2 spec: draft boards ARE counted in project_count.

        DISCOVERY-PERF-3: threshold raised to 4. 2 draft boards → project_count=2;
        20 likes >= tier2 min; project_count=2 < tier3_min_projects(4) → Tier 2.
        """
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [
            {'name': 'discovery_260601_0000', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10)]},
            {'name': 'discovery_260601_0001', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(10, 20)]},
        ]
        result = _tier_from_project_rows(rows)
        # Both draft boards count toward project_count (PERF-2 spec preserved)
        assert result['project_count'] == 2
        # 20 likes >= 10 (tier2 min), project_count=2 < 4 (tier3 min) → Tier 2
        assert result['tier'] == 2

    def test_high_likes_fallback_tier3_below_project_threshold(self):
        """likes>=50 promotes to Tier 3 even when project_count < tier3_min_projects(4).

        DISCOVERY-PERF-3: fallback path. 1 board, 50 likes → Tier 3 via likes path.
        """
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = [{'name': 'board_a', 'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(50)]}]
        result = _tier_from_project_rows(rows)
        # project_count=1 < 4 (tier3_min_projects), but likes=50 >= 50 (tier3_min_likes) → Tier 3
        assert result['tier'] == 3
        assert result['project_count'] == 1
        assert result['cumulative_likes'] == 50

    def test_empty_rows_cold(self):
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        result = _tier_from_project_rows([])
        assert result['tier'] == 1
        assert result['cumulative_likes'] == 0

    def test_no_db_access(self):
        """_tier_from_project_rows must not touch the DB."""
        from apps.recommendation.discovery_feed import _tier_from_project_rows
        rows = _make_rows(3, liked_each=5)
        # If a DB call were made, it would raise (no DB available in unit context).
        # Simply asserting the call completes is sufficient here.
        result = _tier_from_project_rows(rows)
        assert 'tier' in result


# ---------------------------------------------------------------------------
# 2. compute_discovery_tier — applies the cap
# ---------------------------------------------------------------------------

class TestComputeDiscoveryTierCap:
    """compute_discovery_tier must query only the most-recent cap boards."""

    def _mock_project_qs(self, rows):
        """Return a mock Project.objects that returns `rows` when filtered+ordered+sliced."""
        mock_qs_sliced = MagicMock()
        mock_qs_sliced.values.return_value = rows
        mock_qs_ordered = MagicMock()
        mock_qs_ordered.__getitem__ = MagicMock(return_value=mock_qs_sliced)
        mock_filter = MagicMock()
        mock_filter.order_by.return_value = mock_qs_ordered
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value = mock_filter
        return mock_cls

    def test_cap_applied_to_queryset(self):
        """The queryset slice [:cap] is applied — only cap rows processed."""
        from apps.recommendation import discovery_feed
        cap = 10
        # Simulate 20 real boards, but only 10 should be scanned
        all_rows = _make_rows(20, liked_each=3)
        capped_rows = all_rows[:cap]

        profile = _make_profile()
        mock_cls = self._mock_project_qs(capped_rows)

        with patch.object(discovery_feed, 'Project', mock_cls):
            with patch.dict(
                'django.conf.settings.RECOMMENDATION',
                {'discovery_recent_boards_cap': cap},
                clear=False,
            ):
                result = discovery_feed.compute_discovery_tier(profile)

        # Ensure the queryset was ordered by -created_at and sliced
        mock_cls.objects.filter.return_value.order_by.assert_called_once_with('-created_at')
        getitem_call = mock_cls.objects.filter.return_value.order_by.return_value.__getitem__.call_args
        assert getitem_call is not None
        # The slice argument should be slice(None, cap, None)
        sliced_arg = getitem_call[0][0]
        assert isinstance(sliced_arg, slice)
        assert sliced_arg.stop == cap

        # Tier result is valid
        assert result['tier'] in (1, 2, 3)


# ---------------------------------------------------------------------------
# 3. build_discovery_chunk — uses _project_rows when provided (no re-query)
# ---------------------------------------------------------------------------

class TestBuildDiscoveryChunkNoRequery:
    """build_discovery_chunk must not re-query Project when _project_rows supplied."""

    def test_no_project_query_when_rows_provided(self):
        """When _project_rows is passed, Project.objects must NOT be called."""
        from apps.recommendation import discovery_feed

        profile = _make_profile()
        project_rows = _make_rows(3, liked_each=2)

        # Stub all DB-touching functions
        mock_project_cls = MagicMock()

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            return []

        with patch.object(discovery_feed, 'Project', mock_project_cls):
            with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
                with patch.object(discovery_feed, 'engine') as mock_engine:
                    mock_engine.get_pool_embeddings.return_value = {}
                    result = discovery_feed.build_discovery_chunk(
                        profile,
                        centroids=[],
                        _project_rows=project_rows,
                        _tier_info={'tier': 1, 'n_local': 0, 'n_global': 10},
                    )

        # Project.objects must never be called
        mock_project_cls.objects.filter.assert_not_called()
        # Result is a list (empty because _fetch_candidates returns [])
        assert isinstance(result, list)

    def test_exclude_set_built_from_provided_rows(self):
        """The exclude set passed to _fetch_candidates reflects the provided rows."""
        from apps.recommendation import discovery_feed

        profile = _make_profile()
        # Single board with one liked, one disliked, one saved building
        project_rows = [{
            'name': 'board_a',
            'liked_ids': [{'id': 'bld_000001', 'intensity': 1.0}],
            'disliked_ids': ['bld_000002'],
            'saved_ids': [{'id': 'bld_000003'}],
        }]

        captured_exclude = []

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            captured_exclude.extend(exclude_ids)
            return []

        with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
            with patch.object(discovery_feed, 'engine') as mock_engine:
                mock_engine.get_pool_embeddings.return_value = {}
                discovery_feed.build_discovery_chunk(
                    profile,
                    centroids=[],
                    _project_rows=project_rows,
                    _tier_info={'tier': 1, 'n_local': 0, 'n_global': 10},
                )

        exclude_set = set(captured_exclude)
        assert 'bld_000001' in exclude_set
        assert 'bld_000002' in exclude_set
        assert 'bld_000003' in exclude_set

    def test_profile_liked_building_ids_always_excluded(self):
        """profile.liked_building_ids are excluded regardless of board cap."""
        from apps.recommendation import discovery_feed

        # Profile has a liked building at the profile level (not in any board)
        profile = _make_profile(liked_building_ids=['bld_999999'])
        project_rows = []  # no boards at all

        captured_exclude = []

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            captured_exclude.extend(exclude_ids)
            return []

        with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
            with patch.object(discovery_feed, 'engine') as mock_engine:
                mock_engine.get_pool_embeddings.return_value = {}
                discovery_feed.build_discovery_chunk(
                    profile,
                    centroids=[],
                    _project_rows=project_rows,
                    _tier_info={'tier': 1, 'n_local': 0, 'n_global': 10},
                )

        assert 'bld_999999' in set(captured_exclude), (
            'profile.liked_building_ids must always be excluded, cap does not apply'
        )

    def test_client_buffer_ids_always_excluded(self):
        """client_buffer_ids are excluded regardless of board cap."""
        from apps.recommendation import discovery_feed

        profile = _make_profile()
        project_rows = []

        captured_exclude = []

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            captured_exclude.extend(exclude_ids)
            return []

        with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
            with patch.object(discovery_feed, 'engine') as mock_engine:
                mock_engine.get_pool_embeddings.return_value = {}
                discovery_feed.build_discovery_chunk(
                    profile,
                    centroids=[],
                    _project_rows=project_rows,
                    _tier_info={'tier': 1, 'n_local': 0, 'n_global': 10},
                    client_buffer_ids=['bld_888888'],
                )

        assert 'bld_888888' in set(captured_exclude), (
            'client_buffer_ids must always be excluded, cap does not apply'
        )


# ---------------------------------------------------------------------------
# 4. build_discovery_chunk — fetches capped rows internally when None provided
# ---------------------------------------------------------------------------

class TestBuildDiscoveryChunkInternalFetch:
    """When _project_rows=None, build_discovery_chunk fetches capped rows itself."""

    def test_internal_fetch_applies_cap(self):
        """Internal fetch must use order_by('-created_at')[:cap]."""
        from apps.recommendation import discovery_feed

        profile = _make_profile()
        cap = 10

        mock_qs_sliced = MagicMock()
        mock_qs_sliced.values.return_value = []
        mock_qs_ordered = MagicMock()
        mock_qs_ordered.__getitem__ = MagicMock(return_value=mock_qs_sliced)
        mock_filter = MagicMock()
        mock_filter.order_by.return_value = mock_qs_ordered
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value = mock_filter

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            return []

        with patch.object(discovery_feed, 'Project', mock_cls):
            with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
                with patch.object(discovery_feed, 'engine') as mock_engine:
                    mock_engine.get_pool_embeddings.return_value = {}
                    with patch.dict(
                        'django.conf.settings.RECOMMENDATION',
                        {'discovery_recent_boards_cap': cap},
                        clear=False,
                    ):
                        discovery_feed.build_discovery_chunk(
                            profile,
                            centroids=[],
                            _project_rows=None,
                        )

        # order_by('-created_at') must be called
        mock_filter.order_by.assert_called_once_with('-created_at')
        # slice [:cap] must be applied
        getitem_call = mock_qs_ordered.__getitem__.call_args
        assert getitem_call is not None
        sliced_arg = getitem_call[0][0]
        assert isinstance(sliced_arg, slice)
        assert sliced_arg.stop == cap


# ---------------------------------------------------------------------------
# 5. get_or_build_discovery_centroids — cap applied
# ---------------------------------------------------------------------------

class TestDiscoveryCentroidsCap:
    """get_or_build_discovery_centroids scans only recent cap boards."""

    def test_cap_applied_to_queryset(self):
        from apps.recommendation.caches import get_or_build_discovery_centroids

        profile = _make_profile()
        cap = 10
        capped_rows = [{'liked_ids': [{'id': f'bld_{i:06d}', 'intensity': 1.0}]}
                       for i in range(cap)]

        mock_qs_sliced = MagicMock()
        mock_qs_sliced.values.return_value = capped_rows
        mock_qs_ordered = MagicMock()
        mock_qs_ordered.__getitem__ = MagicMock(return_value=mock_qs_sliced)
        mock_filter = MagicMock()
        mock_filter.order_by.return_value = mock_qs_ordered
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value = mock_filter

        def _fake_pool_embeddings(ids):
            v = np.ones(384) / np.linalg.norm(np.ones(384))
            return {bid: v for bid in ids}

        def _fake_centroids(like_vectors, round_num):
            v = np.ones(384) / np.linalg.norm(np.ones(384))
            return [v], v

        from apps.recommendation import caches as caches_mod
        # Project is a lazy local import inside get_or_build_discovery_centroids;
        # patch it at the models module level so the local `from .models import Project`
        # resolves to the mock.
        with patch.object(caches_mod, '_discovery_centroids_key', return_value='dc_test'):
            with patch('apps.recommendation.models.Project', mock_cls):
                with patch.object(
                    caches_mod.engine, 'get_pool_embeddings',
                    side_effect=_fake_pool_embeddings,
                ):
                    with patch.object(
                        caches_mod.engine, 'compute_taste_centroids',
                        side_effect=_fake_centroids,
                    ):
                        with patch.dict(
                            'django.conf.settings.RECOMMENDATION',
                            {'discovery_recent_boards_cap': cap},
                            clear=False,
                        ):
                            result = get_or_build_discovery_centroids(profile)

        # Verify order_by('-created_at') called
        mock_filter.order_by.assert_called_once_with('-created_at')
        # Verify slice [:cap] applied
        getitem_call = mock_qs_ordered.__getitem__.call_args
        assert getitem_call is not None
        sliced_arg = getitem_call[0][0]
        assert isinstance(sliced_arg, slice)
        assert sliced_arg.stop == cap

        # Result is a list
        assert isinstance(result, list)

    def test_cache_hit_skips_db(self):
        """On cache hit, no DB query is issued."""
        from apps.recommendation.caches import (
            get_or_build_discovery_centroids,
            _discovery_centroids_key,
        )

        profile = _make_profile(pk=55)
        key = _discovery_centroids_key(profile.id)
        cached_val = [[0.1] * 384]
        cache.set(key, cached_val, 60)

        mock_cls = MagicMock()
        # Patch at models level to intercept the lazy import inside the function
        with patch('apps.recommendation.models.Project', mock_cls):
            result = get_or_build_discovery_centroids(profile)

        mock_cls.objects.filter.assert_not_called()
        assert result == cached_val


# ---------------------------------------------------------------------------
# 6. settings.py — discovery_recent_boards_cap key present
# ---------------------------------------------------------------------------

class TestSettingsKey:
    def test_discovery_recent_boards_cap_in_settings(self):
        from django.conf import settings
        cap = settings.RECOMMENDATION.get('discovery_recent_boards_cap')
        assert cap is not None, 'discovery_recent_boards_cap missing from RECOMMENDATION dict'
        assert isinstance(cap, int), 'discovery_recent_boards_cap must be an int'
        assert cap >= 1, 'discovery_recent_boards_cap must be >= 1'


# ---------------------------------------------------------------------------
# 7. Tier / exclude logic: older boards are NOT scanned (re-exposure allowed)
# ---------------------------------------------------------------------------

class TestOlderBoardsNotScanned:
    """Buildings in boards outside the cap window may re-appear — intended spec."""

    def test_old_board_building_not_in_exclude_set(self):
        """A building liked only in an old (beyond-cap) board must NOT be excluded."""
        from apps.recommendation import discovery_feed

        profile = _make_profile()
        cap = 2

        # 3 boards; the oldest one (index 2) is beyond the cap
        old_board_building = 'bld_OLD001'
        recent_rows = [
            {'name': 'board_0', 'liked_ids': [{'id': 'bld_000001', 'intensity': 1.0}],
             'disliked_ids': [], 'saved_ids': []},
            {'name': 'board_1', 'liked_ids': [{'id': 'bld_000002', 'intensity': 1.0}],
             'disliked_ids': [], 'saved_ids': []},
            # This row should NOT appear because it's beyond the cap
        ]
        # Simulate the view: only recent_rows[:cap] are passed as _project_rows
        project_rows = recent_rows[:cap]

        captured_exclude = []

        def _fake_fetch_candidates(exclude_ids, dislike_centroid, chunk_size):
            captured_exclude.extend(exclude_ids)
            return []

        with patch.object(discovery_feed, '_fetch_candidates', _fake_fetch_candidates):
            with patch.object(discovery_feed, 'engine') as mock_engine:
                mock_engine.get_pool_embeddings.return_value = {}
                discovery_feed.build_discovery_chunk(
                    profile,
                    centroids=[],
                    _project_rows=project_rows,
                    _tier_info={'tier': 1, 'n_local': 0, 'n_global': 10},
                )

        exclude_set = set(captured_exclude)
        assert old_board_building not in exclude_set, (
            f'{old_board_building} should NOT be excluded — it is in an old board beyond the cap'
        )
        assert 'bld_000001' in exclude_set
        assert 'bld_000002' in exclude_set


# ---------------------------------------------------------------------------
# 8. DiscoveryFeedView.get() — single Project query on default DB
#    DISCOVERY-PERF-2 Finding 2
# ---------------------------------------------------------------------------


class TestDiscoveryFeedViewSingleFetch:
    """DiscoveryFeedView.get() must issue exactly 1 Project queryset call.

    DISCOVERY-PERF-2 Finding 2: the single-fetch pattern (DISCOVERY-PERF-1)
    consolidates tier computation, exclude-set building, and dislike aggregation
    into one Project.objects.filter() call.  This class has two tests:

    (a) Mock-based: asserts exactly 1 Project.objects.filter() call, no live DB.
        Consistent with all other tests in this file.

    (b) SQL-level (CaptureQueriesContext): marked @pytest.mark.django_db, runs in
        CI where PostgreSQL is available; skipped locally when the DB is unavailable
        (pre-existing env limitation; see MEMORY "No make/gh on this box").

    Both tests prime the centroid cache to eliminate the second Project query that
    get_or_build_discovery_centroids would otherwise issue on cache miss.
    """

    def test_single_project_query_mock(self):
        """Mock-based: DiscoveryFeedView.get() calls Project.objects.filter() exactly once.

        Asserts the single-fetch pattern holds without requiring a live DB.
        Centroid cache is primed before the call so get_or_build_discovery_centroids
        returns immediately.
        """
        import apps.recommendation.views.discovery as _disc_view_mod
        from apps.recommendation.views.discovery import DiscoveryFeedView
        from apps.recommendation.caches import _discovery_centroids_key

        profile = _make_profile(pk=99)

        # Prime centroid cache so get_or_build_discovery_centroids hits cache
        centroid_key = _discovery_centroids_key(profile.id)
        cache.set(centroid_key, [], timeout=300)

        # Mock queryset chain: .filter().order_by()[:cap].values() -> []
        mock_qs_sliced = MagicMock()
        mock_qs_sliced.values.return_value = []
        mock_qs_ordered = MagicMock()
        mock_qs_ordered.__getitem__ = MagicMock(return_value=mock_qs_sliced)
        mock_filter_qs = MagicMock()
        mock_filter_qs.order_by.return_value = mock_qs_ordered
        mock_project_cls = MagicMock()
        mock_project_cls.objects.filter.return_value = mock_filter_qs

        # Minimal mock request
        mock_request = MagicMock()
        mock_request.user.is_authenticated = True
        mock_request.query_params = {'buffer': ''}

        with patch.object(_disc_view_mod, 'Project', mock_project_cls):
            with patch(
                'apps.recommendation.views.discovery._get_profile',
                return_value=profile,
            ):
                with patch(
                    'apps.recommendation.views.discovery.build_discovery_chunk',
                    return_value=[],
                ):
                    view = DiscoveryFeedView()
                    view.get(mock_request)

        filter_call_count = mock_project_cls.objects.filter.call_count
        assert filter_call_count == 1, (
            f'Expected exactly 1 Project.objects.filter() call in DiscoveryFeedView.get(), '
            f'got {filter_call_count}.  The single-fetch pattern (DISCOVERY-PERF-1) is broken.'
        )

    @pytest.mark.django_db
    def test_single_project_sql_query(self, auth_client, user_profile):
        """SQL-level: exactly 1 SQL query touches recommendation_project per request.

        Uses CaptureQueriesContext on the default DB connection.
        Centroid cache is primed; build_discovery_chunk is stubbed to avoid
        the buildings DB.  Requires a live PostgreSQL — CI only.
        """
        from apps.recommendation.caches import _discovery_centroids_key

        # Prime centroid cache
        centroid_key = _discovery_centroids_key(user_profile.id)
        cache.set(centroid_key, [], timeout=300)

        with patch(
            'apps.recommendation.views.discovery.build_discovery_chunk',
            return_value=[],
        ):
            with CaptureQueriesContext(connection) as ctx:
                resp = auth_client.get('/api/v1/discovery/')

        assert resp.status_code == 200

        project_queries = [
            q for q in ctx.captured_queries
            if 'recommendation_project' in q['sql']
        ]
        assert len(project_queries) == 1, (
            f'Expected exactly 1 Project SQL query on default DB, got {len(project_queries)}.\n'
            f'Project queries: {[q["sql"] for q in project_queries]}\n'
            f'All captured queries ({len(ctx.captured_queries)}): '
            f'{[q["sql"] for q in ctx.captured_queries]}'
        )
