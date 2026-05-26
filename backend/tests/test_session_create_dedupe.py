"""
test_session_create_dedupe.py -- Dedupe guard for SessionCreateView (2026-05-26).

Covers the belt-and-suspenders backend defense against duplicate
Project + AnalysisSession creation caused by client-side POST retries.

Patch target for timezone.now: apps.recommendation.views.sessions.timezone
(the import is module-level in sessions.py — patching the bound name is
correct and avoids cross-module interference with Django internals).
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from unittest.mock import patch

from apps.recommendation.models import Project, AnalysisSession

# Re-use the shared engine mock infrastructure from test_sessions.py so we
# don't have to duplicate the engine patch table.
from tests.test_sessions import (
    _apply_patches,
    _stop_patches,
)

_SESSIONS_VIEW = 'apps.recommendation.views.sessions'


def _tz_now():
    """Return current aware datetime (UTC, same as Django timezone.now())."""
    return datetime.now(dt_timezone.utc)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _post_session(auth_client, payload=None):
    """POST to /api/v1/analysis/sessions/ with mocked engine. Returns response."""
    if payload is None:
        payload = {'filters': {}, 'name': 'Dedupe Test', 'raw_query': 'modern Korean'}
    patchers = _apply_patches()
    try:
        resp = auth_client.post(
            '/api/v1/analysis/sessions/',
            payload,
            format='json',
        )
    finally:
        _stop_patches(patchers)
    return resp


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSessionDedupeGuard:

    # ------------------------------------------------------------------
    # Test 1: no prior session → fresh creation, 201
    # ------------------------------------------------------------------
    def test_no_dedupe_when_no_prior_session(self, auth_client, user_profile):
        """Single POST with no prior session creates a new session (201)."""
        resp = _post_session(auth_client)

        assert resp.status_code == 201
        data = resp.json()
        assert 'session_id' in data
        assert 'project_id' in data
        assert data.get('deduped') is None or data.get('deduped') is False
        assert AnalysisSession.objects.filter(user=user_profile).count() == 1
        assert Project.objects.filter(user=user_profile).count() == 1

    # ------------------------------------------------------------------
    # Test 2: second POST same payload within 30s → dedupe hit, 200
    # ------------------------------------------------------------------
    def test_dedupe_hit_within_30s_returns_existing_session(self, auth_client, user_profile):
        """Two identical POSTs within 30s: second returns deduped=True and the same session_id."""
        payload = {'filters': {}, 'name': 'Dedupe Test', 'raw_query': 'modern Korean'}

        # First POST — creates the session
        resp1 = _post_session(auth_client, payload)
        assert resp1.status_code == 201
        first_session_id = resp1.json()['session_id']
        first_project_id = resp1.json()['project_id']

        # Second POST — same payload, immediately (well within 30s window)
        resp2 = _post_session(auth_client, payload)
        assert resp2.status_code == 200, (
            f'Expected 200 (dedupe hit), got {resp2.status_code}: {resp2.json()}'
        )
        data2 = resp2.json()
        assert data2['deduped'] is True, f'Expected deduped=True, got {data2}'
        assert data2['session_id'] == first_session_id, (
            f'Expected same session_id {first_session_id}, got {data2["session_id"]}'
        )
        assert data2['project_id'] == first_project_id

        # Exactly 1 Project and 1 AnalysisSession for this user
        assert Project.objects.filter(user=user_profile).count() == 1, (
            'Dedupe must not create a second Project'
        )
        assert AnalysisSession.objects.filter(user=user_profile).count() == 1, (
            'Dedupe must not create a second AnalysisSession'
        )

    # ------------------------------------------------------------------
    # Test 3: second POST after 30s elapsed → fresh creation, 201
    # ------------------------------------------------------------------
    def test_no_dedupe_after_30s_elapsed(self, auth_client, user_profile):
        """First POST at T=0, second at T=35s → two independent sessions (both 201)."""
        payload = {'filters': {}, 'name': 'Time Test', 'raw_query': 'brutalist Seoul'}

        # T=0: create first session with a fixed "now"
        t0 = _tz_now()

        with patch(f'{_SESSIONS_VIEW}.timezone') as mock_tz:
            mock_tz.now.return_value = t0
            resp1 = _post_session(auth_client, payload)
        assert resp1.status_code == 201, f'First POST failed: {resp1.json()}'

        # T=35s: second POST — dedupe window (30s) has expired
        t1 = t0 + timedelta(seconds=35)

        with patch(f'{_SESSIONS_VIEW}.timezone') as mock_tz:
            mock_tz.now.return_value = t1
            resp2 = _post_session(auth_client, payload)

        assert resp2.status_code == 201, (
            f'Expected 201 (fresh creation after window), got {resp2.status_code}: {resp2.json()}'
        )
        assert resp2.json()['session_id'] != resp1.json()['session_id']
        assert AnalysisSession.objects.filter(user=user_profile).count() == 2
        assert Project.objects.filter(user=user_profile).count() == 2

    # ------------------------------------------------------------------
    # Test 4: different raw_query → no dedupe, 201
    # ------------------------------------------------------------------
    def test_no_dedupe_with_different_raw_query(self, auth_client, user_profile):
        """Different raw_query values → two independent sessions."""
        payload1 = {'filters': {}, 'name': 'RQ Test', 'raw_query': 'modern Korean'}
        payload2 = {'filters': {}, 'name': 'RQ Test', 'raw_query': 'brutalist Japanese'}

        resp1 = _post_session(auth_client, payload1)
        assert resp1.status_code == 201

        resp2 = _post_session(auth_client, payload2)
        assert resp2.status_code == 201, (
            f'Expected 201 (different raw_query, no dedupe), got {resp2.status_code}: {resp2.json()}'
        )
        assert resp2.json()['session_id'] != resp1.json()['session_id']
        assert AnalysisSession.objects.filter(user=user_profile).count() == 2

    # ------------------------------------------------------------------
    # Test 5: different name → no dedupe, 201
    # ------------------------------------------------------------------
    def test_no_dedupe_with_different_name(self, auth_client, user_profile):
        """Different project names → two independent sessions."""
        payload1 = {'filters': {}, 'name': 'Project A', 'raw_query': 'modern Korean'}
        payload2 = {'filters': {}, 'name': 'Project B', 'raw_query': 'modern Korean'}

        resp1 = _post_session(auth_client, payload1)
        assert resp1.status_code == 201

        resp2 = _post_session(auth_client, payload2)
        assert resp2.status_code == 201, (
            f'Expected 201 (different name, no dedupe), got {resp2.status_code}: {resp2.json()}'
        )
        assert resp2.json()['session_id'] != resp1.json()['session_id']
        assert AnalysisSession.objects.filter(user=user_profile).count() == 2

    # ------------------------------------------------------------------
    # Test 6: different filters → no dedupe, 201
    # ------------------------------------------------------------------
    def test_no_dedupe_with_different_filters(self, auth_client, user_profile):
        """Different filters → two independent sessions."""
        payload1 = {'filters': {'style': 'Modern'}, 'name': 'Filter Test', 'raw_query': ''}
        payload2 = {'filters': {'style': 'Brutalist'}, 'name': 'Filter Test', 'raw_query': ''}

        resp1 = _post_session(auth_client, payload1)
        assert resp1.status_code == 201

        resp2 = _post_session(auth_client, payload2)
        assert resp2.status_code == 201, (
            f'Expected 201 (different filters, no dedupe), got {resp2.status_code}: {resp2.json()}'
        )
        assert resp2.json()['session_id'] != resp1.json()['session_id']
        assert AnalysisSession.objects.filter(user=user_profile).count() == 2

    # ------------------------------------------------------------------
    # Test 7: project_id=None retry (classic frontend retry scenario)
    # ------------------------------------------------------------------
    def test_dedupe_without_project_id_no_second_project_created(self, auth_client, user_profile):
        """First POST creates Project automatically; retry POST (no project_id) → dedupe hit,
        no second Project or AnalysisSession created."""
        # No project_id — the view auto-creates one
        payload = {'filters': {}, 'name': 'Auto Project', 'raw_query': 'Seoul skyline'}

        resp1 = _post_session(auth_client, payload)
        assert resp1.status_code == 201
        first_session_id = resp1.json()['session_id']

        # Retry — same payload, no project_id
        resp2 = _post_session(auth_client, payload)
        assert resp2.status_code == 200, (
            f'Expected 200 (dedupe), got {resp2.status_code}: {resp2.json()}'
        )
        assert resp2.json()['deduped'] is True
        assert resp2.json()['session_id'] == first_session_id

        assert Project.objects.filter(user=user_profile).count() == 1, (
            'Retry must not create a second Project'
        )
        assert AnalysisSession.objects.filter(user=user_profile).count() == 1, (
            'Retry must not create a second AnalysisSession'
        )

    # ------------------------------------------------------------------
    # Test 8: dedupe response shape sanity check
    # ------------------------------------------------------------------
    def test_dedupe_response_shape(self, auth_client, user_profile):
        """Dedupe response contains the required keys in the correct types."""
        payload = {'filters': {}, 'name': 'Shape Test', 'raw_query': 'modern arch'}

        _post_session(auth_client, payload)  # first → 201
        resp = _post_session(auth_client, payload)  # second → 200 dedupe

        assert resp.status_code == 200
        data = resp.json()

        # All required keys must be present
        for key in ('session_id', 'project_id', 'session_status', 'next_image',
                    'prefetch_image', 'prefetch_image_2', 'progress', 'filter_relaxed', 'deduped'):
            assert key in data, f'Missing key {key!r} in dedupe response'

        assert data['deduped'] is True
        assert data['filter_relaxed'] is False
        assert data['prefetch_image'] is None
        assert data['prefetch_image_2'] is None

        progress = data['progress']
        for pk in ('current_round', 'swipe_count', 'target_swipes', 'like_count',
                   'dislike_count', 'phase', 'pool_size', 'pool_remaining'):
            assert pk in progress, f'Missing progress key {pk!r}'
