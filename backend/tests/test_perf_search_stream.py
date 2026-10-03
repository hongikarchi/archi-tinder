"""
test_perf_search_stream.py -- PERF-SEARCH-1: streaming parse-query.

Covers:
- PartialJSONScanner  (chunk boundaries, escapes, nested objects, surrogate pairs)
- ParseStreamSink     (early filters trigger, ttft/filters_ms, reply deltas)
- generate_content_streaming (openai stream, gemini fallback, pre-output fallback,
                              mid-stream failure, strict schema request shape)
- parse_query / parse_query_stage1 with a sink (identical result, telemetry)
- POST /api/v1/parse-query/stream/ view (event order, final == blocking body, error,
  400 before stream, Accept: text/event-stream)
- schema / prompt key-order + unchanged `required`

All tests are DB-free: the view is driven through APIRequestFactory with a stub
authenticated user, and event_log / vocab / engine / Stage-2 spawn are mocked.
"""
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.recommendation import services
from apps.recommendation import views as _views  # noqa: F401 -- loads swipe_service for tests/conftest autouse patch
from apps.recommendation.services._stream import (
    FILTER_TRIO, ParseStreamSink, PartialJSONScanner,
)

AXES = (
    'location_country', 'location_city', 'program', 'material', 'style',
    'year_min', 'year_max', 'atmosphere', 'color_tone', 'typology_primary',
    'architectural_elements',
)


def _axes(**kw):
    d = {a: None for a in AXES}
    d.update(kw)
    return d


def _llm_output(*, filters=None, delta_set=None, delta_remove=None, priority=None,
                probe_needed=False, reply='이해했어요: 따뜻한 "목재" 주택 — \U0001F3E0 맞을까요?',
                probe_question=None, stage1=True, image_focus=None, image_focus_last=False):
    """Model output in the NEW key order (filters, filter_delta, image_focus,
    filter_priority first). `image_focus_last=True` emits image_focus AFTER the reply
    (a non-conforming order: it is then unknown when the early `filters` event fires)."""
    out = {
        'filters': _axes(**(filters or {})),
        'filter_delta': {'set': _axes(**(delta_set or {})), 'remove': delta_remove or []},
    }
    if not image_focus_last:
        out['image_focus'] = image_focus
    out.update({
        'filter_priority': priority if priority is not None else ['program', 'material'],
        'probe_needed': probe_needed,
        'reply': reply,
        'probe_question': probe_question,
    })
    if image_focus_last:
        out['image_focus'] = image_focus
    out['raw_query'] = 'ignored-by-server-verbatim-rule'
    if not stage1:
        out['visual_description'] = 'A warm timber house.'
    out.update({
        'confidence_score': 0.8, 'system_action': 'NONE',
        'suggested_quick_replies': [], 'priority_ordered': ['program'],
        'llm_response_message': reply,
    })
    return json.dumps(out)  # ensure_ascii=True -> \uXXXX escapes incl. a surrogate pair


HOUSING = {'program': 'Housing', 'material': 'timber', 'style': 'Contemporary'}
FIRST_TURN_TEXT = _llm_output(filters=HOUSING)
HISTORY = [{'role': 'user', 'text': '목재 주택 보여줘'}]

RESULTS = [{'canonical_bld_id': 'bld_000001'}, {'canonical_bld_id': 'bld_000002'}]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunks(text, size):
    return [text[i:i + size] for i in range(0, len(text), size)]


def _scan(text, size, stream_keys=('reply',)):
    sc = PartialJSONScanner(stream_keys=stream_keys)
    events = []
    for c in _chunks(text, size):
        events.extend(sc.feed(c))
    return events, sc


def _stream_chunk(text=None, usage=None):
    if text is None:
        return SimpleNamespace(choices=[], usage=usage)
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None,
    )


def _usage():
    return SimpleNamespace(prompt_tokens=120, completion_tokens=45, prompt_tokens_details=None)


class _FakeOpenAIClient:
    """client.chat.completions.create(...) -> iterator of chunks (or raises)."""

    def __init__(self, text=None, chunk_size=9, raise_before=None, raise_after_chunks=None,
                 delay=0.0):
        self.calls = []
        self._text = text
        self._size = chunk_size
        self._raise_before = raise_before
        self._raise_after = raise_after_chunks
        self._delay = delay
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_before is not None:
            raise self._raise_before
        return self._iter()

    def _iter(self):
        for n, piece in enumerate(_chunks(self._text, self._size)):
            if self._raise_after is not None and n >= self._raise_after:
                raise RuntimeError('boom mid-stream')
            if self._delay:
                time.sleep(self._delay)
            yield _stream_chunk(piece)
        yield _stream_chunk(None, usage=_usage())


def _blocking_response(text):
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=120, candidates_token_count=45,
            cached_content_token_count=None, thoughts_token_count=None,
        ),
    )


@pytest.fixture(autouse=True)
def _isolate():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def parse_env():
    """Mock every non-LLM dependency of parse_query / the view (DB-free)."""
    emitted = []

    def _emit(event_type, session=None, user=None, **payload):
        emitted.append((event_type, payload))

    with patch('apps.recommendation.services.get_axis_vocab',
               return_value=services._VOCAB_SNAPSHOT), \
            patch('apps.recommendation.services.event_log.emit_event', side_effect=_emit), \
            patch('apps.recommendation.views.search.engine.search_by_filters_scored',
                  return_value=list(RESULTS)) as search, \
            patch('apps.recommendation.views.search.engine.get_diverse_random',
                  return_value=list(RESULTS)), \
            patch('apps.recommendation.views.search._spawn_stage2') as spawn, \
            patch.dict('django.conf.settings.RECOMMENDATION',
                       {'stage_decouple_enabled': True, 'hyde_vinitial_enabled': True}):
        yield SimpleNamespace(events=emitted, search=search, spawn=spawn)


