"""
test_chat_phase.py -- Sprint 1 §3: Chat phase parse_query rewrite tests.

Covers:
  - Terminal 4-field response shape
  - Probe (interim) response shape
  - Multi-turn conversation_history passthrough to Gemini
  - Backward compat: legacy string input wraps as single-turn
  - Gemini failure degrades to fallback + emits failure event (A5 integration)
  - Pre-deploy style label corpus verification (skipped on SQLite)
"""
import json
import pytest
from unittest.mock import MagicMock

from apps.recommendation import services


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gemini_response(payload: dict):
    """Create a mock Gemini response object that returns payload as JSON text."""
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(payload)
    return mock_resp


_TERMINAL_PAYLOAD = {
    'probe_needed': False,
    'probe_question': None,
    'reply': '이해했어요: 목재 주택 레퍼런스. 맞을까요?',
    'filters': {
        'location_country': None,
        'program': 'Housing',
        'material': 'timber',
        'style': None,
        'year_min': None,
        'year_max': None,
        'min_area': None,
        'max_area': None,
    },
    'filter_priority': ['program', 'material'],
    'raw_query': '새로 올릴 주택 프로젝트 참고용 찾아요.',
    'visual_description': (
        'A residential house with exposed timber as the dominant surface. '
        'Warm tones, haptic finishes, and natural light.'
    ),
}

