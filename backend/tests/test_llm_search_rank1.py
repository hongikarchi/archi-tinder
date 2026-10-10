"""
test_llm_search_rank1.py -- LLM-SEARCH-RANK-1: A+BM25 soft-score ranking tests.

Covers:
  - _build_idf_score_cases: unit tests (full > partial > none ranking, new fields,
    IDF/ceiling, _total==0 graceful fallback, injection safety via allowlist).
  - engine.search_by_filters_scored: mocked DB integration (pure-soft, fallback path).
"""
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Unit tests: _build_idf_score_cases
# ---------------------------------------------------------------------------

class TestBuildIdfScoreCases:
    """Unit tests for engine_filters._build_idf_score_cases."""

    def _build(self, filters, base_weights=None, idf_map=None, filter_priority=None):
        from apps.recommendation.engine_filters import _build_idf_score_cases
        _base = base_weights or {
            'program': 10.0, 'location_country': 5.0, 'location_city': 5.0,
            'style': 4.0, 'atmosphere': 3.0, 'color_tone': 2.0,
            'typology_primary': 6.0, 'material': 4.0,
            'year_min': 1.0, 'year_max': 1.0,
            '_idf_ceiling': 3.0, '_priority_boost': 0.25,
        }
        _idf = idf_map if idf_map is not None else {'_total': 0}
        _priority = filter_priority or []
        return _build_idf_score_cases(filters, _base, _idf, _priority)

    def test_empty_filters_returns_empty(self):
        cases, params, total = self._build({})
        assert cases == []
        assert params == []
        assert total == 0.0

    def test_program_exact_match_case(self):
        """program uses exact '= %s' not ILIKE."""
        cases, params, total = self._build({'program': 'Housing'})
        assert len(cases) == 1
        assert 'program = %s' in cases[0]
        assert params == ['Housing']
        assert total > 0

    def test_location_ilike_case(self):
        """location_country and location_city use ILIKE %s."""
        cases, params, total = self._build({
            'location_country': 'Japan',
            'location_city': 'Tokyo',
        })
        assert any('location_country ILIKE %s' in c for c in cases)
        assert any('location_city ILIKE %s' in c for c in cases)
        # Values are wrapped in % for ILIKE
        assert '%Japan%' in params
        assert '%Tokyo%' in params

    def test_style_ilike_case(self):
        cases, params, total = self._build({'style': 'Brutalist'})
        assert any('style ILIKE %s' in c for c in cases)
        assert '%Brutalist%' in params

    def test_atmosphere_ilike_case_new_field(self):
        """atmosphere (new soft axis) uses ILIKE."""
        cases, params, total = self._build({'atmosphere': 'warm'})
        assert len(cases) == 1
        assert 'atmosphere ILIKE %s' in cases[0]
        assert '%warm%' in params
        assert total > 0

    def test_color_tone_ilike_case_new_field(self):
        """color_tone (new soft axis) uses ILIKE."""
        cases, params, total = self._build({'color_tone': 'warm'})
        assert len(cases) == 1
        assert 'color_tone ILIKE %s' in cases[0]
        assert '%warm%' in params

    def test_typology_primary_ilike_case_new_field(self):
        """typology_primary (new soft axis) uses ILIKE."""
        cases, params, total = self._build({'typology_primary': 'detached house'})
        assert len(cases) == 1
        assert 'typology_primary ILIKE %s' in cases[0]
        assert '%detached house%' in params

    def test_material_uses_unnest_exists(self):
        """material uses EXISTS(SELECT 1 FROM unnest(material_visual) m WHERE m ILIKE %s)."""
        cases, params, total = self._build({'material': 'timber'})
        assert len(cases) == 1
        assert 'unnest(material_visual)' in cases[0]
        assert '%timber%' in params

    def test_year_min_numeric(self):
        cases, params, total = self._build({'year_min': 2000})
        assert any('project_year >=' in c for c in cases)
        assert 2000 in params

    def test_year_max_numeric(self):
        cases, params, total = self._build({'year_max': 2020})
        assert any('project_year <=' in c for c in cases)
        assert 2020 in params

    def test_full_filter_set_all_cases_present(self):
        """All axes present -> all cases generated."""
        filters = {
            'program': 'Housing',
            'location_country': 'Japan',
            'location_city': 'Tokyo',
            'style': 'Contemporary',
            'atmosphere': 'warm',
            'color_tone': 'warm',
            'typology_primary': 'detached',
            'material': 'timber',
            'year_min': 2000,
            'year_max': 2023,
        }
        cases, params, total = self._build(filters)
        assert len(cases) == 10
        assert total > 0

    def test_total_zero_idf_map_uses_fallback_idf_1(self):
        """When idf_map['_total']==0, IDF factor is 1.0 (no multiplication)."""
        # With _total=0: idf=1.0 exactly, so weight = base * boost * 1.0
        cases, params, total = self._build(
            {'program': 'Housing'},
            idf_map={'_total': 0},
        )
        assert len(cases) == 1
        # Total should be base_weight (no IDF amplification)
        # base = 10.0, priority_boost = 0.25, rank_frac = 0 (no priority), boost = 1.0
        assert abs(total - 10.0) < 0.01

    def test_idf_computed_from_idf_map(self):
        """When _total > 0 and df provided, IDF is log(N/(df+1))."""
        N = 1000
        df = 9  # idf = log(1000/10) = log(100) ≈ 4.6, clamped at ceiling=3.0
        idf_map = {'_total': N, 'program': {'Housing': df}}
        cases, params, total = self._build(
            {'program': 'Housing'},
            idf_map=idf_map,
        )
        # idf_raw = log(1000/10) ≈ 4.605; clamped to 3.0
        # effective = 10.0 * 1.0 * 3.0 = 30.0
        assert abs(total - 30.0) < 0.1

    def test_idf_ceiling_clamps_rare_tags(self):
        """IDF ceiling=3.0 caps very rare tags."""
        N = 10000
        df = 0  # ultra-rare: idf_raw = log(10000/1) ≈ 9.21
        idf_map = {'_total': N, 'program': {'Housing': df}}
        cases, params, total = self._build(
            {'program': 'Housing'},
            idf_map=idf_map,
        )
        # Ceiling = 3.0, so effective = 10.0 * 1.0 * 3.0 = 30.0 (not 92.1)
        assert abs(total - 30.0) < 0.1

    def test_idf_not_below_1(self):
        """IDF is clamped to min 1.0 even for very common tags (log < 1)."""
        N = 100
        df = 90  # very common: idf_raw = log(100/91) ≈ 0.094
        idf_map = {'_total': N, 'program': {'Housing': df}}
        cases, params, total = self._build(
            {'program': 'Housing'},
            idf_map=idf_map,
        )
        # IDF clamped to 1.0, effective = 10.0 * 1.0 * 1.0 = 10.0
        assert total >= 10.0

    def test_priority_boost_increases_top_priority_weight(self):
        """Higher priority axes get boosted weight."""
        filters = {'program': 'Housing', 'style': 'Contemporary'}
        # With program first in priority
        cases_p, params_p, total_p = self._build(
            filters,
            filter_priority=['program', 'style'],
        )
        # Without priority
        cases_n, params_n, total_n = self._build(
            filters,
            filter_priority=[],
        )
        # With priority, total weight should be higher due to boost
        assert total_p > total_n

    def test_none_filter_values_are_skipped(self):
        """None values produce no CASE WHEN clauses."""
        cases, params, total = self._build({
            'program': None,
            'location_country': None,
            'atmosphere': None,
        })
        assert cases == []
        assert params == []

    def test_empty_string_filter_values_are_skipped(self):
        """Empty string values produce no cases (falsy check)."""
        cases, params, total = self._build({
            'program': '',
            'atmosphere': '',
        })
        assert cases == []
        assert params == []

    def test_weight_baked_as_float_not_string_param(self):
        """Weight is baked into SQL string, not a %s param (injection safety)."""
        cases, params, total = self._build({'program': 'Housing'})
        # The %s param should only be the filter value, not the weight
        assert len(params) == 1
        assert params[0] == 'Housing'
        # The weight appears as a literal float in the SQL string
        assert '%s' not in cases[0].replace('= %s', '').replace('ILIKE %s', '')

    def test_axis_names_not_from_user_input(self):
        """Axis names in SQL come from static allowlist, not user-supplied keys.
        A key not in _IDF_SCORE_AXES produces no case even if it has a value.
        """
        from apps.recommendation.engine_filters import _build_idf_score_cases
        base = {
            'unknown_axis': 99.0,
            '_idf_ceiling': 3.0, '_priority_boost': 0.25,
        }
        cases, params, total = _build_idf_score_cases(
            {'unknown_axis': 'malicious_value; DROP TABLE--'},
            base, {'_total': 0}, [],
        )
        # No case should have been generated for unknown_axis
        assert cases == []
        assert 'DROP TABLE' not in str(params)

    def test_full_greater_than_partial_greater_than_none(self):
        """Full-match row > partial-match row > no-match in ranking order."""
        # Simulate scores: full has all axes, partial has only some
        filters = {
            'program': 'Housing',
            'location_country': 'Japan',
            'atmosphere': 'warm',
        }
        # Full match: all axes → highest weight
        cases_full, _, total_full = self._build(filters)
        # Partial: only program
        cases_partial, _, total_partial = self._build({'program': 'Housing'})
        # None: empty
        cases_none, _, total_none = self._build({})

        assert total_full > total_partial > total_none


