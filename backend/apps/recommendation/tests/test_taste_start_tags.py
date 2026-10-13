"""
Tests for apps.recommendation.taste_start (tag recognition layer).

No network and no buildings DB: JEV (`call_jev`) is mocked, `requests.post` is
mocked for the client tests.
"""
from unittest import mock

import pytest
import requests
from django.test import override_settings

from apps.recommendation.taste_start import (
    JevUnavailable, Tag, parse_years, recognize_tags,
)
from apps.recommendation.taste_start import jev_client, recognizer, vocab
from apps.recommendation.taste_start.normalization import (
    MATERIAL_GROUP_MAP, raw_country_values, raw_material_values,
)
from apps.recommendation.taste_start.questions import build_questions

CALL = 'apps.recommendation.taste_start.recognizer.call_jev'


def fake_jev(**picks):
    """Return a call_jev replacement answering `picks` (qid -> choice), defaults elsewhere."""
    def _call(state, questions):
        answers = {}
        for qid, q in questions.items():
            if qid in picks:
                choice = picks[qid]
            elif qid.startswith(('mat_', 'el_')) or qid == 'built':
                choice = 'not_mentioned'
            else:
                choice = 'none'
            answers[qid] = {'type': 'choice', 'choice': choice, 'confidence': 0.9,
                            'probabilities': {choice: 0.9}}
        return answers
    return _call


def run(text, **picks):
    with mock.patch(CALL, side_effect=fake_jev(**picks)):
        return recognize_tags(text)


def by_axis(result):
    return {(t.axis, t.value if not isinstance(t.value, tuple) else t.value): t for t in result.tags}


# -- year rule ----------------------------------------------------------------
@pytest.mark.parametrize('text,want', [
    ('2010년대 일본 주택', (2010, 2019)),
    ('90년대 오피스', (1990, 1999)),
    ('2000년 이후 도서관', (2000, None)),
    ('1950년 이전 건물', (None, 1950)),
    ('since 2005 houses', None),   # 'since' only counts AFTER the number
    ('도서관', None),
    ('최근에 지어진 미술관', None),
    ('콘서트홀', None),
])
def test_parse_years(text, want):
    assert parse_years(text) == want


def test_parse_years_two_digit_2000s():
    assert parse_years('10년대') == (2010, 2019)


# -- vocab sanity -------------------------------------------------------------
def test_vocab_sizes():
    assert len(vocab.PROGRAM) == 13 and 'Other' not in vocab.PROGRAM
    assert len(vocab.TYPOLOGY) == 35
    assert len(vocab.COUNTRY) <= 254
    assert len(vocab.MATERIAL) == 11 and len(vocab.ELEMENT) == 13


def test_choice_questions_stay_under_limit_and_have_strict():
    q = build_questions()
    for qid in ('program', 'typology', 'country'):
        assert len(q[qid]['criteria']) <= 255
        assert 'Judge ONLY the newest message' in q[qid]['instructions']


# -- use merge ----------------------------------------------------------------
def test_typology_wins_over_program():
    res = run('도서관', program='Public', typology='Library')
    use = [t for t in res.tags if t.axis == 'use']
    assert len(use) == 1
    assert use[0].value == 'Library'
    assert use[0].match == {'typology_primary': ['Library']}
    assert res.source == 'jev'


def test_program_only_when_no_typology():
    res = run('공공 건축', program='Public')
    (use,) = [t for t in res.tags if t.axis == 'use']
    assert use.match == {'program': ['Public']}


def test_no_tags_for_vague_message():
    assert run('그냥 멋진 거 보여줘').tags == []


# -- Warm / Industrial merge ---------------------------------------------------
def test_warm_atmosphere_and_color_merge_into_one_tag():
    res = run('따뜻한 색감의 따뜻한 공간', atmosphere='Warm', color_tone='Warm')
    warm = [t for t in res.tags if t.value == 'Warm']
    assert len(warm) == 1
    assert warm[0].axis == 'atmosphere'
    assert warm[0].match == {'atmosphere': ['Warm'], 'color_tone': ['Warm']}


def test_warm_color_alone_becomes_atmosphere_tag():
    res = run('따뜻한 색감', color_tone='Warm')
    (t,) = res.tags
    assert (t.axis, t.value) == ('atmosphere', 'Warm')


def test_industrial_style_and_atmosphere_merge():
    res = run('인더스트리얼', style='Industrial', atmosphere='Industrial')
    (t,) = res.tags
    assert t.axis == 'style'
    assert t.match == {'style': ['Industrial'], 'atmosphere': ['Industrial']}


