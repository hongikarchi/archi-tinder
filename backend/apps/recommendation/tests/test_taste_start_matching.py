"""Taste-start step 2: SQL builder, top_matches ordering/hit-total, and views.

No network and no real buildings DB: the cursor and recognize_tags are mocked.
"""
from unittest import mock

import pytest
from django.conf import settings

from apps.recommendation.taste_start import matching
from apps.recommendation.taste_start.recognizer import make_tag

YEAR = 2026


@pytest.fixture(autouse=True)
def _fixed_year():
    with mock.patch.object(matching, 'current_year', return_value=YEAR):
        yield


def _exprs(*tags):
    score, params, bools = matching.score_sql(list(tags))
    return score, params, bools


# -- SQL builder --------------------------------------------------------------
def test_values_are_parameterised_never_in_sql():
    tag = make_tag('country', 'Japan')
    score, params, bools = _exprs(tag)
    sql = ' '.join(bools) + score
    assert 'Japan' not in sql
    assert params == [tag.match['location_country']]
    assert bools[0].count('%s') == 1


def test_use_program_and_typology_exact_any():
    _, p, b = _exprs(make_tag('use', 'Housing', kind='program'))
    assert 'program = ANY(%s)' in b[0] and 'ILIKE' not in b[0].upper()
    assert p == [['Housing']]


def test_warm_atmosphere_lists_two_columns():
    _, params, bools = _exprs(make_tag('atmosphere', 'Warm'))
    assert 'atmosphere = ANY(%s)' in bools[0]
    assert 'color_tone = ANY(%s)' in bools[0]
    assert ' OR ' in bools[0]
    assert params == [['Warm'], ['Warm']]


def test_industrial_style_two_columns():
    _, params, bools = _exprs(make_tag('style', 'Industrial'))
    assert 'style = ANY(%s)' in bools[0] and 'atmosphere = ANY(%s)' in bools[0]
    assert params == [['Industrial'], ['Industrial']]


def test_material_uses_overlap_lowercased():
    tag = make_tag('material', 'wood')
    _, params, bools = _exprs(tag)
    assert '&& %s::text[]' in bools[0]
    assert 'lower(x)' in bools[0]
    assert params[0] == [v.lower() for v in tag.match['material_visual']]
    assert 'wood' in params[0]


def test_element_tag_or_word_boundary_regex():
    _, params, bools = _exprs(make_tag('element', 'Courtyard'))
    assert '%s = ANY(architectural_elements)' in bools[0]
    assert 'visual_description ~* %s' in bools[0]
    assert params == ['Courtyard', r'\mcourtyard\M']


def test_element_regex_escapes_keyword():
    tag = make_tag('element', 'Courtyard')
    tag.match['visual_description_contains'] = ['a.b (c)']
    _, params, _ = _exprs(tag)
    assert params[1] == r'\ma\.b\ \(c\)\M'


@pytest.mark.parametrize('rng,frag,params', [
    ((2010, 2019), ['project_year >= %s', 'project_year <= %s'], [2010, 2019]),
    ((2000, None), ['project_year >= %s'], [2000]),
    ((None, 1950), ['project_year <= %s'], [1950]),
])
def test_year_ranges_incl_open_ends(rng, frag, params):
    _, p, b = _exprs(make_tag('year', rng))
    assert 'project_year IS NOT NULL' in b[0]
    for f in frag:
        assert f in b[0]
    assert p == params
    if rng[0] is None:
        assert '>=' not in b[0]
    if rng[1] is None:
        assert '<=' not in b[0]


def test_built_only_and_unbuilt_only():
    _, p, b = _exprs(make_tag('built', 'built_only'))
    assert 'project_year <= %s' in b[0] and 'IS NOT NULL' in b[0] and p == [YEAR]
    _, p, b = _exprs(make_tag('built', 'unbuilt_only'))
    assert 'project_year > %s' in b[0] and 'IS NOT NULL' in b[0] and p == [YEAR]


def test_unbuilt_ok_is_not_scored():
    assert matching.scored_tags([make_tag('built', 'unbuilt_ok')]) == []