# ---------------------------------------------------------------------------
# Integration tests: engine.search_by_filters_scored
# ---------------------------------------------------------------------------

class TestSearchByFiltersScored:
    """Mock-based integration tests for engine.search_by_filters_scored."""

    def _make_row(self, bid, program='Housing', style='Contemporary',
                  atmosphere='warm', color_tone='warm',
                  location_country='Japan'):
        """Build a minimal DB row dict for _row_to_card."""
        return {
            'canonical_bld_id': bid,
            'name': f'Building {bid}',
            'architect_names': 'Test Arch',
            'architects_text': 'Test Arch',
            'location_country': location_country,
            'location_city': 'Tokyo',
            'project_year': 2020,
            'program': program,
            'style': style,
            'atmosphere': atmosphere,
            'color_tone': color_tone,
            'material_visual': ['timber'],
            'typology_primary': 'detached house',
            'typology_tags': [],
            'architectural_elements': [],
            'visual_description': 'A warm Japanese house with timber.',
            'covers_by_type': {},
            'all_images': [],
            'display_cover_url': '',
            'cover_image_url_default': '',
            'source_urls': [],
            # CTE columns added by the query
            'tag_score': 25.0,
            'bm25_score': 0.1,
            'final_score': 25.8,
        }

    def _patch_connection_and_run(self, rows, filters, raw_query='', filter_priority=None):
        """Run search_by_filters_scored with mocked buildings DB cursor.

        Patches apps.recommendation.caches.get_corpus_tag_df (the module where
        the function is defined) and the engine connection cursor.
        """
        from apps.recommendation import engine

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.description = [(col,) for col in rows[0].keys()] if rows else []
        mock_cursor.fetchall.return_value = [tuple(r.values()) for r in rows]

        with patch.object(engine.connection, 'cursor', return_value=mock_cursor), \
             patch('apps.recommendation.caches.get_corpus_tag_df',
                   return_value={'_total': 0}):
            return engine.search_by_filters_scored(
                filters, raw_query=raw_query, filter_priority=filter_priority,
                limit=20,
            )

    def test_returns_list_of_cards(self):
        """search_by_filters_scored returns list of ImageCard dicts."""
        row = self._make_row('bld_000001')
        results = self._patch_connection_and_run([row], {'program': 'Housing'})
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]['canonical_bld_id'] == 'bld_000001'

    def test_empty_filters_empty_raw_query_still_runs(self):
        """Empty filters + empty raw_query: query runs (soft-only, bm25=0). No crash."""
        row = self._make_row('bld_000001')
        results = self._patch_connection_and_run([row], {}, raw_query='')
        assert isinstance(results, list)

    def test_raw_query_whitespace_is_safe(self):
        """Whitespace-only raw_query sanitized to empty string - no SQL error."""
        row = self._make_row('bld_000001')
        results = self._patch_connection_and_run([row], {}, raw_query='   ')
        assert isinstance(results, list)

    def test_empty_results_returns_empty_list(self):
        """When cursor returns no rows, empty list is returned (no crash)."""
        from apps.recommendation import engine

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.description = []
        mock_cursor.fetchall.return_value = []

        with patch.object(engine.connection, 'cursor', return_value=mock_cursor), \
             patch('apps.recommendation.caches.get_corpus_tag_df',
                   return_value={'_total': 0}):
            results = engine.search_by_filters_scored(
                {'program': 'Housing'}, raw_query='house', limit=20,
            )
        assert results == []

    def test_db_failure_returns_empty_list(self):
        """On DB exception, search_by_filters_scored returns [] gracefully."""
        from apps.recommendation import engine

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = Exception('DB error')

        with patch.object(engine.connection, 'cursor', return_value=mock_cursor), \
             patch('apps.recommendation.caches.get_corpus_tag_df',
                   return_value={'_total': 0}):
            results = engine.search_by_filters_scored(
                {'program': 'Housing'}, raw_query='house', limit=20,
            )
        assert results == []

    def test_search_by_filters_original_still_exists(self):
        """Original search_by_filters function is not removed (other callers may use it)."""
        from apps.recommendation import engine
        assert callable(engine.search_by_filters)

    def test_idf_map_used_in_query_construction(self):
        """Verify that idf_map with _total > 0 does not crash the function."""
        from apps.recommendation import engine

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: mock_cursor
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.description = []
        mock_cursor.fetchall.return_value = []

        with patch.object(engine.connection, 'cursor', return_value=mock_cursor), \
             patch('apps.recommendation.caches.get_corpus_tag_df',
                   return_value={
                       '_total': 2614,
                       'program': {'Housing': 400, 'Office': 150},
                       'style': {'Contemporary': 600},
                       'atmosphere': {'warm': 200},
                   }):
            results = engine.search_by_filters_scored(
                {'program': 'Housing', 'atmosphere': 'warm'},
                raw_query='warm house',
                filter_priority=['program', 'atmosphere'],
                limit=20,
            )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Tests: settings keys
# ---------------------------------------------------------------------------

class TestSettingsKeys:

    def test_settings_has_llm_search_keys(self):
        """settings.RECOMMENDATION has all llm_search_* tunable keys."""
        from django.conf import settings
        RC = settings.RECOMMENDATION
        assert 'llm_search_topk' in RC
        assert 'llm_search_w_bm25' in RC
        assert 'llm_search_priority_boost' in RC
        assert 'llm_search_idf_ceiling' in RC
        assert 'llm_search_base_weights' in RC
        bw = RC['llm_search_base_weights']
        assert 'program' in bw
        assert 'atmosphere' in bw
        assert 'color_tone' in bw
        assert 'typology_primary' in bw
