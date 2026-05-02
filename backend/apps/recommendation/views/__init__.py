"""views package for apps.recommendation.

Re-exports all public classes and private helpers so that existing imports of the form
    from apps.recommendation.views import SomeView
continue to work without any changes to callers (urls.py, tests, etc.).

Module-level imports of engine/services/etc. are also kept here so that test mock.patch
targets like 'apps.recommendation.views.engine.get_building_card' continue to resolve.
The patch mutates the shared module object, which all sub-modules reference.
"""

import threading  # noqa: F401 — exposed for mock.patch('apps.recommendation.views.threading.Thread')

from django.core.cache import cache  # noqa: F401 — exposed for mock.patch('apps.recommendation.views.cache.set')
from django.utils import timezone  # noqa: F401 — exposed for mock.patch('apps.recommendation.views.timezone')

from .. import engine  # noqa: F401 — exposed for mock.patch('apps.recommendation.views.engine.*')
from .. import services  # noqa: F401 — exposed for mock.patch('apps.recommendation.views.services.*')

from .projects import (
    ProjectListCreateView,
    ProjectDetailView,
    UserProjectsListView,
)
from .sessions import (
    SessionCreateView,
    SessionStateView,
    SessionResultView,
)
from .swipe import (
    SwipeView,
    ProjectBookmarkView,
    BuildingBatchView,
    DiverseRandomView,
    # Private helpers accessed by tests
    _merge_buffer_into_exposed,
    _async_prefetch_thread,
)
from .search import (
    ParseQueryView,
    # Private helper accessed by tests
    _spawn_stage2,
)
from .reports import (
    ProjectReportGenerateView,
    ProjectReportImageView,
)
from .telemetry import (
    ImageLoadTelemetryView,
    ImageLoadTelemetryThrottle,
)
from ._shared import (
    # Private helpers accessed by tests
    _liked_id_only,
    _get_profile,
    _progress,
)

__all__ = [
    # Public view classes
    'ProjectListCreateView',
    'ProjectDetailView',
    'UserProjectsListView',
    'SessionCreateView',
    'SessionStateView',
    'SessionResultView',
    'SwipeView',
    'ProjectBookmarkView',
    'BuildingBatchView',
    'DiverseRandomView',
    'ParseQueryView',
    'ProjectReportGenerateView',
    'ProjectReportImageView',
    'ImageLoadTelemetryView',
    'ImageLoadTelemetryThrottle',
    # Private helpers (re-exported for backward compat with test imports)
    '_liked_id_only',
    '_get_profile',
    '_progress',
    '_merge_buffer_into_exposed',
    '_async_prefetch_thread',
    '_spawn_stage2',
]
