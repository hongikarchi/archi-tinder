"""
engine_filters.py -- SQL string builders from filter dicts.

Extracted from engine.py (FULL-REFACTOR-1). All weight / priority values are
taken as function arguments — no RC reads, no DB, no engine imports.
"""
import math

# F3: required-slate fields are user-explicit intent — must be hard WHERE constraints,
# not soft CASE WHEN scoring. Mirrors parse_query.REQUIRED_SLATE_FIELDS (no import to
# avoid circular-import risk between services and engine).
# Cross-ref: services/parse_query.REQUIRED_SLATE_FIELDS — keep in sync; divergence breaks hard-WHERE silently.
_REQUIRED_SLATE_FIELDS_SET = frozenset(('program', 'material', 'style', 'location_country'))

# LLM-SEARCH-RANK-1: allowlist of axis names recognised by _build_idf_score_cases.
# ONLY these names may appear in the CASE WHEN clauses — no user-supplied axis name
# can ever reach SQL construction (injection safety by static allowlist).
_IDF_SCORE_AXES = (
    'program', 'location_country', 'location_city',
    'style', 'atmosphere', 'color_tone', 'typology_primary',
    'material', 'year_min', 'year_max',
)


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


def _build_idf_score_cases(filters, base_weights, idf_map, filter_priority):
    """Build CASE WHEN SQL for IDF-weighted tag score (LLM-SEARCH-RANK-1).

    Generalises _build_score_cases with per-axis IDF weighting and priority boost.
    Handles all scoring axes including the three new soft axes:
      atmosphere, color_tone, typology_primary (all ILIKE on single TEXT columns).

    Axis-to-column mapping (static allowlist — no user input reaches SQL):
      program             -> exact  'program = %s'
      location_country    -> ILIKE  'location_country ILIKE %s'
      location_city       -> ILIKE  'location_city ILIKE %s'
      style               -> ILIKE  'style ILIKE %s'
      atmosphere          -> ILIKE  'atmosphere ILIKE %s'
      color_tone          -> ILIKE  'color_tone ILIKE %s'
      typology_primary    -> ILIKE  'typology_primary ILIKE %s'
      material            -> EXISTS(unnest(material_visual))
      year_min            -> 'project_year >= %s'
      year_max            -> 'project_year <= %s'

    IDF per axis:
      idf_map['_total'] == 0 -> all idf 1.0 (graceful fallback).
      idf = log(N / (df + 1)), clamped to [1.0, idf_ceiling].
      df is idf_map[idf_axis][filter_value], where idf_axis follows:
        program          -> idf_map['program']
        style            -> idf_map['style']
        atmosphere       -> idf_map['atmosphere']
        typology_primary -> idf_map['typology_primary']
        material         -> idf_map['material_visual']
        location_*       -> no IDF axis -> idf = 1.0
        color_tone       -> no IDF axis -> idf = 1.0
        year_*           -> no IDF axis -> idf = 1.0

    Priority boost:
      filter_priority is an ordered list of axis names.
      rank_frac = (n_axes - rank) / n_axes  (rank 0 = highest priority).
      effective_weight = base_weight * (1 + priority_boost * rank_frac) * clamp(idf, 1.0, ceiling)

    Security:
      - weight is a Python float baked into the SQL string literal (same pattern
        as _build_score_cases) — no user input touches the weight fragment.
      - matching values are always %s parameters.
      - axis names (location_country etc.) are selected from _IDF_SCORE_AXES allowlist
        and mapped to hardcoded column expressions — never interpolated from caller input.

    Args:
        filters:          dict of filter key->value (same shape as parse_query output).
        base_weights:     dict axis->float (from RC['llm_search_base_weights']).
        idf_map:          dict from caches.get_corpus_tag_df() (may be {'_total':0}).
        filter_priority:  ordered list of axis names (highest priority first).

    Returns:
        (cases: list[str], params: list, total_weight: float)
    """
    N = idf_map.get('_total', 0) if idf_map else 0
    use_idf = (N > 0)
    idf_ceiling = base_weights.get('_idf_ceiling', 3.0)
    priority_boost = base_weights.get('_priority_boost', 0.25)

    # Build priority rank map: axis -> rank (0 = highest priority)
    n_axes = max(len(filter_priority), 1)
    priority_rank = {axis: i for i, axis in enumerate(filter_priority)}

    def _effective_weight(axis, value):
        """Compute effective weight for a single axis+value."""
        base = float(base_weights.get(axis, 0.0))
        if base <= 0:
            return 0.0

        # Priority boost: rank_frac = (n_axes - rank) / n_axes
        rank = priority_rank.get(axis, n_axes)  # unranked -> no boost
        rank_frac = float(n_axes - rank) / float(n_axes)
        boost_factor = 1.0 + priority_boost * rank_frac

        # IDF factor
        if use_idf:
            idf_axis_map = {
                'program': 'program',
                'style': 'style',
                'atmosphere': 'atmosphere',
                'typology_primary': 'typology_primary',
                'material': 'material_visual',
            }
            idf_axis = idf_axis_map.get(axis)
            if idf_axis and idf_axis in idf_map:
                axis_df_map = idf_map[idf_axis]
                # Lookup: prefer exact match, then case-insensitive scan for ILIKE axes
                df = axis_df_map.get(value, 0)
                if df == 0 and isinstance(value, str):
                    value_lower = value.lower()
                    for k, v in axis_df_map.items():
                        if isinstance(k, str) and k.lower() == value_lower:
                            df = v
                            break
                idf_raw = math.log(N / (df + 1)) if N > 0 else 1.0
                idf = max(1.0, min(idf_raw, idf_ceiling))
            else:
                idf = 1.0
        else:
            idf = 1.0

        return base * boost_factor * idf

    cases = []
    params = []
    total_weight = 0.0

    # program — exact match
    if filters.get('program') and 'program' in _IDF_SCORE_AXES:
        w = _effective_weight('program', filters['program'])
        if w > 0:
            cases.append(f'CASE WHEN program = %s THEN {w} ELSE 0 END')
            params.append(filters['program'])
            total_weight += w

    # location_country — ILIKE
    if filters.get('location_country') and 'location_country' in _IDF_SCORE_AXES:
        w = _effective_weight('location_country', filters['location_country'])
        if w > 0:
            cases.append(f'CASE WHEN location_country ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['location_country']}%")
            total_weight += w

    # location_city — ILIKE
    if filters.get('location_city') and 'location_city' in _IDF_SCORE_AXES:
        w = _effective_weight('location_city', filters['location_city'])
        if w > 0:
            cases.append(f'CASE WHEN location_city ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['location_city']}%")
            total_weight += w

    # style — ILIKE
    if filters.get('style') and 'style' in _IDF_SCORE_AXES:
        w = _effective_weight('style', filters['style'])
        if w > 0:
            cases.append(f'CASE WHEN style ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['style']}%")
            total_weight += w

    # atmosphere — ILIKE (new soft axis)
    if filters.get('atmosphere') and 'atmosphere' in _IDF_SCORE_AXES:
        w = _effective_weight('atmosphere', filters['atmosphere'])
        if w > 0:
            cases.append(f'CASE WHEN atmosphere ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['atmosphere']}%")
            total_weight += w

    # color_tone — ILIKE (new soft axis)
    if filters.get('color_tone') and 'color_tone' in _IDF_SCORE_AXES:
        w = _effective_weight('color_tone', filters['color_tone'])
        if w > 0:
            cases.append(f'CASE WHEN color_tone ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['color_tone']}%")
            total_weight += w

    # typology_primary — ILIKE (new soft axis)
    if filters.get('typology_primary') and 'typology_primary' in _IDF_SCORE_AXES:
        w = _effective_weight('typology_primary', filters['typology_primary'])
        if w > 0:
            cases.append(f'CASE WHEN typology_primary ILIKE %s THEN {w} ELSE 0 END')
            params.append(f"%{filters['typology_primary']}%")
            total_weight += w

    # material — unnest EXISTS
    if filters.get('material') and 'material' in _IDF_SCORE_AXES:
        w = _effective_weight('material', filters['material'])
        if w > 0:
            cases.append(
                'CASE WHEN EXISTS '
                '(SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s) '
                f'THEN {w} ELSE 0 END'
            )
            params.append(f"%{filters['material']}%")
            total_weight += w

    # year_min — numeric
    if filters.get('year_min') is not None and 'year_min' in _IDF_SCORE_AXES:
        w = _effective_weight('year_min', filters['year_min'])
        if w > 0:
            cases.append(f'CASE WHEN project_year >= %s THEN {w} ELSE 0 END')
            params.append(filters['year_min'])
            total_weight += w

    # year_max — numeric
    if filters.get('year_max') is not None and 'year_max' in _IDF_SCORE_AXES:
        w = _effective_weight('year_max', filters['year_max'])
        if w > 0:
            cases.append(f'CASE WHEN project_year <= %s THEN {w} ELSE 0 END')
            params.append(filters['year_max'])
            total_weight += w

    return cases, params, total_weight
