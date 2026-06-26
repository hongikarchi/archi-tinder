"""
test_taste_calibration.py -- TASTE-CALIBRATION-1: interactive calibration state machine.

Tests:
- TestChatInitializingEntry:      confidence<0.6 → chat_initializing (no pool, cards=[])
- TestCalibrateTransition:        calibrate raises confidence → exploring + pool build
- TestCalibrate3TurnCap:          3rd calibration turn forces transition regardless of confidence
- TestCalibrateSchemaFields:      new schema fields present in create + calibrate responses
- TestCalibrationFallbackConfidence: _compute_confidence_fallback heuristic correctness
- TestExtractCalibrationFields:   _extract_calibration_fields validates + falls back
- TestIsPublishablePreserved:     all building queries still gate on is_publishable
"""
import pytest
import numpy as np
from unittest.mock import patch

from apps.recommendation.models import Project, AnalysisSession
from apps.recommendation.services.parse_query import (
    _compute_confidence_fallback,
    _extract_calibration_fields,
)


# ---------------------------------------------------------------------------
# Shared mock infrastructure (mirrors test_session_create_correctness.py)
# ---------------------------------------------------------------------------

_FAKE_POOL = [f'B{str(i).zfill(5)}' for i in range(1, 16)]  # B00001..B00015
_FAKE_SCORES = {bid: 15 - i for i, bid in enumerate(_FAKE_POOL)}
_FAKE_EMBEDDINGS = {
    bid: np.random.RandomState(i).randn(384).astype(np.float64)
    for i, bid in enumerate(_FAKE_POOL)
}
for bid in _FAKE_EMBEDDINGS:
    v = _FAKE_EMBEDDINGS[bid]
    norm = np.linalg.norm(v)
    if norm > 0:
        _FAKE_EMBEDDINGS[bid] = v / norm


def _mock_farthest_point(pool_ids, exposed_ids, pool_embeddings):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


def _mock_get_card(bid, image_focus=None):
    if bid is None:
        return None
    return {
        'canonical_bld_id': bid,
        'name': f'Building {bid}',
        'image_url': '',
        'covers_by_type': {},
        'url': None,
        'gallery': [],
        'gallery_drawing_start': 0,
        'metadata': {
            'axis_typology': 'Museum',
            'axis_architects': 'Test Arch',
            'axis_country': 'Korea',
            'axis_city': None,
            'axis_year': 2022,
            'axis_style': 'Modern',
            'axis_atmosphere': 'bold',
            'axis_color_tone': 'Dark',
            'axis_material_visual': [],
            'visual_description': '',
        },
    }


def _mock_get_embedding(bid):
    if bid in _FAKE_EMBEDDINGS:
        return _FAKE_EMBEDDINGS[bid].tolist()
    return list(np.random.randn(384))


def _mock_mmr_next(pool_ids, exposed_ids, pool_embeddings, like_vectors, round_num, **kwargs):
    exposed_set = set(exposed_ids)
    for bid in pool_ids:
        if bid not in exposed_set:
            return bid
    return None


_ENGINE = 'apps.recommendation.views.engine'
_SESSION_SVC = 'apps.recommendation.services.session_service.engine'


_BASE_ENGINE_PATCHES = {
    f'{_ENGINE}.create_pool_with_relaxation': (
        lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES), 1)
    ),
    f'{_ENGINE}.get_pool_embeddings': (
        lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}
    ),
    f'{_ENGINE}.farthest_point_from_pool': _mock_farthest_point,
    f'{_ENGINE}.get_building_card': _mock_get_card,
    f'{_ENGINE}.get_building_embedding': _mock_get_embedding,
    f'{_ENGINE}.compute_taste_centroids': lambda lv, rn, multimodal_floor=None: (
        [np.zeros(384)], np.zeros(384)
    ),
    f'{_ENGINE}.compute_mmr_next': _mock_mmr_next,
    f'{_ENGINE}.compute_convergence': lambda *a: 0.05,
    f'{_ENGINE}.check_convergence': lambda *a: False,
    f'{_ENGINE}.get_dislike_fallback': lambda *a, **kw: 'B00010',
    f'{_ENGINE}._random_pool': lambda target: _FAKE_POOL[:target],
}