# -- year / era ----------------------------------------------------------------
def test_numeric_year_wins_over_era_answer():
    res = run('2010년대 최근 건물', era='recent')
    (t,) = res.tags
    assert t.axis == 'year' and t.value == (2010, 2019)


@pytest.mark.parametrize('era,want', [
    ('21st_century', (2000, None)),
    ('modern_20th', (1900, 1999)),
    ('historic', (None, 1899)),
])
def test_era_words_map_to_ranges(era, want):
    (t,) = run('시대', era=era).tags
    assert t.axis == 'year' and t.value == want


def test_recent_era_is_current_year_minus_five():
    with mock.patch.object(recognizer, 'current_year', return_value=2026):
        (t,) = run('최근', era='recent').tags
    assert t.value == (2021, None)


# -- built ---------------------------------------------------------------------
def test_built_tags():
    (t,) = run('지어진 걸로', built='built_only').tags
    assert (t.axis, t.value) == ('built', 'built_only')
    (t,) = run('계획안만', built='unbuilt_only').tags
    assert t.value == 'unbuilt_only'
    assert run('계획안도 괜찮아', built='unbuilt_ok').tags == []
    assert run('아무말').tags == []


# -- materials / elements ------------------------------------------------------
def test_material_and_element_polarity():
    res = run('벽돌은 아니고 나무, 중정', mat_brick='excluded', mat_wood='wanted',
              el_courtyard='wanted', el_stair='excluded')
    tags = by_axis(res)
    assert tags[('material', 'brick')].polarity == 'exclude'
    assert tags[('material', 'wood')].polarity == 'want'
    assert 'timber' in tags[('material', 'wood')].match['material_visual']
    court = tags[('element', 'Courtyard')]
    assert court.match == {'architectural_elements': ['Courtyard'],
                           'visual_description_contains': ['courtyard']}
    assert tags[('element', 'Stair')].polarity == 'exclude'


def test_country_match_uses_raw_spellings():
    (t,) = run('튀르키예', country='Turkey').tags
    assert 'Türkiye' in t.match['location_country']
    assert t.prob == 0.9


# -- single message ------------------------------------------------------------
def test_single_value_axis_keeps_one_want():
    res = run('스페인과 일본', country='Spain')
    countries = [t for t in res.tags if t.axis == 'country']
    assert [t.value for t in countries] == ['Spain']


def test_no_prev_questions_generated():
    assert not [qid for qid in build_questions() if qid.startswith('prev_')]


# -- dictionary fallback --------------------------------------------------------
def dict_run(text):
    with mock.patch(CALL, side_effect=JevUnavailable('down')):
        return recognize_tags(text)


def test_dictionary_source_and_basic_tags():
    res = dict_run('일본의 미술관')
    assert res.source == 'dictionary'
    tags = by_axis(res)
    assert ('country', 'Japan') in tags
    assert ('use', 'Museum') in tags


def test_dictionary_brick_does_not_also_match_stone():
    res = dict_run('벽돌로 지은 주택')
    mats = [t.value for t in res.tags if t.axis == 'material']
    assert mats == ['brick']


def test_dictionary_drop_negation_yields_no_tag():
    res = dict_run('일본일 필요는 없는 것 같아')
    assert res.tags == []


def test_dictionary_exclude_negation():
    res = dict_run('벽돌은 아니고')
    (t,) = res.tags
    assert (t.axis, t.value, t.polarity) == ('material', 'brick', 'exclude')


def test_dictionary_english_negation():
    (t,) = dict_run('not brick please').tags
    assert (t.value, t.polarity) == ('brick', 'exclude')


def test_dictionary_year_and_use_merge():
    res = dict_run('2010년대 도서관')
    tags = by_axis(res)
    assert tags[('year', (2010, 2019))]
    (use,) = [t for t in res.tags if t.axis == 'use']
    assert use.value == 'Library'


# -- Tag serialisation ----------------------------------------------------------
def test_tag_round_trip():
    tags = [
        recognizer.make_tag('country', 'Turkey', prob=0.8),
        recognizer.make_tag('year', (2010, 2019)),
        recognizer.make_tag('year', (None, 1899)),
        recognizer.make_tag('material', 'wood', 'exclude'),
        recognizer.make_tag('element', 'Courtyard'),
        recognizer.make_tag('use', 'Library', kind='typology'),
    ]
    import json
    for t in tags:
        again = Tag.from_dict(json.loads(json.dumps(t.to_dict())))
        assert again == t


# -- normalization --------------------------------------------------------------
def test_country_aliases():
    assert 'Türkiye' in raw_country_values('Turkey')
    assert raw_country_values('Turkey')[0] == 'Turkey'
    assert raw_country_values('Chile') == ['Chile']
    assert 'Tabriz' in raw_country_values('Iran')