def test_exclude_penalty_sign_and_weight():
    score, _, _ = _exprs(make_tag('country', 'Japan'),
                         make_tag('material', 'brick', polarity='exclude'))
    w = settings.RECOMMENDATION['taste_tag_weights']
    assert f'CASE WHEN t0 THEN {float(w["country"])!r}' in score
    assert f'CASE WHEN t1 THEN {-float(w["material"])!r}' in score


def test_exclude_penalty_factor_applies(settings):
    settings.RECOMMENDATION = dict(settings.RECOMMENDATION, taste_exclude_penalty_factor=2.0)
    score, _, _ = _exprs(make_tag('material', 'brick', polarity='exclude'))
    assert f'{-4.0!r}' in score


# -- top_matches --------------------------------------------------------------
class _Cur:
    def __init__(self, rows):
        self.rows, self.sql, self.params = rows, None, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchall(self):
        return self.rows


def _run_with(rows, fn, *args, **kw):
    cur = _Cur(rows)
    conn = mock.MagicMock()
    conn.cursor.return_value = cur
    with mock.patch.object(matching, 'connections', {'buildings': conn}):
        return fn(*args, **kw), cur


def test_top_matches_hit_total_and_keys():
    tags = [make_tag('use', 'Housing', kind='program'), make_tag('country', 'Japan'),
            make_tag('material', 'brick', polarity='exclude')]
    rows = [('bld_000001', 6.0, True, True, False),
            ('bld_000002', 0.0, True, False, True)]
    out, cur = _run_with(rows, matching.top_matches, tags, exclude_ids=['bld_9'], limit=3)
    assert [o['canonical_bld_id'] for o in out] == ['bld_000001', 'bld_000002']
    assert out[0]['hit'] == 2 and out[0]['total'] == 2
    assert out[1]['hit'] == 1 and out[1]['matched_keys'] == [('use', 'Housing')]
    # exclude tag is never counted in total / matched_keys
    assert ('material', 'brick') not in out[0]['matched_keys']
    assert 'is_publishable = true' in cur.sql
    assert 'NOT (canonical_bld_id = ANY(%s))' in cur.sql
    assert cur.sql.count('%s') == len(cur.params)
    assert cur.params[-2:] == [['bld_9'], 3]


def test_order_clause_is_deterministic_tiebreak():
    tags = [make_tag('country', 'Japan')]
    _, cur = _run_with([], matching.top_matches, tags)
    flat = ' '.join(cur.sql.split())
    assert ('ORDER BY score DESC, n_sources DESC, CASE confidence_tier WHEN \'T1\' THEN 1 '
            'WHEN \'T2\' THEN 2 ELSE 3 END, canonical_bld_id ASC') in flat


def test_no_want_tags_runs_no_query():
    tags = [make_tag('material', 'brick', polarity='exclude')]
    out, cur = _run_with([], matching.top_matches, tags)
    assert out == [] and cur.sql is None


def test_ranked_pool_default_limit_and_shape():
    tags = [make_tag('country', 'Japan')]
    out, cur = _run_with([('bld_000001', 3.0, True)], matching.ranked_pool, tags)
    assert out == [{'canonical_bld_id': 'bld_000001', 'score': 3.0}]
    assert cur.params[-1] == settings.RECOMMENDATION['bounded_pool_target']


# -- views --------------------------------------------------------------------
RECOGNIZE = '/api/v1/taste/recognize/'
CARDS = '/api/v1/taste/cards/'


def _card(i):
    return {'canonical_bld_id': i, 'name': f'n-{i}'}


def _matches(*ids):
    return [{'canonical_bld_id': i, 'score': 3.0, 'matched_keys': [('country', 'Japan')],
             'hit': 1, 'total': 1} for i in ids]


class _Client:
    """DB-free client: force-authenticates an unsaved user through the real URL conf."""

    def __init__(self, authed):
        from rest_framework.test import APIClient
        self.c = APIClient()
        if authed:
            from django.contrib.auth.models import User
            self.c.force_authenticate(user=User(id=987654, username='taste-test'))

    def post(self, *a, **kw):
        return self.c.post(*a, **kw)