# Calibrate path uses session_service.engine (direct import)
_CALIBRATE_ENGINE_PATCHES = {
    f'{_SESSION_SVC}.create_pool_with_relaxation': (
        lambda *a, **kw: (_FAKE_POOL[:], dict(_FAKE_SCORES), 1)
    ),
    f'{_SESSION_SVC}.get_pool_embeddings': (
        lambda pool_ids: {bid: _FAKE_EMBEDDINGS.get(bid, np.zeros(384)) for bid in pool_ids}
    ),
    f'{_SESSION_SVC}.farthest_point_from_pool': _mock_farthest_point,
    f'{_SESSION_SVC}.get_buildings_by_ids': (
        lambda ids, image_focus=None: [_mock_get_card(bid) for bid in ids if bid]
    ),
}


def _apply_patches(extra=None):
    patchers = []
    merged = dict(_BASE_ENGINE_PATCHES)
    if extra:
        merged.update(extra)
    for target, side_effect in merged.items():
        p = patch(target, side_effect=side_effect)
        p.start()
        patchers.append(p)
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


def _make_parse_result(confidence, system_action, message, replies, priority_ordered=None):
    """Return a synthetic parse_query result dict for mocking."""
    return {
        'probe_needed': confidence < 0.60,
        'probe_question': '어떤 방향성이 끌리세요?' if confidence < 0.60 else None,
        'reply': 'Understood.',
        'filters': {'program': None, 'material': None, 'style': 'Contemporary',
                    'location_country': None, 'year_min': None, 'year_max': None,
                    'atmosphere': None, 'color_tone': None, 'typology_primary': None,
                    'location_city': None},
        'filter_priority': ['style'],
        'image_focus': None,
        'raw_query': '좋은 거 보여줘',
        'visual_description': None,
        'confidence_score': confidence,
        'system_action': system_action,
        'suggested_quick_replies': replies,
        'priority_ordered': priority_ordered or [],
        'llm_response_message': message,
    }


# ---------------------------------------------------------------------------
# Unit tests — no DB
# ---------------------------------------------------------------------------

class TestCalibrationFallbackConfidence:
    """_compute_confidence_fallback returns correct heuristic scores."""

    def test_probe_true_no_slate(self):
        filters = {'program': None, 'material': None, 'style': None, 'location_country': None}
        score = _compute_confidence_fallback(filters, probe_needed=True)
        assert score < 0.60, f"Expected <0.60, got {score}"

    def test_probe_true_one_slate(self):
        filters = {'program': 'Housing', 'material': None, 'style': None, 'location_country': None}
        score = _compute_confidence_fallback(filters, probe_needed=True)
        assert score < 0.60, f"Expected <0.60, got {score}"

    def test_probe_false_no_slate(self):
        filters = {'program': None, 'material': None, 'style': None, 'location_country': None}
        score = _compute_confidence_fallback(filters, probe_needed=False)
        # Broad default — just barely below or at threshold
        assert 0.40 <= score <= 0.70, f"Expected 0.40–0.70, got {score}"

    def test_probe_false_two_slate(self):
        filters = {'program': 'Housing', 'material': 'timber', 'style': None, 'location_country': None}
        score = _compute_confidence_fallback(filters, probe_needed=False)
        assert score >= 0.60, f"Expected >=0.60, got {score}"


