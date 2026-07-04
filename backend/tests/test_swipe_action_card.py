"""
test_swipe_action_card.py -- TASTE-FLOW: action-card emit-once behaviour.

Tests:
  (1) Converged session returns next_image as action card (card_type='action',
      canonical_bld_id='__action_card__') and is_analysis_completed is NOT True.
      Sets action_card_shown=True on the session.
  (2) '__action_card__' pass-swipe (LEFT = dislike) returns the next real card
      without recording a building like/dislike.
  (3) Guard: '__action_card__' swipe does NOT hit buildings-DB existence check.
  (4) Guard: '__action_card__' pass-swipe does NOT append to like_vectors.
  (5) '__action_card__' like-swipe (RIGHT = go to report) returns
      is_analysis_completed=True without erroring.
  (6) EMIT-ONCE: after a pass-swipe and one more real swipe, when the session
      is still converged and action_card_shown=True, a REAL card is served —
      NOT the action card again.  (FLIPPED from old re-offer test.)
  (7) action_card_shown flag is set to True after first convergence swipe.

Root-cause note: check_convergence is gated on session.phase == 'analyzing'.
Sessions start in 'exploring'; transition requires >=4 likes
(min_likes_for_clustering=4, Spec v1.8 Topic 06). Tests that need a converged
session must first pump 4 real likes to reach 'analyzing', then override
check_convergence=True on the triggering swipe.  _reach_analyzing() does this.
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from apps.recommendation.models import Project

_ACTION_CARD_ID = '__action_card__'

# ── min_likes threshold (mirrors config/settings.py) ─────────────────────────
# Using 4 because Spec v1.8 Topic 06 raised it from 3 to 4.
# If this constant ever changes, update _reach_analyzing accordingly.
_MIN_LIKES = 4


# ---------------------------------------------------------------------------
# Test infrastructure (mirrors test_swipe.py conventions)
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 20)]  # B00001..B00019
_FAKE_SCORES = {bid: 19 - i for i, bid in enumerate(_FAKE_POOL)}
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for _bid in _FAKE_EMBEDDINGS:
    _v = _FAKE_EMBEDDINGS[_bid]
    _norm = np.linalg.norm(_v)
    if _norm > 0:
        _FAKE_EMBEDDINGS[_bid] = _v / _norm


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num, **kwargs):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_get_embedding(bid):
    if bid in _FAKE_EMBEDDINGS:
        return _FAKE_EMBEDDINGS[bid].tolist()
    return list(np.random.randn(384))


def _mock_update_pref(pref_vector, embedding, action):
    return list(np.random.RandomState(42).randn(384))


def _mock_compute_centroids(like_vectors, round_num, multimodal_floor=None):
    c = np.random.RandomState(42).randn(384)
    c = c / np.linalg.norm(c)
    return ([c], c)


_ENGINE = 'apps.recommendation.views.engine'
_SWIPE_VIEW = 'apps.recommendation.views.swipe'


class _SyncThread:
    """Run telemetry synchronously; suppress async prefetch thread."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **kw):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if getattr(self._target, '__name__', '') == '_async_prefetch_thread':
            return
        if self._target:
            self._target(*self._args, **self._kwargs)


def _sync_emit_telemetry(swipe_kwargs, confidence_kwargs):
    from apps.recommendation import event_log
    event_log.emit_swipe_event(**swipe_kwargs)
    if confidence_kwargs is not None:
        event_log.emit_event('confidence_update', **confidence_kwargs)


# Base engine patches — convergence never fires unless overridden.
_SESSION_PATCHES = {
    f'{_ENGINE}.create_bounded_pool': lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES)),
    f'{_ENGINE}.get_pool_embeddings': (
        lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}
    ),
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': lambda bid, image_focus=None: {
        'canonical_bld_id': bid, 'name': f'Bld {bid}',
        'image_url': '', 'covers_by_type': {}, 'url': None,
        'gallery': [], 'gallery_drawing_start': 0, 'metadata': {},
    } if bid else None,
    f'{_ENGINE}.get_building_embedding': _mock_get_embedding,
    f'{_ENGINE}.update_preference_vector': _mock_update_pref,
    f'{_ENGINE}.compute_taste_centroids': _mock_compute_centroids,
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a, **kw: False,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
    f'{_SWIPE_VIEW}.threading.Thread': _SyncThread,
    f'{_SWIPE_VIEW}._emit_telemetry_thread': _sync_emit_telemetry,
}


def _apply_patches():
    patchers = []
    for target, side_effect in _SESSION_PATCHES.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