def _timing(env):
    rows = [p for t, p in env.events if t == 'parse_query_timing']
    assert len(rows) == 1
    return rows[0]


OPENAI = dict(LLM_PROVIDER='openai', OPENAI_TEXT_MODEL='gpt-test', OPENAI_STRICT_SCHEMA=True)


# ---------------------------------------------------------------------------
# PartialJSONScanner
# ---------------------------------------------------------------------------

class TestPartialJSONScanner:
    @pytest.mark.parametrize('size', [1, 2, 3, 5, 11, 64, 10_000])
    def test_values_and_reply_reassemble_across_any_chunk_boundary(self, size):
        text = FIRST_TURN_TEXT
        events, sc = _scan(text, size)
        values = {e[1]: e[2] for e in events if e[0] == 'value'}
        full = json.loads(text)
        assert values == full
        assert ''.join(e[2] for e in events if e[0] == 'delta' and e[1] == 'reply') == full['reply']
        assert not sc.broken

    def test_key_order_events_follow_output_order(self):
        events, _ = _scan(FIRST_TURN_TEXT, 4)
        keys = [e[1] for e in events if e[0] == 'key']
        assert keys[:6] == [
            'filters', 'filter_delta', 'image_focus', 'filter_priority', 'probe_needed', 'reply',
        ]

    def test_filters_value_available_before_reply_text_arrives(self):
        text = FIRST_TURN_TEXT
        cut = text.index('"reply"') + len('"reply": "이해')
        sc = PartialJSONScanner()
        events = sc.feed(text[:cut])
        done = [e[1] for e in events if e[0] == 'value']
        assert 'filters' in done and 'filter_priority' in done
        assert 'reply' not in done

    def test_nested_objects_and_braces_inside_strings(self):
        text = '{"filters": {"a": {"b": "}{ \\" ]"}, "c": [1, {"d": 2}]}, "reply": "x}"}'
        for size in (1, 2, 7):
            events, sc = _scan(text, size)
            values = {e[1]: e[2] for e in events if e[0] == 'value'}
            assert values['filters'] == {'a': {'b': '}{ " ]'}, 'c': [1, {'d': 2}]}
            assert values['reply'] == 'x}'
            assert not sc.broken

    def test_escaped_quote_and_backslash_in_reply(self):
        text = json.dumps({'reply': 'say "hi" \\ back\nline', 'z': 1}, ensure_ascii=False)
        for size in (1, 2, 3, 100):
            events, _ = _scan(text, size)
            joined = ''.join(e[2] for e in events if e[0] == 'delta')
            assert joined == 'say "hi" \\ back\nline'

    def test_split_unicode_escape_never_emits_partial_or_garbage(self):
        text = '{"reply": "ab\\uc774\\ud574cd"}'  # 이해 as \u escapes
        seen = ''
        sc = PartialJSONScanner()
        for c in _chunks(text, 1):
            for e in sc.feed(c):
                if e[0] == 'delta':
                    seen += e[2]
                    assert '\\' not in e[2] and '�' not in e[2]
        assert seen == 'ab이해cd'

    def test_surrogate_pair_emitted_whole_or_not_at_all(self):
        text = json.dumps({'reply': 'a\U0001F3E0b'})  # 🏠
        sc = PartialJSONScanner()
        deltas = []
        for c in _chunks(text, 1):
            deltas += [e[2] for e in sc.feed(c) if e[0] == 'delta']
        assert ''.join(deltas) == 'a\U0001F3E0b'
        assert all(d.encode('utf-8') for d in deltas)  # no lone surrogates

    def test_scalars_null_bool_number(self):
        text = '{"a": null, "b": true, "c": 12.5, "d": -3, "e": "s"}'
        events, _ = _scan(text, 1)
        values = {e[1]: e[2] for e in events if e[0] == 'value'}
        assert values == {'a': None, 'b': True, 'c': 12.5, 'd': -3, 'e': 's'}

    def test_leading_junk_and_code_fence_ignored(self):
        events, _ = _scan('```json\n{"a": 1}', 3)
        assert [e for e in events if e[0] == 'value'] == [('value', 'a', 1)]

    def test_malformed_input_never_raises(self):
        sc = PartialJSONScanner()
        for c in _chunks('{"a": {"b": nope}, "c": 1}', 2):
            sc.feed(c)  # must not raise
        assert sc.broken

    def test_only_watched_string_keys_produce_deltas(self):
        events, _ = _scan('{"probe_question": "q?", "reply": "r"}', 2)
        assert {e[1] for e in events if e[0] == 'delta'} == {'reply'}


# ---------------------------------------------------------------------------
# ParseStreamSink
# ---------------------------------------------------------------------------

