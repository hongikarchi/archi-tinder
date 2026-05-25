"""
test_projects_n_plus_one.py -- N+1 guard for ProjectListCreateView.

Verifies that GET /api/v1/projects/ with N projects does not issue N extra
AnalysisSession.objects.get() queries — the Subquery annotations must supply
session data without per-row lookups.

Uses CaptureQueriesContext to assert total query count stays under a constant
ceiling regardless of project count.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.recommendation.models import AnalysisSession, Project


@pytest.mark.django_db
class TestProjectListN1:
    """GET /api/v1/projects/ must not issue N per-project session queries."""

    def test_query_count_constant_with_sessions(self, auth_client, user_profile):
        """
        5 projects each with 1 session: query count must stay below a fixed ceiling.

        Without the Subquery annotations fix, _get_latest_session would issue one
        AnalysisSession.objects.get() per project row (N=5 extra queries).
        With the fix, all session fields come from the annotated queryset.

        PERF-1 (change C): COUNT(*) removed via page_size+1 trick.

        Expected queries with PERF-1 fix:
          1. JWT auth token validation
          2. _get_profile() UserProfile lookup
          3. SELECT with JOINs + Subquery annotations (projects + user + session fields)
        Plus up to a few ancillary lookups → ceiling of 7 is conservative.
        """
        for i in range(5):
            project = Project.objects.create(user=user_profile, name=f'P{i}')
            AnalysisSession.objects.create(
                user=user_profile,
                project=project,
                like_vectors=[{'embedding': [0.1] * 5, 'round': j} for j in range(i + 1)],
            )

        with CaptureQueriesContext(connection) as ctx:
            resp = auth_client.get('/api/v1/projects/')

        assert resp.status_code == 200
        data = resp.json()
        # PERF-1: total is now None (deprecated); frontend uses has_more
        assert data['total'] is None

        query_count = len(ctx.captured_queries)
        # With N+1 bug: 7 + 5 = 12 queries (one get() per project)
        # With PERF-1 fix: <= 7 queries (constant regardless of project count;
        # no COUNT query compared to the previous ceiling of 8)
        assert query_count < 8, (
            f'Expected < 8 queries (N+1 + PERF-1 fix), got {query_count}. '
            'Did the Subquery annotation or page_size+1 trick regress?'
        )

    def test_like_count_correct_from_annotations(self, auth_client, user_profile):
        """
        latest_session_meta.like_count must reflect actual like_vectors length
        when served from the Subquery-annotated path.
        """
        project = Project.objects.create(user=user_profile, name='LikeCountTest')
        AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            like_vectors=[{'embedding': [0.0] * 5, 'round': i} for i in range(4)],
        )

        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        results = resp.json()['results']
        assert len(results) == 1
        meta = results[0]['latest_session_meta']
        assert meta is not None
        assert meta['like_count'] == 4

    def test_no_session_returns_null_meta(self, auth_client, user_profile):
        """Project with no AnalysisSession must return latest_session_meta=null via annotated path."""
        Project.objects.create(user=user_profile, name='NoSession')

        resp = auth_client.get('/api/v1/projects/')
        assert resp.status_code == 200
        results = resp.json()['results']
        assert len(results) == 1
        assert results[0]['latest_session_meta'] is None
        assert results[0]['latest_session_id'] is None
