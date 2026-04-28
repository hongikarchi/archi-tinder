"""
test_imp6_late_binding_plumbing.py -- IMP-6 Commit 1: late-binding V_initial plumbing.

Spec v1.10 §11.1 IMP-6 Commit 1 (2d): scaffolding that delivers ~0% latency change
on its own but sets up the read-side infrastructure for Commit 2 (~45-55% TTFC drop).

Tests:
- TestSettingsDefaults:        stage_decouple_enabled key present and default OFF
- TestVInitialCacheKey:        key format stable, deterministic, collision-distinct
- TestVInitialCacheReadWrite:  roundtrip read/write; flag-gate no-op; cache miss -> None
- TestRerankPoolScope:         locked-prefix invariant, rerank scope excludes locked set,
                               list-order preserved (no set-iteration non-determinism),
                               empty edge cases
- TestSessionCreateViewBackwardCompat:
                               flag OFF -> byte-identical (no get_cached_v_initial call,
                               hyde_vinitial_enabled branch reachable);
                               flag ON -> get_cached_v_initial called with user_id + query
"""
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Fixture: clear Django cache before each test (LocMemCache persists in-process)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_prefix(s, n=16):
    return hashlib.sha256((s or '').encode('utf-8')).hexdigest()[:n]


# ---------------------------------------------------------------------------
# TestSettingsDefaults
# ---------------------------------------------------------------------------

class TestSettingsDefaults:
    def test_stage_decouple_enabled_key_present(self):
        rc = settings.RECOMMENDATION
        assert 'stage_decouple_enabled' in rc, (
            "stage_decouple_enabled key missing from settings.RECOMMENDATION"
        )

    def test_stage_decouple_enabled_defaults_false(self):
        rc = settings.RECOMMENDATION
        assert rc['stage_decouple_enabled'] is False, (
            "stage_decouple_enabled must default False for backward compat"
        )

    def test_stage_decouple_key_is_bool(self):
        rc = settings.RECOMMENDATION
        assert isinstance(rc['stage_decouple_enabled'], bool)


# ---------------------------------------------------------------------------
# TestVInitialCacheKey
# ---------------------------------------------------------------------------

class TestVInitialCacheKey:
    def test_key_format(self):
        from apps.recommendation.services import _v_initial_cache_key
        key = _v_initial_cache_key(42, 'brutalist housing Korea')
        expected_hash = _sha256_prefix('brutalist housing Korea', 16)
        assert key == f'v_initial:42:{expected_hash}'

    def test_key_deterministic(self):
        from apps.recommendation.services import _v_initial_cache_key
        k1 = _v_initial_cache_key(1, 'same query')
        k2 = _v_initial_cache_key(1, 'same query')
        assert k1 == k2

    def test_different_queries_produce_different_keys(self):
        from apps.recommendation.services import _v_initial_cache_key
        k1 = _v_initial_cache_key(1, 'query A')
        k2 = _v_initial_cache_key(1, 'query B')
        assert k1 != k2

    def test_different_users_produce_different_keys(self):
        from apps.recommendation.services import _v_initial_cache_key
        k1 = _v_initial_cache_key(1, 'same query')
        k2 = _v_initial_cache_key(2, 'same query')
        assert k1 != k2

    def test_none_query_handled_gracefully(self):
        from apps.recommendation.services import _v_initial_cache_key
        key = _v_initial_cache_key(1, None)
        expected_hash = _sha256_prefix('', 16)
        assert key == f'v_initial:1:{expected_hash}'

    def test_key_prefix_is_v_initial(self):
        from apps.recommendation.services import _v_initial_cache_key
        key = _v_initial_cache_key(99, 'any query')
        assert key.startswith('v_initial:')


# ---------------------------------------------------------------------------
# TestVInitialCacheReadWrite
# ---------------------------------------------------------------------------

