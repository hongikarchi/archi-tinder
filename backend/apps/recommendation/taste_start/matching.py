"""
matching.py -- Rank buildings by recognised taste-start tags (one raw SQL query).

Every tag becomes one boolean SQL expression (EXACT / word-boundary matching,
never ILIKE substring). The expressions are computed in an inner SELECT as
t0..tN; the outer SELECT turns them into a weighted score:

    score = sum(weight of satisfied want tags) - factor * sum(weight of satisfied exclude tags)

Exclude is a penalty, never a filter. Candidates must satisfy >= 1 want tag.
Ordering is deterministic: score DESC, n_sources DESC, confidence_tier
(T1 > T2 > T3), canonical_bld_id ASC.

All values travel as bind parameters; no tag text is formatted into SQL.
"""
import logging
import re

from django.conf import settings
from django.db import connections

from .year_rule import current_year

logger = logging.getLogger('apps.recommendation')

# Columns matched with `col = ANY(%s)` (exact value lists).
_ANY_COLUMNS = ('program', 'typology_primary', 'style', 'atmosphere',
                'color_tone', 'location_country')


def scored_tags(tags):
    """Tags that take part in matching. 'unbuilt_ok' constrains nothing -> skipped."""
    return [t for t in tags if not (t.axis == 'built' and t.value == 'unbuilt_ok')]


def _tag_expr(tag, year_now):
    """Return (boolean_sql, params) for one tag. NULL columns evaluate to false."""
    m = tag.match or {}
    parts, params = [], []

    for col in _ANY_COLUMNS:
        if m.get(col):
            parts.append(f'COALESCE({col} = ANY(%s), false)')
            params.append(list(m[col]))

    if m.get('material_visual'):
        parts.append(
            'COALESCE(ARRAY(SELECT lower(x) FROM unnest(material_visual) AS x) && %s::text[], false)')
        params.append([str(v).lower() for v in m['material_visual']])

    if m.get('architectural_elements') or m.get('visual_description_contains'):
        sub = []
        for el in m.get('architectural_elements') or []:
            sub.append('COALESCE(%s = ANY(architectural_elements), false)')
            params.append(el)
        for kw in m.get('visual_description_contains') or []:
            sub.append('COALESCE(visual_description ~* %s, false)')
            params.append(r'\m' + re.escape(kw) + r'\M')
        parts.append('(' + ' OR '.join(sub) + ')')

    if tag.axis == 'year':
        lo, hi = m.get('year_min'), m.get('year_max')
        if lo is None and hi is None:
            return 'false', []
        conds = ['project_year IS NOT NULL']
        if lo is not None:
            conds.append('project_year >= %s')
            params.append(int(lo))
        if hi is not None:
            conds.append('project_year <= %s')
            params.append(int(hi))
        parts.append('(' + ' AND '.join(conds) + ')')

    if tag.axis == 'built':
        if m.get('built') == 'built_only':
            parts.append('(project_year IS NOT NULL AND project_year <= %s)')
            params.append(year_now)
        elif m.get('built') == 'unbuilt_only':
            parts.append('(project_year IS NOT NULL AND project_year > %s)')
            params.append(year_now)

    if not parts:
        return 'false', []
    return '(' + ' OR '.join(parts) + ')', params


def score_sql(tags):
    """Build the parameterised pieces of the scoring query.

    Returns (score_expr, params, bool_exprs):
      bool_exprs  one boolean SQL expression per scored tag (placeholders %s)
      params      flat parameter list, in the order bool_exprs are concatenated
      score_expr  SQL over the aliases t0..tN (no placeholders)
    """
    rc = settings.RECOMMENDATION
    weights = rc['taste_tag_weights']
    factor = float(rc.get('taste_exclude_penalty_factor', 1.0))
    year_now = current_year()

    bool_exprs, params, terms = [], [], []
    for i, tag in enumerate(scored_tags(tags)):
        expr, p = _tag_expr(tag, year_now)
        bool_exprs.append(expr)
        params.extend(p)
        w = float(weights.get(tag.axis, 1))
        if tag.polarity == 'exclude':
            w = -factor * w
        terms.append(f'(CASE WHEN t{i} THEN {w!r} ELSE 0 END)')
    score_expr = ' + '.join(terms) if terms else '0'
    return score_expr, params, bool_exprs


