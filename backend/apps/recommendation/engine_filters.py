"""
engine_filters.py -- SQL string builders from filter dicts.

Extracted from engine.py (FULL-REFACTOR-1). All weight / priority values are
taken as function arguments — no RC reads, no DB, no engine imports.
"""

# F3: required-slate fields are user-explicit intent — must be hard WHERE constraints,
# not soft CASE WHEN scoring. Mirrors parse_query.REQUIRED_SLATE_FIELDS (no import to
# avoid circular-import risk between services and engine).
# Cross-ref: services/parse_query.REQUIRED_SLATE_FIELDS — keep in sync; divergence breaks hard-WHERE silently.
_REQUIRED_SLATE_FIELDS_SET = frozenset(('program', 'material', 'style', 'location_country'))


def _build_filter_sql(filters):
    """Build WHERE clauses from a filters dict. Returns (clauses_str, params_list).

    Always prepends `is_publishable = true` so that every building query in the
    engine is publishable-gated. Callers do NOT need to add this themselves.
    """
    clauses = ['is_publishable = true']
    params = []
    if not filters:
        filters = {}
    if filters.get('program'):
        clauses.append('program = %s')
        params.append(filters['program'])
    if filters.get('location_country'):
        clauses.append('location_country ILIKE %s')
        params.append(f"%{filters['location_country']}%")
    if filters.get('location_city'):
        clauses.append('location_city ILIKE %s')
        params.append(f"%{filters['location_city']}%")
    if filters.get('material'):
        # material_visual is TEXT[] — match against any element.
        clauses.append(
            'EXISTS (SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s)'
        )
        params.append(f"%{filters['material']}%")
    if filters.get('style'):
        clauses.append('style ILIKE %s')
        params.append(f"%{filters['style']}%")
    if filters.get('year_min') is not None:
        clauses.append('project_year >= %s')
        params.append(filters['year_min'])
    if filters.get('year_max') is not None:
        clauses.append('project_year <= %s')
        params.append(filters['year_max'])
    where = 'WHERE ' + ' AND '.join(clauses)
    return where, params


def _build_required_slate_where(filters):
    """Build hard WHERE clauses for required-slate filter fields present in `filters`.

    F3 fix: fields in _REQUIRED_SLATE_FIELDS_SET that the user explicitly requested
    are hard constraints — buildings that don't match must be excluded, not just
    scored lower. Returns (clauses_list, params_list). Empty if no slate fields match.

    Uses same SQL fragments as _build_filter_sql for consistency (ILIKE, EXISTS/unnest).
    Does NOT include `is_publishable = true` (caller already has it).
    """
    clauses = []
    params = []
    if not filters:
        return clauses, params
    if filters.get('program') and 'program' in _REQUIRED_SLATE_FIELDS_SET:
        clauses.append('program = %s')
        params.append(filters['program'])
    if filters.get('location_country') and 'location_country' in _REQUIRED_SLATE_FIELDS_SET:
        clauses.append('location_country ILIKE %s')
        params.append(f"%{filters['location_country']}%")
    if filters.get('material') and 'material' in _REQUIRED_SLATE_FIELDS_SET:
        clauses.append(
            'EXISTS (SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s)'
        )
        params.append(f"%{filters['material']}%")
    if filters.get('style') and 'style' in _REQUIRED_SLATE_FIELDS_SET:
        clauses.append('style ILIKE %s')
        params.append(f"%{filters['style']}%")
    return clauses, params


def _build_score_cases(filters, weights):
    """Build CASE WHEN SQL for each active filter with priority weight.

    Schema-aligned to canonical_v2_buildings: drops area_sqm; year -> project_year;
    material ILIKE -> material_visual[] EXISTS match; adds location_city.
    """
    cases, params = [], []
    total_weight = 0
    if filters.get('program') and 'program' in weights:
        w = weights['program']
        cases.append(f'CASE WHEN program = %s THEN {w} ELSE 0 END')
        params.append(filters['program'])
        total_weight += w
    if filters.get('location_country') and 'location_country' in weights:
        w = weights['location_country']
        cases.append(f'CASE WHEN location_country ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['location_country']}%")
        total_weight += w
    if filters.get('location_city') and 'location_city' in weights:
        w = weights['location_city']
        cases.append(f'CASE WHEN location_city ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['location_city']}%")
        total_weight += w
    if filters.get('style') and 'style' in weights:
        w = weights['style']
        cases.append(f'CASE WHEN style ILIKE %s THEN {w} ELSE 0 END')
        params.append(f"%{filters['style']}%")
        total_weight += w
    if filters.get('material') and 'material' in weights:
        w = weights['material']
        cases.append(
            'CASE WHEN EXISTS '
            '(SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s) '
            f'THEN {w} ELSE 0 END'
        )
        params.append(f"%{filters['material']}%")
        total_weight += w
    if filters.get('year_min') is not None and 'year_min' in weights:
        w = weights['year_min']
        cases.append(f'CASE WHEN project_year >= %s THEN {w} ELSE 0 END')
        params.append(filters['year_min'])
        total_weight += w
    if filters.get('year_max') is not None and 'year_max' in weights:
        w = weights['year_max']
        cases.append(f'CASE WHEN project_year <= %s THEN {w} ELSE 0 END')
        params.append(filters['year_max'])
        total_weight += w
    return cases, params, total_weight