@pytest.fixture
def api_client():
    return _Client(False)


@pytest.fixture
def auth_client():
    from django.core.cache import cache
    cache.clear()
    return _Client(True)


class TestViews:
    def test_auth_required(self, api_client):
        assert api_client.post(RECOGNIZE, {'text': 'x'}, format='json').status_code in (401, 403)
        assert api_client.post(CARDS, {'tags': []}, format='json').status_code in (401, 403)

    @pytest.mark.parametrize('body', [
        {}, {'text': ''}, {'text': 5}, {'text': 'x' * 501},
        {'text': 'a', 'exclude_ids': 'x'}, {'text': 'a', 'exclude_ids': [1]},
        {'text': 'a', 'exclude_ids': ['b'] * 101},
    ])
    def test_recognize_400(self, auth_client, body):
        with mock.patch('apps.recommendation.views.taste_start.recognize_tags') as rec:
            r = auth_client.post(RECOGNIZE, body, format='json')
        assert r.status_code == 400
        rec.assert_not_called()

    @pytest.mark.parametrize('body', [
        {}, {'tags': 'x'}, {'tags': [{'axis': 'use'}]}, {'tags': [], 'exclude_ids': [3]},
    ])
    def test_cards_400(self, auth_client, body):
        assert auth_client.post(CARDS, body, format='json').status_code == 400

    def test_recognize_shape_and_order(self, auth_client):
        from apps.recommendation.taste_start import RecognitionResult
        tags = [make_tag('country', 'Japan')]
        res = RecognitionResult(tags=tags, source='jev', raw_probabilities={'a': 1})
        with mock.patch('apps.recommendation.views.taste_start.recognize_tags', return_value=res), \
                mock.patch('apps.recommendation.views.taste_start.matching.top_matches',
                           return_value=_matches('b2', 'a1', 'c3')) as tm, \
                mock.patch('apps.recommendation.views.taste_start.engine.get_buildings_by_ids',
                           return_value=[_card('a1'), _card('b2'), _card('c3')]):
            r = auth_client.post(RECOGNIZE, {'text': '일본', 'exclude_ids': ['z']}, format='json')
        assert r.status_code == 200
        body = r.json()
        assert body['source'] == 'jev'
        assert body['tags'][0]['axis'] == 'country'
        assert [c['card']['canonical_bld_id'] for c in body['cards']] == ['b2', 'a1', 'c3']
        assert body['cards'][0]['hit'] == 1 and body['cards'][0]['total'] == 1
        assert body['cards'][0]['matched_keys'] == [['country', 'Japan']]
        assert tm.call_args.kwargs['exclude_ids'] == ['z']

    def test_cards_endpoint_no_jev(self, auth_client):
        tag = make_tag('country', 'Japan').to_dict()
        with mock.patch('apps.recommendation.views.taste_start.recognize_tags') as rec, \
                mock.patch('apps.recommendation.views.taste_start.matching.top_matches',
                           return_value=_matches('a1')), \
                mock.patch('apps.recommendation.views.taste_start.engine.get_buildings_by_ids',
                           return_value=[_card('a1')]):
            r = auth_client.post(CARDS, {'tags': [tag]}, format='json')
        assert r.status_code == 200 and len(r.json()['cards']) == 1
        rec.assert_not_called()

    def test_no_want_tags_falls_back_to_diverse_random(self, auth_client):
        with mock.patch('apps.recommendation.views.taste_start.engine.get_diverse_random',
                        return_value=[_card('a1'), _card('b2'), _card('c3'), _card('d4')]) as dr:
            r = auth_client.post(CARDS, {'tags': [], 'exclude_ids': ['a1']}, format='json')
        assert r.status_code == 200
        cards = r.json()['cards']
        assert [c['card']['canonical_bld_id'] for c in cards] == ['b2', 'c3', 'd4']
        assert all(c['hit'] == 0 and c['total'] == 0 for c in cards)
        assert dr.call_args.kwargs['n'] == 4
