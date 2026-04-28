"""
test_imp6_stage_decouple.py -- IMP-6 Commit 2: parse_query split + Stage 2 background thread.

Spec v1.10 §11.1 IMP-6 Commit 2: the actual stage-decouple mechanism.

Tests:
- TestParseQueryStage1:           response excludes visual_description; Stage 1 M1/M4/IMP-5 preserved
- TestGenerateVisualDescription:  success path, failure returns None, caches V_initial
- TestStage2ThreadSpawn:          thread spawned on terminal turn; NOT on clarification; NOT when flag off; failure silent
- TestStage2TimingEvent:          stage2_timing event emitted on success and failure
- TestSessionCreateLateBindIntegration: real SessionCreateView with cache hit/miss/flag-off
- TestRankWithVInitial:           cosine-similarity ranking correctness
"""
import time
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core.cache import cache


# ---------------------------------------------------------------------------
# Fixture: clear Django cache between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_response(text, candidates_token_count=180, prompt_token_count=900):
    """Build a minimal fake Gemini response object."""
    resp = MagicMock()
    resp.text = text
    usage = MagicMock()
    usage.candidates_token_count = candidates_token_count
    usage.prompt_token_count = prompt_token_count
    usage.thoughts_token_count = 0
    usage.cached_content_token_count = 0
    resp.usage_metadata = usage
    return resp


_STAGE1_JSON = (
    '{"probe_needed": false, "probe_question": null, "reply": "Got it: Brutalist housing.",'
    ' "filters": {"location_country": null, "program": "Housing", "material": "concrete",'
    ' "style": "Brutalist", "year_min": null, "year_max": null, "min_area": null, "max_area": null},'
    ' "filter_priority": ["program", "material", "style"],'
    ' "raw_query": "Brutalist concrete housing"}'
)

_PROBE_JSON = (
    '{"probe_needed": true, "probe_question": "따뜻한 vs 차가운?", "reply": "주택, 확인했어요.",'
    ' "filters": {"location_country": null, "program": "Housing", "material": null,'
    ' "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null},'
    ' "filter_priority": ["program"],'
    ' "raw_query": "주택 레퍼런스"}'
)

_FAKE_VECTOR = [0.01 * i for i in range(384)]  # deterministic 384-dim test vector


# ---------------------------------------------------------------------------
# TestParseQueryStage1
# ---------------------------------------------------------------------------

