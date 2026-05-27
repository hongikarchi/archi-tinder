"""
test_profile_perf.py — Profile-page latency optimisation tests.

Covers:
  Fix 1: engine.get_building_thumbnails — minimal 2-column SQL, not 17-column.
  Fix 2: _build_boards_field calls get_building_thumbnails, not get_buildings_by_ids.
  Fix 3: UserProfileDetailView response cache (60 s TTL + version-based invalidation).

DB tests (Fixes 2+3) are run via @pytest.mark.django_db where a local Postgres
test DB is available (CI). They are skipped with pytest.mark.skip on local
machines where the Neon role lacks CREATEDB. The CI gate is authoritative.
"""
from unittest.mock import MagicMock, patch
from django.core.cache import cache


# ── Fix 1 — get_building_thumbnails: minimal SQL ──────────────────────────────

def test_get_building_thumbnails_minimal_columns():
    """get_building_thumbnails issues a SELECT with only canonical_bld_id +
    COALESCE-derived image_url — NOT the 17-column full-card SELECT.

    Uses a mock cursor so no real DB needed; verifies SQL content.
    """
    from apps.recommendation import engine

    thumb_rows = [
        {'canonical_bld_id': 'bld_001', 'image_url': 'https://cdn.example.com/a.jpg'},
        {'canonical_bld_id': 'bld_002', 'image_url': 'https://cdn.example.com/b.jpg'},
    ]

    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    # Patch _dictfetchall so it returns our shaped dicts directly.
    with patch.object(engine, '_dictfetchall', return_value=thumb_rows) as mock_dfa, \
         patch.object(engine.connection, 'cursor', return_value=mock_cursor):
        result = engine.get_building_thumbnails(['bld_001', 'bld_002'])

    # _dictfetchall was called (DB was hit for cache misses)
    assert mock_dfa.called

    # Verify the SQL executed contained only the two lightweight columns and no
    # heavy fields (name, architect_names, visual_description, all_images, etc.)
    executed_sql = mock_cursor.execute.call_args[0][0]
    assert 'canonical_bld_id' in executed_sql
    assert 'COALESCE' in executed_sql
    # Negative: heavy full-card columns must NOT appear
    assert 'architect_names' not in executed_sql
    assert 'visual_description' not in executed_sql
    assert 'all_images' not in executed_sql
    # Publishability gate must be present
    assert 'is_publishable' in executed_sql

    # Return shape: list of {canonical_bld_id, image_url}
    assert len(result) == 2
    assert result[0] == {'canonical_bld_id': 'bld_001', 'image_url': 'https://cdn.example.com/a.jpg'}
    assert result[1] == {'canonical_bld_id': 'bld_002', 'image_url': 'https://cdn.example.com/b.jpg'}


def test_get_building_thumbnails_empty_input():
    """Empty input returns empty list without touching DB."""
    from apps.recommendation import engine
    with patch.object(engine.connection, 'cursor') as mock_cursor:
        result = engine.get_building_thumbnails([])
    assert result == []
    mock_cursor.assert_not_called()


def test_get_building_thumbnails_cache_hit():
    """Second call for the same ID is served from cache — no DB round trip."""
    from apps.recommendation import engine

    thumb = {'canonical_bld_id': 'bld_001', 'image_url': 'https://cdn.example.com/a.jpg'}
    # Pre-seed thumb cache
    cache.set(f'{engine._THUMB_CACHE_KEY_PREFIX}bld_001', thumb, 300)

    with patch.object(engine.connection, 'cursor') as mock_cursor:
        result = engine.get_building_thumbnails(['bld_001'])

    # No DB cursor opened
    mock_cursor.assert_not_called()
    assert result == [thumb]


def test_get_building_thumbnails_coalesce_priority():
    """COALESCE priority matches _row_to_card: display_cover_url first,
    then cover_image_url_default, then covers_by_type->>'exterior'.
    """
    from apps.recommendation import engine

    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    with patch.object(engine, '_dictfetchall', return_value=[]), \
         patch.object(engine.connection, 'cursor', return_value=mock_cursor):
        engine.get_building_thumbnails(['bld_999'])

    executed_sql = mock_cursor.execute.call_args[0][0]
    # Confirm COALESCE order: display_cover_url before cover_image_url_default
    # before covers_by_type->>'exterior'
    dcov_pos = executed_sql.find('display_cover_url')
    ciud_pos = executed_sql.find('cover_image_url_default')
    ext_pos = executed_sql.find("'exterior'")
    assert dcov_pos != -1, "display_cover_url missing from SQL"
    assert ciud_pos != -1, "cover_image_url_default missing from SQL"
    assert ext_pos != -1, "exterior key missing from SQL"
    assert dcov_pos < ciud_pos < ext_pos, (
        f"COALESCE priority wrong: display_cover_url@{dcov_pos} "
        f"cover_image_url_default@{ciud_pos} exterior@{ext_pos}"
    )


