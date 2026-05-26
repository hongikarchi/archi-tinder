"""
test_discovery_perf.py -- BACK-PERFORMANCE-4: Discovery cold-path optimisations.

Tests:
1. test_taste_ranked_page_uses_direct_query_no_cte
   SQL does NOT contain the CTE barrier (`WITH ranked AS`).
2. test_compute_user_taste_vector_caps_at_50_likes
   get_pool_embeddings is called with at most 50 distinct IDs even when the
   user has 80+ liked buildings across projects.
3. test_swipe_spawns_async_warm_taste_thread
   After a swipe, a daemon thread targeting _async_warm_taste is constructed
   and started.
"""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_vec(seed=0):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(384)
    return (v / np.linalg.norm(v)).tolist()


def _make_profile(pk=42):
    p = MagicMock()
    p.id = pk
    return p


# ---------------------------------------------------------------------------
# Fix 1 — CTE removed from taste_ranked_page
# ---------------------------------------------------------------------------

class TestTasteRankedPageNoCTE:
    """taste_ranked_page SQL must NOT contain a WITH ranked AS CTE."""

    def test_taste_ranked_page_uses_direct_query_no_cte(self):
        """Executed SQL does not contain the CTE pattern 'WITH ranked AS'."""
        from apps.recommendation import engine

        v_taste = _fake_vec()
        executed_sqls = []

        class _FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def execute(self, sql, params=None):
                executed_sqls.append(sql)

            def fetchall(self):
                return []

            @property
            def description(self):
                return []

        class _FakeConnection:
            def cursor(self):
                return _FakeCursor()

        with patch('apps.recommendation.engine.connection', _FakeConnection()):
            engine.taste_ranked_page(
                v_taste=v_taste,
                exclude_ids=[],
                limit=12,
                offset=0,
            )

        # Filter out internal introspection queries (information_schema.columns check
        # performed by _build_select_columns) — we only care about the ranking query.
        ranking_sqls = [s for s in executed_sqls if 'canonical_v2_buildings' in s and 'information_schema' not in s]
        assert len(ranking_sqls) == 1, (
            f'Expected exactly 1 ranking SQL call, got {len(ranking_sqls)}.\n'
            f'All executed SQL: {executed_sqls}'
        )
        sql = ranking_sqls[0]
        assert 'WITH ranked AS' not in sql, (
            f'CTE pattern "WITH ranked AS" found in SQL — top-K push-down not applied.\n'
            f'SQL: {sql}'
        )
        # Confirm ORDER BY and LIMIT are present (the push-down requires both).
        assert 'ORDER BY' in sql, 'ORDER BY missing from SQL'
        assert 'LIMIT' in sql, 'LIMIT missing from SQL'
        assert 'is_publishable = true' in sql, 'is_publishable gate missing'


# ---------------------------------------------------------------------------
# Fix 2 — compute_user_taste_vector caps at 50 likes
# ---------------------------------------------------------------------------

class TestComputeUserTasteVectorCap:
    """compute_user_taste_vector passes at most 50 IDs to get_pool_embeddings.

    Uses mock queryset chain — no DB access required.
    """

    @staticmethod
    def _mock_project_class(liked_lists):
        """Return a mock Project class whose .objects.filter().order_by().values_list() returns liked_lists."""
        mock_cls = MagicMock()
        mock_cls.objects.filter.return_value.order_by.return_value.values_list.return_value = liked_lists
        return mock_cls

    def test_compute_user_taste_vector_caps_at_50_likes(self):
        """User with 80 liked buildings: get_pool_embeddings receives <= 50 IDs."""
        from apps.recommendation import engine

        # 80 liked entries across 2 simulated projects (40 each).
        liked_a = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(40)]
        liked_b = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(40, 80)]

        profile = _make_profile(pk=42)
        captured_ids = []

        def _fake_pool_embeddings(ids):
            captured_ids.extend(ids)
            v = np.ones(384) / np.linalg.norm(np.ones(384))
            return {bid: v.tolist() for bid in ids}

        # Project is imported locally inside compute_user_taste_vector via
        # `from .models import Project`, so patch at the models module.
        with patch('apps.recommendation.models.Project', self._mock_project_class([liked_a, liked_b])):
            with patch.object(engine, 'get_pool_embeddings', side_effect=_fake_pool_embeddings):
                result = engine.compute_user_taste_vector(profile)

        assert result is not None, 'Expected a taste vector, got None'
        assert len(captured_ids) <= 50, (
            f'get_pool_embeddings received {len(captured_ids)} IDs — cap not applied (expected <= 50)'
        )

    def test_compute_user_taste_vector_fewer_than_50_unchanged(self):
        """User with 20 liked buildings: all 20 are passed (cap does not truncate small sets)."""
        from apps.recommendation import engine

        liked = [{'id': f'bld_{i:06d}', 'intensity': 1.0} for i in range(20)]

        profile = _make_profile(pk=43)
        captured_ids = []

        def _fake_pool_embeddings(ids):
            captured_ids.extend(ids)
            v = np.ones(384) / np.linalg.norm(np.ones(384))
            return {bid: v.tolist() for bid in ids}

        with patch('apps.recommendation.models.Project', self._mock_project_class([liked])):
            with patch.object(engine, 'get_pool_embeddings', side_effect=_fake_pool_embeddings):
                result = engine.compute_user_taste_vector(profile)

        assert result is not None
        assert len(captured_ids) == 20, (
            f'Expected 20 IDs passed for a 20-like user, got {len(captured_ids)}'
        )