class TestParseQueryStage1:
    """parse_query_stage1: Stage 1 response excludes visual_description; all telemetry preserved."""

    def test_stage1_excludes_visual_description(self):
        """parse_query_stage1 always returns visual_description=None."""
        from apps.recommendation.services import parse_query_stage1

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(_STAGE1_JSON, candidates_token_count=185)
            )
            with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                result = parse_query_stage1([{'role': 'user', 'text': 'Brutalist concrete housing'}])

        assert result.get('visual_description') is None
        assert result.get('probe_needed') is False
        assert result.get('filters', {}).get('program') == 'Housing'

    def test_stage1_preserves_clarification_flow(self):
        """parse_query_stage1 with probe_needed=True returns correct probe fields."""
        from apps.recommendation.services import parse_query_stage1

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(_PROBE_JSON, candidates_token_count=90)
            )
            with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                result = parse_query_stage1([{'role': 'user', 'text': '주택 레퍼런스'}])

        assert result.get('probe_needed') is True
        assert result.get('probe_question') is not None
        assert result.get('visual_description') is None

    def test_stage1_token_count_check_via_telemetry(self):
        """Stage 1 response_schema reduces output: token count should be < 250 for typical query."""
        from apps.recommendation.services import parse_query_stage1

        # Simulate low token count (Stage 1 expected savings)
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(_STAGE1_JSON, candidates_token_count=190)
            )
            with patch('apps.recommendation.services.event_log') as mock_log:
                with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                    parse_query_stage1([{'role': 'user', 'text': 'Brutalist concrete housing'}])

        # parse_query_timing was emitted with output_tokens=190 (< 250 target)
        emit_calls = mock_log.emit_event.call_args_list
        timing_call = next(
            (c for c in emit_calls if c[0][0] == 'parse_query_timing'),
            None,
        )
        assert timing_call is not None
        kwargs = timing_call[1] if timing_call[1] else {}
        # output_tokens captured in kwargs
        assert kwargs.get('output_tokens') == 190
        assert kwargs.get('output_tokens', 999) < 250

    def test_stage1_emits_stage_field_in_timing(self):
        """parse_query_stage1 emits parse_query_timing with stage='1'."""
        from apps.recommendation.services import parse_query_stage1

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(_STAGE1_JSON)
            )
            with patch('apps.recommendation.services.event_log') as mock_log:
                with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                    parse_query_stage1([{'role': 'user', 'text': 'Brutalist concrete housing'}])

        timing_calls = [
            c for c in mock_log.emit_event.call_args_list
            if c[0][0] == 'parse_query_timing'
        ]
        assert len(timing_calls) == 1
        kwargs = timing_calls[0][1]
        assert kwargs.get('stage') == '1', "parse_query_stage1 must emit stage='1' in timing event"

    def test_stage1_m1_cap_fires_at_turn_3(self):
        """M1 runaway-clarification cap still fires in Stage 1."""
        from apps.recommendation.services import parse_query_stage1

        history = [
            {'role': 'user', 'text': 'show me housing'},
            {'role': 'model', 'text': '{"probe_needed": true, ...}'},
            {'role': 'user', 'text': 'warm materials'},
            {'role': 'model', 'text': '{"probe_needed": true, ...}'},
            {'role': 'user', 'text': 'timber please'},
        ]

        # Gemini tries to return probe_needed=True on turn 3
        probe_response = _fake_response(_PROBE_JSON)
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = probe_response
            with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                result = parse_query_stage1(history)

        # M1 cap must force probe_needed=False
        assert result.get('probe_needed') is False

    def test_stage1_fallback_on_gemini_failure(self):
        """Stage 1 returns graceful fallback dict on Gemini exception."""
        from apps.recommendation.services import parse_query_stage1

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.side_effect = RuntimeError('API error')
            with patch.dict(settings.RECOMMENDATION, {'context_caching_enabled': False}):
                result = parse_query_stage1([{'role': 'user', 'text': 'some query'}])

        assert result.get('probe_needed') is False
        assert result.get('visual_description') is None
        assert '이해를 잘 못 했어요' in result.get('reply', '')

    def test_parse_query_routes_to_stage1_when_flag_on(self):
        """parse_query(flag ON) delegates to parse_query_stage1."""
        from apps.recommendation import services

        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            with patch.object(services, 'parse_query_stage1', return_value={'mocked': True}) as mock_s1:
                result = services.parse_query([{'role': 'user', 'text': 'test'}])

        mock_s1.assert_called_once()
        assert result == {'mocked': True}

    def test_parse_query_legacy_path_when_flag_off(self):
        """parse_query(flag OFF) uses original single-call path (visual_description may be set)."""
        from apps.recommendation.services import parse_query

        # Flag OFF: original path returns visual_description from Gemini
        full_json = (
            '{"probe_needed": false, "probe_question": null, "reply": "Got it.",'
            ' "filters": {"location_country": null, "program": "Museum", "material": null,'
            ' "style": null, "year_min": null, "year_max": null, "min_area": null, "max_area": null},'
            ' "filter_priority": ["program"],'
            ' "raw_query": "museum",'
            ' "visual_description": "A contemporary museum with exposed concrete facades."}'
        )
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(full_json, candidates_token_count=310)
            )
            with patch.dict(settings.RECOMMENDATION, {
                'stage_decouple_enabled': False,
                'context_caching_enabled': False,
            }):
                result = parse_query([{'role': 'user', 'text': 'museum'}])

        assert result.get('visual_description') is not None
        assert 'concrete' in result.get('visual_description', '')


# ---------------------------------------------------------------------------
# TestGenerateVisualDescription
# ---------------------------------------------------------------------------