class TestParseStreamSink:
    def test_filters_callback_fires_once_when_filter_priority_closes(self):
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        sink.mark_start()
        text = FIRST_TURN_TEXT
        for c in _chunks(text, 6):
            sink.feed(c)
        assert len(got) == 1
        assert set(got[0]) == set(FILTER_TRIO) | {'image_focus'}
        assert got[0]['filters']['program'] == 'Housing'
        assert sink.filters_emitted and sink.filters_ms is not None
        assert sink.ttft_ms is not None and sink.filters_ms >= sink.ttft_ms

    def test_filters_not_fired_until_filter_priority_closed(self):
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        text = FIRST_TURN_TEXT
        cut = text.index('"filter_priority"')
        sink.feed(text[:cut])
        assert got == []
        sink.feed(text[cut:])
        assert len(got) == 1

    def test_no_early_filters_when_model_puts_reply_first(self):
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        # reply first, filter_priority missing entirely -> trigger never closes
        sink.feed('{"reply": "hi", "filters": {"a": 1}, "filter_delta": {}}')
        assert got == [] and not sink.filters_emitted and sink.filters_ms is None

    def test_filters_fire_when_filters_key_absent_follow_up_turn(self):
        """Follow-up turn without `filters`: filter_delta + filter_priority is enough."""
        obj = json.loads(_llm_output(delta_set={'material': 'timber'}, priority=['material']))
        del obj['filters']
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        sink.mark_start()
        for c in _chunks(json.dumps(obj), 7):
            sink.feed(c)
        assert len(got) == 1  # exactly once
        assert set(got[0]) == {'filter_delta', 'filter_priority', 'image_focus'}
        assert sink.filters_emitted and sink.filters_ms is not None

    def test_filters_fire_when_only_filters_present_no_delta(self):
        obj = json.loads(_llm_output(filters=HOUSING))
        del obj['filter_delta']
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        for c in _chunks(json.dumps(obj), 7):
            sink.feed(c)
        assert len(got) == 1 and set(got[0]) == {'filters', 'filter_priority', 'image_focus'}

    def test_no_early_filters_with_priority_only(self):
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        sink.feed('{"filter_priority": ["program"], "reply": "hi"}')
        assert got == [] and not sink.filters_emitted

    def test_filters_emitted_stays_false_when_callback_fails(self):
        calls = []

        def _boom(partial):
            calls.append(partial)
            raise RuntimeError('cb')

        sink = ParseStreamSink(on_filters_ready=_boom)
        sink.mark_start()
        for c in _chunks(FIRST_TURN_TEXT, 6):
            sink.feed(c)  # must not raise
        assert len(calls) == 1  # attempted once, never retried
        assert sink.filters_emitted is False and sink.filters_ms is None

    def test_filters_emitted_true_without_callback(self):
        sink = ParseStreamSink()
        sink.mark_start()
        for c in _chunks(FIRST_TURN_TEXT, 6):
            sink.feed(c)
        assert sink.filters_emitted and sink.filters_ms is not None

    def test_reply_deltas_forwarded_and_callback_errors_swallowed(self):
        deltas = []

        def _boom(_):
            raise RuntimeError('cb')

        sink = ParseStreamSink(on_filters_ready=_boom, on_reply_delta=deltas.append)
        for c in _chunks(FIRST_TURN_TEXT, 5):
            sink.feed(c)  # must not raise even though on_filters_ready explodes
        assert ''.join(deltas) == json.loads(FIRST_TURN_TEXT)['reply']


# ---------------------------------------------------------------------------
# generate_content_streaming
# ---------------------------------------------------------------------------

def _config(stage1=True):
    from google.genai import types
    return types.GenerateContentConfig(
        system_instruction='sys', response_mime_type='application/json',
        response_schema=services._STAGE1_RESPONSE_SCHEMA if stage1 else None,
    )


def _contents():
    from google.genai import types
    return [types.Content(role='user', parts=[types.Part.from_text(text='hi')])]


class TestGenerateContentStreaming:
    @override_settings(**OPENAI)
    def test_openai_stream_request_shape_and_accumulated_response(self):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT)
        sink = ParseStreamSink()
        resp = services.generate_content_streaming(
            client, sink=sink, contents=_contents(), config=_config(stage1=True),
        )
        assert resp.text == FIRST_TURN_TEXT
        assert resp.usage_metadata.prompt_token_count == 120
        assert resp.usage_metadata.candidates_token_count == 45
        assert resp.ttft_ms is not None and sink.ttft_ms is not None
        kw = client.calls[0]
        assert kw['stream'] is True and kw['stream_options'] == {'include_usage': True}
        assert kw['model'] == 'gpt-test'
        rf = kw['response_format']
        assert rf['type'] == 'json_schema' and rf['json_schema']['strict'] is True
        props = list(rf['json_schema']['schema']['properties'])
        assert props[:4] == ['filters', 'filter_delta', 'image_focus', 'filter_priority']
        assert props.index('reply') > props.index('filter_priority')
        assert 'visual_description' not in props  # Stage-1 variant

    @override_settings(**OPENAI)
    def test_legacy_route_keeps_visual_description_in_strict_schema(self):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT)
        services.generate_content_streaming(
            client, sink=ParseStreamSink(), contents=_contents(), config=_config(stage1=False),
        )
        props = client.calls[0]['response_format']['json_schema']['schema']['properties']
        assert 'visual_description' in props

    @override_settings(**dict(OPENAI, OPENAI_STRICT_SCHEMA=False))
    def test_non_strict_falls_back_to_json_object(self):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT)
        services.generate_content_streaming(
            client, sink=ParseStreamSink(), contents=_contents(), config=_config(),
        )
        assert client.calls[0]['response_format'] == {'type': 'json_object'}

    @override_settings(**OPENAI)
    def test_blocking_request_shape_unchanged(self):
        """The refactored kwargs builder must not change the non-stream request."""
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=FIRST_TURN_TEXT))],
            usage=None,
        )
        services.generate_content_with_fallback(client, contents=_contents(), config=_config())
        kw = client.chat.completions.create.call_args.kwargs
        assert 'stream' not in kw and 'stream_options' not in kw
        assert kw['response_format'] == {'type': 'json_object'}  # stage1 route: not strict
        client.chat.completions.create.reset_mock()
        services.generate_content_with_fallback(
            client, contents=_contents(), config=_config(stage1=False),
        )
        kw = client.chat.completions.create.call_args.kwargs
        assert kw['response_format']['json_schema']['strict'] is True
        assert 'visual_description' in kw['response_format']['json_schema']['schema']['properties']

    @override_settings(LLM_PROVIDER='gemini')
    def test_gemini_provider_uses_blocking_call_and_feeds_nothing(self):
        sink = ParseStreamSink()
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   return_value=_blocking_response(FIRST_TURN_TEXT)) as blocking:
            resp = services.generate_content_streaming(
                MagicMock(), sink=sink, contents=_contents(), config=_config(),
            )
        assert resp.text == FIRST_TURN_TEXT
        blocking.assert_called_once()
        assert sink.got_output is False and sink.error is None

    @override_settings(**OPENAI)
    def test_failure_before_output_falls_back_to_blocking(self):
        client = _FakeOpenAIClient(raise_before=RuntimeError('502 upstream'))
        sink = ParseStreamSink()
        with patch('apps.recommendation.services.generate_content_with_fallback',
                   return_value=_blocking_response(FIRST_TURN_TEXT)) as blocking:
            resp = services.generate_content_streaming(
                client, sink=sink, contents=_contents(), config=_config(),
            )
        assert resp.text == FIRST_TURN_TEXT
        blocking.assert_called_once()
        assert sink.error is None

    @override_settings(**OPENAI)
    def test_failure_after_output_reraises_and_sets_sink_error(self):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=10, raise_after_chunks=2)
        sink = ParseStreamSink()
        with patch('apps.recommendation.services.generate_content_with_fallback') as blocking:
            with pytest.raises(RuntimeError):
                services.generate_content_streaming(
                    client, sink=sink, contents=_contents(), config=_config(),
                )
        blocking.assert_not_called()  # never a second request once output was seen
        assert isinstance(sink.error, RuntimeError)

    @override_settings(**OPENAI)
    def test_total_deadline_raises_timeout(self):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=1, delay=0.05)
        sink = ParseStreamSink()
        with patch('apps.recommendation.services.generate_content_with_fallback') as blocking:
            with pytest.raises(TimeoutError):
                services.generate_content_streaming(
                    client, sink=sink, timeout=0.2, contents=_contents(), config=_config(),
                )
        blocking.assert_not_called()
        assert isinstance(sink.error, TimeoutError)