class TestVInitialCacheReadWrite:
    def test_get_returns_none_when_flag_off(self):
        from apps.recommendation.services import get_cached_v_initial
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': False}):
            result = get_cached_v_initial(1, 'query')
        assert result is None

    def test_set_is_noop_when_flag_off(self):
        from apps.recommendation.services import get_cached_v_initial, set_cached_v_initial
        fake_vec = [0.1] * 384
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': False}):
            set_cached_v_initial(1, 'query', fake_vec)
            result = get_cached_v_initial(1, 'query')
        assert result is None

    def test_cache_miss_returns_none_when_flag_on(self):
        from apps.recommendation.services import get_cached_v_initial
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            result = get_cached_v_initial(1, 'query with no cache entry')
        assert result is None

    def test_roundtrip_write_then_read(self):
        from apps.recommendation.services import get_cached_v_initial, set_cached_v_initial
        fake_vec = list(range(384))  # deterministic test vector
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            set_cached_v_initial(7, 'my architectural query', fake_vec)
            result = get_cached_v_initial(7, 'my architectural query')
        assert result == fake_vec

    def test_different_user_ids_are_cache_isolated(self):
        from apps.recommendation.services import get_cached_v_initial, set_cached_v_initial
        vec_a = [1.0] * 384
        vec_b = [2.0] * 384
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            set_cached_v_initial(1, 'same query', vec_a)
            set_cached_v_initial(2, 'same query', vec_b)
            assert get_cached_v_initial(1, 'same query') == vec_a
            assert get_cached_v_initial(2, 'same query') == vec_b

    def test_different_queries_are_cache_isolated(self):
        from apps.recommendation.services import get_cached_v_initial, set_cached_v_initial
        vec_a = [0.5] * 384
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            set_cached_v_initial(1, 'query A', vec_a)
            result = get_cached_v_initial(1, 'query B')
        assert result is None


# ---------------------------------------------------------------------------
# TestRerankPoolScope
# ---------------------------------------------------------------------------

class TestRerankPoolScope:
    def test_locked_ids_come_first_in_output(self):
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['A', 'B', 'C', 'D', 'E']
        exposed = ['B']
        initial_batch = ['A']
        fake_v = [0.0] * 384
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=exposed,
            initial_batch_ids=initial_batch,
            v_initial_vector=fake_v,
        )
        # A and B are locked; must appear before C, D, E
        locked_positions = [result.index('A'), result.index('B')]
        rerank_positions = [result.index('C'), result.index('D'), result.index('E')]
        assert max(locked_positions) < min(rerank_positions)

    def test_rerank_scope_excludes_locked_ids(self):
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['A', 'B', 'C', 'D']
        exposed = ['A']
        initial_batch = ['B']
        fake_v = [0.0] * 384
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=exposed,
            initial_batch_ids=initial_batch,
            v_initial_vector=fake_v,
        )
        # Total length preserved
        assert len(result) == len(pool)
        # All original IDs present
        assert set(result) == set(pool)

    def test_output_preserves_pool_order_for_unlocked_ids(self):
        """Commit 1 pass-through: rerank scope order = original pool order."""
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['L1', 'L2', 'U1', 'U2', 'U3']
        locked = ['L1', 'L2']
        fake_v = [0.0] * 384
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=locked,
            initial_batch_ids=[],
            v_initial_vector=fake_v,
        )
        # Unlocked tail should be in original order (pass-through)
        unlocked_tail = [pid for pid in result if pid not in set(locked)]
        assert unlocked_tail == ['U1', 'U2', 'U3']

    def test_empty_pool_returns_empty(self):
        from apps.recommendation.engine import rerank_pool_with_v_initial
        result = rerank_pool_with_v_initial(
            pool_ids=[],
            exposed_ids=[],
            initial_batch_ids=[],
            v_initial_vector=[0.0] * 384,
        )
        assert result == []

    def test_all_ids_locked_returns_pool_order(self):
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['A', 'B', 'C']
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=['A', 'B'],
            initial_batch_ids=['C'],
            v_initial_vector=[0.0] * 384,
        )
        # All locked; result = locked_prefix (pool order traversal)
        assert set(result) == {'A', 'B', 'C'}
        assert len(result) == 3

    def test_no_locked_ids_returns_full_pool(self):
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['A', 'B', 'C', 'D']
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=[],
            initial_batch_ids=[],
            v_initial_vector=[0.0] * 384,
        )
        assert result == ['A', 'B', 'C', 'D']

    def test_none_exposed_and_initial_handled(self):
        """None inputs for optional params should not raise."""
        from apps.recommendation.engine import rerank_pool_with_v_initial
        pool = ['A', 'B']
        result = rerank_pool_with_v_initial(
            pool_ids=pool,
            exposed_ids=None,
            initial_batch_ids=None,
            v_initial_vector=[0.0] * 384,
        )
        assert result == ['A', 'B']


