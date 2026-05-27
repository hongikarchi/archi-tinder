"""
F3: Required-slate fields are hard WHERE constraints, not soft CASE WHEN scoring.

Tests:
  1. Hard WHERE excludes buildings that don't match a required-slate field.
  2. Tier 2 relaxation drops location_country → hard WHERE dropped → Bolivia-like
     records can appear at Tier 2 (correct — relaxation intent).
  3. Optional (non-slate) fields like year_min stay soft (CASE WHEN only, no hard WHERE).
"""
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────────────────────

def _cursor_returning(rows):
    """Return a context-manager mock cursor that returns `rows` from fetchall."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = rows
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    return mock_cur


def _connection_with_cursor(cursor):
    """Mock engine.connection object."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ── Test 1: hard WHERE excludes non-matching rows ────────────────────────────

def test_required_slate_field_emits_hard_where():
    """
    Mode F: filters with a required-slate field (style='Modern') must produce a
    WHERE clause containing 'style ILIKE'. A Bolivia-like record (style='Rustic')
    must not appear in results because it fails the hard WHERE.
    Verifies by inspecting the SQL passed to cursor.execute.
    """
    from apps.recommendation import engine

    captured_sql = []
    captured_params = []

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [('bld_000001', 0.9)]
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    def capture_execute(sql, params=None):
        captured_sql.append(sql)
        captured_params.append(params or [])

    mock_cur.execute = capture_execute

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    filters = {'style': 'Modern', 'program': 'Museum'}

    with patch.object(engine, 'connection', mock_conn):
        engine.create_bounded_pool(filters, target=10)

    assert captured_sql, 'No SQL executed'
    final_sql = captured_sql[-1]
    # Hard WHERE for style must be present (ILIKE)
    assert 'style ILIKE' in final_sql, (
        f'Expected hard WHERE style ILIKE in SQL but got:\n{final_sql}'
    )
    # Hard WHERE for program must be present (exact match)
    assert 'program = %s' in final_sql, (
        f'Expected hard WHERE program = %s in SQL but got:\n{final_sql}'
    )
    # Verify these appear in the WHERE clause (after the WHERE keyword, not only in SELECT).
    # Both fields appear in SELECT (CASE WHEN) AND in WHERE (hard constraint). We check
    # that WHERE portion contains them by inspecting the WHERE clause substring.
    where_clause = final_sql[final_sql.find('WHERE'):]
    assert 'style ILIKE' in where_clause, (
        f'style ILIKE must appear in WHERE clause.\nWHERE portion: {where_clause}'
    )
    assert 'program = %s' in where_clause, (
        f'program = %s must appear in WHERE clause.\nWHERE portion: {where_clause}'
    )

    # ── Param-order assertion (F3 Fix 2) ────────────────────────────────────────
    # Mode F SQL structure (no HyDE):
    #   SELECT … score_sql … FROM … WHERE is_publishable
    #   AND _slate_where_sql          ← _slate_params consumed here
    #   AND (score_sql) > 0           ← params consumed here (second copy)
    #   LIMIT %s                      ← target consumed here
    # score_sql = ((cases)::float / total_weight) uses: params (first copy)
    # Correct execute order: params + _slate_params + params + [target]
    #
    # filters = {'style': 'Modern', 'program': 'Museum'}
    # _build_score_cases order: program first (= 'Museum'), style second (= '%Modern%')
    # _build_required_slate_where order: program first (= 'Museum'), style second (= '%Modern%')
    # Full params list: ['Museum', '%Modern%', 'Museum', '%Modern%', 10]
    assert captured_params, 'No params captured'
    final_params = captured_params[-1]
    # score_sql (first copy): program='Museum' at [0], style='%Modern%' at [1]
    assert final_params[0] == 'Museum', (
        f'params[0] should be score_sql program value "Museum", got {final_params[0]!r}'
    )
    assert final_params[1] == '%Modern%', (
        f'params[1] should be score_sql style value "%Modern%", got {final_params[1]!r}'
    )
    # _slate_params: program hard WHERE at [2], style hard WHERE at [3]
    assert final_params[2] == 'Museum', (
        f'params[2] should be slate program value "Museum", got {final_params[2]!r}'
    )
    assert final_params[3] == '%Modern%', (
        f'params[3] should be slate style value "%Modern%", got {final_params[3]!r}'
    )
    # where_sql (second copy): program at [4], style at [5]
    assert final_params[4] == 'Museum', (
        f'params[4] should be where_sql program value "Museum", got {final_params[4]!r}'
    )
    assert final_params[5] == '%Modern%', (
        f'params[5] should be where_sql style value "%Modern%", got {final_params[5]!r}'
    )
    # LIMIT target at [-1]
    assert final_params[-1] == 10, (
        f'params[-1] should be LIMIT target=10, got {final_params[-1]!r}'
    )