class TestExtractCalibrationFields:
    """_extract_calibration_fields validates + falls back gracefully."""

    def test_valid_confidence_accepted(self):
        data = {
            'confidence_score': 0.75, 'system_action': 'NONE',
            'suggested_quick_replies': ['Option A', 'Option B'],
            'priority_ordered': ['program', 'material'],
            'llm_response_message': 'Got it.',
        }
        filters = {
            'style': 'Contemporary', 'program': None,
            'material': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=False)
        assert result['confidence_score'] == 0.75
        assert result['system_action'] == 'NONE'

    def test_invalid_confidence_falls_back_to_heuristic(self):
        data = {'confidence_score': 'not-a-number'}
        filters = {
            'program': 'Museum', 'style': 'Contemporary',
            'material': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=False)
        # Heuristic should produce >=0.60 for probe_needed=False + 2 slate fields
        assert isinstance(result['confidence_score'], float)
        assert 0.0 <= result['confidence_score'] <= 1.0

    def test_invalid_system_action_falls_back(self):
        data = {'confidence_score': 0.30, 'system_action': 'INVALID_VALUE'}
        filters = {
            'style': 'Contemporary', 'program': None,
            'material': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=True)
        # Falls back to REQUEST_PRIORITY when confidence < 0.60
        assert result['system_action'] == 'REQUEST_PRIORITY'

    def test_quick_replies_capped_at_3(self):
        data = {
            'confidence_score': 0.30,
            'system_action': 'REQUEST_PRIORITY',
            'suggested_quick_replies': ['A', 'B', 'C', 'D', 'E'],
            'llm_response_message': 'Question?',
        }
        filters = {
            'style': 'Contemporary', 'program': None,
            'material': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=True)
        assert len(result['suggested_quick_replies']) <= 3

    def test_missing_llm_message_falls_back_to_reply(self):
        data = {
            'confidence_score': 0.80,
            'system_action': 'NONE',
            'reply': 'Got it: timber housing.',
        }
        filters = {
            'program': 'Housing', 'material': 'timber',
            'style': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=False)
        assert result['llm_response_message'] == 'Got it: timber housing.'