def _create_session(auth_client, user_profile, name='Action Card Test'):
    """Create a Project + AnalysisSession. Return (project, session_id)."""
    project = Project.objects.create(user=user_profile, name=name, filters={})
    patchers = _apply_patches()
    try:
        resp = auth_client.post(
            '/api/v1/analysis/sessions/',
            {'project_id': str(project.project_id), 'filters': {}},
            format='json',
        )
    finally:
        _stop_patches(patchers)
    assert resp.status_code == 201, f'Session create failed: {resp.json()}'
    return project, resp.json()['session_id']


def _swipe(auth_client, session_id, bid, action, **extra):
    payload = {'canonical_bld_id': bid, 'action': action}
    payload.update(extra)
    return auth_client.post(
        f'/api/v1/analysis/sessions/{session_id}/swipes/',
        payload,
        format='json',
    )


def _reach_analyzing(auth_client, session_id, start_idx=1):
    """Post _MIN_LIKES 'like' swipes with convergence disabled to transition
    the session from 'exploring' → 'analyzing'.

    check_convergence is forced False here so we don't accidentally converge
    during setup. Returns the list of building IDs swiped.
    """
    bids = [f'B{str(start_idx + i).zfill(5)}' for i in range(_MIN_LIKES)]
    with patch(f'{_ENGINE}.check_convergence', return_value=False):
        for i, bid in enumerate(bids):
            resp = _swipe(
                auth_client, session_id, bid, 'like',
                idempotency_key=f'setup_like_{start_idx}_{i}',
            )
            assert resp.status_code == 200, (
                f'Setup like {i} failed: {resp.json()}'
            )
    return bids


# ---------------------------------------------------------------------------
# (1) Converged session → action card, NOT is_analysis_completed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_converged_session_returns_action_card_not_force_complete(
    auth_client, user_profile,
):
    """When convergence fires, next_image must be the action card,
    and is_analysis_completed must be False (user is NOT forced to report).

    Setup: 4 likes → 'analyzing'; then 1 more swipe with check_convergence=True
    so the phase transitions to 'converged' inside that swipe's handler.
    """
    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Pump 4 likes to reach 'analyzing'
        _reach_analyzing(auth_client, session_id, start_idx=1)

        # One more swipe; this time check_convergence returns True → converged
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            resp = _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_1',
            )
    finally:
        _stop_patches(patchers)

    assert resp.status_code == 200, resp.json()
    data = resp.json()

    assert data['is_analysis_completed'] is False, (
        'Convergence must NOT force is_analysis_completed=True; '
        f'got: {data["is_analysis_completed"]}'
    )

    next_img = data['next_image']
    assert next_img is not None, 'next_image must not be None on convergence'
    assert next_img.get('canonical_bld_id') == _ACTION_CARD_ID, (
        f'Expected canonical_bld_id={_ACTION_CARD_ID!r}, '
        f'got {next_img.get("canonical_bld_id")!r}. '
        f'Session phase in progress: {data.get("progress", {}).get("phase")}'
    )
    assert next_img.get('card_type') == 'action', (
        f'Expected card_type="action", got {next_img.get("card_type")!r}'
    )
    assert 'action_card_message' in next_img, 'action_card_message field missing'
    assert 'action_card_subtitle' in next_img, 'action_card_subtitle field missing'


# ---------------------------------------------------------------------------
# (2) '__action_card__' pass-swipe → next real card, no building like recorded
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_pass_swipe_returns_next_real_card(auth_client, user_profile):
    """LEFT-swiping the action card (action='dislike') must return the next real
    building card without recording a building like/dislike.
    """
    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing'
        _reach_analyzing(auth_client, session_id, start_idx=1)

        # Trigger convergence
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            resp_converge = _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_2',
            )
        assert resp_converge.status_code == 200, resp_converge.json()
        assert resp_converge.json()['next_image']['canonical_bld_id'] == _ACTION_CARD_ID, (
            f"Convergence swipe did not produce action card; "
            f"phase={resp_converge.json().get('progress', {}).get('phase')}"
        )

        # Pass the action card (LEFT swipe)
        resp_pass = _swipe(auth_client, session_id, _ACTION_CARD_ID, 'dislike')
    finally:
        _stop_patches(patchers)

    assert resp_pass.status_code == 200, resp_pass.json()
    data = resp_pass.json()

    assert data['is_analysis_completed'] is False, (
        'Pass-swipe on action card must not complete the session'
    )

    next_img = data['next_image']
    assert next_img is not None, 'Pass-swipe must return a real next card'
    assert next_img.get('canonical_bld_id') != _ACTION_CARD_ID, (
        'Pass-swipe must return a real building card (pool is not exhausted)'
    )

    # '__action_card__' must NOT appear in project liked_ids or disliked_ids
    project.refresh_from_db()
    all_liked = [
        e.get('id') if isinstance(e, dict) else e
        for e in (project.liked_ids or [])
    ]
    assert _ACTION_CARD_ID not in all_liked, (
        f'{_ACTION_CARD_ID!r} must not appear in project.liked_ids'
    )
    assert _ACTION_CARD_ID not in (project.disliked_ids or []), (
        f'{_ACTION_CARD_ID!r} must not appear in project.disliked_ids'
    )


