"""
BACK-LLM-1: required-slate contract for chat-phase query parsing.

The LLM may still produce weak payloads for diffuse prompts. These tests pin the
contract in two places:
- prompt text must instruct Gemini to collect the slate deterministically;
- Python post-processing must not let a successful parse finish with only
  non-slate filters such as year_min.
"""
import json
from unittest.mock import MagicMock, patch


def _response(payload):
    resp = MagicMock()
    resp.text = json.dumps(payload)
    usage = MagicMock()
    usage.prompt_token_count = 120
    usage.candidates_token_count = 80
    usage.thoughts_token_count = 0
    usage.cached_content_token_count = None
    resp.usage_metadata = usage
    return resp


def _run_with_payload(func, history, payload):
    with patch('apps.recommendation.services._get_client') as mock_client, \
         patch('apps.recommendation.services.event_log.emit_event'):
        mock_client.return_value.models.generate_content.return_value = _response(payload)
        return func(history)


def test_chat_prompt_defines_required_slate_and_probe_priority():
    from apps.recommendation.services.parse_query import _CHAT_PHASE_SYSTEM_PROMPT

    assert 'Required information slate' in _CHAT_PHASE_SYSTEM_PROMPT
    assert 'program > material > style > location_country' in _CHAT_PHASE_SYSTEM_PROMPT
    assert 'Do not choose a free abstract axis' in _CHAT_PHASE_SYSTEM_PROMPT
    assert 'style: "Contemporary"' in _CHAT_PHASE_SYSTEM_PROMPT


def test_parse_query_promotes_present_required_slate_into_priority():
    from apps.recommendation.services import parse_query

    payload = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '이해했어요.',
        'filters': {
            'location_country': None,
            'program': 'Museum',
            'material': None,
            'style': None,
            'year_min': 2000,
            'year_max': None,
        },
        'filter_priority': ['year_min'],
        'raw_query': '현대 미술관 추천',
        'visual_description': 'A contemporary museum.',
    }

    result = _run_with_payload(
        parse_query,
        [{'role': 'user', 'text': '현대 미술관 추천'}],
        payload,
    )

    assert result['filters']['program'] == 'Museum'
    assert result['filter_priority'][0] == 'program'
    assert 'year_min' in result['filter_priority']


def test_parse_query_adds_broad_slate_default_when_success_has_no_slate():
    from apps.recommendation.services import parse_query

    payload = {
        'probe_needed': False,
        'probe_question': None,
        'reply': '알겠습니다: 폭넓게 보여드릴게요.',
        'filters': {
            'location_country': None,
            'program': None,
            'material': None,
            'style': None,
            'year_min': 2000,
            'year_max': None,
        },
        'filter_priority': ['year_min'],
        'raw_query': '그냥 멋진 거 보여줘',
        'visual_description': 'A broad set of high-quality architecture.',
    }

    result = _run_with_payload(
        parse_query,
        [{'role': 'user', 'text': '그냥 멋진 거 보여줘'}],
        payload,
    )

    assert result['filters']['style'] == 'Contemporary'
    assert result['filter_priority'][0] == 'style'
    assert 'year_min' in result['filter_priority']


def test_parse_query_stage1_adds_broad_slate_default_on_probe_payload():
    from apps.recommendation.services import parse_query_stage1

    payload = {
        'probe_needed': True,
        'probe_question': '어떤 용도의 레퍼런스를 먼저 볼까요?',
        'reply': '방향을 좁혀볼게요.',
        'filters': {
            'location_country': None,
            'program': None,
            'material': None,
            'style': None,
            'year_min': None,
            'year_max': None,
        },
        'filter_priority': [],
        'raw_query': '추천해줘',
    }

    result = _run_with_payload(
        parse_query_stage1,
        [{'role': 'user', 'text': '추천해줘'}],
        payload,
    )

    assert result['probe_needed'] is True
    assert result['filters']['style'] == 'Contemporary'
    assert result['filter_priority'] == ['style']


def test_parse_query_stage1_repairs_forced_terminal_after_probe_budget():
    from apps.recommendation.services import parse_query_stage1

    history = [
        {'role': 'user', 'text': '좋은 레퍼런스 보여줘'},
        {'role': 'model', 'text': '어떤 용도인가요?'},
        {'role': 'user', 'text': '아무거나'},
        {'role': 'model', 'text': '재료는요?'},
        {'role': 'user', 'text': '상관없어'},
    ]
    payload = {
        'probe_needed': True,
        'probe_question': '세 번째 질문입니다.',
        'reply': '메모했어요.',
        'filters': {
            'location_country': None,
            'program': None,
            'material': None,
            'style': None,
            'year_min': None,
            'year_max': None,
        },
        'filter_priority': [],
        'raw_query': '좋은 레퍼런스 보여줘',
    }

    result = _run_with_payload(parse_query_stage1, history, payload)

    assert result['probe_needed'] is False
    assert result['probe_question'] is None
    assert result['filters']['style'] == 'Contemporary'
    assert result['filter_priority'] == ['style']
