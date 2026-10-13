"""explain_tag (pure Python) must agree with _tag_expr (SQL) on the same building row.

The pure-Python cases always run. The SQL parity case needs a real Postgres
(regex `\\m..\\M`, `= ANY`, array overlap) and runs only when FEEDBACK_PARITY_DSN
is set, e.g. a throwaway local database.
"""
import os

import pytest

from apps.recommendation.taste_start import matching
from apps.recommendation.taste_start.recognizer import make_tag

YEAR = 2026

ROWS = {
    1: {'program': 'Housing', 'typology_primary': 'Apartment', 'style': 'Modernism',
        'atmosphere': 'Warm', 'color_tone': 'Warm', 'location_country': 'Japan',
        'project_year': 2005, 'material_visual': ['Wood', 'Concrete'],
        'architectural_elements': ['Courtyard'],
        'visual_description': 'Rooms are separated by a shared Garden, with timber screens.'},
    2: {'program': None, 'typology_primary': None, 'style': None, 'atmosphere': None,
        'color_tone': None, 'location_country': None, 'project_year': None,
        'material_visual': None, 'architectural_elements': None, 'visual_description': None},
    3: {'program': 'Museum', 'typology_primary': 'Museum', 'style': 'Brutalist',
        'atmosphere': 'Cold', 'color_tone': 'Cool', 'location_country': 'South Korea',
        'project_year': 2040, 'material_visual': ['glass'],
        'architectural_elements': ['Atrium'],
        'visual_description': 'The gardener walks the gardens. Courtyards abound.'},
}


def _tags():
    return [
        make_tag('country', 'Japan'),
        make_tag('use', 'Housing', kind='program'),
        make_tag('atmosphere', 'Warm'),
        make_tag('style', 'Brutalist'),
        make_tag('material', 'wood'),
        make_tag('material', 'glass'),
        make_tag('element', 'Courtyard'),
        make_tag('element', 'Garden'),
        make_tag('year', (2000, 2009)),
        make_tag('year', (None, 1990)),
        make_tag('built', 'built_only'),
        make_tag('built', 'unbuilt_only'),
    ]


def test_explain_basic_hits():
    row = ROWS[1]
    matched, via = matching.explain_tag(make_tag('country', 'Japan'), row, YEAR)
    assert matched and via == [{'column': 'location_country', 'value': 'Japan'}]
    matched, via = matching.explain_tag(make_tag('element', 'Courtyard'), row, YEAR)
    assert matched and {'column': 'architectural_elements', 'value': 'Courtyard'} in via


def test_description_match_is_word_bounded_case_insensitive_with_excerpt():
    tag = make_tag('element', 'Garden')
    matched, via = matching.explain_tag(tag, ROWS[1], YEAR)
    assert matched
    ex = [v for v in via if v['column'] == 'visual_description']
    assert ex and 'garden' in ex[0]['excerpt'].lower() and 'separated' in ex[0]['excerpt']
    # 'gardener' / 'gardens' must NOT satisfy the word-boundary match
    assert matching.explain_tag(tag, ROWS[3], YEAR)[0] is False


def test_null_columns_never_match():
    for tag in _tags():
        assert matching.explain_tag(tag, ROWS[2], YEAR) == (False, [])


@pytest.mark.skipif(not os.environ.get('FEEDBACK_PARITY_DSN'),
                    reason='needs a real Postgres (set FEEDBACK_PARITY_DSN)')
def test_parity_with_sql_tag_expr():
    import psycopg
    with psycopg.connect(os.environ['FEEDBACK_PARITY_DSN']) as conn, conn.cursor() as cur:
        cur.execute(
            'CREATE TEMP TABLE b (id int, program text, typology_primary text, style text, '
            'atmosphere text, color_tone text, location_country text, project_year int, '
            'material_visual text[], architectural_elements text[], visual_description text)')
        for i, r in ROWS.items():
            cur.execute(
                'INSERT INTO b VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                [i, r['program'], r['typology_primary'], r['style'], r['atmosphere'],
                 r['color_tone'], r['location_country'], r['project_year'],
                 r['material_visual'], r['architectural_elements'], r['visual_description']])
        for tag in _tags():
            expr, params = matching._tag_expr(tag, YEAR)
            cur.execute(f'SELECT id, {expr} FROM b ORDER BY id', params)
            for bid, sql_matched in cur.fetchall():
                py_matched, _ = matching.explain_tag(tag, ROWS[bid], YEAR)
                assert py_matched == sql_matched, (tag.key, bid)
