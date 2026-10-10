"""Taste-start: old Gemini-era filters -> tags, tag_io, and score_ids (mocked cursor)."""
from unittest import mock

import pytest

from apps.recommendation.taste_start import matching, tag_io
from apps.recommendation.taste_start.legacy_filters import filters_to_tags
from apps.recommendation.taste_start.recognizer import make_tag


def keys(filters):
    return [t.key for t in filters_to_tags(filters)]


def test_program_in_program_vocab_is_use():
    tags = filters_to_tags({'program': 'Housing'})
    assert [(t.axis, t.value) for t in tags] == [('use', 'Housing')]
    assert 'program' in tags[0].match


def test_program_only_in_typology_becomes_typology_use():
    tags = filters_to_tags({'program': 'house'})
    assert tags[0].axis == 'use' and 'typology_primary' in tags[0].match


def test_typology_primary_wins_over_program():
    tags = filters_to_tags({'program': 'Housing', 'typology_primary': 'Apartment'})
    uses = [t for t in tags if t.axis == 'use']
    assert len(uses) == 1 and uses[0].value == 'Apartment'
    assert 'typology_primary' in uses[0].match


def test_style_atmosphere_color_case_insensitive():
    k = keys({'style': 'minimalist', 'atmosphere': ['SERENE'], 'color_tone': 'earth'})
    assert ('style', 'Minimalist') in k
    assert ('atmosphere', 'Serene') in k
    assert ('color', 'Earth') in k


def test_warm_color_merges_into_atmosphere_warm():
    tags = filters_to_tags({'color_tone': 'Warm'})
    assert [(t.axis, t.value) for t in tags] == [('atmosphere', 'Warm')]
    assert tags[0].match['color_tone'] == ['Warm']


def test_industrial_atmosphere_becomes_style():
    tags = filters_to_tags({'atmosphere': 'Industrial'})
    assert [(t.axis, t.value) for t in tags] == [('style', 'Industrial')]
    assert 'atmosphere' in tags[0].match


def test_industrial_in_both_gives_one_tag():
    k = keys({'style': 'Industrial', 'atmosphere': 'Industrial'})
    assert k == [('style', 'Industrial')]


def test_elements_str_or_list():
    assert keys({'architectural_elements': 'courtyard'}) == [('element', 'Courtyard')]
    k = keys({'architectural_elements': ['Garden', 'Atrium', 'nonsense']})
    assert k == [('element', 'Garden'), ('element', 'Atrium')]


def test_material_group_mapping_and_drop():
    assert keys({'material': ['Timber', 'steel']}) == [('material', 'wood'), ('material', 'metal')]
    assert keys({'material': 'unobtainium'}) == []


def test_country_canonical_and_alias():
    assert keys({'location_country': 'japan'}) == [('country', 'Japan')]
    assert keys({'location_country': 'Türkiye'}) == [('country', 'Turkey')]
    assert keys({'location_country': 'Atlantis'}) == []


@pytest.mark.parametrize('f,expect', [
    ({'year_min': 2000, 'year_max': 2010}, [(2000, 2010)]),
    ({'year_min': 2000}, [(2000, None)]),
    ({'year_max': 1950}, [(None, 1950)]),
    ({'year_min': 2010, 'year_max': 2000}, []),
    ({'year_min': 1000}, []),
    ({'year_min': 'x'}, []),
    ({'year_min': True}, []),
])
def test_year_rules(f, expect):
    assert [t.value for t in filters_to_tags(f) if t.axis == 'year'] == expect


def test_unmappable_keys_dropped():
    assert filters_to_tags({'location_city': 'Tokyo', 'image_focus': 'facade', 'x': 1}) == []


def test_all_tags_are_want():
    tags = filters_to_tags({'program': 'Office', 'style': 'Brutalist', 'location_country': 'Spain'})
    assert tags and all(t.polarity == 'want' for t in tags)


@pytest.mark.parametrize('junk', [
    None, 'text', 5, [], [1, 2], {}, {'program': 5}, {'style': {'a': 1}},
    {'material': [None, 3, {}]}, {'architectural_elements': [[]]},
    {'location_country': 7}, {'year_min': [1], 'year_max': {}},
])
def test_junk_never_raises(junk):
    assert isinstance(filters_to_tags(junk), list)


# -- tag_io -------------------------------------------------------------------------
def test_tag_io_rebuild_ignores_client_match():
    t = tag_io.rebuild_tag({'axis': 'country', 'value': 'Japan', 'match': {'x': 1}, 'label_ko': 'zz'})
    assert t.match == make_tag('country', 'Japan').match and t.label_ko != 'zz'


def test_tag_io_errors_are_value_errors():
    for bad in ({'axis': 'country', 'value': 'Nowhere'}, 'x', {'axis': 'year', 'value': [1, 2]}):
        with pytest.raises(ValueError):
            tag_io.rebuild_tag(bad)
    with pytest.raises(ValueError):
        tag_io.parse_tags('nope')
    with pytest.raises(ValueError):
        tag_io.parse_tags([{'axis': 'country', 'value': 'Japan'}] * 3, max_tags=2)
    with pytest.raises(ValueError):
        tag_io.parse_tags([{'axis': 'bogus', 'value': 'x'}])


def test_tag_io_parse_ok():
    tags = tag_io.parse_tags([{'axis': 'country', 'value': 'Japan'},
                              {'axis': 'year', 'value': [2000, None], 'polarity': 'exclude'}])
    assert [t.key for t in tags] == [('country', 'Japan'), ('year', (2000, None))]


# -- score_ids ----------------------------------------------------------------------
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


def _run(rows, tags, ids):
    cur = _Cur(rows)
    conn = mock.MagicMock()
    conn.cursor.return_value = cur
    with mock.patch.object(matching, 'connections', {'buildings': conn}):
        out = matching.score_ids(tags, ids)
    return out, cur, conn


def test_score_ids_parameterised_and_gated():
    tags = [make_tag('country', 'Japan'), make_tag('material', 'brick', polarity='exclude')]
    out, cur, _ = _run([('bld_1', 3.0), ('bld_2', -2.0)], tags, ['bld_1', 'bld_2', 'bld_gone'])
    assert out == {'bld_1': 3.0, 'bld_2': -2.0}          # missing ids simply absent
    assert 'is_publishable = true' in cur.sql
    assert 'canonical_bld_id = ANY(%s)' in cur.sql
    assert 'LIMIT' not in cur.sql.upper()
    assert 'Japan' not in cur.sql and 'bld_1' not in cur.sql
    assert cur.sql.count('%s') == len(cur.params)
    assert cur.params[-1] == ['bld_1', 'bld_2', 'bld_gone']


def test_score_ids_no_want_tag_filter():
    tags = [make_tag('material', 'brick', polarity='exclude')]
    out, cur, _ = _run([('bld_1', -2.0)], tags, ['bld_1'])
    assert out == {'bld_1': -2.0}


def test_score_ids_empty_ids_runs_no_query():
    out, cur, conn = _run([], [make_tag('country', 'Japan')], [])
    assert out == {} and cur.sql is None and not conn.cursor.called


def test_score_ids_no_scored_tags_runs_no_query():
    out, cur, conn = _run([], [make_tag('built', 'unbuilt_ok')], ['bld_1'])
    assert out == {} and cur.sql is None
    out, cur, conn = _run([], [], ['bld_1'])
    assert out == {} and cur.sql is None