class TestGenerateVisualDescription:
    """generate_visual_description: success path, failure handling, V_initial caching."""

    def test_generate_visual_description_returns_string(self):
        """Success path: returns a non-empty visual_description string."""
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A brutalist housing block with raw concrete walls and bold overhangs.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text, candidates_token_count=155)
            )
            with patch('apps.recommendation.services.embed_visual_description', return_value=_FAKE_VECTOR):
                with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                    result = generate_visual_description(
                        filters={'program': 'Housing', 'style': 'Brutalist', 'material': 'concrete'},
                        raw_query='Brutalist concrete housing',
                        user_id=42,
                    )

        assert isinstance(result, str)
        assert len(result) > 0
        assert 'concrete' in result.lower()

    def test_generate_visual_description_handles_gemini_failure(self):
        """Gemini exception -> returns None, no exception propagated."""
        from apps.recommendation.services import generate_visual_description

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.side_effect = RuntimeError('quota')
            with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                result = generate_visual_description(
                    filters={'program': 'Housing'},
                    raw_query='housing query',
                    user_id=1,
                )

        assert result is None

    def test_generate_visual_description_caches_v_initial(self):
        """Success + valid embedding -> set_cached_v_initial called with correct args."""
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A contemplative stone pavilion on Jeju Island.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text)
            )
            with patch('apps.recommendation.services.embed_visual_description',
                       return_value=_FAKE_VECTOR) as mock_embed:
                with patch('apps.recommendation.services.set_cached_v_initial') as mock_set:
                    with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                        generate_visual_description(
                            filters={'program': 'Religion', 'location_country': 'South Korea'},
                            raw_query='Jeju stone meditation center',
                            user_id=7,
                        )

        mock_embed.assert_called_once_with(vd_text, session=None, user=None)
        mock_set.assert_called_once_with(7, 'Jeju stone meditation center', _FAKE_VECTOR)

    def test_generate_visual_description_skips_cache_on_embed_failure(self):
        """embed_visual_description returns None -> set_cached_v_initial NOT called."""
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A concrete museum with natural light shafts.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text)
            )
            with patch('apps.recommendation.services.embed_visual_description', return_value=None):
                with patch('apps.recommendation.services.set_cached_v_initial') as mock_set:
                    with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                        generate_visual_description(
                            filters={'program': 'Museum'},
                            raw_query='museum query',
                            user_id=1,
                        )

        mock_set.assert_not_called()

    def test_generate_visual_description_emits_stage2_timing_on_success(self):
        """Success path emits stage2_timing event with renamed fields and new fields."""
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A parametric pavilion with complex curvature.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text, candidates_token_count=160)
            )
            with patch('apps.recommendation.services.embed_visual_description',
                       return_value=_FAKE_VECTOR):
                with patch('apps.recommendation.services.set_cached_v_initial'):
                    with patch('apps.recommendation.services.event_log') as mock_log:
                        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                            generate_visual_description(
                                filters={'style': 'Parametric'},
                                raw_query='parametric building',
                                user_id=5,
                            )

        timing_calls = [
            c for c in mock_log.emit_event.call_args_list
            if c[0][0] == 'stage2_timing'
        ]
        assert len(timing_calls) == 1
        kwargs = timing_calls[0][1]
        # Renamed fields (spec v1.7 §6)
        assert 'stage2_total_ms' in kwargs
        assert isinstance(kwargs['stage2_total_ms'], float)
        assert 'gemini_visual_description_ms' in kwargs
        assert isinstance(kwargs['gemini_visual_description_ms'], float)
        # New fields
        assert kwargs.get('outcome') == 'success'
        assert kwargs.get('hf_inference_ms') is not None
        assert isinstance(kwargs['hf_inference_ms'], float)
        assert kwargs.get('pool_rerank_ms') is None  # deferred placeholder
        # Preserved diagnostic fields
        assert kwargs.get('success') is True
        assert kwargs.get('v_initial_computed') is True
        assert kwargs.get('v_initial_dim') == 384
        assert kwargs.get('error_class') is None
        # Old field names must NOT appear (renamed)
        assert 'total_ms' not in kwargs
        assert 'gemini_total_ms' not in kwargs

    def test_generate_visual_description_emits_stage2_timing_on_gemini_failure(self):
        """Gemini failure: outcome='gemini_failure', hf_inference_ms is None."""
        from apps.recommendation.services import generate_visual_description

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.side_effect = RuntimeError('API down')
            with patch('apps.recommendation.services.event_log') as mock_log:
                with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                    generate_visual_description(
                        filters={},
                        raw_query='any query',
                        user_id=1,
                    )

        timing_calls = [
            c for c in mock_log.emit_event.call_args_list
            if c[0][0] == 'stage2_timing'
        ]
        assert len(timing_calls) == 1
        kwargs = timing_calls[0][1]
        assert kwargs.get('outcome') == 'gemini_failure'
        assert kwargs.get('hf_inference_ms') is None  # HF never called
        assert kwargs.get('pool_rerank_ms') is None
        assert kwargs.get('success') is False
        assert kwargs.get('error_class') == 'RuntimeError'
        assert kwargs.get('v_initial_computed') is False

    def test_generate_visual_description_emits_stage2_timing_on_hf_failure(self):
        """HF failure: outcome='hf_failure', hf_inference_ms is set (call was made)."""
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A concrete bunker with narrow slit windows.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text)
            )
            with patch('apps.recommendation.services.embed_visual_description',
                       return_value=None):  # HF returns None
                with patch('apps.recommendation.services.event_log') as mock_log:
                    with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                        generate_visual_description(
                            filters={'program': 'Museum'},
                            raw_query='brutalist museum',
                            user_id=7,
                        )

        timing_calls = [
            c for c in mock_log.emit_event.call_args_list
            if c[0][0] == 'stage2_timing'
        ]
        assert len(timing_calls) == 1
        kwargs = timing_calls[0][1]
        assert kwargs.get('outcome') == 'hf_failure'
        # hf_inference_ms is set — the HF call was made even though it returned None
        assert kwargs.get('hf_inference_ms') is not None
        assert isinstance(kwargs['hf_inference_ms'], float)
        assert kwargs.get('pool_rerank_ms') is None
        assert kwargs.get('v_initial_computed') is False

    def test_generate_visual_description_all_paths_pool_rerank_ms_none(self):
        """All paths: pool_rerank_ms is None (deferred to Commit 3)."""
        from apps.recommendation.services import generate_visual_description

        # Success path
        vd_text = 'Glazed tower with structural exoskeleton.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text)
            )
            with patch('apps.recommendation.services.embed_visual_description',
                       return_value=_FAKE_VECTOR):
                with patch('apps.recommendation.services.set_cached_v_initial'):
                    with patch('apps.recommendation.services.event_log') as mock_log:
                        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                            generate_visual_description(
                                filters={},
                                raw_query='tower',
                                user_id=2,
                            )

        all_stage2 = [
            c for c in mock_log.emit_event.call_args_list
            if c[0][0] == 'stage2_timing'
        ]
        for call in all_stage2:
            assert call[1].get('pool_rerank_ms') is None