# ── Test 2: Tier 2 relaxation drops location_country hard WHERE ──────────────

def test_tier2_relaxation_drops_location_country_hard_where():
    """
    create_pool_with_relaxation Tier 2 drops location_country from the filters dict.
    After this drop, the hard WHERE for location_country should NOT appear in Mode F SQL.
    This is correct relaxation behaviour: Bolivia-like records are allowed at Tier 2.
    """
    from apps.recommendation import engine

    captured_sql = []
    call_count = [0]

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    def capture_and_return(sql, params=None):
        captured_sql.append(sql)
        call_count[0] += 1
        # Tier 1: empty result → forces relaxation
        # Tier 2+: return one row
        if call_count[0] == 1:
            mock_cur.fetchall.return_value = []
        else:
            mock_cur.fetchall.return_value = [('bld_000002', 0.5)]

    mock_cur.execute = capture_and_return

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # Filters with both location_country (required-slate) and style (required-slate)
    filters = {'location_country': 'Japan', 'style': 'Modern'}

    with patch.object(engine, 'connection', mock_conn), \
         patch.object(engine, 'cache') as mock_cache:
        mock_cache.get.return_value = None  # no tier-1 pool cache
        pool_ids, pool_scores, tier = engine.create_pool_with_relaxation(
            filters, ['location_country', 'style'], seed_ids=None,
        )

    assert tier == 2, f'Expected tier=2 (Tier 1 returns empty), got tier={tier}'
    assert pool_ids, 'Tier 2 should return results'

    # Find the Tier 2 SQL (second execute call, after Tier 1 empty)
    assert len(captured_sql) >= 2, 'Expected at least 2 SQL calls (tier 1 + tier 2)'
    tier2_sql = captured_sql[1]

    # After Tier 2 relaxation location_country is dropped → no hard WHERE for it
    assert 'location_country ILIKE' not in tier2_sql, (
        f'location_country hard WHERE should be absent at Tier 2, but found in:\n{tier2_sql}'
    )
    # style is NOT dropped by Tier 2 relaxation → still hard WHERE
    assert 'style ILIKE' in tier2_sql, (
        f'style hard WHERE should remain at Tier 2, but absent in:\n{tier2_sql}'
    )


# ── Test 3: optional (non-slate) fields stay soft ────────────────────────────

def test_optional_field_year_min_stays_soft():
    """
    year_min is NOT in _REQUIRED_SLATE_FIELDS_SET → must NOT appear as a hard
    WHERE clause, only as a CASE WHEN score term.
    """
    from apps.recommendation import engine

    captured_sql = []

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [('bld_000003', 0.6)]
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)

    def capture_execute(sql, params=None):
        captured_sql.append(sql)

    mock_cur.execute = capture_execute

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # year_min only — no required-slate fields
    filters = {'year_min': 2010}

    with patch.object(engine, 'connection', mock_conn):
        engine.create_bounded_pool(filters, target=10)

    assert captured_sql, 'No SQL executed'
    final_sql = captured_sql[-1]

    # year_min is NOT in _REQUIRED_SLATE_FIELDS_SET so _build_required_slate_where
    # must not emit a standalone 'project_year >= %s' hard WHERE clause.
    # The SQL will contain 'project_year >= %s' inside CASE WHEN (correct),
    # but the WHERE clause must NOT have a bare 'project_year >= %s' outside CASE.
    assert 'CASE' in final_sql, 'Expected CASE WHEN scoring for year_min filter'

    # Verify by checking the _REQUIRED_SLATE_FIELDS_SET excludes year_min:
    from apps.recommendation.engine import _REQUIRED_SLATE_FIELDS_SET
    assert 'year_min' not in _REQUIRED_SLATE_FIELDS_SET, (
        'year_min must not be in _REQUIRED_SLATE_FIELDS_SET (it is a soft/optional field)'
    )
    # And confirm the WHERE part doesn't start with a bare project_year constraint
    # (it only contains project_year inside the CASE WHEN score expression)
    # A standalone hard WHERE would be: "AND project_year >= %s" outside a CASE block.
    # Inside CASE WHEN it's:
    # "CASE WHEN project_year >= %s THEN ..."
    # Count occurrences outside CASE context: none expected
    # Simple heuristic: all project_year refs inside CASE have 'CASE WHEN' before them
    case_when_count = final_sql.count('CASE WHEN project_year')
    total_project_year_count = final_sql.count('project_year')
    assert case_when_count == total_project_year_count, (
        f'All project_year refs should be inside CASE WHEN. '
        f'CASE WHEN count={case_when_count}, total={total_project_year_count}.\n'
        f'SQL: {final_sql}'
    )