_PROBE_PAYLOAD = {
    'probe_needed': True,
    'probe_question': '따뜻한 재료감이 끌리세요, 차가운 기하성이 끌리세요?',
    'reply': '주택 프로젝트 레퍼런스 찾는 거 확인했어요.',
    'filters': {
        'location_country': None,
        'program': 'Housing',
        'material': None,
        'style': None,
        'year_min': None,
        'year_max': None,
        'min_area': None,
        'max_area': None,
    },
    'filter_priority': ['program'],
    'raw_query': '새로 올릴 주택 프로젝트 참고용 찾아요.',
    'visual_description': None,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatPhaseParseQuery:
    """Sprint 1 §3: chat phase 4-field output + 0-2 turn probe per Investigation 06."""

    def test_terminal_response_4_fields(self, monkeypatch):
        """parse_query with clear input returns terminal payload with required 4 spec fields."""
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _make_gemini_response(_TERMINAL_PAYLOAD),
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        result = services.parse_query([{'role': 'user', 'text': '새로 올릴 주택 프로젝트 참고용 찾아요.'}])

        assert result['probe_needed'] is False
        assert result['probe_question'] is None
        assert isinstance(result['reply'], str) and result['reply']
        assert isinstance(result['filters'], dict)
        assert isinstance(result['filter_priority'], list)
        assert isinstance(result['raw_query'], str) and result['raw_query']
        assert isinstance(result['visual_description'], str) and result['visual_description']
        # The 4 spec §3 terminal fields:
        assert 'filters' in result
        assert 'filter_priority' in result
        assert 'raw_query' in result
        assert 'visual_description' in result

    def test_probe_response_shape(self, monkeypatch):
        """parse_query with ambiguous input returns probe payload — no visual_description."""
        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: _make_gemini_response(_PROBE_PAYLOAD),
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        result = services.parse_query([{'role': 'user', 'text': '새로 올릴 주택 프로젝트 참고용 찾아요.'}])

        assert result['probe_needed'] is True
        assert isinstance(result['probe_question'], str) and result['probe_question']
        assert isinstance(result['reply'], str)
        assert result['visual_description'] is None

    def test_multi_turn_passes_history_to_gemini(self, monkeypatch):
        """parse_query with 2-turn history correctly builds Gemini contents list."""
        captured_contents = []

        def _fake_generate_content(*args, **kwargs):
            # contents is always passed as keyword arg
            contents = kwargs.get('contents', [])
            captured_contents.extend(contents)
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_generate_content
        monkeypatch.setattr(services, '_get_client', lambda: mock_client)

        history = [
            {'role': 'user', 'text': '새로 올릴 주택 프로젝트 참고용 찾아요.'},
            {'role': 'model', 'text': json.dumps(_PROBE_PAYLOAD)},
            {'role': 'user', 'text': '따뜻한 재료 쪽이요.'},
        ]
        result = services.parse_query(history)

        # Verify Gemini was called with exactly 3 Content turns in captured_contents
        assert mock_client.models.generate_content.called
        assert len(captured_contents) == 3
        # raw_query must be verbatim first user message
        assert result['raw_query'] == '새로 올릴 주택 프로젝트 참고용 찾아요.'

    def test_legacy_string_input_wrapped_as_single_turn(self, monkeypatch):
        """Backward compat: parse_query('query string') wraps as [{role:user, text:...}]."""
        captured_contents_len = []

        def _fake_generate_content(**kwargs):
            captured_contents_len.append(len(kwargs.get('contents', [])))
            return _make_gemini_response(_TERMINAL_PAYLOAD)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_generate_content
        monkeypatch.setattr(services, '_get_client', lambda: mock_client)

        result = services.parse_query('새로 올릴 주택 프로젝트 참고용 찾아요.')

        # Should have been wrapped to a 1-element history
        assert captured_contents_len == [1]
        assert result['probe_needed'] is False
        assert result['raw_query'] == '새로 올릴 주택 프로젝트 참고용 찾아요.'

    @pytest.mark.django_db
    def test_gemini_failure_returns_fallback_with_failure_event(self, monkeypatch):
        """On Gemini exception, parse_query degrades gracefully + emits failure event (A5)."""
        from apps.recommendation.models import SessionEvent

        def _raise(*a, **kw):
            raise RuntimeError('Gemini unavailable')

        monkeypatch.setattr(services, '_retry_gemini_call', _raise)
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        result = services.parse_query([{'role': 'user', 'text': 'concrete brutalist museum'}])

        # Fallback shape per Investigation 06 §"Fallback payload"
        assert result['probe_needed'] is False
        assert result['probe_question'] is None
        assert isinstance(result['filters'], dict)
        assert result['filter_priority'] == []
        assert result['raw_query'] == 'concrete brutalist museum'
        assert result['visual_description'] is None

        # A5 failure event emitted
        failure_events = SessionEvent.objects.filter(event_type='failure')
        assert failure_events.count() >= 1
        last = failure_events.order_by('-created_at').first()
        assert last.payload.get('failure_type') == 'gemini_parse'

    @pytest.mark.django_db
    def test_chat_phase_style_labels_in_corpus(self):
        """
        Pre-deploy gate: every style label in few-shot examples must exist in
        the architecture_vectors corpus.

        Skips automatically when architecture_vectors is not in the test DB
        (i.e., SQLite in-memory — the normal CI environment).
        """
        from django.db import connection, OperationalError, ProgrammingError
        from apps.recommendation.services import _CHAT_PHASE_FEW_SHOT_STYLE_LABELS

        # Check whether architecture_vectors exists in this DB.
        # OperationalError: SQLite missing table. ProgrammingError: Postgres missing table.
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT style FROM architecture_vectors "
                    "WHERE style IS NOT NULL ORDER BY style"
                )
                corpus_styles = {row[0] for row in cur.fetchall()}
        except (OperationalError, ProgrammingError):
            pytest.skip('architecture_vectors table not available in test DB')

        if not corpus_styles:
            pytest.skip('architecture_vectors table is empty — cannot verify style labels')

        missing = _CHAT_PHASE_FEW_SHOT_STYLE_LABELS - corpus_styles
        assert not missing, (
            f'Few-shot style labels not found in corpus: {missing}. '
            f'Corpus has: {sorted(corpus_styles)}. '
            f'Update the few-shot examples or accept null-filter degradation for these labels.'
        )


# ---------------------------------------------------------------------------
# Sprint 1 fix-loop tests (Reviewer FAIL #2/#3 + Security FAIL #1/#2)
# ---------------------------------------------------------------------------