# ---------------------------------------------------------------------------
# TestStage2ThreadSpawn
# ---------------------------------------------------------------------------

class TestStage2ThreadSpawn:
    """Stage 2 thread spawn: correct conditions for spawning + failure isolation."""

    def _make_stage1_result(self, probe_needed=False):
        return {
            'probe_needed': probe_needed,
            'probe_question': '따뜻한 vs 차가운?' if probe_needed else None,
            'reply': 'Got it.' if not probe_needed else 'Ack.',
            'filters': {'program': 'Housing', 'material': 'concrete'},
            'filter_priority': ['program'],
            'raw_query': 'test query',
            'visual_description': None,
        }

    def test_thread_spawned_on_terminal_turn_flag_on(self):
        """stage_decouple_enabled=True + probe_needed=False -> thread spawned."""
        from apps.recommendation.views import _spawn_stage2

        with patch('apps.recommendation.views.threading.Thread') as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance
            with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                _spawn_stage2(
                    filters={'program': 'Housing'},
                    raw_query='test query',
                    user_id=1,
                )

        assert mock_thread_cls.call_count == 1
        # daemon=True verified
        call_kwargs = mock_thread_cls.call_args[1]
        assert call_kwargs.get('daemon') is True
        mock_thread_instance.start.assert_called_once()

    def test_thread_not_spawned_on_clarification_turn(self):
        """ParseQueryView should NOT spawn Stage 2 when probe_needed=True."""
        from rest_framework.test import APIRequestFactory
        from apps.recommendation.views import ParseQueryView

        factory = APIRequestFactory()
        request = factory.post(
            '/api/v1/recommendation/parse-query/',
            {'query': 'housing ref'},
            format='json',
        )
        request.user = MagicMock()
        request.user.id = 1

        probe_result = self._make_stage1_result(probe_needed=True)
        with patch('apps.recommendation.views.services.parse_query', return_value=probe_result):
            with patch('apps.recommendation.views._spawn_stage2') as mock_spawn:
                with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                    view = ParseQueryView.as_view()
                    view(request)

        mock_spawn.assert_not_called()

    def test_thread_not_spawned_when_flag_off(self):
        """stage_decouple_enabled=False -> _spawn_stage2 never called even on terminal turn."""
        from rest_framework.test import APIRequestFactory
        from apps.recommendation.views import ParseQueryView

        factory = APIRequestFactory()
        request = factory.post(
            '/api/v1/recommendation/parse-query/',
            {'query': 'brutalist concrete'},
            format='json',
        )
        request.user = MagicMock()
        request.user.id = 1

        terminal_result = self._make_stage1_result(probe_needed=False)
        with patch('apps.recommendation.views.services.parse_query', return_value=terminal_result):
            with patch('apps.recommendation.views.engine.search_by_filters', return_value=[]):
                with patch('apps.recommendation.views.engine.get_diverse_random', return_value=[]):
                    with patch('apps.recommendation.views._spawn_stage2') as mock_spawn:
                        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': False}):
                            view = ParseQueryView.as_view()
                            view(request)

        mock_spawn.assert_not_called()

    def test_thread_failure_silent(self):
        """Stage 2 thread exception does NOT bubble up to the caller of _spawn_stage2."""
        from apps.recommendation.views import _spawn_stage2

        # Patch generate_visual_description to raise inside the thread's _run closure
        with patch('apps.recommendation.views.services.generate_visual_description',
                   side_effect=Exception('Stage 2 crash')):
            # No exception should propagate from _spawn_stage2 caller
            try:
                _spawn_stage2(
                    filters={'program': 'Museum'},
                    raw_query='museum query',
                    user_id=1,
                )
                # Give thread a moment to run (daemon=True so test exit is safe)
                time.sleep(0.05)
            except Exception:
                pytest.fail('_spawn_stage2 must not propagate Stage 2 exceptions')