# ---------------------------------------------------------------------------
# (3) Guard: '__action_card__' swipe does NOT hit buildings-DB
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_swipe_does_not_query_buildings_db(auth_client, user_profile):
    """The buildings-DB existence check must be SKIPPED for '__action_card__'.

    We supply a custom connections mock with call tracking and verify that
    cursor.execute is NOT called with '__action_card__' in the query params.
    """
    project, session_id = _create_session(auth_client, user_profile)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    # 6-tuple for _update_question_state (only reached for real buildings)
    mock_cursor.fetchone.return_value = (None, None, [], None, [], [])
    mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor

    patchers = _apply_patches()
    try:
        # Reach 'analyzing' and converge (using default connections mock from conftest)
        _reach_analyzing(auth_client, session_id, start_idx=1)
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_3',
            )

        # Now send action-card pass with our own connections mock to track calls
        with patch(
            'apps.recommendation.services.swipe_service.connections', mock_conn,
        ):
            resp = _swipe(auth_client, session_id, _ACTION_CARD_ID, 'dislike')
    finally:
        _stop_patches(patchers)

    assert resp.status_code == 200, resp.json()

    # No call to cursor.execute should reference '__action_card__' as a param
    execute_calls = mock_cursor.execute.call_args_list
    action_card_db_calls = [
        c for c in execute_calls
        if _ACTION_CARD_ID in str(c)
    ]
    assert not action_card_db_calls, (
        f'Buildings-DB was queried with {_ACTION_CARD_ID!r}: {action_card_db_calls}'
    )


# ---------------------------------------------------------------------------
# (4) Guard: '__action_card__' pass-swipe does NOT append to like_vectors
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_pass_swipe_does_not_append_like_vectors(auth_client, user_profile):
    """like_vectors must not grow after a pass-swipe on the action card."""
    from apps.recommendation.models import AnalysisSession

    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing' with 4 likes
        _reach_analyzing(auth_client, session_id, start_idx=1)

        session = AnalysisSession.objects.get(session_id=session_id)
        like_count_before = len(session.like_vectors or [])

        # Trigger convergence
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            _swipe(
                auth_client, session_id, 'B00005', 'dislike',
                idempotency_key='converge_trigger_4',
            )

        # Pass the action card
        _swipe(auth_client, session_id, _ACTION_CARD_ID, 'dislike')
    finally:
        _stop_patches(patchers)

    session.refresh_from_db()
    like_count_after = len(session.like_vectors or [])

    assert like_count_after == like_count_before, (
        f'like_vectors grew from {like_count_before} to {like_count_after} '
        'after action-card pass-swipe — action card must not be recorded as a like'
    )


# ---------------------------------------------------------------------------
# (5) '__action_card__' like-swipe (RIGHT) → is_analysis_completed=True
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_like_swipe_returns_completed(auth_client, user_profile):
    """RIGHT-swiping the action card (user chose the report) must return
    is_analysis_completed=True so the frontend can navigate to the report.
    """
    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing' and converge
        _reach_analyzing(auth_client, session_id, start_idx=1)
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_5',
            )

        # RIGHT-swipe the action card
        resp = _swipe(auth_client, session_id, _ACTION_CARD_ID, 'like')
    finally:
        _stop_patches(patchers)

    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data['is_analysis_completed'] is True, (
        'RIGHT-swipe on action card (user chose report) must set '
        f'is_analysis_completed=True; got {data["is_analysis_completed"]}'
    )