class TestGeneratePersonaReportThinkingBudget:
    """Issue 1: generate_persona_report must pass thinking_budget=0 (spec §11.1 IMP-4)."""

    def test_generate_persona_report_uses_thinking_budget_zero(self, monkeypatch):
        """GenerateContentConfig passed to Gemini must include ThinkingConfig(thinking_budget=0)."""
        from unittest.mock import MagicMock
        from apps.recommendation import services

        captured_configs = []

        def _fake_generate_content(**kwargs):
            captured_configs.append(kwargs.get('config'))
            mock_resp = MagicMock()
            mock_resp.text = json.dumps({
                'persona_type': 'The Minimalist',
                'one_liner': 'Clean lines, quiet spaces.',
                'description': 'Two sentences of description here.',
                'dominant_programs': ['Housing'],
                'dominant_styles': ['Modernist'],
                'dominant_materials': ['concrete'],
            })
            return mock_resp

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = _fake_generate_content
        monkeypatch.setattr(services, '_get_client', lambda: mock_client)

        # Bypass the DB fetch
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: MagicMock()
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(services, 'connection', mock_conn)
        monkeypatch.setattr(
            services, '_dictfetchall',
            lambda cur: [{
                'program': 'Housing', 'style': 'Modernist', 'atmosphere': 'serene',
                'material': 'concrete', 'architect': 'Test Arch', 'location_country': 'KR',
            }],
        )

        services.generate_persona_report(['B00001'])

        assert len(captured_configs) == 1, 'Gemini generate_content should be called exactly once'
        cfg = captured_configs[0]
        assert cfg is not None, 'config must be provided'
        thinking = cfg.thinking_config
        assert thinking is not None, 'thinking_config must be set'
        assert thinking.thinking_budget == 0, (
            f'thinking_budget must be 0 to suppress hidden reasoning tokens; got {thinking.thinking_budget}'
        )


class TestParseQueryTimingEvent:
    """Issue 2: parse_query must emit parse_query_timing event after each Gemini call."""

    @pytest.mark.django_db
    def test_parse_query_emits_timing_event(self, monkeypatch):
        """After a successful Gemini call, a parse_query_timing SessionEvent is created."""
        from apps.recommendation import services
        from apps.recommendation.models import SessionEvent

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(_TERMINAL_PAYLOAD)
        mock_resp.usage_metadata = MagicMock()
        mock_resp.usage_metadata.prompt_token_count = 100
        mock_resp.usage_metadata.candidates_token_count = 50
        mock_resp.usage_metadata.thoughts_token_count = 0

        monkeypatch.setattr(
            services, '_retry_gemini_call',
            lambda func, *a, **kw: mock_resp,
        )
        monkeypatch.setattr(services, '_get_client', lambda: MagicMock())

        before_count = SessionEvent.objects.filter(event_type='parse_query_timing').count()
        services.parse_query([{'role': 'user', 'text': 'concrete brutalist museum'}])
        after_count = SessionEvent.objects.filter(event_type='parse_query_timing').count()

        assert after_count == before_count + 1, (
            'parse_query must emit exactly one parse_query_timing event per call'
        )
        event = SessionEvent.objects.filter(event_type='parse_query_timing').order_by('-created_at').first()
        payload = event.payload
        assert 'gemini_total_ms' in payload
        assert 'gen_ms' in payload
        assert payload['input_tokens'] == 100
        assert payload['output_tokens'] == 50
        assert payload['thinking_tokens'] == 0
        assert payload['ttft_ms'] is None


class TestParseQueryInputValidation:
    """Issues 3 & 4: input validation for conversation_history in ParseQueryView."""

    @pytest.fixture
    def auth_client(self, db):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        from apps.accounts.models import UserProfile

        User = get_user_model()
        user = User.objects.create_user(username='testval', password='pass')
        UserProfile.objects.create(user=user, display_name='Test Val')
        token = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
        return client

    def test_parse_query_rejects_long_history(self, auth_client):
        """POST with 11-element conversation_history must return 400."""
        history = [{'role': 'user', 'text': 'msg'} for _ in range(11)]
        resp = auth_client.post(
            '/api/v1/parse-query/',
            data={'conversation_history': history},
            format='json',
        )
        assert resp.status_code == 400
        assert 'too long' in resp.data.get('detail', '').lower()

    def test_parse_query_rejects_invalid_role(self, auth_client):
        """POST with role='admin' in history must return 400."""
        history = [{'role': 'admin', 'text': 'concrete brutalist museum'}]
        resp = auth_client.post(
            '/api/v1/parse-query/',
            data={'conversation_history': history},
            format='json',
        )
        assert resp.status_code == 400
        assert 'role' in resp.data.get('detail', '').lower()