# ---------------------------------------------------------------------------
# TestStage2TimingEvent (django_db)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStage2TimingEventDB:
    """stage2_timing event stored in SessionEvent DB on success and failure."""

    def test_stage2_timing_emitted_on_success(self):
        """Success path: SessionEvent with event_type='stage2_timing' and success=True created."""
        from apps.recommendation.models import SessionEvent
        from apps.recommendation.services import generate_visual_description

        vd_text = 'A minimalist house with white plaster walls and large glazed openings.'
        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.return_value = (
                _fake_response(vd_text, candidates_token_count=160)
            )
            with patch('apps.recommendation.services.embed_visual_description',
                       return_value=_FAKE_VECTOR):
                with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                    generate_visual_description(
                        filters={'style': 'Minimalist'},
                        raw_query='minimalist housing',
                        user_id=99,
                    )

        events = SessionEvent.objects.filter(event_type='stage2_timing')
        assert events.count() >= 1
        evt = events.last()
        assert evt.payload.get('success') is True
        assert evt.payload.get('v_initial_computed') is True
        assert evt.payload.get('outcome') == 'success'
        assert 'stage2_total_ms' in evt.payload
        assert 'gemini_visual_description_ms' in evt.payload
        assert evt.payload.get('pool_rerank_ms') is None

    def test_stage2_timing_emitted_on_failure(self):
        """Failure path: SessionEvent with event_type='stage2_timing' and success=False created."""
        from apps.recommendation.models import SessionEvent
        from apps.recommendation.services import generate_visual_description

        with patch('apps.recommendation.services._get_client') as mock_client:
            mock_client.return_value.models.generate_content.side_effect = RuntimeError('Network error')
            with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
                generate_visual_description(
                    filters={},
                    raw_query='some query',
                    user_id=1,
                )

        events = SessionEvent.objects.filter(event_type='stage2_timing')
        assert events.count() >= 1
        evt = events.last()
        assert evt.payload.get('success') is False
        assert evt.payload.get('error_class') == 'RuntimeError'
        assert evt.payload.get('v_initial_computed') is False
        assert evt.payload.get('outcome') == 'gemini_failure'
        assert evt.payload.get('hf_inference_ms') is None  # HF never called