# ---------------------------------------------------------------------------
# parse_query / parse_query_stage1 with a sink
# ---------------------------------------------------------------------------

class TestParseQueryWithSink:
    @pytest.mark.parametrize('stage1', [True, False])
    @override_settings(**OPENAI)
    def test_sink_result_equals_blocking_result(self, parse_env, stage1):
        text = _llm_output(filters=HOUSING, stage1=stage1)
        with patch.dict('django.conf.settings.RECOMMENDATION', {'stage_decouple_enabled': stage1}), \
                patch('apps.recommendation.services._get_client',
                      return_value=_FakeOpenAIClient(text=text)):
            sink = ParseStreamSink()
            streamed = services.parse_query(HISTORY, language='ko', _stream_sink=sink)
        with patch.dict('django.conf.settings.RECOMMENDATION', {'stage_decouple_enabled': stage1}), \
                patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(text)):
            blocking = services.parse_query(HISTORY, language='ko')
        assert streamed == blocking
        assert streamed['filters']['program'] == 'Housing'
        assert sink.filters_emitted

    @override_settings(**OPENAI)
    def test_stream_timing_event_has_ttft_and_filters_ms_blocking_does_not(self, parse_env):
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=FIRST_TURN_TEXT)):
            services.parse_query(HISTORY, _stream_sink=ParseStreamSink())
        t = _timing(parse_env)
        assert t['ttft_ms'] is not None and t['filters_ms'] is not None
        assert t['streamed'] is True and t['stage'] == '1'
        assert t['input_tokens'] == 120 and t['output_tokens'] == 45

        parse_env.events.clear()
        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            services.parse_query(HISTORY)
        t = _timing(parse_env)
        assert t['ttft_ms'] is None
        assert 'filters_ms' not in t and 'streamed' not in t

    @override_settings(**OPENAI)
    def test_early_filters_equal_final_filters_on_follow_up_turn(self, parse_env):
        """Delta turn: `filters` is null-ish, the real data is filter_delta."""
        prior = {'program': 'Housing', 'material': 'brick'}
        text = _llm_output(
            delta_set={'material': 'timber'}, delta_remove=['program'],
            priority=['material'],
        )
        got = []
        sink = ParseStreamSink(on_filters_ready=got.append)
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=text)):
            parsed = services.parse_query(HISTORY, prior_filters=prior, _stream_sink=sink)
        early_filters, early_priority = services.resolve_filters_from_partial(got[0], prior)
        assert early_filters == parsed['filters']
        assert early_priority == parsed['filter_priority']
        assert 'program' not in parsed['filters']
        assert parsed['filters']['material'] == 'timber'

    @override_settings(**OPENAI)
    def test_mid_stream_failure_sets_sink_error_and_returns_fallback(self, parse_env):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=10, raise_after_chunks=3)
        sink = ParseStreamSink()
        with patch('apps.recommendation.services._get_client', return_value=client):
            parsed = services.parse_query(HISTORY, _stream_sink=sink)
        assert isinstance(sink.error, RuntimeError)
        assert parsed['reply'].startswith('이해를 잘 못')  # existing graceful fallback dict


# ---------------------------------------------------------------------------
# The streaming view
# ---------------------------------------------------------------------------

def _user(uid=7):
    return SimpleNamespace(
        id=uid, pk=uid, is_authenticated=True, is_active=True,
        profile=SimpleNamespace(language='ko'),
    )


