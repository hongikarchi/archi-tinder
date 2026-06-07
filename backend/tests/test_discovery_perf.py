"""
test_discovery_perf.py -- BACK-PERFORMANCE-4: Discovery cold-path optimisations.

Tests:
1. test_taste_ranked_page_uses_direct_query_no_cte
   SQL does NOT contain the CTE barrier (`WITH ranked AS`).
2. test_compute_user_taste_vector_caps_at_50_likes
   get_pool_embeddings is called with at most 50 distinct IDs even when the
   user has 80+ liked buildings across projects.

(Fix 3 — swipe-time async taste-cache warm — rolled back 2026-05-27 due to
pytest-django connection-pool race; investigation deferred.)
"""
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
# Fix 3 — async warm taste thread: ROLLED BACK 2026-05-27
# Reason: spawning a daemon thread that calls connections.close_all() in
# pytest-django context cascades InterfaceError("connection already closed")
# across 24+ swipe-touching tests. Root cause investigation deferred. Fix 1
# (CTE removal) and Fix 2 (recent-50 cap) provide 2/3 of the Discovery cold
# latency win without the threading machinery.
