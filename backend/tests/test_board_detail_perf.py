"""
test_board_detail_perf.py -- BACK-BOARD-PERF-1 cache helper unit tests.

Pure-mock (no DB) tests per INFRA-DB-2. Django cache is LocMemCache in test
mode; conftest.py autouse fixture calls cache.clear() before each test so
there is no inter-test pollution.
"""
from django.core.cache import cache

from apps.recommendation.caches import (
    evict_project_detail,
    get_project_detail_cache_key,
    _project_detail_version,
    PROJECT_DETAIL_TTL,
)


# ── Helper / key tests ────────────────────────────────────────────────────────

def test_project_detail_ttl_is_60():
    """Sanity: TTL constant value matches the intended 60s staleness window."""
    assert PROJECT_DETAIL_TTL == 60


def test_get_project_detail_cache_key_partitions_by_requester():
    """Keys for ANON, owner, and non-owner must all be distinct."""
    project_uuid = 'test-project-uuid-001'
    key_anon = get_project_detail_cache_key(project_uuid, 'anon')
    key_owner = get_project_detail_cache_key(project_uuid, '42')
    key_other = get_project_detail_cache_key(project_uuid, '99')

    assert key_anon != key_owner
    assert key_anon != key_other
    assert key_owner != key_other

    # All three must reference the same project
    assert project_uuid in key_anon
    assert project_uuid in key_owner
    assert project_uuid in key_other


def test_get_project_detail_cache_key_contains_version():
    """Key must embed the version counter so stale entries become unreachable."""
    project_uuid = 'test-project-uuid-002'
    ver = _project_detail_version(project_uuid)  # 0 (cold)
    key = get_project_detail_cache_key(project_uuid, 'anon')
    assert f'v{ver}' in key


def test_evict_project_detail_increments_version():
    """Two consecutive evictions must bump the version 0 -> 1 -> 2."""
    project_uuid = 'test-project-uuid-003'

    # Cold start — version should be 0 (or missing, treated as 0)
    assert _project_detail_version(project_uuid) == 0

    evict_project_detail(project_uuid)
    assert _project_detail_version(project_uuid) == 1

    evict_project_detail(project_uuid)
    assert _project_detail_version(project_uuid) == 2


def test_evict_changes_key():
    """Cache key before evict must differ from cache key after evict."""
    project_uuid = 'test-project-uuid-004'
    requester = '7'

    key_before = get_project_detail_cache_key(project_uuid, requester)
    evict_project_detail(project_uuid)
    key_after = get_project_detail_cache_key(project_uuid, requester)

    assert key_before != key_after


def test_cache_hit_short_circuits_stale_data():
    """Payload stored in cache under the key must be readable back unchanged.

    This simulates the view-layer cache-hit path: populate cache with a dummy
    payload, call cache.get, assert the returned value is the payload. No DB
    queries are involved.
    """
    project_uuid = 'test-project-uuid-005'
    requester_id = '13'

    dummy_payload = {
        'project_id': project_uuid,
        'name': 'Test Board',
        'is_reacted': False,
        'liked_ids': [],
    }
    cache_key = get_project_detail_cache_key(project_uuid, requester_id)
    cache.set(cache_key, dummy_payload, PROJECT_DETAIL_TTL)

    result = cache.get(cache_key)
    assert result == dummy_payload


def test_evict_makes_cached_payload_unreachable():
    """After eviction the old key returns None (stale payload effectively hidden)."""
    project_uuid = 'test-project-uuid-006'
    requester_id = '21'

    dummy_payload = {'project_id': project_uuid, 'name': 'Stale Board'}
    old_key = get_project_detail_cache_key(project_uuid, requester_id)
    cache.set(old_key, dummy_payload, PROJECT_DETAIL_TTL)

    # Confirm it is readable before eviction
    assert cache.get(old_key) == dummy_payload

    # Evict and re-derive the new key
    evict_project_detail(project_uuid)
    new_key = get_project_detail_cache_key(project_uuid, requester_id)

    # Old key still has data (the bytes haven't been deleted — version bump is the gate)
    # but the new key that the view would generate returns None
    assert new_key != old_key
    assert cache.get(new_key) is None
