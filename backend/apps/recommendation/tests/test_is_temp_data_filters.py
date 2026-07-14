"""
test_is_temp_data_filters.py — FULL-ONBOARDING-2 data-correctness filter tests.

Verifies that the is_temp=False filter is applied correctly to:
1. compute_user_taste_vector — must exclude temp-board liked_ids
2. build_discovery_chunk (fallback fetch) — must exclude temp boards in project_rows

These are pure unit tests (no DB); they verify the filter kwargs passed to
Project.objects.filter(), following the patch pattern in test_discovery_perf.py.
"""
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 1. compute_user_taste_vector excludes temp-board liked_ids
# ---------------------------------------------------------------------------

def test_compute_user_taste_vector_excludes_temp_board_likes():
    """compute_user_taste_vector must query only is_temp=False projects.

    Pattern: patch 'apps.recommendation.models.Project' (the import target
    inside the function body: `from .models import Project`) so the filter
    kwargs can be captured without triggering circular imports.
    """
    from apps.recommendation import engine

    profile = MagicMock()
    profile.id = 99
    profile.liked_building_ids = []

    captured_filter_kwargs = []

    class _FakeOrderedQS:
        def values_list(self, *a, **kw):
            return []

    class _FakeFilterQS:
        def order_by(self, *a):
            return _FakeOrderedQS()

    def _fake_filter(**kwargs):
        captured_filter_kwargs.append(kwargs)
        return _FakeFilterQS()

    mock_project_cls = MagicMock()
    mock_project_cls.objects.filter = _fake_filter

    with patch('apps.recommendation.models.Project', mock_project_cls):
        with patch.object(engine, 'get_pool_embeddings', return_value={}):
            engine.compute_user_taste_vector(profile)

    assert any(
        kw.get('is_temp') is False for kw in captured_filter_kwargs
    ), f"Expected is_temp=False in filter kwargs; got: {captured_filter_kwargs}"


# ---------------------------------------------------------------------------
# 2. build_discovery_chunk fallback fetch excludes temp boards
# ---------------------------------------------------------------------------

def test_build_discovery_chunk_fallback_fetch_excludes_temp():
    """build_discovery_chunk internal project fetch (when _project_rows=None)
    must include is_temp=False in the filter kwargs.

    Pattern: patch.object(discovery_feed, 'Project') to intercept the
    filter() call inside the fallback code path.
    """
    from apps.recommendation import discovery_feed

    profile = MagicMock()
    profile.id = 77
    profile.liked_building_ids = []

    captured_filter_kwargs = []

    class _FakeValuesQS:
        def __iter__(self):
            return iter([])

        def __len__(self):
            return 0

    class _FakeSlicedQS:
        """Represents the result of .order_by(...)[:cap] — must support .values()."""
        def values(self, *a):
            return _FakeValuesQS()

        def __iter__(self):
            return iter([])

    class _FakeOrderedQS:
        def __getitem__(self, sl):
            return _FakeSlicedQS()

        def values(self, *a):
            return _FakeValuesQS()

    class _FakeFilterQS:
        def order_by(self, *a):
            return _FakeOrderedQS()

    def _fake_filter(**kwargs):
        captured_filter_kwargs.append(kwargs)
        return _FakeFilterQS()

    with patch.object(discovery_feed, 'Project') as MockProject:
        MockProject.objects.filter = _fake_filter
        with patch.object(discovery_feed, '_fetch_candidates', return_value=[]):
            with patch.object(discovery_feed, 'engine') as mock_engine:
                mock_engine.get_pool_embeddings.return_value = {}
                discovery_feed.build_discovery_chunk(
                    profile,
                    centroids=[],
                    _project_rows=None,  # force the internal fetch path
                )

    assert any(
        kw.get('is_temp') is False for kw in captured_filter_kwargs
    ), f"Expected is_temp=False in filter kwargs; got: {captured_filter_kwargs}"