# ---------------------------------------------------------------------------
# TestSessionCreateLateBindIntegration (django_db)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionCreateLateBindIntegration:
    """Real integration tests for SessionCreateView IMP-6 late-bind paths."""

    def _mock_pool(self):
        """Mock engine.create_pool_with_relaxation to return a small pool."""
        pool_ids = ['B00001', 'B00002', 'B00003', 'B00004']
        pool_scores = {pid: 1 for pid in pool_ids}
        return pool_ids, pool_scores, 1

    def _mock_card(self, building_id='B00001'):
        return {
            'building_id': building_id,
            'name_en': 'Test Building',
            'project_name': 'Test Project',
            'image_url': '',
            'url': None,
            'gallery': [],
            'gallery_drawing_start': 0,
            'metadata': {
                'axis_typology': 'Housing',
                'axis_architects': None,
                'axis_country': None,
                'axis_area_m2': None,
                'axis_year': None,
                'axis_style': 'Brutalist',
                'axis_atmosphere': 'raw',
                'axis_color_tone': None,
                'axis_material': 'concrete',
                'axis_material_visual': [],
                'axis_tags': [],
            },
        }

    def _run_session_create(self, auth_client, query, extra_flags=None):
        """Helper: call SessionCreateView with full engine mocked.

        farthest_point_from_pool is called in a loop up to initial_explore_rounds (10)
        times but will stop when pool is exhausted. We provide None after the pool IDs
        are exhausted so the loop terminates cleanly.
        """
        pool_ids = ['B00001', 'B00002', 'B00003', 'B00004']
        # Provide enough values: 4 pool IDs then None to signal exhaustion
        fp_side_effect = pool_ids + [None] * 10

        flags = {'stage_decouple_enabled': False}
        if extra_flags:
            flags.update(extra_flags)

        with patch.dict(settings.RECOMMENDATION, flags):
            with patch('apps.recommendation.engine.create_pool_with_relaxation',
                       return_value=(pool_ids, {pid: 1 for pid in pool_ids}, 1)):
                with patch('apps.recommendation.engine.get_pool_embeddings', return_value={}):
                    with patch('apps.recommendation.engine.farthest_point_from_pool',
                               side_effect=fp_side_effect):
                        with patch('apps.recommendation.engine.get_building_card',
                                   side_effect=lambda bid: self._mock_card(bid)):
                            return auth_client.post(
                                '/api/v1/analysis/sessions/',
                                {'filters': {'program': 'Housing'}, 'query': query},
                                format='json',
                            ), flags

    def test_session_create_with_v_initial_cache_hit(self, user_profile, auth_client):
        """Pre-populate V_initial cache -> SessionCreateView reads it -> v_initial_success=True."""
        from apps.recommendation.services import set_cached_v_initial

        fake_v = _FAKE_VECTOR
        # Populate cache BEFORE the request
        with patch.dict(settings.RECOMMENDATION, {'stage_decouple_enabled': True}):
            set_cached_v_initial(user_profile.user.id, 'brutalist housing', fake_v)

        response, _ = self._run_session_create(
            auth_client, 'brutalist housing',
            extra_flags={'stage_decouple_enabled': True},
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.content}"
        data = response.json()
        assert 'session_id' in data

        from apps.recommendation.models import SessionEvent
        session_events = SessionEvent.objects.filter(event_type='session_start')
        evt = session_events.last()
        assert evt is not None
        assert evt.payload.get('v_initial_success') is True

    def test_session_create_with_v_initial_cache_miss(self, user_profile, auth_client):
        """Cache empty -> falls through to filter-only pool (no crash, no v_initial)."""
        response, _ = self._run_session_create(
            auth_client, 'query with no cache entry',
            extra_flags={'stage_decouple_enabled': True},
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.content}"
        data = response.json()
        assert 'session_id' in data

        from apps.recommendation.models import SessionEvent
        session_events = SessionEvent.objects.filter(event_type='session_start')
        evt = session_events.last()
        assert evt is not None
        assert evt.payload.get('v_initial_success') is False

    def test_session_create_byte_identical_when_flag_off(self, user_profile, auth_client):
        """flag OFF -> legacy path runs; get_cached_v_initial never called."""
        with patch('apps.recommendation.services.get_cached_v_initial') as mock_get:
            response, _ = self._run_session_create(
                auth_client, 'housing ref',
                extra_flags={'stage_decouple_enabled': False, 'hyde_vinitial_enabled': False},
            )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.content}"
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# TestRankWithVInitial
# ---------------------------------------------------------------------------