# ── Fix 2 — _build_boards_field uses thumbnails-only fetch ───────────────────

def test_build_boards_field_uses_thumbnails_not_full_cards():
    """_build_boards_field calls engine.get_building_thumbnails and NOT
    engine.get_buildings_by_ids when building images are needed.

    Uses mock Project model to avoid DB — tests the callsite routing only.
    """
    from apps.accounts.views import _build_boards_field

    # Build a mock profile and project list
    mock_project = MagicMock()
    mock_project.project_id = 'proj-001'
    mock_project.name = 'Test Board'
    mock_project.created_at.isoformat.return_value = '2026-05-27T00:00:00'
    mock_project.visibility = 'public'
    mock_project.liked_ids = [{'id': 'bld_001'}]
    mock_project.saved_ids = []

    mock_qs = MagicMock()
    mock_qs.count.return_value = 1
    mock_qs.__getitem__ = lambda s, k: [mock_project]
    mock_qs.filter.return_value = mock_qs
    mock_qs.order_by.return_value = mock_qs

    mock_profile = MagicMock()

    # _build_boards_field does a local `from apps.recommendation.models import Project`
    # and `from apps.recommendation import engine`, so patch at the source module level.
    thumb_result = [{'canonical_bld_id': 'bld_001', 'image_url': 'https://example.com/img.jpg'}]
    with patch('apps.recommendation.models.Project') as MockProject, \
         patch('apps.recommendation.engine.get_building_thumbnails',
               return_value=thumb_result) as mock_thumbs, \
         patch('apps.recommendation.engine.get_buildings_by_ids') as mock_full:
        MockProject.objects.filter.return_value = mock_qs
        result = _build_boards_field(mock_profile, is_owner=True)

    mock_thumbs.assert_called_once_with(['bld_001'])
    mock_full.assert_not_called()

    # Result shape intact
    assert 'items' in result
    assert result['total_count'] == 1


# ── Fix 3 — UserProfileDetailView response cache + invalidation ───────────────

def test_user_profile_detail_cache_key_helper():
    """get_user_profile_detail_cache_key embeds version, requester, and pagination."""
    from apps.recommendation.caches import get_user_profile_detail_cache_key
    # With no version key set, version defaults to 0
    cache.delete('user_profile_version:42')
    key = get_user_profile_detail_cache_key(42, 'anon', 1, 12)
    assert 'user_profile_detail:42' in key
    assert 'v0' in key
    assert 'ranon' in key
    assert 'p1' in key
    assert 'ps12' in key


def test_evict_user_profile_detail_bumps_version():
    """evict_user_profile_detail increments the version so old keys become stale."""
    from apps.recommendation.caches import (
        evict_user_profile_detail,
        _user_profile_version,
    )
    cache.delete('user_profile_version:99')
    assert _user_profile_version(99) == 0

    evict_user_profile_detail(99)
    assert _user_profile_version(99) == 1

    evict_user_profile_detail(99)
    assert _user_profile_version(99) == 2


def test_evict_user_profile_detail_from_zero():
    """First eviction (key absent) initialises version to 1."""
    from apps.recommendation.caches import (
        evict_user_profile_detail,
        _user_profile_version,
    )
    cache.delete('user_profile_version:777')
    evict_user_profile_detail(777)
    assert _user_profile_version(777) == 1


def test_profile_detail_cache_key_changes_after_eviction():
    """After eviction the cache key changes (version bump), so old payload
    is no longer retrievable under the new key.
    """
    from apps.recommendation.caches import (
        get_user_profile_detail_cache_key,
        evict_user_profile_detail,
        PROFILE_DETAIL_TTL,
    )
    cache.delete('user_profile_version:55')

    key_v0 = get_user_profile_detail_cache_key(55, 'anon', 1, 12)
    cache.set(key_v0, {'display_name': 'Old Name'}, PROFILE_DETAIL_TTL)
    assert cache.get(key_v0) is not None

    evict_user_profile_detail(55)

    key_v1 = get_user_profile_detail_cache_key(55, 'anon', 1, 12)
    assert key_v0 != key_v1, "Key must change after eviction"
    # Old entry still technically in cache under v0 key (TTL-based GC)
    # but the new key returns None (cache miss → forces rebuild)
    assert cache.get(key_v1) is None
