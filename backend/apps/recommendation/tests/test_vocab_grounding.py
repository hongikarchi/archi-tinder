"""
test_vocab_grounding.py -- BACK-PARSER-VOCAB-1: DB-grounded vocab + snap tests.

Covers:
  - _snap_to_vocab: exact pass-through, case snap, ism->ist repair, unmatched->None,
    program untouched, None-safe.
  - get_axis_vocab: DB-failure -> snapshot fallback (mock connections['buildings']
    cursor to raise).
  - build_vocab_prompt_block: contains all 5 sections + exact vocab strings.
  - engine_filters: architectural_elements filter produces the EXISTS unnest SQL
    fragment + '%Courtyard%' param in the IDF score cases.
  - Few-shot conformance: every ASSISTANT example JSON in _CHAT_PHASE_SYSTEM_PROMPT
    has axis values inside _VOCAB_SNAPSHOT (regression test keeping few-shots honest).
"""
import json
import re
from unittest.mock import MagicMock, patch

import pytest

from apps.recommendation.services.vocab import _VOCAB_SNAPSHOT, get_axis_vocab
from apps.recommendation.services._prompts import (
    build_vocab_prompt_block,
    _CHAT_PHASE_SYSTEM_PROMPT,
)
from apps.recommendation.services.parse_query import _snap_to_vocab


# ---------------------------------------------------------------------------
# _snap_to_vocab
# ---------------------------------------------------------------------------

class TestSnapToVocab:

    def _patch_vocab(self, monkeypatch, vocab=None):
        """Patch the services facade get_axis_vocab (late-bound _svc access)."""
        from apps.recommendation import services as _svc
        monkeypatch.setattr(_svc, 'get_axis_vocab', lambda: vocab or dict(_VOCAB_SNAPSHOT))

    def test_exact_match_passthrough(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'Brutalist'})
        assert result['style'] == 'Brutalist'

    def test_case_snap_to_canonical(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'brutalist'})
        assert result['style'] == 'Brutalist'

    def test_atmosphere_case_snap(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'atmosphere': 'warm'})
        assert result['atmosphere'] == 'Warm'

    def test_ism_to_ist_repair(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'Brutalism'})
        assert result['style'] == 'Brutalist'

    def test_ism_to_ist_repair_modernism(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'Modernism'})
        assert result['style'] == 'Modernist'

    def test_ism_to_ist_repair_lowercase(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'brutalism'})
        assert result['style'] == 'Brutalist'

    def test_ism_to_ist_repair_all_caps(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'MODERNISM'})
        assert result['style'] == 'Modernist'

    def test_unmatched_value_becomes_none(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': 'Avant-Garde'})
        assert result['style'] is None

    def test_unmatched_typology_becomes_none(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'typology_primary': 'detached house'})
        assert result['typology_primary'] is None

    def test_architectural_elements_case_snap(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'architectural_elements': 'courtyard'})
        assert result['architectural_elements'] == 'Courtyard'

    def test_color_tone_exact(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'color_tone': 'Earth'})
        assert result['color_tone'] == 'Earth'

    def test_program_untouched(self, monkeypatch):
        """program is NOT one of the 5 snapped axes -- passes through unchanged
        even though it is not in the style/atmosphere/etc vocab lists."""
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'program': 'Housing', 'style': 'Brutalist'})
        assert result['program'] == 'Housing'

    def test_program_not_in_snap_axes(self):
        from apps.recommendation.services.parse_query import _SNAP_AXES
        assert 'program' not in _SNAP_AXES

    def test_none_values_are_safe(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({
            'style': None, 'atmosphere': None, 'color_tone': None,
            'typology_primary': None, 'architectural_elements': None,
        })
        assert result['style'] is None
        assert result['atmosphere'] is None
        assert result['color_tone'] is None
        assert result['typology_primary'] is None
        assert result['architectural_elements'] is None

    def test_missing_keys_are_not_added(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'program': 'Housing'})
        assert 'style' not in result
        assert 'atmosphere' not in result

    def test_non_string_value_left_alone(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'year_min': 2000})
        assert result['year_min'] == 2000

    def test_empty_string_left_alone(self, monkeypatch):
        self._patch_vocab(monkeypatch)
        result = _snap_to_vocab({'style': ''})
        assert result['style'] == ''

    def test_get_axis_vocab_failure_does_not_raise(self, monkeypatch):
        """If get_axis_vocab() itself blows up, _snap_to_vocab must not raise."""
        from apps.recommendation import services as _svc

        def _boom():
            raise RuntimeError('vocab fetch failed')

        monkeypatch.setattr(_svc, 'get_axis_vocab', _boom)
        result = _snap_to_vocab({'style': 'Brutalist'})
        # Falls back to returning filters unchanged (no snap applied, no crash)
        assert result['style'] == 'Brutalist'

    def test_empty_axis_vocab_leaves_value_unchanged(self, monkeypatch):
        """When live vocab has no entries at all for an axis, don't null out
        a possibly-valid value on what looks like a data outage."""
        self._patch_vocab(monkeypatch, vocab={
            'style': [], 'atmosphere': [], 'color_tone': [],
            'typology_primary': [], 'architectural_elements': [],
        })
        result = _snap_to_vocab({'style': 'Brutalist'})
        assert result['style'] == 'Brutalist'