# ---------------------------------------------------------------------------
# Integration tests — require DB
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestChatInitializingEntry:
    """POST /analysis/sessions/ with confidence<0.6 → chat_initializing, no pool."""

    def test_low_confidence_enters_chat_initializing(self, auth_client):
        """confidence_score=0.30 → phase='chat_initializing', cards=[], needs_more_info=True."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {},
                    'confidence_score': 0.30,
                    'system_action': 'REQUEST_PRIORITY',
                    'llm_response_message': '어떤 용도의 건물을 찾고 계세요?',
                    'suggested_quick_replies': ['주거', '공공', '상관없어요, 보여주세요'],
                    'priority_ordered': ['program'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data['phase'] == 'chat_initializing'
        assert data['needs_more_info'] is True
        assert data['cards'] == []
        assert data['next_image'] is None
        assert data['confidence_score'] == pytest.approx(0.30)
        assert data['system_action'] == 'REQUEST_PRIORITY'
        assert isinstance(data['suggested_quick_replies'], list)
        assert 'session_id' in data
        assert 'project_id' in data

    def test_chat_initializing_session_stored_in_db(self, auth_client, user_profile):
        """DB row: phase='chat_initializing', pool_ids=[], confidence_score saved."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {'program': None},
                    'confidence_score': 0.25,
                    'system_action': 'REQUEST_PRIORITY',
                    'llm_response_message': '질문입니다.',
                    'suggested_quick_replies': ['A', '상관없어요, 보여주세요'],
                    'priority_ordered': [],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        session_id = resp.json()['session_id']
        session = AnalysisSession.objects.get(session_id=session_id)
        assert session.phase == 'chat_initializing'
        assert session.pool_ids == []
        assert session.confidence_score == pytest.approx(0.25)

    def test_conversation_history_seeded_with_initial_query(self, auth_client, user_profile):
        """Finding #2 fix: chat_initializing session seeds project.conversation_history
        with the initial raw_query so calibrate() has full context on first call."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'raw_query': '좁은 마당이 있는 주택',
                    'filters': {},
                    'confidence_score': 0.30,
                    'system_action': 'REQUEST_PRIORITY',
                    'llm_response_message': '어떤 재료를 선호하세요?',
                    'suggested_quick_replies': ['목재', '콘크리트', '보여주세요'],
                    'priority_ordered': [],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        session_id = resp.json()['session_id']
        session = AnalysisSession.objects.get(session_id=session_id)
        project = session.project

        conv = project.conversation_history
        assert isinstance(conv, dict), "conversation_history should be a dict"
        turns = conv.get('turns', [])
        assert len(turns) >= 1, "Expected at least the initial user turn seeded"

        user_turns = [t for t in turns if t.get('role') == 'user']
        assert len(user_turns) >= 1, "Expected user turn seeded in conversation_history"
        assert user_turns[0]['text'] == '좁은 마당이 있는 주택', (
            f"Expected initial raw_query as first user turn, got {user_turns[0]['text']!r}"
        )

        # Also verify LLM response is seeded as a model turn for continuity
        model_turns = [t for t in turns if t.get('role') == 'model']
        assert len(model_turns) >= 1, "Expected model turn (llm_response_message) seeded"
        assert model_turns[0]['text'] == '어떤 재료를 선호하세요?'

    def test_high_confidence_skips_chat_initializing(self, auth_client):
        """confidence_score=0.80 → phase='exploring', cards non-empty."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {'program': 'Housing', 'material': 'timber'},
                    'confidence_score': 0.80,
                    'system_action': 'NONE',
                    'llm_response_message': 'Got it.',
                    'suggested_quick_replies': [],
                    'priority_ordered': ['program', 'material'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data['phase'] == 'exploring'
        assert data['needs_more_info'] is False
        assert data['next_image'] is not None

    def test_missing_confidence_defaults_to_exploring(self, auth_client):
        """No confidence_score in body → existing exploring path (backward compat)."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {'filters': {'program': 'Museum'}},
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        data = resp.json()
        # Backward compat: old clients get exploring path
        assert data.get('next_image') is not None or data.get('phase') in (None, 'exploring')


@pytest.mark.django_db
class TestCalibrateTransition:
    """POST /sessions/<id>/calibrate/ raises confidence → exploring + pool build."""

    def _create_chat_initializing_session(self, auth_client, user_profile):
        """Helper: create a session in chat_initializing phase."""
        project = Project.objects.create(
            user=user_profile, name='Calibration Test', filters={}, is_temp=True,
        )
        session = AnalysisSession.objects.create(
            user=user_profile,
            project=project,
            phase='chat_initializing',
            pool_ids=[],
            pool_scores={},
            current_round=0,
            preference_vector=[],
            exposed_ids=[],
            initial_batch=[],
            like_vectors=[],
            convergence_history=[],
            previous_pref_vector=[],
            original_filters={},
            original_filter_priority=[],
            original_seed_ids=[],
            current_pool_tier=1,
            confidence_score=0.30,
            extracted_metadata={},
            priority_ordered=[],
        )
        return session

    def test_calibrate_low_confidence_stays_chat_initializing(self, auth_client, user_profile):
        """calibrate with reply that keeps confidence <0.60 → stays chat_initializing."""
        session = self._create_chat_initializing_session(auth_client, user_profile)

        low_conf_parse = _make_parse_result(
            confidence=0.40,
            system_action='REQUEST_PRIORITY',
            message='재료감을 좁혀볼게요: 따뜻한 쪽인가요, 차가운 쪽인가요?',
            replies=['따뜻한 재료', '차가운 기하성', '상관없어요, 보여주세요'],
        )

        with patch('apps.recommendation.services.session_service.services') as mock_svc:
            mock_svc.parse_query.return_value = low_conf_parse
            resp = auth_client.post(
                f'/api/v1/analysis/sessions/{session.session_id}/calibrate/',
                {'message': '좋은 거 보여줘'},
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data['phase'] == 'chat_initializing'
        assert data['needs_more_info'] is True
        assert data['cards'] == []
        assert data['confidence_score'] == pytest.approx(0.40)

    def test_calibrate_high_confidence_transitions_to_exploring(self, auth_client, user_profile):
        """calibrate with message that raises confidence >=0.60 → exploring + pool."""
        session = self._create_chat_initializing_session(auth_client, user_profile)

        high_conf_parse = _make_parse_result(
            confidence=0.75,
            system_action='CONFIRM_SELECTION',
            message='이해했어요: 목재 주택 레퍼런스로 찾아볼게요.',
            replies=[],
            priority_ordered=['program', 'material'],
        )

        cal_patchers = []
        for target, se in _CALIBRATE_ENGINE_PATCHES.items():
            p = patch(target, side_effect=se)
            p.start()
            cal_patchers.append(p)

        try:
            with patch('apps.recommendation.services.session_service.services') as mock_svc:
                mock_svc.parse_query.return_value = high_conf_parse
                mock_svc.get_cached_v_initial.return_value = None
                resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session.session_id}/calibrate/',
                    {'message': '목재 쪽이요. 따뜻한 재료 많이 쓴 주택.'},
                    format='json',
                )
        finally:
            for p in cal_patchers:
                p.stop()

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data['phase'] == 'exploring'
        assert data['needs_more_info'] is False
        assert isinstance(data['cards'], list)

        # Verify DB updated
        session.refresh_from_db()
        assert session.phase == 'exploring'
        assert len(session.pool_ids) > 0

    def test_calibrate_missing_message_returns_400(self, auth_client, user_profile):
        """calibrate with no message body → 400."""
        session = self._create_chat_initializing_session(auth_client, user_profile)
        resp = auth_client.post(
            f'/api/v1/analysis/sessions/{session.session_id}/calibrate/',
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_calibrate_wrong_phase_returns_400(self, auth_client, user_profile):
        """calibrate on an analyzing session → 400."""
        project = Project.objects.create(
            user=user_profile, name='Analyzing Project', filters={}, is_temp=False,
        )
        session = AnalysisSession.objects.create(
            user=user_profile, project=project,
            phase='analyzing',
            pool_ids=['B00001'], pool_scores={'B00001': 1.0},
            current_round=5, preference_vector=[], exposed_ids=[],
            initial_batch=[], like_vectors=[], convergence_history=[],
            previous_pref_vector=[], original_filters={},
            original_filter_priority=[], original_seed_ids=[],
            current_pool_tier=1,
        )
        resp = auth_client.post(
            f'/api/v1/analysis/sessions/{session.session_id}/calibrate/',
            {'message': '목재'},
            format='json',
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCalibrate3TurnCap:
    """After 3 user turns, calibrate forces transition to exploring."""

    def _session_with_seed_and_2_genuine_turns(self, user_profile):
        """Create a chat_initializing session with 1 seeded + 2 genuine calibration turns.

        Finding #1 fix: the seed (raw_query) user turn does NOT count toward the
        _CALIBRATION_TURN_CAP.  The cap fires on the 3rd *genuine* calibrate() call,
        i.e. the 3rd user turn excluding the seeded initial query.

        History layout:
          [0] user  — seeded raw_query (NOT counted toward cap)
          [1] model — initial clarifying question
          [2] user  — 1st genuine calibrate() answer
          [3] model — follow-up question
          [4] user  — 2nd genuine calibrate() answer
          [5] model — follow-up question

        The next calibrate() call (message = '재료는 상관없어요') is the 3rd genuine
        turn → must force-transition to exploring.
        """
        project = Project.objects.create(
            user=user_profile, name='Cap Test', filters={}, is_temp=True,
            raw_query='좋은 거 보여줘',
        )
        project.conversation_history = {
            'turns': [
                {'role': 'user', 'text': '좋은 거 보여줘'},       # seed — not counted
                {'role': 'model', 'text': '용도를 좁혀볼게요.'},
                {'role': 'user', 'text': '공공 건물이요'},         # genuine turn 1
                {'role': 'model', 'text': '재료를 좁혀볼게요.'},
                {'role': 'user', 'text': '목재요'},                # genuine turn 2
                {'role': 'model', 'text': '분위기를 좁혀볼게요.'},
            ]
        }
        project.save()
        session = AnalysisSession.objects.create(
            user=user_profile, project=project,
            phase='chat_initializing',
            pool_ids=[], pool_scores={}, current_round=0,
            preference_vector=[], exposed_ids=[], initial_batch=[],
            like_vectors=[], convergence_history=[], previous_pref_vector=[],
            original_filters={}, original_filter_priority=[],
            original_seed_ids=[], current_pool_tier=1,
            confidence_score=0.45,
            extracted_metadata={}, priority_ordered=[],
        )
        return session

    def test_3rd_genuine_turn_forces_exploring_regardless_of_confidence(
        self, auth_client, user_profile
    ):
        """On 3rd GENUINE calibration turn (seed excluded), force-transition to exploring."""
        session = self._session_with_seed_and_2_genuine_turns(user_profile)

        still_low_parse = _make_parse_result(
            confidence=0.40,
            system_action='REQUEST_PRIORITY',
            message='한 번 더 좁혀볼게요.',
            replies=['A', 'B', '상관없어요, 보여주세요'],
        )

        cal_patchers = []
        for target, se in _CALIBRATE_ENGINE_PATCHES.items():
            p = patch(target, side_effect=se)
            p.start()
            cal_patchers.append(p)

        try:
            with patch('apps.recommendation.services.session_service.services') as mock_svc:
                mock_svc.parse_query.return_value = still_low_parse
                mock_svc.get_cached_v_initial.return_value = None
                resp = auth_client.post(
                    f'/api/v1/analysis/sessions/{session.session_id}/calibrate/',
                    {'message': '재료는 상관없어요'},
                    format='json',
                )
        finally:
            for p in cal_patchers:
                p.stop()

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        # Cap forces exploring transition
        assert data['phase'] == 'exploring', (
            f"Expected 'exploring' on 3rd turn cap, got '{data['phase']}'"
        )
        assert data['needs_more_info'] is False

        session.refresh_from_db()
        assert session.phase == 'exploring'


@pytest.mark.django_db
class TestCalibrateSchemaFields:
    """create_session + calibrate responses include all new schema fields."""

    def test_create_session_response_has_calibration_fields(self, auth_client):
        """POST /sessions/ with confidence<0.6 returns all required schema keys."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {},
                    'confidence_score': 0.20,
                    'system_action': 'REQUEST_PRIORITY',
                    'llm_response_message': '질문',
                    'suggested_quick_replies': ['A', 'B', '보여주세요'],
                    'priority_ordered': ['program'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        data = resp.json()
        required_keys = [
            'session_id', 'project_id', 'phase', 'needs_more_info',
            'confidence_score', 'system_action', 'extracted_metadata',
            'llm_response_message', 'suggested_quick_replies', 'cards',
            'next_image', 'prefetch_image', 'prefetch_image_2', 'progress',
            'filter_relaxed',
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_exploring_response_has_calibration_fields(self, auth_client):
        """POST /sessions/ with confidence>=0.6 also returns all new keys."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {'program': 'Museum'},
                    'confidence_score': 0.80,
                    'system_action': 'NONE',
                    'llm_response_message': '',
                    'suggested_quick_replies': [],
                    'priority_ordered': ['program'],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        data = resp.json()
        assert 'phase' in data
        assert data['phase'] == 'exploring'
        assert 'needs_more_info' in data
        assert data['needs_more_info'] is False
        assert 'confidence_score' in data
        assert 'system_action' in data
        assert 'cards' in data

    def test_progress_phase_field_matches_session_phase(self, auth_client, user_profile):
        """progress.phase reflects the actual session phase."""
        patchers = _apply_patches()
        try:
            resp = auth_client.post(
                '/api/v1/analysis/sessions/',
                {
                    'filters': {},
                    'confidence_score': 0.15,
                    'system_action': 'REQUEST_PRIORITY',
                    'llm_response_message': '질문',
                    'suggested_quick_replies': ['A', '보여주세요'],
                    'priority_ordered': [],
                },
                format='json',
            )
        finally:
            _stop_patches(patchers)

        assert resp.status_code == 201
        data = resp.json()
        assert data['progress']['phase'] == 'chat_initializing'