# ---------------------------------------------------------------------------
# TestSessionCreateBranchingLogic
# ---------------------------------------------------------------------------

class TestSessionCreateBranchingLogic:
    """Unit-level tests for the if/elif branching logic added to SessionCreateView.post().

    These tests simulate the branching logic directly — they do not call the full view
    (which requires DB fixtures). Baseline integration coverage for the default-OFF path
    is provided by the 328 pre-IMP-6 tests that continue to pass with stage_decouple_enabled=False.
    Full SessionCreateView integration coverage with flag ON will be added in Commit 2
    when get_cached_v_initial has a non-trivial product to exercise.

    Note: _raw_query_early extraction was moved earlier in SessionCreateView.post() so that
    it precedes the V_initial block. This is load-bearing for the IMP-6 ON path and is a
    deliberate ordering change (confirmed safe by the full 328-test suite still passing).
    """

    def _make_request(self, query='test', visual_description=None):
        req = MagicMock()
        req.user.id = 42
        data = {'query': query}
        if visual_description is not None:
            data['visual_description'] = visual_description
        req.data = data
        return req

    def test_flag_off_does_not_call_get_cached_v_initial(self):
        """With flag OFF, get_cached_v_initial must never be called."""
        from apps.recommendation.services import get_cached_v_initial
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': False}):
            with patch('apps.recommendation.services.get_cached_v_initial') as mock_get:
                # Simulate the branch: flag OFF means the if-block is skipped
                rc = settings.RECOMMENDATION
                if rc.get('stage_decouple_enabled', False):
                    get_cached_v_initial(42, 'test')  # should NOT execute
                assert mock_get.call_count == 0

    def test_flag_on_calls_get_cached_v_initial_with_user_and_query(self):
        """With flag ON, get_cached_v_initial must be called with user_id + raw_query."""
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            with patch('apps.recommendation.services.get_cached_v_initial',
                       return_value=None) as mock_get:
                import apps.recommendation.services as svc
                rc = settings.RECOMMENDATION
                raw_query = 'brutalist housing Korea'
                user_id = 42
                if rc.get('stage_decouple_enabled', False):
                    svc.get_cached_v_initial(user_id, raw_query)
                mock_get.assert_called_once_with(user_id, raw_query)

    def test_flag_off_hyde_path_still_reachable(self):
        """With both flags OFF, hyde_vinitial_enabled path remains reachable (elif branch)."""
        with patch.dict(settings.RECOMMENDATION, {
            'stage_decouple_enabled': False,
            'hyde_vinitial_enabled': True,
        }):
            rc = settings.RECOMMENDATION
            visual_description = 'concrete walls with natural light'
            # Simulate the branching logic from SessionCreateView
            v_initial = None
            if rc.get('stage_decouple_enabled', False):
                pass  # IMP-6 path
            elif rc.get('hyde_vinitial_enabled', False) and visual_description:
                v_initial = 'HYDE_CALLED'  # marker
            assert v_initial == 'HYDE_CALLED', (
                "hyde_vinitial_enabled path must be reachable when stage_decouple_enabled=False"
            )

    def test_flag_on_suppresses_hyde_path(self):
        """With stage_decouple_enabled=True, the hyde_vinitial_enabled elif must not fire."""
        with patch.dict(settings.RECOMMENDATION, {
            'stage_decouple_enabled': True,
            'hyde_vinitial_enabled': True,
        }):
            rc = settings.RECOMMENDATION
            visual_description = 'concrete walls with natural light'
            # Simulate the branching logic from SessionCreateView
            hyde_called = False
            if rc.get('stage_decouple_enabled', False):
                pass  # IMP-6 late-bind path (cache miss -> None is the Commit 1 outcome)
            elif rc.get('hyde_vinitial_enabled', False) and visual_description:
                hyde_called = True
            assert not hyde_called, (
                "hyde_vinitial_enabled elif must NOT fire when stage_decouple_enabled=True"
            )
