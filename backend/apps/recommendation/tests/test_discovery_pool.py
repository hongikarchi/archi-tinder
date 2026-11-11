"""Tests for the pre-built Discovery candidate pool (no DB access)."""
from unittest import mock

import pytest

from apps.recommendation import discovery_feed, discovery_pool


def _row(i, vec):
    return {'canonical_bld_id': f'bld_{i:06d}', 'embedding': str(vec), '_vec': list(vec)}


@pytest.fixture(autouse=True)
def _reset_pool():
    discovery_pool.reset_for_tests()
    yield
    discovery_pool.reset_for_tests()


def _set_pool(rows):
    discovery_pool._pool = rows
    discovery_pool._built_at = __import__('time').monotonic()


def test_pool_used_and_exclusion_respected():
    rows = [_row(i, [1.0, 0.0]) for i in range(60)]
    _set_pool(rows)
    excluded = {r['canonical_bld_id'] for r in rows[:20]}
    out = discovery_feed._candidates_from_pool(excluded, None, 10)
    assert out is not None and len(out) == 40
    assert not ({r['canonical_bld_id'] for r in out} & excluded)


def test_dislike_zone_filtered():
    near = [_row(i, [1.0, 0.0]) for i in range(30)]
    far = [_row(100 + i, [0.0, 1.0]) for i in range(30)]
    _set_pool(near + far)
    out = discovery_feed._candidates_from_pool(set(), [1.0, 0.0], 10)
    ids = {r['canonical_bld_id'] for r in out}
    assert ids == {r['canonical_bld_id'] for r in far}


def test_too_small_after_exclusion_returns_none():
    rows = [_row(i, [1.0, 0.0]) for i in range(25)]
    _set_pool(rows)
    excluded = {r['canonical_bld_id'] for r in rows[:10]}
    assert discovery_feed._candidates_from_pool(excluded, None, 10) is None


def test_none_pool_returns_none():
    assert discovery_feed._candidates_from_pool(set(), None, 10) is None


def test_shallow_copy_isolation():
    rows = [_row(i, [1.0, 0.0]) for i in range(40)]
    _set_pool(rows)
    out = discovery_feed._candidates_from_pool(set(), None, 10)
    out[0]['_vec'] = 'mutated'
    out[0]['extra'] = 1
    assert all(r['_vec'] != 'mutated' and 'extra' not in r for r in rows)


def test_build_pool_never_raises():
    with mock.patch.dict(discovery_pool._dj_connections.__dict__, {}, clear=False), \
            mock.patch.object(discovery_pool, '_dj_connections',
                              mock.MagicMock(__getitem__=mock.Mock(side_effect=RuntimeError('boom')))):
        assert discovery_pool.build_pool() is None


def test_build_pool_parses_and_warms_cache():
    cur = mock.MagicMock()
    cur.fetchall.side_effect = [
        [('a',), ('b',)],
        [('a', '[1,2]'), ('b', '[3,4]')],
    ]
    conn = mock.MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conns = mock.MagicMock()
    conns.__getitem__.return_value = conn
    settings_rc = {'discovery_pool_size': 2, 'discovery_tablesample_pct': 2.0}
    with mock.patch.object(discovery_pool, '_dj_connections', conns), \
            mock.patch.object(discovery_pool, '_rc', return_value=settings_rc), \
            mock.patch('apps.recommendation.engine.get_buildings_by_ids') as warm:
        rows = discovery_pool.build_pool()
    assert [r['canonical_bld_id'] for r in rows] == ['a', 'b']
    assert rows[1]['_vec'] == [3.0, 4.0]
    warm.assert_called_once_with(['a', 'b'])


def test_get_pool_never_built_is_none_and_stale_triggers_one_rebuild():
    assert discovery_pool.get_pool() is None
    _set_pool([_row(1, [1.0])])
    discovery_pool._built_at -= 10_000
    with mock.patch.object(discovery_pool.threading, 'Thread') as thread:
        assert discovery_pool.get_pool() is not None
        assert discovery_pool.get_pool() is not None
    assert thread.call_count == 1