def _post(view_cls, body, path, uid=7, **extra):
    req = APIRequestFactory().post(path, body, format='json', **extra)
    force_authenticate(req, user=_user(uid))
    return view_cls.as_view()(req)


def _stream_post(body, uid=7, **extra):
    from apps.recommendation.views import ParseQueryStreamView
    return _post(ParseQueryStreamView, body, '/api/v1/parse-query/stream/', uid, **extra)


def _blocking_post(body, uid=8):
    from apps.recommendation.views import ParseQueryView
    return _post(ParseQueryView, body, '/api/v1/parse-query/', uid)


def _frames(resp):
    raw = b''.join(resp.streaming_content).decode('utf-8')
    out = []
    for block in raw.split('\n\n'):
        block = block.strip()
        if not block or block.startswith(':'):
            continue
        lines = dict(ln.split(': ', 1) for ln in block.split('\n'))
        out.append((lines['event'], json.loads(lines['data'])))
    return out


class TestParseQueryStreamView:
    @override_settings(**OPENAI)
    def test_event_order_and_final_equals_blocking_body(self, parse_env):
        body = {'conversation_history': HISTORY}
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=5)):
            resp = _stream_post(body)
        assert resp.status_code == 200
        assert resp['Content-Type'].startswith('text/event-stream')
        assert resp['Cache-Control'] == 'no-cache'
        assert resp['X-Accel-Buffering'] == 'no'
        frames = _frames(resp)
        names = [n for n, _ in frames]

        assert names[-1] == 'final' and names.count('final') == 1
        assert names.count('filters') == 1
        assert names.index('filters') < names.index('final')
        assert 'reply' in names
        # filters (raw model order) arrive before the first reply text
        assert names.index('filters') < names.index('reply')
        assert names.index('reply') < names.index('final')

        reply_text = ''.join(d['text'] for n, d in frames if n == 'reply')
        final = dict(frames)['final']
        assert reply_text == final['reply'] == json.loads(FIRST_TURN_TEXT)['reply']
        early = dict(frames)['filters']
        assert early['structured_filters'] == final['structured_filters']
        assert early['filter_priority'] == final['filter_priority']

        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            blocking = _blocking_post(body)
        assert json.loads(json.dumps(blocking.data)) == final
        assert parse_env.spawn.call_count == 2  # Stage 2 spawned on both terminal turns
        assert parse_env.search.call_count == 2

    @override_settings(**OPENAI)
    def test_probe_turn_final_equals_blocking_body_and_no_stage2(self, parse_env):
        text = _llm_output(
            filters={'program': 'Housing'}, priority=['program'], probe_needed=True,
            probe_question='따뜻한 재료 vs 차가운 기하?', reply='주택 확인했어요.',
        )
        body = {'conversation_history': HISTORY}
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=text)):
            final = dict(_frames(_stream_post(body)))['final']
        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(text)):
            blocking = _blocking_post(body)
        assert final['probe_needed'] is True
        assert json.loads(json.dumps(blocking.data)) == final
        parse_env.spawn.assert_not_called()

    @override_settings(LLM_PROVIDER='gemini')
    def test_gemini_provider_emits_derived_filters_then_final_only(self, parse_env):
        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        assert [n for n, _ in frames] == ['filters', 'final']
        d = dict(frames)
        assert d['filters']['structured_filters'] == d['final']['structured_filters']
        assert d['final']['structured_filters']['program'] == 'Housing'

    @override_settings(**OPENAI)
    def test_failing_early_callback_still_emits_filters_via_post_parse_fallback(self, parse_env):
        """Early callback raises -> exactly one `filters` (fallback) before `final`."""
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=5)), \
                patch('apps.recommendation.services.resolve_filters_from_partial',
                      side_effect=RuntimeError('resolve failed')):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        names = [n for n, _ in frames]
        assert names.count('filters') == 1 and names.count('final') == 1
        assert names.index('filters') < names.index('final')
        d = dict(frames)
        assert d['filters']['structured_filters'] == d['final']['structured_filters']
        assert d['filters']['structured_filters']['program'] == 'Housing'

    @override_settings(**OPENAI)
    def test_follow_up_turn_without_filters_key_gets_single_early_filters(self, parse_env):
        prior = {'program': 'Housing', 'material': 'brick'}
        obj = json.loads(_llm_output(
            delta_set={'material': 'timber'}, delta_remove=[], priority=['material'],
        ))
        del obj['filters']
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=json.dumps(obj), chunk_size=5)):
            body = {'conversation_history': HISTORY, 'prior_filters': prior}
            frames = _frames(_stream_post(body))
        names = [n for n, _ in frames]
        assert names.count('filters') == 1 and names[-1] == 'final'
        assert names.index('filters') < names.index('reply') < names.index('final')
        d = dict(frames)
        assert d['filters']['structured_filters']['material'] == 'timber'
        assert d['filters']['structured_filters'] == d['final']['structured_filters']
        assert d['filters']['filter_priority'] == d['final']['filter_priority']

    @override_settings(**OPENAI)
    def test_stream_failure_before_output_still_delivers_final_via_fallback(self, parse_env):
        client = _FakeOpenAIClient(raise_before=RuntimeError('upstream 500'))
        with patch('apps.recommendation.services._get_client', return_value=client), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        names = [n for n, _ in frames]
        assert names == ['filters', 'final']
        assert dict(frames)['final']['structured_filters']['program'] == 'Housing'

    @override_settings(**OPENAI)
    def test_mid_stream_failure_emits_error_and_no_final(self, parse_env):
        client = _FakeOpenAIClient(text=FIRST_TURN_TEXT, chunk_size=10, raise_after_chunks=4)
        with patch('apps.recommendation.services._get_client', return_value=client):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        names = [n for n, _ in frames]
        assert names[-1] == 'error' and 'final' not in names
        assert 'detail' in dict(frames)['error']
        parse_env.search.assert_not_called()

    @override_settings(**OPENAI)
    def test_unexpected_exception_in_pipeline_becomes_error_event(self, parse_env):
        parse_env.search.side_effect = RuntimeError('db down')
        with patch('apps.recommendation.services._get_client',
                   return_value=_FakeOpenAIClient(text=FIRST_TURN_TEXT)):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        assert frames[-1][0] == 'error'
        assert 'final' not in [n for n, _ in frames]

    def test_validation_errors_are_plain_json_400_before_streaming(self, parse_env):
        resp = _stream_post({'conversation_history': [{'role': 'admin', 'text': 'x'}]})
        assert resp.status_code == 400 and 'role' in resp.data['detail']
        resp = _stream_post({})
        assert resp.status_code == 400
        resp = _stream_post({'priority_axis': 'bogus'})
        assert resp.status_code == 400

    def test_accept_event_stream_is_not_406(self, parse_env):
        resp = _stream_post({'priority_axis': 'program', 'prior_filters': {'program': 'Housing'}},
                            HTTP_ACCEPT='text/event-stream')
        assert resp.status_code == 200

    def test_priority_axis_rerank_emits_single_final_equal_to_blocking(self, parse_env):
        body = {'priority_axis': 'program', 'prior_filters': {'program': 'Housing'},
                'raw_query': '주택'}
        frames = _frames(_stream_post(body))
        assert [n for n, _ in frames] == ['final']
        assert frames[0][1]['chosen_axis'] == 'program'
        assert json.loads(json.dumps(_blocking_post(body).data)) == frames[0][1]

    def test_requires_authentication(self):
        from apps.recommendation.views import ParseQueryStreamView
        req = APIRequestFactory().post(
            '/api/v1/parse-query/stream/', {'query': 'x'}, format='json',
        )
        assert ParseQueryStreamView.as_view()(req).status_code in (401, 403)

    def test_url_is_routed(self):
        from django.urls import resolve
        match = resolve('/api/v1/parse-query/stream/')
        assert match.func.view_class.__name__ == 'ParseQueryStreamView'
        assert resolve('/api/v1/parse-query/').func.view_class.__name__ == 'ParseQueryView'

    def test_shares_throttle_class_with_blocking_endpoint(self):
        from apps.recommendation.views import ParseQueryStreamView, ParseQueryView
        assert ParseQueryStreamView.throttle_classes == ParseQueryView.throttle_classes
        assert ParseQueryStreamView.permission_classes == ParseQueryView.permission_classes