# ---------------------------------------------------------------------------
# (6) EMIT-ONCE: action card is NOT re-offered after pass + subsequent swipe
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_is_NOT_reoffered_after_pass_if_still_converged(
    auth_client, user_profile,
):
    """EMIT-ONCE: after a pass-swipe and one more real swipe, if the session is still
    converged (phase stays 'converged') and action_card_shown is True, a REAL card
    must be served — the action card must NOT reappear.

    Old behaviour (action card re-offered on every converged swipe) is explicitly
    reversed: subsequent converged swipes go through the converged-continue path
    (compute_mmr_next / farthest-point) once action_card_shown=True.
    """
    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing' then converge
        _reach_analyzing(auth_client, session_id, start_idx=1)
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            resp1 = _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_6',
            )
        assert resp1.status_code == 200, resp1.json()
        assert resp1.json()['next_image']['canonical_bld_id'] == _ACTION_CARD_ID, (
            f"Expected action card on first convergence, got: {resp1.json()['next_image']}"
        )

        # Pass the action card → should get a real card back
        resp_pass = _swipe(auth_client, session_id, _ACTION_CARD_ID, 'dislike')
        assert resp_pass.status_code == 200, resp_pass.json()
        real_card = resp_pass.json()['next_image']
        assert real_card is not None, 'Pass-swipe must return a real card'
        real_bid = real_card['canonical_bld_id']
        assert real_bid != _ACTION_CARD_ID, 'Pass-swipe must not re-offer action card immediately'

        # Swipe that real card — phase is still 'converged' and action_card_shown=True.
        # The card-selection must serve ANOTHER real card, NOT the action card.
        resp2 = _swipe(auth_client, session_id, real_bid, 'dislike')
    finally:
        _stop_patches(patchers)

    assert resp2.status_code == 200, resp2.json()
    data2 = resp2.json()
    next_img2 = data2['next_image']
    # The action card must NOT reappear — a real building card or None (pool exhausted).
    if next_img2 is not None:
        assert next_img2.get('canonical_bld_id') != _ACTION_CARD_ID, (
            'Action card must NOT be re-offered after action_card_shown=True. '
            f'Got: {next_img2.get("canonical_bld_id")!r}'
        )


# ---------------------------------------------------------------------------
# (7) action_card_shown flag is set to True after first convergence swipe
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_action_card_shown_flag_set_after_first_convergence(
    auth_client, user_profile,
):
    """action_card_shown must be False before convergence and True after the
    first converged swipe emits the action card.
    """
    from apps.recommendation.models import AnalysisSession

    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing'
        _reach_analyzing(auth_client, session_id, start_idx=1)

        # Flag must be False before convergence
        session_before = AnalysisSession.objects.get(session_id=session_id)
        assert session_before.action_card_shown is False, (
            'action_card_shown must be False before convergence'
        )

        # Trigger convergence — action card emitted, flag set True
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            resp = _swipe(
                auth_client, session_id, 'B00005', 'like',
                idempotency_key='converge_trigger_7',
            )
        assert resp.status_code == 200, resp.json()
        assert resp.json()['next_image']['canonical_bld_id'] == _ACTION_CARD_ID
    finally:
        _stop_patches(patchers)

    session_after = AnalysisSession.objects.get(session_id=session_id)
    assert session_after.action_card_shown is True, (
        'action_card_shown must be True after the first converged swipe emits the action card'
    )


# ---------------------------------------------------------------------------
# (8) progress['action_card_shown'] reflects the session flag
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_progress_action_card_shown_flag_in_response(
    auth_client, user_profile,
):
    """progress['action_card_shown'] must be False before convergence and True
    after the first converged swipe emits the action card.

    Both the swipe response and the session-state response build progress via
    _progress(), so this asserts the flag flows through to the API payload.
    """
    project, session_id = _create_session(auth_client, user_profile)

    patchers = _apply_patches()
    try:
        # Reach 'analyzing' (4 likes)
        _reach_analyzing(auth_client, session_id, start_idx=1)

        # Before convergence: action_card_shown must be False in progress
        resp_before = _swipe(
            auth_client, session_id, 'B00005', 'dislike',
            idempotency_key='pre_converge_8',
        )
        assert resp_before.status_code == 200, resp_before.json()
        assert resp_before.json()['progress']['action_card_shown'] is False, (
            "progress['action_card_shown'] must be False before convergence"
        )

        # Trigger convergence — action card emitted, flag set True
        with patch(f'{_ENGINE}.check_convergence', return_value=True):
            resp_converge = _swipe(
                auth_client, session_id, 'B00006', 'like',
                idempotency_key='converge_trigger_8',
            )
        assert resp_converge.status_code == 200, resp_converge.json()
        assert resp_converge.json()['next_image']['canonical_bld_id'] == _ACTION_CARD_ID
    finally:
        _stop_patches(patchers)

    # After convergence: flag must be True in progress
    assert resp_converge.json()['progress']['action_card_shown'] is True, (
        "progress['action_card_shown'] must be True after the first converged swipe "
        "emits the action card"
    )