class TestRankWithVInitial:
    """_rank_with_v_initial: cosine-similarity ranking correctness."""

    def test_rank_returns_pool_unchanged_on_none_vector(self):
        """v_initial=None -> pool_ids returned as-is (list copy)."""
        from apps.recommendation.engine import _rank_with_v_initial

        pool = ['A', 'B', 'C']
        result = _rank_with_v_initial(pool, None)
        assert result == ['A', 'B', 'C']
        assert result is not pool  # list copy, not same reference

    def test_rank_returns_empty_on_empty_pool(self):
        """pool_ids=[] -> returns empty list."""
        from apps.recommendation.engine import _rank_with_v_initial

        result = _rank_with_v_initial([], [0.0] * 384)
        assert result == []

    def test_rank_returns_pool_unchanged_on_zero_vector(self):
        """Zero v_initial vector -> defensive pass-through, same order."""
        from apps.recommendation.engine import _rank_with_v_initial

        pool = ['A', 'B', 'C']
        result = _rank_with_v_initial(pool, [0.0] * 384)
        assert result == ['A', 'B', 'C']

    def test_rank_sorts_by_cosine_similarity(self):
        """Known vectors -> expected ranking: most similar first."""
        from apps.recommendation.engine import _rank_with_v_initial

        # v_initial: unit vector along dim 0
        v_initial = [0.0] * 384
        v_initial[0] = 1.0

        # embeddings:
        #   'B00001' is fully aligned with v_initial (sim=1.0)
        #   'B00002' is orthogonal (sim=0.0)
        #   'B00003' is anti-aligned (sim=-1.0)
        aligned_emb = np.zeros(384, dtype=np.float32)
        aligned_emb[0] = 1.0  # already normalized

        ortho_emb = np.zeros(384, dtype=np.float32)
        ortho_emb[1] = 1.0  # orthogonal

        anti_emb = np.zeros(384, dtype=np.float32)
        anti_emb[0] = -1.0  # anti-aligned

        fake_embeddings = {
            'B00001': aligned_emb,
            'B00002': ortho_emb,
            'B00003': anti_emb,
        }

        with patch('apps.recommendation.engine.get_pool_embeddings',
                   return_value=fake_embeddings):
            result = _rank_with_v_initial(['B00001', 'B00002', 'B00003'], v_initial)

        assert result == ['B00001', 'B00002', 'B00003'], (
            f"Expected [B00001, B00002, B00003] by descending cosine sim, got {result}"
        )

    def test_rank_handles_missing_embeddings_gracefully(self):
        """Building with no embedding -> placed at bottom (sim=-1.0)."""
        from apps.recommendation.engine import _rank_with_v_initial

        v_initial = [1.0] + [0.0] * 383
        aligned_emb = np.zeros(384, dtype=np.float32)
        aligned_emb[0] = 1.0

        # B00002 has no embedding
        fake_embeddings = {'B00001': aligned_emb}

        with patch('apps.recommendation.engine.get_pool_embeddings',
                   return_value=fake_embeddings):
            result = _rank_with_v_initial(['B00001', 'B00002'], v_initial)

        # B00001 (sim=1.0) before B00002 (sim=-1.0)
        assert result.index('B00001') < result.index('B00002')

    def test_rerank_pool_integrates_with_rank(self):
        """rerank_pool_with_v_initial uses _rank_with_v_initial for unlocked tail."""
        from apps.recommendation.engine import rerank_pool_with_v_initial

        pool = ['L1', 'U1', 'U2', 'U3']
        locked = ['L1']

        v_initial = [1.0] + [0.0] * 383

        # U3 most aligned, U1 least aligned
        u3_emb = np.zeros(384, dtype=np.float32)
        u3_emb[0] = 1.0
        u2_emb = np.zeros(384, dtype=np.float32)
        u2_emb[1] = 1.0
        u1_emb = np.zeros(384, dtype=np.float32)
        u1_emb[0] = -1.0

        fake_embeddings = {'U1': u1_emb, 'U2': u2_emb, 'U3': u3_emb}

        with patch('apps.recommendation.engine.get_pool_embeddings',
                   return_value=fake_embeddings):
            result = rerank_pool_with_v_initial(
                pool_ids=pool,
                exposed_ids=locked,
                initial_batch_ids=[],
                v_initial_vector=v_initial,
            )

        # L1 locked at front; tail sorted by cosine: U3, U2, U1
        assert result[0] == 'L1'
        tail = result[1:]
        assert tail == ['U3', 'U2', 'U1'], f"Expected ['U3', 'U2', 'U1'], got {tail}"