def has_want_tags(tags):
    return any(t.polarity != 'exclude' for t in scored_tags(tags))


def _run(tags, exclude_ids, limit):
    scored = scored_tags(tags)
    want_idx = [i for i, t in enumerate(scored) if t.polarity != 'exclude']
    if not want_idx:
        return []
    score_expr, params, bool_exprs = score_sql(tags)
    select_bools = ', '.join(f'{e} AS t{i}' for i, e in enumerate(bool_exprs))
    any_want = ' OR '.join(f't{i}' for i in want_idx)
    flags = ', '.join(f't{i}' for i in range(len(scored)))
    sql = f"""
        SELECT canonical_bld_id, ({score_expr}) AS score, {flags}
        FROM (
            SELECT canonical_bld_id, n_sources, confidence_tier, {select_bools}
            FROM canonical_v2_buildings
            WHERE is_publishable = true
              AND NOT (canonical_bld_id = ANY(%s))
        ) s
        WHERE {any_want}
        ORDER BY score DESC, n_sources DESC,
                 CASE confidence_tier WHEN 'T1' THEN 1 WHEN 'T2' THEN 2 ELSE 3 END,
                 canonical_bld_id ASC
        LIMIT %s
    """
    # Placeholders appear in select_bools first, then exclude ids, then limit.
    all_params = list(params) + [list(exclude_ids), int(limit)]
    with connections['buildings'].cursor() as cur:
        cur.execute(sql, all_params)
        rows = cur.fetchall()

    total = len(want_idx)
    out = []
    for row in rows:
        bld_id, score, flag_vals = row[0], row[1], row[2:]
        matched = [scored[i].key for i in want_idx if flag_vals[i]]
        out.append({
            'canonical_bld_id': bld_id,
            'score': float(score),
            'matched_keys': matched,
            'hit': len(matched),
            'total': total,
        })
    return out


def score_ids(tags, ids):
    """Tag score for a given id list: {canonical_bld_id: score}.

    Same scoring as score_sql/top_matches, but no LIMIT and no ">= 1 want tag"
    filter. Ids missing from the DB (or not publishable) are simply absent.
    One parameterised query; no query when there is nothing to score.
    """
    ids = list(ids or [])
    if not ids or not scored_tags(tags):
        return {}
    score_expr, params, bool_exprs = score_sql(tags)
    select_bools = ', '.join(f'{e} AS t{i}' for i, e in enumerate(bool_exprs))
    sql = f"""
        SELECT canonical_bld_id, ({score_expr}) AS score
        FROM (
            SELECT canonical_bld_id, {select_bools}
            FROM canonical_v2_buildings
            WHERE is_publishable = true
              AND canonical_bld_id = ANY(%s)
        ) s
    """
    with connections['buildings'].cursor() as cur:
        cur.execute(sql, list(params) + [ids])
        rows = cur.fetchall()
    return {row[0]: float(row[1]) for row in rows}


def top_matches(tags, exclude_ids=(), limit=3):
    """Top `limit` buildings by tag match: [{canonical_bld_id, score, matched_keys, hit, total}]."""
    return _run(tags, exclude_ids, limit)


def ranked_pool(tags, limit=None, exclude_ids=()):
    """Same ordering as top_matches, sized for a session pool (default bounded_pool_target)."""
    if limit is None:
        limit = settings.RECOMMENDATION['bounded_pool_target']
    return [{'canonical_bld_id': r['canonical_bld_id'], 'score': r['score']}
            for r in _run(tags, exclude_ids, limit)]