# ---------------------------------------------------------------------------
# Fix 3 — swipe spawns async warm taste thread
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwipeSpawnsAsyncWarmTasteThread:
    """After a swipe, a daemon thread targeting _async_warm_taste is spawned."""

    def _create_session_and_project(self, user_profile, pool_size=10):
        from apps.recommendation.models import Project, AnalysisSession
        pool_ids = [f'B{str(i).zfill(5)}' for i in range(1, pool_size + 1)]
        project = Project.objects.create(user=user_profile, name='TestProj', filters={})
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='exploring',
            pool_ids=pool_ids,
            pool_scores={bid: 1.0 for bid in pool_ids},
            current_round=0,
            preference_vector=[],
            exposed_ids=[pool_ids[0]],
            initial_batch=pool_ids[:5],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            v_initial=None,
        )
        return session, pool_ids

    def _fake_embs(self, pool_ids):
        v = np.ones(384) / np.linalg.norm(np.ones(384))
        return {bid: v for bid in pool_ids}

    def _engine_patches(self, pool_ids):
        _E = 'apps.recommendation.views.engine'
        return {
            f'{_E}.get_pool_embeddings': lambda ids: self._fake_embs(ids),
            f'{_E}.get_building_card': lambda bid: {'canonical_bld_id': bid} if bid else None,
            f'{_E}.get_building_embedding': lambda bid: _fake_vec(),
            f'{_E}.update_preference_vector': lambda p, e, a: _fake_vec(),
            f'{_E}.compute_taste_centroids': lambda lv, rn: (
                [np.ones(384) / np.linalg.norm(np.ones(384))],
                np.ones(384) / np.linalg.norm(np.ones(384)),
            ),
            f'{_E}.compute_mmr_next': lambda *a: pool_ids[1],
            f'{_E}.compute_convergence': lambda *a: 0.05,
            f'{_E}.check_convergence': lambda *a: False,
            f'{_E}.get_dislike_fallback': lambda *a, **kw: pool_ids[2],
            f'{_E}.refresh_pool_if_low': lambda *a, **kw: None,
            f'{_E}.farthest_point_from_pool': lambda pid, exp, embs: next(
                (b for b in pid if b not in set(exp)), None
            ),
            f'{_E}.compute_confidence': lambda *a, **kw: None,
            f'{_E}.get_last_embedding_call_stats': lambda: {
                'requested': 10, 'cache_hits': 10, 'cache_misses': 0,
            },
            f'{_E}.get_last_clustering_stats': lambda: None,
        }

    def test_swipe_spawns_async_warm_taste_thread(self, auth_client, user_profile, settings):
        """POST swipe constructs a daemon Thread(target=_async_warm_taste) and calls .start()."""
        from apps.recommendation.views.swipe import _async_warm_taste

        settings.RECOMMENDATION = {**settings.RECOMMENDATION, 'async_prefetch_enabled': False}
        session, pool_ids = self._create_session_and_project(user_profile)

        constructed_threads = []

        class _RecordingNoop:
            """Records construction; does NOT run target (unsafe in test DB context)."""
            def __init__(self, target=None, args=(), daemon=None, **kw):
                self.target = target
                self.args = args
                self.daemon = daemon
                constructed_threads.append(self)

            def start(self):
                pass

            def join(self, timeout=None):
                pass

        patchers = []
        for target, side_effect in self._engine_patches(pool_ids).items():
            p = patch(target, side_effect=side_effect)
            p.start()
            patchers.append(p)

        # Patch telemetry so DB writes land in test transaction.
        def _sync_emit(swipe_kwargs, confidence_kwargs):
            from apps.recommendation import event_log
            event_log.emit_swipe_event(**swipe_kwargs)
            if confidence_kwargs is not None:
                event_log.emit_event('confidence_update', **confidence_kwargs)

        tel_p = patch(
            'apps.recommendation.views.swipe._emit_telemetry_thread',
            side_effect=_sync_emit,
        )
        tel_p.start()
        patchers.append(tel_p)

        thread_p = patch(
            'apps.recommendation.views.swipe.threading.Thread',
            side_effect=lambda *a, **kw: _RecordingNoop(*a, **kw),
        )
        thread_p.start()
        patchers.append(thread_p)

        try:
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/swipes/',
                {'building_id': pool_ids[0], 'action': 'like'},
                format='json',
            )
        finally:
            for p in patchers:
                p.stop()

        assert resp.status_code == 200, f'Swipe returned {resp.status_code}: {resp.json()}'
        assert resp.json()['accepted'] is True

        # Must have at least one thread targeting _async_warm_taste.
        warm_threads = [t for t in constructed_threads if t.target is _async_warm_taste]
        assert len(warm_threads) >= 1, (
            f'No threading.Thread(target=_async_warm_taste) constructed. '
            f'Threads constructed: {[(t.target, t.args) for t in constructed_threads]}'
        )
        warm = warm_threads[0]
        assert warm.daemon is True, '_async_warm_taste thread must be daemon=True'
        assert warm.args == (user_profile.id,), (
            f'Expected args=({user_profile.id!r},), got {warm.args!r}'
        )