# ---------------------------------------------------------------------------
# PERF-SEARCH-2: early (speculative) results
# ---------------------------------------------------------------------------

EARLY = [{'canonical_bld_id': 'bld_early_1'}, {'canonical_bld_id': 'bld_early_2'}]
LATE = [{'canonical_bld_id': 'bld_late_1'}]


def _stream_frames(text, body=None, chunk_size=5):
    body = body or {'conversation_history': HISTORY}
    with patch('apps.recommendation.services._get_client',
               return_value=_FakeOpenAIClient(text=text, chunk_size=chunk_size)):
        return _frames(_stream_post(body))


class TestEarlyResults:
    @override_settings(**OPENAI)
    def test_results_emitted_right_after_filters_before_reply_and_final(self, parse_env):
        parse_env.search.return_value = list(EARLY)
        frames = _stream_frames(FIRST_TURN_TEXT)
        names = [n for n, _ in frames]
        assert names.count('results') == 1
        assert names.index('filters') + 1 == names.index('results')
        assert names.index('results') < names.index('reply') < names.index('final')
        early = dict(frames)['results']
        assert early == {'results': EARLY, 'is_fallback': False, 'fallback_note': ''}

    @override_settings(**OPENAI)
    def test_equal_inputs_reuse_speculative_results_without_second_search(self, parse_env):
        parse_env.search.return_value = list(EARLY)
        frames = _stream_frames(FIRST_TURN_TEXT)
        assert parse_env.search.call_count == 1  # speculative only; final reused it
        final = dict(frames)['final']
        assert final['results'] == dict(frames)['results']['results'] == EARLY
        # the speculative search used exactly the args the final path would
        args, kwargs = parse_env.search.call_args
        assert args[0] == final['structured_filters']
        assert kwargs['filter_priority'] == final['filter_priority']
        assert kwargs['raw_query'] == HISTORY[0]['text']
        assert kwargs['limit'] == 20 and kwargs['image_focus'] is None

    @override_settings(**OPENAI)
    def test_final_payload_identical_to_blocking_when_results_reused(self, parse_env):
        body = {'conversation_history': HISTORY}
        final = dict(_stream_frames(FIRST_TURN_TEXT, body))['final']
        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            blocking = _blocking_post(body)
        assert json.loads(json.dumps(blocking.data)) == final

    @override_settings(**OPENAI)
    def test_image_focus_in_schema_order_keeps_early_and_final_search_equal(self, parse_env):
        parse_env.search.return_value = list(EARLY)
        text = _llm_output(filters=HOUSING, image_focus='interior')
        frames = _stream_frames(text)
        assert parse_env.search.call_count == 1
        _, kwargs = parse_env.search.call_args
        assert kwargs['image_focus'] == 'interior'
        final = dict(frames)['final']
        assert final['image_focus'] == 'interior' and final['results'] == EARLY

    @override_settings(**OPENAI)
    def test_different_final_inputs_rerun_search_and_final_is_authoritative(self, parse_env):
        # image_focus emitted AFTER reply: unknown at the early event (None), final has
        # 'interior' -> the early result is stale -> search runs again.
        parse_env.search.side_effect = [list(EARLY), list(LATE)]
        text = _llm_output(filters=HOUSING, image_focus='interior', image_focus_last=True)
        frames = _stream_frames(text)
        assert parse_env.search.call_count == 2
        assert dict(frames)['results']['results'] == EARLY
        final = dict(frames)['final']
        assert final['results'] == LATE
        assert parse_env.search.call_args_list[0][1]['image_focus'] is None
        assert parse_env.search.call_args_list[1][1]['image_focus'] == 'interior'

    @override_settings(**OPENAI)
    def test_probe_turn_emits_early_results_and_final_still_carries_results(self, parse_env):
        parse_env.search.return_value = list(EARLY)
        text = _llm_output(
            filters={'program': 'Housing'}, priority=['program'], probe_needed=True,
            probe_question='따뜻한 재료 vs 차가운 기하?', reply='주택 확인했어요.',
        )
        frames = _stream_frames(text)
        names = [n for n, _ in frames]
        assert names.count('results') == 1 and names[-1] == 'final'
        final = dict(frames)['final']
        # final carries results on probe turns too (see _parse_body) -> early cards are
        # never withdrawn: the probe overlay is added on top of the same cards.
        assert final['probe_needed'] is True and final['results'] == EARLY
        assert parse_env.search.call_count == 1
        parse_env.spawn.assert_not_called()

    @override_settings(**OPENAI)
    def test_follow_up_turn_uses_merged_filters_for_early_search(self, parse_env):
        prior = {'program': 'Housing', 'material': 'brick'}
        text = _llm_output(delta_set={'material': 'timber'}, priority=['material'])
        obj = json.loads(text)
        del obj['filters']
        frames = _stream_frames(
            json.dumps(obj), {'conversation_history': HISTORY, 'prior_filters': prior},
        )
        assert parse_env.search.call_count == 1
        args, _ = parse_env.search.call_args
        assert args[0]['material'] == 'timber' and args[0]['program'] == 'Housing'
        assert args[0] == dict(frames)['final']['structured_filters']

    @override_settings(**OPENAI)
    def test_empty_search_fallback_is_emitted_early_and_reused_not_rerolled(self, parse_env):
        parse_env.search.return_value = []
        with patch('apps.recommendation.views.search.engine.get_diverse_random',
                   return_value=list(EARLY)) as rnd:
            frames = _stream_frames(FIRST_TURN_TEXT)
        assert rnd.call_count == 1  # reused at final, random cards not re-rolled
        early = dict(frames)['results']
        assert early['is_fallback'] is True and early['results'] == EARLY
        final = dict(frames)['final']
        assert final['is_fallback'] is True and final['results'] == EARLY
        assert final['fallback_note'] == early['fallback_note'] != ''

    @override_settings(**OPENAI)
    def test_speculative_failure_is_isolated_single_filters_and_final_recomputes(self, parse_env):
        parse_env.search.side_effect = [RuntimeError('db blip'), list(LATE)]
        frames = _stream_frames(FIRST_TURN_TEXT)
        names = [n for n, _ in frames]
        assert names.count('filters') == 1 and 'results' not in names
        assert names[-1] == 'final'
        assert dict(frames)['final']['results'] == LATE

    @override_settings(LLM_PROVIDER='gemini')
    def test_gemini_path_has_no_early_results(self, parse_env):
        with patch('apps.recommendation.services._get_client', return_value=MagicMock()), \
                patch('apps.recommendation.services.generate_content_with_fallback',
                      return_value=_blocking_response(FIRST_TURN_TEXT)):
            frames = _frames(_stream_post({'conversation_history': HISTORY}))
        assert [n for n, _ in frames] == ['filters', 'final']
        assert parse_env.search.call_count == 1

    def test_final_search_inputs_helper_equality(self):
        from apps.recommendation.views.search import _search_inputs
        a = _search_inputs({'program': 'Housing'}, ['program'], 'q', None)
        assert a == _search_inputs({'program': 'Housing'}, ('program',), 'q', None)
        assert a != _search_inputs({'program': 'Housing'}, ['program'], 'q', 'interior')
        assert a != _search_inputs({'program': 'Office'}, ['program'], 'q', None)
        assert a != _search_inputs({'program': 'Housing'}, ['program'], 'q2', None)
        assert a != _search_inputs({'program': 'Housing'}, [], 'q', None)