# ── Test 4: Mode V (HyDE) param order is correct ────────────────────────────

def test_mode_v_param_order_matches_sql_placeholder_order():
    """
    Mode V (HyDE blend): when slate + non-slate filters are mixed and v_initial
    is supplied, the execute call must bind params in the same order as SQL
    placeholders:
      score_sql: params (cases), hyde_weight, vec_str
      _slate_where_sql: _slate_params
      where_sql: params (cases again), vec_str
      LIMIT: target

    Wrong order (_slate_params first) was the F3 bug: psycopg2 binds slate values
    to score_sql placeholders → type mismatch / silent cross-contamination.

    Requires patching engine.RC to set hyde_vinitial_enabled=True (default: False
    in settings.py) so the Mode V branch is exercised.
    """
    from unittest.mock import patch as _patch, MagicMock as _MM
    from apps.recommendation import engine

    captured_params = []

    mock_cur = _MM()
    mock_cur.fetchall.return_value = [('bld_000004', 0.8)]
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = _MM(return_value=False)

    def capture_execute(sql, params=None):
        captured_params.append(list(params) if params else [])

    mock_cur.execute = capture_execute

    mock_conn = _MM()
    mock_conn.cursor.return_value = mock_cur

    # style is a required-slate field → emits both a CASE WHEN param and a _slate_param.
    # Use a dummy HyDE vector (384 floats of 0.0 — normalised to zero-vec, still valid for test).
    dummy_vec = [0.0] * 384
    filters = {'style': 'Brutalist'}

    # RC override: enable Mode V (hyde_vinitial_enabled default is False in settings).
    # Keep only the keys the Mode V path reads: hyde_vinitial_enabled, hyde_score_weight.
    rc_override = dict(engine.RC)
    rc_override['hyde_vinitial_enabled'] = True
    rc_override['hyde_score_weight'] = 50.0

    with _patch.object(engine, 'connection', mock_conn), \
         _patch.object(engine, 'RC', rc_override):
        engine.create_bounded_pool(filters, target=5, v_initial=dummy_vec)

    assert captured_params, 'No params captured for Mode V execute'
    p = captured_params[0]  # Mode V is tried first

    # With filters={'style': 'Brutalist'} and v_initial supplied (Mode V path):
    # _build_score_cases produces: params = ['%Brutalist%']
    # _build_required_slate_where produces: _slate_params = ['%Brutalist%']
    # hyde_weight = 50.0, vec_str = '[0.0, ...]'
    # Full params list: ['%Brutalist%', 50.0, vec_str, '%Brutalist%', '%Brutalist%', vec_str, 5]
    #   index 0: score_sql first case  → '%Brutalist%'
    #   index 1: hyde_weight           → 50.0 (float)
    #   index 2: vec_str (score cosine)→ string starting '['
    #   index 3: _slate_param          → '%Brutalist%'
    #   index 4: where_sql first case  → '%Brutalist%'
    #   index 5: vec_str (where cosine)→ string starting '['
    #   index -1 (6): LIMIT target     → 5
    assert len(p) == 7, (
        f'Expected 7 params for Mode V with 1 slate filter, got {len(p)}: {p}'
    )
    # Score CASE param comes before hyde_weight (a float, not a string)
    assert p[0] == '%Brutalist%', (
        f'params[0] should be score CASE value "%Brutalist%", got {p[0]!r}'
    )
    assert isinstance(p[1], float), (
        f'params[1] should be hyde_weight (float), got {type(p[1])}: {p[1]!r}'
    )
    assert isinstance(p[2], str) and p[2].startswith('['), (
        f'params[2] should be vec_str (string starting "["), got {p[2]!r}'
    )
    # _slate_param comes after hyde_weight/vec_str, before second copy of cases
    assert p[3] == '%Brutalist%', (
        f'params[3] should be _slate_param "%Brutalist%", got {p[3]!r}'
    )
    # where_sql case param
    assert p[4] == '%Brutalist%', (
        f'params[4] should be where_sql CASE value "%Brutalist%", got {p[4]!r}'
    )
    assert isinstance(p[5], str) and p[5].startswith('['), (
        f'params[5] should be vec_str for where cosine (string starting "["), got {p[5]!r}'
    )
    assert p[-1] == 5, (
        f'params[-1] should be LIMIT target=5, got {p[-1]!r}'
    )