# ---------------------------------------------------------------------------
# get_axis_vocab: DB failure -> snapshot fallback
# ---------------------------------------------------------------------------

class TestGetAxisVocabFallback:

    def test_full_connection_failure_falls_back_to_snapshot(self):
        """connections['buildings'] raising entirely -> full snapshot fallback."""
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.side_effect = RuntimeError('DB unreachable')
                result = get_axis_vocab()

        for axis, values in _VOCAB_SNAPSHOT.items():
            assert result[axis] == values

    def test_per_axis_query_failure_falls_back_per_axis(self):
        """One axis's cursor.execute raises -> that axis falls back to snapshot,
        other axes still come from the (mocked) live query."""
        mock_cursor = MagicMock()

        call_log = {'n': 0}

        def _execute(sql, *a, **kw):
            call_log['n'] += 1
            if 'style' in sql:
                raise RuntimeError('style column query failed')

        mock_cursor.execute.side_effect = _execute
        mock_cursor.fetchall.return_value = [('Custom Value',)]

        mock_cm = MagicMock()
        mock_cm.__enter__ = lambda s: mock_cursor
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.return_value.cursor.return_value = mock_cm
                result = get_axis_vocab()

        # style failed -> snapshot fallback for style specifically
        assert result['style'] == _VOCAB_SNAPSHOT['style']
        # other axes succeeded via the (mocked) live query
        assert result['atmosphere'] == ['Custom Value']

    def test_empty_axis_result_falls_back_to_snapshot(self):
        """Live query succeeds but returns zero rows for an axis -> snapshot fallback
        for that axis (per spec: 'any axis coming back empty' triggers fallback)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_cm = MagicMock()
        mock_cm.__enter__ = lambda s: mock_cursor
        mock_cm.__exit__ = MagicMock(return_value=False)

        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = None
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                mock_conns.__getitem__.return_value.cursor.return_value = mock_cm
                result = get_axis_vocab()

        for axis, values in _VOCAB_SNAPSHOT.items():
            assert result[axis] == values

    def test_never_raises(self):
        """get_axis_vocab must never propagate an exception to the caller."""
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.side_effect = RuntimeError('cache backend down')
            # Should not raise even when the cache backend itself is broken.
            try:
                result = get_axis_vocab()
            except Exception as e:  # noqa: BLE001
                pytest.fail(f'get_axis_vocab raised: {e}')
            assert isinstance(result, dict)

    def test_cache_hit_returns_cached_value_without_db_call(self):
        cached_value = {'style': ['CachedStyle']}
        with patch('apps.recommendation.services.vocab.django_cache') as mock_cache:
            mock_cache.get.return_value = cached_value
            with patch('apps.recommendation.services.vocab.connections') as mock_conns:
                result = get_axis_vocab()
                mock_conns.__getitem__.assert_not_called()
        assert result == cached_value


# ---------------------------------------------------------------------------
# build_vocab_prompt_block
# ---------------------------------------------------------------------------

class TestBuildVocabPromptBlock:

    def test_contains_all_5_sections(self):
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        for axis in ('style', 'atmosphere', 'color_tone', 'typology_primary',
                     'architectural_elements'):
            assert f'`{axis}`' in block, f'missing section header for {axis}'

    def test_contains_exact_vocab_strings(self):
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        for axis, values in _VOCAB_SNAPSHOT.items():
            for v in values:
                assert v in block, f'{axis} value {v!r} missing from prompt block'

    def test_color_tone_has_color_word_mapping_rule(self):
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        # spot-check a couple of the required color-word -> tone-family mappings
        assert 'Light' in block
        assert 'Dark' in block

    def test_typology_has_specific_type_to_program_rule(self):
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        assert 'program' in block.lower()

    def test_cannot_map_to_null_rule_present_per_axis(self):
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        assert block.count('null') >= 5

    def test_empty_vocab_returns_empty_string(self):
        assert build_vocab_prompt_block({}) == ''
        assert build_vocab_prompt_block(None) == ''

    def test_token_budget_under_600(self):
        """Prompt growth budget: <= ~600 tokens (approx 4 chars/token)."""
        block = build_vocab_prompt_block(_VOCAB_SNAPSHOT)
        approx_tokens = len(block) / 4
        assert approx_tokens <= 650, f'vocab block ~{approx_tokens:.0f} tokens, budget ~600'


# ---------------------------------------------------------------------------
# engine_filters: architectural_elements EXISTS/unnest scoring
# ---------------------------------------------------------------------------

class TestEngineFiltersArchitecturalElements:

    def test_architectural_elements_produces_exists_unnest_case(self):
        from apps.recommendation.engine_filters import _build_idf_score_cases

        base_weights = {
            'architectural_elements': 4.0,
            '_idf_ceiling': 3.0, '_priority_boost': 0.25,
        }
        cases, params, total = _build_idf_score_cases(
            {'architectural_elements': 'Courtyard'}, base_weights, {'_total': 0}, [],
        )
        assert len(cases) == 1
        assert 'EXISTS' in cases[0]
        assert 'unnest(architectural_elements)' in cases[0]
        assert 'ILIKE %s' in cases[0]
        assert '%Courtyard%' in params
        assert total > 0

    def test_architectural_elements_in_idf_score_axes_allowlist(self):
        from apps.recommendation.engine_filters import _IDF_SCORE_AXES
        assert 'architectural_elements' in _IDF_SCORE_AXES

    def test_architectural_elements_not_in_required_slate(self):
        """architectural_elements must NOT be added to the required-slate set."""
        from apps.recommendation.engine_filters import _REQUIRED_SLATE_FIELDS_SET
        assert 'architectural_elements' not in _REQUIRED_SLATE_FIELDS_SET
        assert len(_REQUIRED_SLATE_FIELDS_SET) == 4

    def test_none_value_produces_no_case(self):
        from apps.recommendation.engine_filters import _build_idf_score_cases
        base_weights = {'architectural_elements': 4.0, '_idf_ceiling': 3.0, '_priority_boost': 0.25}
        cases, params, total = _build_idf_score_cases(
            {'architectural_elements': None}, base_weights, {'_total': 0}, [],
        )
        assert cases == []


# ---------------------------------------------------------------------------
# Few-shot conformance: every ASSISTANT example JSON stays inside _VOCAB_SNAPSHOT
# ---------------------------------------------------------------------------

class TestFewShotConformance:
    """Regression test: keeps few-shot examples honest against the vocab snapshot."""

    _ASSISTANT_LINE_RE = re.compile(r'^ASSISTANT:\s*(\{.*\})\s*$', re.MULTILINE)

    def _iter_examples(self):
        for m in self._ASSISTANT_LINE_RE.finditer(_CHAT_PHASE_SYSTEM_PROMPT):
            yield json.loads(m.group(1))

    def test_at_least_one_example_found(self):
        examples = list(self._iter_examples())
        assert len(examples) >= 5, 'expected multiple ASSISTANT few-shot examples'

    def test_all_examples_parse_as_valid_json(self):
        # _iter_examples itself calls json.loads -- if any example is malformed
        # this raises and fails the test with a clear json.JSONDecodeError.
        examples = list(self._iter_examples())
        assert all(isinstance(e, dict) for e in examples)

    def test_style_values_within_snapshot(self):
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                value = src.get('style')
                if isinstance(value, str) and value:
                    assert value in _VOCAB_SNAPSHOT['style'], (
                        f"style={value!r} not in vocab snapshot (example={example.get('raw_query')!r})"
                    )

    def test_atmosphere_values_within_snapshot(self):
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                value = src.get('atmosphere')
                if isinstance(value, str) and value:
                    assert value in _VOCAB_SNAPSHOT['atmosphere'], (
                        f"atmosphere={value!r} not in vocab snapshot "
                        f"(example={example.get('raw_query')!r})"
                    )

    def test_color_tone_values_within_snapshot(self):
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                value = src.get('color_tone')
                if isinstance(value, str) and value:
                    assert value in _VOCAB_SNAPSHOT['color_tone'], (
                        f"color_tone={value!r} not in vocab snapshot "
                        f"(example={example.get('raw_query')!r})"
                    )

    def test_typology_primary_values_within_snapshot(self):
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                value = src.get('typology_primary')
                if isinstance(value, str) and value:
                    assert value in _VOCAB_SNAPSHOT['typology_primary'], (
                        f"typology_primary={value!r} not in vocab snapshot "
                        f"(example={example.get('raw_query')!r})"
                    )

    def test_architectural_elements_values_within_snapshot(self):
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                value = src.get('architectural_elements')
                if isinstance(value, str) and value:
                    assert value in _VOCAB_SNAPSHOT['architectural_elements'], (
                        f"architectural_elements={value!r} not in vocab snapshot "
                        f"(example={example.get('raw_query')!r})"
                    )

    def test_new_courtyard_example_present(self):
        """The new 중정(courtyard) house few-shot example must be present."""
        found = False
        for example in self._iter_examples():
            for src in self._filter_sources(example):
                if src.get('architectural_elements') == 'Courtyard':
                    found = True
        assert found, 'expected a few-shot example with architectural_elements=Courtyard'

    @staticmethod
    def _filter_sources(example):
        sources = []
        f = example.get('filters')
        if isinstance(f, dict):
            sources.append(f)
        fd = example.get('filter_delta')
        if isinstance(fd, dict) and isinstance(fd.get('set'), dict):
            sources.append(fd['set'])
        return sources