# ---------------------------------------------------------------------------
# PERF-SEARCH-2 Part B: fields no longer requested from the model are derived
# ---------------------------------------------------------------------------

_TRIMMED = ('raw_query', 'suggested_quick_replies', 'priority_ordered', 'llm_response_message')


def _trimmed_output(**kw):
    obj = json.loads(_llm_output(**kw))
    for k in _TRIMMED:
        obj.pop(k, None)
    return json.dumps(obj)


class TestServerDerivedFields:
    @override_settings(**OPENAI)
    def test_terminal_single_axis_fields_derived_server_side(self, parse_env):
        text = _trimmed_output(filters={'program': 'Housing'}, priority=['program'])
        final = dict(_stream_frames(text))['final']
        assert final['raw_query'] == HISTORY[0]['text']          # request text, not the model
        assert final['priority_ordered'] == final['filter_priority'] == ['program']
        assert final['llm_response_message'] == final['reply']   # existing reply fallback
        assert final['suggested_quick_replies'] == []

    @override_settings(**OPENAI)
    def test_probe_message_falls_back_to_probe_question(self, parse_env):
        text = _trimmed_output(
            filters={'program': 'Housing'}, priority=['program'], probe_needed=True,
            probe_question='따뜻한 재료 vs 차가운 기하?', reply='주택 확인했어요.',
        )
        final = dict(_stream_frames(text))['final']
        assert final['probe_needed'] is True
        assert final['llm_response_message'] == '따뜻한 재료 vs 차가운 기하?'
        assert final['suggested_quick_replies'] == []

    @override_settings(**OPENAI)
    def test_multi_axis_chips_are_server_built_not_model_built(self, parse_env):
        final = dict(_stream_frames(_trimmed_output(filters=HOUSING)))['final']
        chips = final['suggested_quick_replies']
        assert {c['axis'] for c in chips} == {'program', 'material', 'style'}
        assert all(set(c) == {'label', 'axis', 'value'} for c in chips)
        assert final['system_action'] == 'REQUEST_PRIORITY'
        assert final['llm_response_message'] == '추천에 더 중요하게 생각할 기준이 있나요?'

    @override_settings(**OPENAI)
    def test_model_supplied_values_still_honoured_when_present(self, parse_env):
        """Gemini / legacy output may still carry the fields: not discarded."""
        obj = json.loads(_llm_output(filters={'program': 'Housing'}, priority=['program']))
        obj['priority_ordered'] = ['program', 'space_experience']
        obj['llm_response_message'] = '직접 쓴 메시지'
        final = dict(_stream_frames(json.dumps(obj)))['final']
        assert final['priority_ordered'] == ['program', 'space_experience']
        assert final['llm_response_message'] == '직접 쓴 메시지'

    def test_prompt_no_longer_asks_for_trimmed_fields(self):
        prompt = services._CHAT_PHASE_SYSTEM_PROMPT + services._CALIBRATION_PROMPT_EXTENSION
        block = prompt[prompt.index('## Your output schema'):prompt.index('## Allowed `program`')]
        for k in _TRIMMED:
            assert '"%s"' % k not in block
        for k in ('suggested_quick_replies', 'priority_ordered', 'llm_response_message'):
            assert '**%s**' % k not in services._CALIBRATION_PROMPT_EXTENSION
        for ln in prompt.split(chr(10)):
            if ln.startswith('ASSISTANT: {'):
                assert 'raw_query' not in json.loads(ln[len('ASSISTANT: '):])
        for name in ('_STAGE1_RESPONSE_SCHEMA',):
            assert not set(_TRIMMED) & set(getattr(services, name)['properties'])