def test_material_groups():
    assert 'timber' in raw_material_values('wood')
    assert 'textile' not in raw_material_values('tile')
    assert 'textile' in raw_material_values('fabric')
    assert MATERIAL_GROUP_MAP['polycarbonate'] == 'plastic'
    assert 'water' not in MATERIAL_GROUP_MAP and 'vegetation' not in MATERIAL_GROUP_MAP


# -- jev_client -----------------------------------------------------------------
@override_settings(TYPESAFE_API_KEY='')
def test_client_missing_key():
    with pytest.raises(JevUnavailable):
        jev_client.call_jev('s', {})


@override_settings(TYPESAFE_API_KEY='k', JEV_API_URL='http://x', JEV_TIMEOUT_SECONDS=1.0)
def test_client_failure_modes():
    with mock.patch.object(jev_client.requests, 'post', side_effect=requests.Timeout()):
        with pytest.raises(JevUnavailable):
            jev_client.call_jev('s', {})
    with mock.patch.object(jev_client.requests, 'post', side_effect=requests.ConnectionError()):
        with pytest.raises(JevUnavailable):
            jev_client.call_jev('s', {})
    resp = mock.Mock(status_code=500)
    with mock.patch.object(jev_client.requests, 'post', return_value=resp):
        with pytest.raises(JevUnavailable):
            jev_client.call_jev('s', {})
    resp = mock.Mock(status_code=200)
    resp.json.side_effect = ValueError('bad')
    with mock.patch.object(jev_client.requests, 'post', return_value=resp):
        with pytest.raises(JevUnavailable):
            jev_client.call_jev('s', {})


@override_settings(TYPESAFE_API_KEY='k', JEV_API_URL='http://x', JEV_TIMEOUT_SECONDS=1.5,
                   JEV_MODEL='jev-latest')
def test_client_success_sends_bearer_and_timeout():
    resp = mock.Mock(status_code=200)
    resp.json.return_value = {'answers': {'a': {'choice': 'none'}}}
    with mock.patch.object(jev_client.requests, 'post', return_value=resp) as post:
        out = jev_client.call_jev('state', {'a': {}})
    assert out == {'a': {'choice': 'none'}}
    kwargs = post.call_args.kwargs
    assert kwargs['headers']['Authorization'] == 'Bearer k'
    assert kwargs['timeout'] == 1.5
    assert kwargs['json']['model'] == 'jev-latest'


@override_settings(TYPESAFE_API_KEY='')
def test_recognize_without_key_falls_back_to_dictionary():
    res = recognize_tags('벽돌 주택')
    assert res.source == 'dictionary'


# -- prompt-text guards ---------------------------------------------------------
def test_era_instruction_separates_style_words():
    q = build_questions()['era']
    assert 'STYLE' in q['instructions'] and '모던' in q['instructions']
    assert 'answer none' in q['instructions']
    assert 'NOT the style words' in q['criteria']['modern_20th']


def test_element_and_material_questions_are_strict():
    q = build_questions()
    for qid in ('el_courtyard', 'el_garden', 'el_atrium', 'mat_wood'):
        ins = q[qid]['instructions']
        assert 'THIS exact item' in ins
    assert '중정 = Courtyard only' in q['el_garden']['instructions']


def test_typology_instruction_rejects_generic_words():
    q = build_questions()['typology']
    assert '주거' in q['instructions'] and 'answered none' in q['instructions']
    assert 'NOT generic' in q['criteria']['House']
    assert 'NOT plain' in q['criteria']['Housing']


def test_question_ids_unchanged():
    ids = set(build_questions())
    assert {'program', 'typology', 'style', 'atmosphere', 'color_tone', 'country', 'era',
            'built', 'mat_wood', 'el_courtyard'} <= ids


# -- dictionary: bare adjective stems -------------------------------------------
@pytest.mark.parametrize('text,axis,value', [
    ('따뜻한 나무 도서관', 'atmosphere', 'Warm'),
    ('따뜻 한 느낌', 'atmosphere', 'Warm'),
    ('차분한 미술관', 'atmosphere', 'Serene'),
    ('고요한 공간', 'atmosphere', 'Serene'),
    ('모던한 미술관', 'style', 'Modernist'),
])
def test_dictionary_bare_adjectives(text, axis, value):
    assert (axis, value) in by_axis(dict_run(text))


def test_dictionary_modern_is_not_era():
    assert not [t for t in dict_run('모던한 미술관').tags if t.axis == 'year']


def test_dictionary_plain_housing_is_program():
    (use,) = [t for t in dict_run('벽돌로 지은 주거').tags if t.axis == 'use']
    assert use.match == {'program': ['Housing']}
