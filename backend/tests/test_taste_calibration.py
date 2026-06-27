"""
test_taste_calibration.py -- TASTE-CALIBRATION-1 refactored into parse-query layer.

Tests:
- TestCalibrationFallbackConfidence:  _compute_confidence_fallback heuristic correctness
- TestExtractCalibrationFields:       _extract_calibration_fields validates + falls back
- TestParseQueryCalibrationKeys:      parse_query returns all 5 calibration keys
- TestMultiAxisPriorityProbe:         D1 multi-axis trigger + suppression; chip objects shape
- TestParseQueryViewCalibrationKeys:  ParseQueryView echoes 5 keys in probe + terminal Response
- TestTopPriorityMultiplierRanking:   D2 rank-0 axis effective weight dominates
- TestDeterministicReRank:            Branch A — priority_axis chip click skips LLM, keeps all filters
- TestFreeTextFilterMerge:            Branch B — prior_filters merged into parsed_filters
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from apps.recommendation.services.parse_query import (
    _compute_confidence_fallback,
    _extract_calibration_fields,
)


# ---------------------------------------------------------------------------
# Shared Gemini mock helper
# ---------------------------------------------------------------------------

def _make_gemini_resp(payload: dict):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(payload)
    mock_resp.usage_metadata = MagicMock()
    mock_resp.usage_metadata.prompt_token_count = 10
    mock_resp.usage_metadata.candidates_token_count = 5
    mock_resp.usage_metadata.thoughts_token_count = 0
    mock_resp.usage_metadata.cached_content_token_count = 0
    return mock_resp


_MULTI_AXIS_PAYLOAD = {
    'probe_needed': False,
    'probe_question': None,
    'reply': '이해했어요.',
    'filters': {
        'location_country': 'Japan',
        'location_city': None,
        'program': 'Museum',
        'material': None,
        'style': None,
        'year_min': None,
        'year_max': None,
        'atmosphere': None,
        'color_tone': None,
        'typology_primary': None,
    },
    'filter_priority': ['program', 'location_country'],
    'raw_query': '일본 미술관',
    'visual_description': 'A museum in Japan.',
    'confidence_score': 0.75,
    'system_action': 'NONE',
    'suggested_quick_replies': [],
    'priority_ordered': ['program', 'location_country'],
    'llm_response_message': '이해했어요.',
}

_TERMINAL_PAYLOAD = {
    'probe_needed': False,
    'probe_question': None,
    'reply': '이해했어요: 목재 주택.',
    'filters': {
        'location_country': None,
        'location_city': None,
        'program': 'Housing',
        'material': 'timber',
        'style': None,
        'year_min': None,
        'year_max': None,
        'atmosphere': None,
        'color_tone': None,
        'typology_primary': None,
    },
    'filter_priority': ['program', 'material'],
    'raw_query': '목재 주택',
    'visual_description': 'A warm timber house.',
    'confidence_score': 0.80,
    'system_action': 'NONE',
    'suggested_quick_replies': [],
    'priority_ordered': ['program', 'material'],
    'llm_response_message': '이해했어요: 목재 주택.',
}

_PROBE_PAYLOAD = {
    'probe_needed': True,
    'probe_question': '어떤 방향을 원하세요?',
    'reply': '확인했어요.',
    'filters': {
        'location_country': None,
        'location_city': None,
        'program': 'Housing',
        'material': None,
        'style': None,
        'year_min': None,
        'year_max': None,
        'atmosphere': None,
        'color_tone': None,
        'typology_primary': None,
    },
    'filter_priority': ['program'],
    'raw_query': '주택',
    'visual_description': None,
    'confidence_score': 0.40,
    'system_action': 'REQUEST_PRIORITY',
    'suggested_quick_replies': ['따뜻한 재료', '차가운 기하성', '상관없어요, 다 보여주세요'],
    'priority_ordered': ['program'],
    'llm_response_message': '어떤 방향을 원하세요?',
}


# ---------------------------------------------------------------------------
# Pure unit tests — no DB
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
        assert 0.40 <= score <= 0.70, f"Expected 0.40-0.70, got {score}"

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
        assert isinstance(result['confidence_score'], float)
        assert 0.0 <= result['confidence_score'] <= 1.0

    def test_invalid_system_action_falls_back(self):
        data = {'confidence_score': 0.30, 'system_action': 'INVALID_VALUE'}
        filters = {
            'style': 'Contemporary', 'program': None,
            'material': None, 'location_country': None,
        }
        result = _extract_calibration_fields(data, filters, probe_needed=True)
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
# (a) parse_query returns all 5 calibration keys
# ---------------------------------------------------------------------------

class TestParseQueryCalibrationKeys:
    """parse_query returns all 5 calibration keys on both probe and terminal paths."""

    def test_terminal_has_all_5_calibration_keys(self, monkeypatch):
        from apps.recommendation import services
        monkeypatch.setitem(
            __import__('django.conf', fromlist=['settings']).settings.RECOMMENDATION,
            'stage_decouple_enabled', False,
        )
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda client, contents, config: _make_gemini_resp(_TERMINAL_PAYLOAD),
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        result = services.parse_query([{'role': 'user', 'text': '목재 주택'}])

        for key in ('confidence_score', 'system_action', 'suggested_quick_replies',
                    'priority_ordered', 'llm_response_message'):
            assert key in result, f"Missing calibration key: {key}"

    def test_probe_has_all_5_calibration_keys(self, monkeypatch):
        from apps.recommendation import services
        monkeypatch.setitem(
            __import__('django.conf', fromlist=['settings']).settings.RECOMMENDATION,
            'stage_decouple_enabled', False,
        )
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda client, contents, config: _make_gemini_resp(_PROBE_PAYLOAD),
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        result = services.parse_query([{'role': 'user', 'text': '주택'}])

        for key in ('confidence_score', 'system_action', 'suggested_quick_replies',
                    'priority_ordered', 'llm_response_message'):
            assert key in result, f"Missing calibration key: {key}"


# ---------------------------------------------------------------------------
# (b)+(c) Multi-axis D1 trigger tests
# ---------------------------------------------------------------------------

class TestMultiAxisPriorityProbe:
    """D1: multi-axis optional prompt fires on any terminal turn with >=2 strong axes (NON-BLOCKING).

    Results are always returned immediately (probe_needed stays False).
    The priority question + chips appear as an optional refinement alongside results.
    """

    def _run_parse(self, monkeypatch, gemini_payload, history):
        from apps.recommendation import services
        monkeypatch.setitem(
            __import__('django.conf', fromlist=['settings']).settings.RECOMMENDATION,
            'stage_decouple_enabled', False,
        )
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda client, contents, config: _make_gemini_resp(gemini_payload),
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())
        return services.parse_query(history)

    def test_two_strong_axes_non_blocking_with_chips(self, monkeypatch):
        """>=2 strong axes on terminal response -> probe_needed=False (results shown),
        system_action=REQUEST_PRIORITY, >=2 chip objects with label/axis/value,
        non-empty llm_response_message, and NO skip chip."""
        history = [{'role': 'user', 'text': '일본 미술관'}]
        result = self._run_parse(monkeypatch, _MULTI_AXIS_PAYLOAD, history)

        # Results are returned immediately — probe_needed must stay False
        assert result['probe_needed'] is False, (
            f"Expected probe_needed=False (non-blocking) with 2 strong axes, "
            f"got {result['probe_needed']}"
        )
        # Optional refinement metadata is populated
        assert result['system_action'] == 'REQUEST_PRIORITY'
        chips = result['suggested_quick_replies']
        assert len(chips) >= 2, f"Expected >=2 chips, got: {chips}"
        # Each chip must be a dict with label, axis, value keys
        for chip in chips:
            assert isinstance(chip, dict), f"Chip must be a dict, got: {type(chip)}"
            assert 'label' in chip, f"Chip missing 'label': {chip}"
            assert 'axis' in chip, f"Chip missing 'axis': {chip}"
            assert 'value' in chip, f"Chip missing 'value': {chip}"
            assert isinstance(chip['label'], str), f"chip.label must be str: {chip}"
            assert isinstance(chip['axis'], str), f"chip.axis must be str: {chip}"
        assert isinstance(result['llm_response_message'], str)
        assert result['llm_response_message'].strip() != ''
        # Skip chip must NOT be present — results are always shown
        skip_label = '상관없어요, 다 보여주세요'
        chip_labels = [c['label'] for c in chips]
        assert skip_label not in chip_labels, (
            f"Skip chip must not appear in non-blocking mode; labels: {chip_labels}"
        )

    def test_single_strong_axis_no_prompt(self, monkeypatch):
        """Only 1 strong axis -> D1 does NOT fire (no axis-labelled chips injected)."""
        single_axis_payload = dict(_PROBE_PAYLOAD)  # only program set
        history = [{'role': 'user', 'text': '주택'}]
        result = self._run_parse(monkeypatch, single_axis_payload, history)

        # D1 must NOT fire (only 1 strong axis in filters)
        # _PROBE_PAYLOAD has probe_needed=True from LLM (genuine slate probe) —
        # _maybe_multi_axis_probe must return it unchanged when probe_needed=True.
        chips = result.get('suggested_quick_replies', [])
        # Chips are now objects {label, axis, value}; check no D1-injected chip objects
        d1_pattern_chips = [
            c for c in chips
            if isinstance(c, dict) and c.get('axis') in ('program', 'location_country')
        ]
        assert len(d1_pattern_chips) == 0, (
            f"D1 must not fire with 1 strong axis; got D1-shaped chips: {chips}"
        )

    def test_turn_agnostic_fires_again_on_subsequent_terminal(self, monkeypatch):
        """Multi-axis query on turn-2 terminal also fires D1 (turn-agnostic).

        After the user picks a chip and sends a follow-up, the next terminal
        response still shows the optional priority question if >=2 axes remain.
        Chips are structured objects {label, axis, value}.
        """
        history = [
            {'role': 'user', 'text': '일본 미술관'},
            {'role': 'model', 'text': '추천에 더 중요하게 생각할 기준이 있나요?'},
            {'role': 'user', 'text': '프로그램(Museum)'},
        ]
        result = self._run_parse(monkeypatch, _MULTI_AXIS_PAYLOAD, history)

        # probe_needed=False (terminal), D1 should still fire with >=2 axes
        assert result['probe_needed'] is False
        assert result['system_action'] == 'REQUEST_PRIORITY'
        chips = result['suggested_quick_replies']
        assert len(chips) >= 2, f"Expected >=2 chips from D1, got: {chips}"
        # Each chip must be a structured object
        for chip in chips:
            assert isinstance(chip, dict) and 'axis' in chip and 'value' in chip, (
                f"Chip must be {{label, axis, value}} dict; got: {chip}"
            )

    def test_single_axis_query_no_d1_on_any_turn(self, monkeypatch):
        """Single-axis query on any turn -> D1 does NOT inject chips."""
        # Use a terminal payload with only one strong axis
        single_axis_terminal = {
            'probe_needed': False,
            'probe_question': None,
            'reply': '이해했어요: 주택.',
            'filters': {
                'location_country': None, 'location_city': None,
                'program': 'Housing',
                'material': None, 'style': None, 'year_min': None, 'year_max': None,
                'atmosphere': None, 'color_tone': None, 'typology_primary': None,
            },
            'filter_priority': ['program'],
            'raw_query': '주택',
            'visual_description': 'A housing project.',
            'confidence_score': 0.80,
            'system_action': 'NONE',
            'suggested_quick_replies': [],
            'priority_ordered': ['program'],
            'llm_response_message': '이해했어요: 주택.',
        }
        history = [
            {'role': 'user', 'text': '주택'},
            {'role': 'model', 'text': '이해했어요.'},
            {'role': 'user', 'text': '더 보여줘'},
        ]
        result = self._run_parse(monkeypatch, single_axis_terminal, history)

        # Only 1 strong axis -> D1 must not inject axis-labelled chips
        chips = result.get('suggested_quick_replies', [])
        # Chips are now objects {label, axis, value}; check no D1-injected chip objects
        d1_pattern_chips = [
            c for c in chips
            if isinstance(c, dict) and c.get('axis') == 'program'
        ]
        assert len(d1_pattern_chips) == 0, (
            f"D1 must not fire with 1 strong axis on turn-2+; got: {chips}"
        )


# ---------------------------------------------------------------------------
# (d) ParseQueryView echoes 5 keys in both probe and terminal Response
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestParseQueryViewCalibrationKeys:
    """ParseQueryView includes all 5 calibration keys in both probe and terminal Responses."""

    @pytest.fixture
    def auth_client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.models import UserProfile

        User = get_user_model()
        user = User.objects.create_user(username='testcalview', password='pass')
        UserProfile.objects.create(user=user, display_name='CalView')
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        return client

    def _5_keys(self):
        return ('confidence_score', 'system_action', 'suggested_quick_replies',
                'priority_ordered', 'llm_response_message')

    def test_probe_response_has_5_calibration_keys(self, auth_client):
        """Probe path (probe_needed=True) response includes all 5 calibration keys."""
        probe_result = dict(_PROBE_PAYLOAD)
        probe_result['filters'] = {
            'location_country': None, 'location_city': None, 'program': 'Housing',
            'material': None, 'style': None, 'year_min': None, 'year_max': None,
            'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        }
        with patch('apps.recommendation.views.services.parse_query', return_value=probe_result):
            with patch('apps.recommendation.views.engine.search_by_filters_scored',
                       return_value=[{'canonical_bld_id': 'bld_000001'}]):
                resp = auth_client.post(
                    '/api/v1/parse-query/',
                    {'conversation_history': [{'role': 'user', 'text': '주택'}]},
                    format='json',
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data.get('probe_needed') is True
        for key in self._5_keys():
            assert key in data, f"Probe response missing calibration key: {key}"

    def test_probe_response_includes_non_empty_results(self, auth_client):
        """Probe path always returns ~20 results (never empty list).

        Product rule: every parse-query response shows references; the probe
        question/chips are a supplementary overlay, not a replacement.
        """
        probe_result = dict(_PROBE_PAYLOAD)
        probe_result['filters'] = {
            'location_country': None, 'location_city': None, 'program': 'Housing',
            'material': None, 'style': None, 'year_min': None, 'year_max': None,
            'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        }
        fake_results = [{'canonical_bld_id': f'bld_{i:06d}'} for i in range(1, 21)]
        with patch('apps.recommendation.views.services.parse_query', return_value=probe_result):
            with patch('apps.recommendation.views.engine.search_by_filters_scored',
                       return_value=fake_results):
                resp = auth_client.post(
                    '/api/v1/parse-query/',
                    {'conversation_history': [{'role': 'user', 'text': '주택'}]},
                    format='json',
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data.get('probe_needed') is True, "Expected probe_needed=True"
        assert isinstance(data.get('results'), list), "results must be a list"
        assert len(data['results']) > 0, (
            "Probe response must include results (non-empty); got empty list"
        )
        assert data.get('probe_question') is not None, "probe_question must be present"

    def test_terminal_response_has_5_calibration_keys(self, auth_client):
        """Terminal path (probe_needed=False) response includes all 5 calibration keys."""
        terminal_result = dict(_TERMINAL_PAYLOAD)
        terminal_result['filters'] = {
            'location_country': None, 'location_city': None, 'program': 'Housing',
            'material': 'timber', 'style': None, 'year_min': None, 'year_max': None,
            'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        }
        with patch('apps.recommendation.views.services.parse_query', return_value=terminal_result):
            with patch('apps.recommendation.views.engine.search_by_filters_scored',
                       return_value=[{'canonical_bld_id': 'bld_000001'}]):
                resp = auth_client.post(
                    '/api/v1/parse-query/',
                    {'conversation_history': [{'role': 'user', 'text': '목재 주택'}]},
                    format='json',
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data.get('probe_needed') is False
        for key in self._5_keys():
            assert key in data, f"Terminal response missing calibration key: {key}"

    def test_probe_calibration_values_match_parse_query_output(self, auth_client):
        """Values echoed in probe response match what parse_query returned."""
        probe_result = dict(_PROBE_PAYLOAD)
        probe_result['filters'] = {
            'location_country': None, 'location_city': None, 'program': 'Housing',
            'material': None, 'style': None, 'year_min': None, 'year_max': None,
            'atmosphere': None, 'color_tone': None, 'typology_primary': None,
        }
        with patch('apps.recommendation.views.services.parse_query', return_value=probe_result):
            with patch('apps.recommendation.views.engine.search_by_filters_scored',
                       return_value=[{'canonical_bld_id': 'bld_000001'}]):
                resp = auth_client.post(
                    '/api/v1/parse-query/',
                    {'conversation_history': [{'role': 'user', 'text': '주택'}]},
                    format='json',
                )

        data = resp.json()
        assert data['confidence_score'] == pytest.approx(0.40)
        assert data['system_action'] == 'REQUEST_PRIORITY'
        assert isinstance(data['suggested_quick_replies'], list)
        assert isinstance(data['priority_ordered'], list)
        assert isinstance(data['llm_response_message'], str)


# ---------------------------------------------------------------------------
# (e) Ranking unit — D2 rank-0 effective weight dominates
# ---------------------------------------------------------------------------

class TestTopPriorityMultiplierRanking:
    """D2: _build_idf_score_cases rank-0 effective weight > summed weight of remaining axes.

    Note: _build_idf_score_cases outputs CASE WHEN expressions in a fixed axis order
    (program → location_country → style → ...) that is independent of filter_priority.
    We identify the rank-0 axis by matching the param value (e.g. '%Japan%') against
    the known filter_priority[0] axis param, rather than by case-list position.
    """

    def _build(self, filters, base_weights, idf_map=None, filter_priority=None):
        from apps.recommendation.engine_filters import _build_idf_score_cases
        _idf_map = idf_map if idf_map is not None else {'_total': 0}
        _priority = filter_priority or []
        return _build_idf_score_cases(filters, base_weights, _idf_map, _priority)

    def _extract_weight(self, case_str):
        """Extract the THEN <weight> float from a CASE WHEN expression."""
        parts = case_str.split('THEN ')
        if len(parts) >= 2:
            w_str = parts[-1].split(' ')[0]
            try:
                return float(w_str)
            except ValueError:
                pass
        return None

    def test_rank0_weight_greater_than_rank1_2_axes(self):
        """With filter_priority=['location_country', 'program'] + top_mult=4.0,
        rank-0 (location_country) effective weight > rank-1 (program) effective weight.

        Cases are output in fixed order: program first, then location_country.
        location_country is rank-0 (top priority), program is rank-1.
        """
        filters = {'location_country': 'Japan', 'program': 'Museum'}
        base_weights = {
            'location_country': 5.0,
            'program': 10.0,
            '_idf_ceiling': 3.0,
            '_priority_boost': 0.25,
            '_top_priority_multiplier': 4.0,
        }
        filter_priority = ['location_country', 'program']
        cases, params, total_weight = self._build(filters, base_weights,
                                                  filter_priority=filter_priority)

        assert len(cases) == 2, f"Expected 2 CASE expressions, got: {cases}"

        # Identify rank-0 case: params[i] is '%Japan%' (location_country, rank-0)
        # params[j] is 'Museum' (program, rank-1)
        weight_by_param = {p: self._extract_weight(c) for c, p in zip(cases, params)}
        rank0_w = weight_by_param['%Japan%']   # location_country = rank-0
        rank1_w = weight_by_param['Museum']     # program = rank-1

        assert rank0_w is not None and rank1_w is not None
        assert rank0_w > rank1_w, (
            f"rank-0 location_country weight ({rank0_w}) must dominate "
            f"rank-1 program weight ({rank1_w}) with top_priority_multiplier=4.0"
        )

    def test_rank0_weight_greater_than_sum_of_3_axes(self):
        """rank-0 effective weight must exceed the SUM of rank-1 + rank-2 weights.

        filter_priority=['location_country', 'program', 'style']
        Rank-0 = location_country (base=5.0), ranks 1-2 = program (10.0) + style (4.0).
        With top_mult=4.0, location_country should dominate even with lower base weight.
        """
        filters = {'location_country': 'Japan', 'program': 'Museum', 'style': 'Minimalist'}
        base_weights = {
            'location_country': 5.0,
            'program': 10.0,
            'style': 4.0,
            '_idf_ceiling': 3.0,
            '_priority_boost': 0.25,
            '_top_priority_multiplier': 4.0,
        }
        filter_priority = ['location_country', 'program', 'style']
        cases, params, total_weight = self._build(filters, base_weights,
                                                  filter_priority=filter_priority)

        assert len(cases) == 3, f"Expected 3 CASE expressions, got: {cases}"

        weight_by_param = {p: self._extract_weight(c) for c, p in zip(cases, params)}
        # Cases emitted in code order: program → location_country → style
        rank0_w = weight_by_param['%Japan%']        # location_country rank-0
        rank1_w = weight_by_param['Museum']          # program rank-1
        rank2_w = weight_by_param['%Minimalist%']   # style rank-2

        assert all(w is not None for w in [rank0_w, rank1_w, rank2_w])
        remainder_sum = rank1_w + rank2_w
        assert rank0_w > remainder_sum, (
            f"rank-0 location_country ({rank0_w}) must exceed sum of remainder "
            f"({remainder_sum} = program {rank1_w} + style {rank2_w}) "
            "with top_priority_multiplier=4.0"
        )

    def test_no_top_mult_rank0_does_not_dominate_higher_base(self):
        """Without top_mult amplification (mult=1.0), a higher-base rank-1 axis
        can outweigh a lower-base rank-0 axis.

        location_country (base=5.0, rank-0) vs program (base=10.0, rank-1).
        With top_mult=1.0, priority boost alone should not overcome the 2x base difference.
        """
        filters = {'location_country': 'Japan', 'program': 'Museum'}
        base_weights = {
            'location_country': 5.0,
            'program': 10.0,
            '_idf_ceiling': 3.0,
            '_priority_boost': 0.25,
            '_top_priority_multiplier': 1.0,
        }
        filter_priority = ['location_country', 'program']
        cases, params, total_weight = self._build(filters, base_weights,
                                                  filter_priority=filter_priority)

        assert len(cases) == 2
        weight_by_param = {p: self._extract_weight(c) for c, p in zip(cases, params)}
        rank0_w = weight_by_param['%Japan%']   # location_country rank-0
        rank1_w = weight_by_param['Museum']     # program rank-1

        # Expected: rank0 = 5.0 * (1 + 0.25 * 1.0) = 6.25
        #           rank1 = 10.0 * (1 + 0.25 * 0.5) = 11.25
        # Without top_mult, program (higher base) still outweighs location_country
        assert rank0_w < rank1_w, (
            f"Without top_mult, location_country rank-0 ({rank0_w}) should be less than "
            f"program rank-1 ({rank1_w}) given program has double the base weight"
        )


# ---------------------------------------------------------------------------
# (f) Deterministic re-rank path — Branch A (priority_axis chip click)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeterministicReRank:
    """Branch A: POST with priority_axis skips LLM, preserves ALL prior filters,
    returns results, and emits the structured chip list with chosen axis first."""

    @pytest.fixture
    def auth_client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.models import UserProfile

        User = get_user_model()
        user = User.objects.create_user(username='testdeterministic', password='pass')
        UserProfile.objects.create(user=user, display_name='Deterministic')
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        return client

    def test_deterministic_rerank_keeps_all_prior_filters(self, auth_client):
        """priority_axis + prior_filters -> response structured_filters keeps ALL three axes."""
        prior = {'program': 'Housing', 'location_country': 'South Korea', 'material': 'brick'}
        fake_results = [{'canonical_bld_id': f'bld_{i:06d}'} for i in range(1, 5)]

        with patch('apps.recommendation.views.services.parse_query') as mock_pq, \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '벽돌 주택'}],
                    'prior_filters': prior,
                    'priority_axis': 'material',
                    'raw_query': '벽돌 주택',
                },
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()

        # LLM must NOT be called on the deterministic path
        mock_pq.assert_not_called()

        # All three filters preserved in structured_filters
        sf = data['structured_filters']
        assert sf.get('program') == 'Housing', f"program lost; structured_filters={sf}"
        assert sf.get('location_country') == 'South Korea', f"location_country lost; sf={sf}"
        assert sf.get('material') == 'brick', f"material lost; sf={sf}"

    def test_deterministic_rerank_priority_axis_first_in_filter_priority(self, auth_client):
        """priority_axis='material' -> filter_priority[0] == 'material'."""
        prior = {'program': 'Housing', 'location_country': 'South Korea', 'material': 'brick'}
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query'), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '벽돌'}],
                    'prior_filters': prior,
                    'priority_axis': 'material',
                },
                format='json',
            )

        assert resp.status_code == 200
        fp = resp.json()['filter_priority']
        assert len(fp) > 0, "filter_priority must not be empty"
        assert fp[0] == 'material', f"Expected material first in filter_priority; got: {fp}"

    def test_deterministic_rerank_returns_results(self, auth_client):
        """Branch A always returns a non-empty results list (mocked engine)."""
        prior = {'program': 'Housing', 'location_country': 'South Korea', 'material': 'brick'}
        fake_results = [{'canonical_bld_id': f'bld_{i:06d}'} for i in range(1, 6)]

        with patch('apps.recommendation.views.services.parse_query'), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '벽돌 주택'}],
                    'prior_filters': prior,
                    'priority_axis': 'material',
                },
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data['probe_needed'] is False
        assert isinstance(data['results'], list)
        assert len(data['results']) > 0, "Branch A must return results"

    def test_deterministic_rerank_chips_chosen_axis_first(self, auth_client):
        """Branch A response chips list has chosen axis as first chip."""
        prior = {'program': 'Housing', 'location_country': 'South Korea', 'material': 'brick'}
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query'), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '벽돌'}],
                    'prior_filters': prior,
                    'priority_axis': 'material',
                },
                format='json',
            )

        assert resp.status_code == 200
        data = resp.json()
        chips = data['suggested_quick_replies']
        assert isinstance(chips, list) and len(chips) > 0
        # Each chip is a structured object
        for chip in chips:
            assert isinstance(chip, dict)
            assert 'label' in chip and 'axis' in chip and 'value' in chip
        # Chosen axis must appear first
        assert chips[0]['axis'] == 'material', (
            f"Expected chosen axis 'material' first in chips; got: {chips[0]}"
        )

    def test_deterministic_rerank_invalid_priority_axis_rejected(self, auth_client):
        """priority_axis not in allowed set -> 400."""
        prior = {'program': 'Housing'}
        resp = auth_client.post(
            '/api/v1/parse-query/',
            {
                'conversation_history': [{'role': 'user', 'text': '주택'}],
                'prior_filters': prior,
                'priority_axis': 'invalid_axis_xyz',
            },
            format='json',
        )
        assert resp.status_code == 400

    def test_deterministic_rerank_parse_query_not_called(self, auth_client):
        """parse_query service must NOT be called when priority_axis is provided."""
        prior = {'program': 'Housing', 'material': 'concrete'}
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query') as mock_pq, \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '콘크리트'}],
                    'prior_filters': prior,
                    'priority_axis': 'material',
                },
                format='json',
            )

        mock_pq.assert_not_called()


# ---------------------------------------------------------------------------
# (g) Free-text filter merge — Branch B (prior_filters + LLM)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFreeTextFilterMerge:
    """Branch B: prior_filters merged with LLM-parsed filters so prior axes survive."""

    @pytest.fixture
    def auth_client(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.models import UserProfile

        User = get_user_model()
        user = User.objects.create_user(username='testmerge', password='pass')
        UserProfile.objects.create(user=user, display_name='Merge')
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        return client

    def test_prior_filters_merged_with_llm_filters(self, auth_client):
        """LLM returns {material:brick}; prior has {program:Housing, location_country:'South Korea'}.
        Merged structured_filters must contain all three axes."""
        llm_result = {
            'probe_needed': False,
            'probe_question': None,
            'reply': '벽돌 건물을 찾아드릴게요.',
            'filters': {
                'location_country': None,
                'location_city': None,
                'program': None,
                'material': 'brick',
                'style': None,
                'year_min': None,
                'year_max': None,
                'atmosphere': None,
                'color_tone': None,
                'typology_primary': None,
            },
            'filter_priority': ['material'],
            'raw_query': '벽돌',
            'visual_description': 'A brick building.',
            'confidence_score': 0.75,
            'system_action': 'NONE',
            'suggested_quick_replies': [],
            'priority_ordered': ['material'],
            'llm_response_message': '벽돌 건물을 찾아드릴게요.',
            'image_focus': None,
        }
        prior = {'program': 'Housing', 'location_country': 'South Korea'}
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query', return_value=llm_result), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '벽돌'}],
                    'prior_filters': prior,
                },
                format='json',
            )

        assert resp.status_code == 200
        sf = resp.json()['structured_filters']

        # All three axes must be present after merge
        assert sf.get('program') == 'Housing', f"program dropped; sf={sf}"
        assert sf.get('location_country') == 'South Korea', f"location_country dropped; sf={sf}"
        assert sf.get('material') == 'brick', f"material missing; sf={sf}"

    def test_current_turn_axis_overrides_prior(self, auth_client):
        """If LLM returns a value for an axis already in prior_filters, LLM value wins."""
        llm_result = {
            'probe_needed': False,
            'probe_question': None,
            'reply': '일본 건물.',
            'filters': {
                'location_country': 'Japan',
                'location_city': None,
                'program': None,
                'material': None,
                'style': None,
                'year_min': None,
                'year_max': None,
                'atmosphere': None,
                'color_tone': None,
                'typology_primary': None,
            },
            'filter_priority': ['location_country'],
            'raw_query': '일본',
            'visual_description': 'A Japanese building.',
            'confidence_score': 0.70,
            'system_action': 'NONE',
            'suggested_quick_replies': [],
            'priority_ordered': ['location_country'],
            'llm_response_message': '일본 건물.',
            'image_focus': None,
        }
        # Prior has location_country='South Korea'; LLM says 'Japan' — Japan must win
        prior = {'location_country': 'South Korea', 'program': 'Housing'}
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query', return_value=llm_result), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '일본'}],
                    'prior_filters': prior,
                },
                format='json',
            )

        assert resp.status_code == 200
        sf = resp.json()['structured_filters']
        # LLM override wins for location_country
        assert sf.get('location_country') == 'Japan', (
            f"Expected LLM 'Japan' to override prior 'South Korea'; sf={sf}"
        )
        # Prior program axis preserved (LLM returned None for it)
        assert sf.get('program') == 'Housing', f"program dropped; sf={sf}"

    def test_empty_prior_filters_uses_llm_only(self, auth_client):
        """No prior_filters -> behaviour unchanged (only LLM filters used)."""
        llm_result = {
            'probe_needed': False,
            'probe_question': None,
            'reply': '알겠어요.',
            'filters': {
                'location_country': None,
                'location_city': None,
                'program': 'Housing',
                'material': None,
                'style': None,
                'year_min': None,
                'year_max': None,
                'atmosphere': None,
                'color_tone': None,
                'typology_primary': None,
            },
            'filter_priority': ['program'],
            'raw_query': '주택',
            'visual_description': 'A housing project.',
            'confidence_score': 0.70,
            'system_action': 'NONE',
            'suggested_quick_replies': [],
            'priority_ordered': ['program'],
            'llm_response_message': '알겠어요.',
            'image_focus': None,
        }
        fake_results = [{'canonical_bld_id': 'bld_000001'}]

        with patch('apps.recommendation.views.services.parse_query', return_value=llm_result), \
             patch('apps.recommendation.views.engine.search_by_filters_scored',
                   return_value=fake_results):
            resp = auth_client.post(
                '/api/v1/parse-query/',
                {
                    'conversation_history': [{'role': 'user', 'text': '주택'}],
                    # no prior_filters
                },
                format='json',
            )

        assert resp.status_code == 200
        sf = resp.json()['structured_filters']
        assert sf.get('program') == 'Housing'
        # No extra axes injected from nowhere
        assert sf.get('location_country') is None or 'location_country' not in sf