# ---------------------------------------------------------------------------
# Schema / prompt ordering (filters BEFORE reply; `required` unchanged)
# ---------------------------------------------------------------------------

class TestSchemaAndPromptOrder:
    def test_strict_schema_order_and_required_unchanged(self):
        from apps.recommendation.services._prompts import _OPENAI_STRICT_PARSE_SCHEMA as s
        props = list(s['properties'])
        assert props[:4] == ['filters', 'filter_delta', 'image_focus', 'filter_priority']
        assert props.index('reply') > props.index('filter_priority')
        assert props.index('probe_question') > props.index('filter_priority')
        assert set(props) == set(s['required'])
        # PERF-SEARCH-2: raw_query / suggested_quick_replies / priority_ordered /
        # llm_response_message are server-derived, not requested from the model.
        assert s['required'] == [
            'probe_needed', 'probe_question', 'reply', 'filters', 'filter_delta',
            'filter_priority', 'image_focus', 'visual_description',
            'confidence_score', 'system_action',
        ]
        for dropped in ('raw_query', 'suggested_quick_replies', 'priority_ordered',
                        'llm_response_message'):
            assert dropped not in s['properties']

    def test_stage1_strict_schema_is_legacy_minus_visual_description(self):
        from apps.recommendation.services._prompts import (
            _OPENAI_STRICT_PARSE_SCHEMA as legacy, _OPENAI_STRICT_STAGE1_SCHEMA as s1,
        )
        assert 'visual_description' not in s1['properties']
        assert 'visual_description' not in s1['required']
        assert set(s1['required']) == set(legacy['required']) - {'visual_description'}
        assert set(s1['required']) == set(s1['properties'])
        assert list(s1['properties']) == [k for k in legacy['properties'] if k != 'visual_description']
        assert s1['additionalProperties'] is False

    def test_stage1_gemini_schema_order_and_required_unchanged(self):
        s = services._STAGE1_RESPONSE_SCHEMA
        props = list(s['properties'])
        assert props[:4] == ['filters', 'filter_delta', 'image_focus', 'filter_priority']
        assert props.index('reply') > props.index('filter_priority')
        assert s['required'] == ['probe_needed', 'reply']

    def test_prompt_schema_block_and_examples_emit_filters_before_reply(self):
        prompt = services._CHAT_PHASE_SYSTEM_PROMPT
        block = prompt[prompt.index('## Your output schema'):]
        assert block.index('"filters"') < block.index('"reply"')
        assert block.index('"filter_priority"') < block.index('"reply"')
        assert block.index('"filter_priority"') < block.index('"probe_question"')
        examples = [ln for ln in prompt.split('\n') if ln.startswith('ASSISTANT: {')]
        assert len(examples) >= 15
        for ln in examples:
            data = json.loads(ln[len('ASSISTANT: '):])
            keys = list(data)
            assert keys[0] in ('filters', 'filter_delta'), keys
            if 'filters' in data:
                assert keys.index('filters') < keys.index('reply')
            assert keys.index('filter_priority') < keys.index('reply')
            if 'filter_delta' in data and 'filters' in data:
                assert keys.index('filters') < keys.index('filter_delta') < keys.index('filter_priority')
