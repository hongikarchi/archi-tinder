"""
test_taste_facts.py -- BACK-LLM-5: deterministic swipe-fact grounding.

Two layers:
  1. Pure unit tests of apps.recommendation.services.taste_facts
     (compute_taste_facts + its private helpers) -- no DB, no LLM, no Django
     fixtures beyond what backend/conftest.py already sets up at import time.
  2. A handful of generation.generate_persona_report tests with Gemini + the
     buildings DB cursor fully mocked, covering the grounding wiring
     (language -> system prompt, taste_facts attachment, forced-empty
     pattern_paragraph, backward-compatible call shape).
  3. FULL-REPORT-BILINGUAL tests: one Gemini call stores BOTH ko/en text
     under report['i18n'], top-level text tracks the requested language, a
     missing language block is filled from the other (with a warning), empty
     facts force pattern_paragraph='' in both languages, and pre-bilingual
     flat model output is handled without crashing.
"""
import json
import logging
from unittest.mock import MagicMock

from apps.recommendation.services import taste_facts as tf
from apps.recommendation.services.taste_facts import (
    compute_taste_facts,
    extract_axis_values,
)

# Small, explicit rc used by most pure unit tests instead of
# settings.RECOMMENDATION, so each test's numbers are self-contained and
# don't drift if the production defaults change.
_RC = {
    'report_fact_min_shown': 3,
    'report_fact_min_liked': 2,
    'report_fact_min_ratio': 1.5,
    'report_fact_tie_ratio': 0.3,
    'report_fact_max_likes': 3,
    'report_fact_max_dislikes': 1,
    'report_dislike_often': 0.4,
    'report_dislike_mostly': 0.8,
    'report_fact_overlap_max': 0.8,
    'report_fact_smoothing': 1,
}


def _row(bid, **overrides):
    base = {
        'canonical_bld_id': bid,
        'program': None,
        'style': None,
        'atmosphere': None,
        'color_tone': None,
        'material_visual': [],
        'typology_primary': None,
        'typology_tags': [],
        'architectural_elements': [],
        'project_year': None,
        'location_country': None,
        'architect_names': [],
        'architects_text': None,
        'visual_description': None,
    }
    base.update(overrides)
    return base


def _rows_by_id(*rows):
    return {r['canonical_bld_id']: r for r in rows}


def _fact_for(result, axis, value):
    for fact in result['facts']:
        if fact['axis'] == axis and fact['value'] == value:
            return fact
    return None


# ---------------------------------------------------------------------------
# Smoothing + ratio math
# ---------------------------------------------------------------------------

class TestSmoothingAndRatioMath:

    def test_ratio_matches_hand_computed_smoothed_rates(self):
        # style='x' on 3 shown (2 liked, 1 disliked); notA = 2 shown (1 liked,
        # 1 disliked). s=1 (default smoothing).
        #   r_A    = (2+1)/(3+2) = 0.6
        #   r_notA = (1+1)/(2+2) = 0.5
        #   ratio  = 1.2
        rows = _rows_by_id(
            _row('A1', style='x'), _row('A2', style='x'), _row('D1', style='x'),
            _row('A3', style='y'), _row('D2', style='y'),
        )
        result = compute_taste_facts(
            rows, liked_ids=['A1', 'A2', 'A3'], disliked_ids=['D1', 'D2'],
            rc={**_RC, 'report_fact_min_ratio': 1.0},
        )
        fact = _fact_for(result, 'style', 'x')
        assert fact is not None
        assert fact['ratio'] == 1.2
        assert fact['shown'] == 3
        assert fact['liked'] == 2
        assert fact['disliked'] == 1

    def test_high_like_rate_user_still_gets_facts(self):
        """A user who likes ~70% of everything shown must still surface a
        fact for a value that is liked even MORE disproportionately (ratio
        math is relative, not an absolute like-rate gate)."""
        liked_ids = [f'L{i}' for i in range(1, 8)]     # 7 liked
        disliked_ids = [f'D{i}' for i in range(1, 4)]  # 3 disliked -> 70% like rate
        rows = []
        # value 'v' on 5 ids, ALL liked (L1..L5).
        for bid in liked_ids[:5]:
            rows.append(_row(bid, style='v'))
        # remaining 2 liked + 3 disliked carry no style value.
        for bid in liked_ids[5:] + disliked_ids:
            rows.append(_row(bid))
        result = compute_taste_facts(_rows_by_id(*rows), liked_ids, disliked_ids, _RC)
        fact = _fact_for(result, 'style', 'v')
        assert fact is not None, 'expected a LIKE fact for style=v despite high overall like rate'
        assert fact['ratio'] >= _RC['report_fact_min_ratio']
        assert result['summary'] == {'shown': 10, 'liked': 7, 'disliked': 3}


# ---------------------------------------------------------------------------
# LIKE thresholds
# ---------------------------------------------------------------------------

class TestLikeThresholds:
    """Strict (Tier 1) thresholds, tested on the strict core directly."""

    def test_shown_below_min_shown_no_fact(self):
        # style='x' shown on only 2 ids (< min_shown=3), both liked.
        rows = _rows_by_id(
            _row('A1', style='x'), _row('A2', style='x'),
            _row('A3', style='y'), _row('D1', style='y'),
        )
        result = tf._compute_like_dislike_facts(
            rows, liked_ids=['A1', 'A2', 'A3'], disliked_ids=['D1'], rc=_RC,
        )
        assert _fact_for(result, 'style', 'x') is None

    def test_liked_below_min_liked_no_fact(self):
        # style='x' shown 3x but only 1 liked (< min_liked=2).
        rows = _rows_by_id(
            _row('A1', style='x'), _row('D1', style='x'), _row('D2', style='x'),
            _row('A2', style='y'), _row('D3', style='y'),
        )
        result = tf._compute_like_dislike_facts(
            rows, liked_ids=['A1', 'A2'], disliked_ids=['D1', 'D2', 'D3'], rc=_RC,
        )
        assert _fact_for(result, 'style', 'x') is None

    def test_ratio_below_min_ratio_no_fact(self):
        # style='x' liked at the SAME rate as everything else -> ratio ~= 1.0,
        # below min_ratio=1.5.
        rows = _rows_by_id(
            _row('A1', style='x'), _row('A2', style='x'), _row('D1', style='x'),
            _row('A3', style='y'), _row('A4', style='y'), _row('D2', style='y'),
        )
        result = tf._compute_like_dislike_facts(
            rows, liked_ids=['A1', 'A2', 'A3', 'A4'], disliked_ids=['D1', 'D2'], rc=_RC,
        )
        assert _fact_for(result, 'style', 'x') is None


# ---------------------------------------------------------------------------
# DISLIKE requires BOTH the rate gate AND the ratio gate
# ---------------------------------------------------------------------------

class TestDislikeBothConditions:

    def test_heavy_disliker_does_not_get_spurious_dislike_fact(self):
        """A user who dislikes 9/10 shown cards overall must NOT get a
        dislike fact for a value whose relative like-rate isn't actually
        depressed vs. the (already very low) baseline -- rate alone is not
        enough, the ratio gate must also fire."""
        rows = _rows_by_id(
            _row('L1', style='z'), _row('D1', style='z'),
            _row('D2', style='z'), _row('D3', style='z'),
            _row('D4', style='y'), _row('D5', style='y'), _row('D6', style='y'),
            _row('D7', style='y'), _row('D8', style='y'), _row('D9', style='y'),
        )
        result = compute_taste_facts(
            rows,
            liked_ids=['L1'],
            disliked_ids=['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9'],
            rc=_RC,
        )
        # rate = 3/4 = 0.75 >= 0.4 (rate gate passes) but ratio ends up HIGH
        # (not <= 1/1.5) because the single like happens to land on 'z' and
        # the notA baseline (all-disliked 'y') is even more depressed.
        assert _fact_for(result, 'style', 'z') is None

    def test_dislike_word_mostly_at_or_above_080(self):
        # value shown 5x: 1 liked, 4 disliked -> rate 0.8 -> 'mostly'.
        # notA: 5 more, all liked -> ratio qualifies (<=1/1.5).
        rows = _rows_by_id(
            _row('L1', style='m'), _row('D1', style='m'), _row('D2', style='m'),
            _row('D3', style='m'), _row('D4', style='m'),
            _row('L2', style='n'), _row('L3', style='n'), _row('L4', style='n'),
            _row('L5', style='n'), _row('L6', style='n'),
        )
        liked = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6']
        disliked = ['D1', 'D2', 'D3', 'D4']
        result = compute_taste_facts(rows, liked, disliked, _RC)
        fact = _fact_for(result, 'style', 'm')
        assert fact is not None
        assert fact['polarity'] == 'dislike'
        assert fact['dislike_word'] == 'mostly'
        assert fact['ratio'] == round(1 / 3, 2)

    def test_dislike_word_often_below_080(self):
        # value shown 5x: 2 liked, 3 disliked -> rate 0.6 -> 'often'.
        # notA: 5 more (4 liked, 1 disliked) -> ratio 0.6 qualifies (<=1/1.5).
        rows = _rows_by_id(
            _row('L1', style='o'), _row('L2', style='o'),
            _row('D1', style='o'), _row('D2', style='o'), _row('D3', style='o'),
            _row('L3', style='p'), _row('L4', style='p'), _row('L5', style='p'),
            _row('L6', style='p'), _row('D4', style='p'),
        )
        liked = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6']
        disliked = ['D1', 'D2', 'D3', 'D4']
        result = compute_taste_facts(rows, liked, disliked, _RC)
        fact = _fact_for(result, 'style', 'o')
        assert fact is not None
        assert fact['dislike_word'] == 'often'
        assert fact['ratio'] == 0.6


# ---------------------------------------------------------------------------
# Selection: tie-break, one-per-axis, overlap dedupe, caps
# ---------------------------------------------------------------------------

class TestSelection:

    def test_tie_break_prefers_more_support_within_tie_ratio(self):
        strong_support = {'ratio': 2.0, 'liked': 5, 'disliked': 0}
        weak_support = {'ratio': 2.1, 'liked': 2, 'disliked': 0}
        # |2.1 - 2.0| = 0.1 <= tie_ratio(0.3) -> support decides, not raw ratio.
        assert tf._tie_aware_cmp(weak_support, strong_support, 0.3, 'liked', ascending=False) > 0
        assert tf._tie_aware_cmp(strong_support, weak_support, 0.3, 'liked', ascending=False) < 0

    def test_no_tie_break_outside_tie_ratio(self):
        higher_ratio = {'ratio': 3.0, 'liked': 1, 'disliked': 0}
        lower_ratio = {'ratio': 1.5, 'liked': 10, 'disliked': 0}
        # diff = 1.5 > tie_ratio(0.3) -> raw ratio wins regardless of support.
        assert tf._tie_aware_cmp(higher_ratio, lower_ratio, 0.3, 'liked', ascending=False) < 0

    def test_one_fact_per_axis(self):
        candidates = [
            {'axis': 'style', 'value': 'a', 'building_ids': ['1', '2']},
            {'axis': 'style', 'value': 'b', 'building_ids': ['3', '4']},
            {'axis': 'atmosphere', 'value': 'c', 'building_ids': ['5', '6']},
        ]
        selected = tf._select(candidates, cap=3, overlap_max=0.8, used_axes=set(), already_selected=[])
        axes = [c['axis'] for c in selected]
        assert axes == ['style', 'atmosphere']  # second 'style' candidate skipped

    def test_overlap_dedupe_drops_80pct_shared_support(self):
        candidates = [
            {'axis': 'style', 'value': 'a', 'building_ids': ['1', '2', '3', '4']},
            # shares 4 of its 5 ids with the first -> overlap = 4/min(4,5)=1.0 >= 0.8
            {'axis': 'atmosphere', 'value': 'b', 'building_ids': ['1', '2', '3', '4', '5']},
        ]
        selected = tf._select(candidates, cap=3, overlap_max=0.8, used_axes=set(), already_selected=[])
        assert len(selected) == 1
        assert selected[0]['value'] == 'a'

    def test_overlap_below_threshold_keeps_both(self):
        candidates = [
            {'axis': 'style', 'value': 'a', 'building_ids': ['1', '2', '3', '4']},
            # overlap = 1/min(4,4) = 0.25 < 0.8 -> keep both
            {'axis': 'atmosphere', 'value': 'b', 'building_ids': ['4', '5', '6', '7']},
        ]
        selected = tf._select(candidates, cap=3, overlap_max=0.8, used_axes=set(), already_selected=[])
        assert len(selected) == 2

    def test_cap_limits_selection_count(self):
        candidates = [
            {'axis': f'axis{i}', 'value': 'v', 'building_ids': [str(i)]}
            for i in range(5)
        ]
        selected = tf._select(candidates, cap=3, overlap_max=0.8, used_axes=set(), already_selected=[])
        assert len(selected) == 3

    def test_like_cap_max_likes_3_dislike_cap_max_dislikes_1(self):
        # 4 independent axes; each axis has a 'v' value (all 3 liked) and a
        # 'w' value (all 3 disliked). Every axis independently qualifies as
        # BOTH a like candidate (its 'v') and a dislike candidate (its 'w'),
        # with near-identical ratios (well within tie_ratio of each other) and
        # equal support -- so selection falls back to the stable AXES base
        # order and caps at max_likes=3 / max_dislikes=1 respectively.
        rows = []
        liked, disliked = [], []
        for axis_name in ('style', 'atmosphere', 'color_tone', 'program'):
            v_ids = [f'{axis_name}_v{n}' for n in range(3)]
            w_ids = [f'{axis_name}_w{n}' for n in range(3)]
            for bid in v_ids:
                rows.append(_row(bid, **{axis_name: 'v'}))
            for bid in w_ids:
                rows.append(_row(bid, **{axis_name: 'w'}))
            liked.extend(v_ids)
            disliked.extend(w_ids)
        result = compute_taste_facts(_rows_by_id(*rows), liked, disliked, _RC)
        like_facts = [f for f in result['facts'] if f['polarity'] == 'like']
        dislike_facts = [f for f in result['facts'] if f['polarity'] == 'dislike']
        assert len(like_facts) == _RC['report_fact_max_likes']
        assert len(dislike_facts) == _RC['report_fact_max_dislikes']


# ---------------------------------------------------------------------------
# ratio_display floor-to-0.5
# ---------------------------------------------------------------------------

class TestRatioDisplay:

    def test_floors_to_nearest_half_step(self):
        assert tf._ratio_display(1.7) == 1.5
        assert tf._ratio_display(2.3) == 2.0
        assert tf._ratio_display(3.8) == 3.5
        assert tf._ratio_display(1.5) == 1.5
        assert tf._ratio_display(2.0) == 2.0


# ---------------------------------------------------------------------------
# Misc extraction / partition rules
# ---------------------------------------------------------------------------

class TestExtractionRules:

    def test_id_in_both_liked_and_disliked_counts_as_like(self):
        # X appears in BOTH liked_ids and disliked_ids -> must resolve to
        # liked-only. Y carries a DIFFERENT style so it can't contaminate the
        # 'dual' bucket -- isolates the both-lists resolution cleanly.
        rows = _rows_by_id(_row('X', style='dual'), _row('Y', style='other'))
        rc = {**_RC, 'report_fact_min_shown': 1, 'report_fact_min_liked': 1, 'report_fact_min_ratio': 1.0}
        result = compute_taste_facts(rows, liked_ids=['X'], disliked_ids=['X', 'Y'], rc=rc)
        assert result['summary'] == {'shown': 2, 'liked': 1, 'disliked': 1}
        fact = _fact_for(result, 'style', 'dual')
        assert fact is not None
        assert fact['liked'] == 1
        assert fact['disliked'] == 0

    def test_case_and_whitespace_normalisation(self):
        rows = _rows_by_id(
            _row('A1', style=' Brutalist'), _row('A2', style='BRUTALIST'),
            _row('D1', style='other'),
        )
        rc = {**_RC, 'report_fact_min_shown': 2, 'report_fact_min_liked': 2, 'report_fact_min_ratio': 1.0}
        result = compute_taste_facts(rows, liked_ids=['A1', 'A2'], disliked_ids=['D1'], rc=rc)
        fact = _fact_for(result, 'style', 'brutalist')
        assert fact is not None
        assert fact['shown'] == 2

    def test_null_project_year_skipped_for_decade(self):
        assert extract_axis_values({'project_year': None}, 'decade') == set()
        assert extract_axis_values({'project_year': 1995}, 'decade') == {'1990s'}
        assert extract_axis_values({'project_year': 2001}, 'decade') == {'2000s'}

    def test_others_rarely_liked_flag(self):
        # value 'v': 2 liked, 0 disliked. notA: 0 liked, 2 disliked ->
        # liked_notA == 0 and shown_notA(2) >= min_shown(2).
        rows = _rows_by_id(
            _row('L1', style='v'), _row('L2', style='v'),
            _row('D1', style='w'), _row('D2', style='w'),
        )
        rc = {**_RC, 'report_fact_min_shown': 2, 'report_fact_min_liked': 2, 'report_fact_min_ratio': 1.0}
        result = compute_taste_facts(rows, liked_ids=['L1', 'L2'], disliked_ids=['D1', 'D2'], rc=rc)
        fact = _fact_for(result, 'style', 'v')
        assert fact is not None
        assert fact['others_rarely_liked'] is True


# ---------------------------------------------------------------------------
# generation.generate_persona_report wiring (Gemini + DB fully mocked)
# ---------------------------------------------------------------------------

def _mock_cursor(monkeypatch, rows):
    from apps.recommendation import services

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = lambda s: MagicMock()
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(services, 'connection', mock_conn)
    monkeypatch.setattr(services, '_dictfetchall', lambda cur: rows)
    monkeypatch.setattr(services, '_get_gemini_client', lambda: MagicMock())
    return services


def _fake_gemini_response(payload):
    resp = MagicMock()
    resp.text = json.dumps(payload)
    return resp


_STUB_REPORT = {
    'persona_type': 'The Minimalist',
    'one_liner': 'Clean concrete lines.',
    'pattern_paragraph': 'stub pattern text',
    'description': 'stub description text',
    'dominant_programs': ['Housing'],
    'dominant_styles': ['Modernist'],
    'dominant_materials': ['concrete'],
}

# FULL-REPORT-BILINGUAL: the new shape -- one Gemini call, both languages.
_STUB_BILINGUAL_REPORT = {
    'ko': {
        'persona_type': '미니멀리스트',
        'one_liner': '노출 콘크리트 건물을 고르는 미니멀리스트예요.',
        'pattern_paragraph': '보여드린 건물 중 노출 콘크리트 건물을 자주 고르셨어요.',
        'description': '차갑고 단단한 재료를 절제된 형태로 쓴 건물에 눈이 가는 편이에요.',
    },
    'en': {
        'persona_type': 'The Minimalist',
        'one_liner': 'Chooses buildings with exposed concrete.',
        'pattern_paragraph': 'Among the buildings shown, you often chose exposed concrete ones.',
        'description': 'You tend to be drawn to cold, solid materials used in a restrained form.',
    },
    'dominant_programs': ['Housing'],
    'dominant_styles': ['Modernist'],
    'dominant_materials': ['concrete'],
}


class TestGeneratePersonaReportGrounding:

    def test_language_passed_into_system_prompt(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [
            _row('B1', style='x'), _row('B2', style='y'),
        ])
        captured = {}

        def fake_build_prompt(language):
            captured['language'] = language
            return 'SYSTEM_PROMPT_EN'

        def fake_generate(*args, **kwargs):
            assert kwargs['config'].system_instruction == 'SYSTEM_PROMPT_EN'
            return _fake_gemini_response(_STUB_REPORT)

        monkeypatch.setattr(generation, 'build_persona_prompt', fake_build_prompt)
        monkeypatch.setattr(services, 'generate_content_with_fallback', fake_generate)

        generation.generate_persona_report(['B1'], ['B2'], language='en')
        assert captured['language'] == 'en'

    def test_taste_facts_attached_and_grounded(self, monkeypatch):
        from apps.recommendation.services import generation

        rows = [
            _row('B1', style='brutalist'), _row('B2', style='brutalist'),
            _row('B3', style='brutalist'), _row('B4', style='other'),
            _row('B5', style='other'), _row('B6', style='other'),
        ]
        services = _mock_cursor(monkeypatch, rows)
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_REPORT),
        )

        report = generation.generate_persona_report(
            ['B1', 'B2', 'B3', 'B4'], ['B5', 'B6'], language='ko',
        )

        assert 'taste_facts' in report
        facts = report['taste_facts']['facts']
        style_fact = next((f for f in facts if f['axis'] == 'style' and f['value'] == 'brutalist'), None)
        assert style_fact is not None
        assert style_fact['polarity'] == 'like'
        assert style_fact['shown'] == 3
        assert style_fact['liked'] == 3
        assert style_fact['disliked'] == 0
        assert style_fact['ratio'] == 2.0
        assert sorted(style_fact['building_ids']) == ['B1', 'B2', 'B3']
        # facts non-empty -> pattern_paragraph is NOT clobbered.
        assert report['pattern_paragraph'] == 'stub pattern text'

    def test_dislike_fact_building_ids_stripped_from_report(self, monkeypatch):
        """SECURITY REGRESSION (fix cycle 2026-09-26): a dislike fact's
        building_ids are disliked canonical_bld_ids. project.final_report is
        served by ProjectDetailView (AllowAny for public boards) via
        ProjectSerializer, and serializers.py's `disliked_ids` invariant says
        those ids must never reach ANY caller, owner included. Confirm
        generate_persona_report strips building_ids from dislike-polarity
        facts before attaching taste_facts to the report, while like-polarity
        facts (whose building_ids are liked ids, already exposed elsewhere)
        keep theirs.
        """
        from apps.recommendation.services import generation

        rows = [
            _row('B1', style='other'), _row('B2', style='other'), _row('B3', style='other'),
            _row('B4', style='brutalist'), _row('B5', style='brutalist'), _row('B6', style='brutalist'),
        ]
        services = _mock_cursor(monkeypatch, rows)
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_REPORT),
        )

        report = generation.generate_persona_report(
            ['B1', 'B2', 'B3'], ['B4', 'B5', 'B6'], language='ko',
        )

        facts = report['taste_facts']['facts']
        dislike_fact = next((f for f in facts if f['polarity'] == 'dislike'), None)
        assert dislike_fact is not None
        assert 'building_ids' not in dislike_fact
        # No disliked id anywhere in the serialised report at all.
        blob = json.dumps(report)
        for disliked_id in ('B4', 'B5', 'B6'):
            assert disliked_id not in blob
        # Like facts are unaffected -- their building_ids are liked ids.
        like_fact = next((f for f in facts if f['polarity'] == 'like'), None)
        assert like_fact is not None
        assert sorted(like_fact['building_ids']) == ['B1', 'B2', 'B3']

    def test_pattern_paragraph_kept_in_interpretive_mode_when_no_facts(self, monkeypatch):
        # Product decision 2026-10-25: no forced blanking; digit-free LLM text is kept.
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_REPORT),
        )

        report = generation.generate_persona_report(['B1'])
        assert report['taste_facts']['facts'] == []
        assert report['pattern_paragraph'] == 'stub pattern text'
        assert report['pattern_source'] == 'interpretive'

    def test_backward_compatible_call_with_liked_ids_only(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_REPORT),
        )

        report = generation.generate_persona_report(['B1'])
        assert report['persona_type'] == 'The Minimalist'
        assert 'taste_facts' in report


class TestGeneratePersonaReportBilingual:
    """FULL-REPORT-BILINGUAL: one Gemini call, ko+en stored under i18n."""

    def test_both_languages_stored_under_i18n_and_top_level_matches_requested_language(self, monkeypatch):
        from apps.recommendation.services import generation

        rows = [
            _row('B1', style='brutalist'), _row('B2', style='brutalist'),
            _row('B3', style='brutalist'), _row('B4', style='other'),
            _row('B5', style='other'), _row('B6', style='other'),
        ]
        services = _mock_cursor(monkeypatch, rows)
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_BILINGUAL_REPORT),
        )

        report = generation.generate_persona_report(
            ['B1', 'B2', 'B3', 'B4'], ['B5', 'B6'], language='en',
        )

        assert report['i18n']['ko']['persona_type'] == '미니멀리스트'
        assert report['i18n']['en']['persona_type'] == 'The Minimalist'
        assert report['i18n']['ko']['pattern_paragraph'] == _STUB_BILINGUAL_REPORT['ko']['pattern_paragraph']
        assert report['i18n']['en']['pattern_paragraph'] == _STUB_BILINGUAL_REPORT['en']['pattern_paragraph']
        # Top-level (backward-compat) fields track the REQUESTED language ('en').
        assert report['persona_type'] == 'The Minimalist'
        assert report['one_liner'] == _STUB_BILINGUAL_REPORT['en']['one_liner']
        # dominant_* stay single top-level English arrays, unaffected by i18n split.
        assert report['dominant_programs'] == ['Housing']
        assert report['dominant_styles'] == ['Modernist']
        assert report['dominant_materials'] == ['concrete']

    def test_top_level_defaults_to_korean_when_language_omitted(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_BILINGUAL_REPORT),
        )

        report = generation.generate_persona_report(['B1'])  # language defaults to 'ko'
        assert report['persona_type'] == '미니멀리스트'
        assert report['i18n']['en']['persona_type'] == 'The Minimalist'

    def test_missing_language_block_filled_from_other_with_warning(self, monkeypatch, caplog):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        malformed_payload = {
            'en': _STUB_BILINGUAL_REPORT['en'],
            'dominant_programs': ['Housing'],
            'dominant_styles': ['Modernist'],
            'dominant_materials': ['concrete'],
            # 'ko' block entirely missing -- model ignored the bilingual instruction.
        }
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(malformed_payload),
        )

        # settings.LOGGING sets the 'apps' logger propagate=False, so caplog's root
        # handler misses the record; attach caplog's handler to the emitting logger.
        rec_logger = logging.getLogger('apps.recommendation')
        rec_logger.addHandler(caplog.handler)
        try:
            report = generation.generate_persona_report(['B1'], language='en')
        finally:
            rec_logger.removeHandler(caplog.handler)

        assert report['i18n']['ko'] == report['i18n']['en']
        assert report['i18n']['ko']['persona_type'] == 'The Minimalist'
        assert any('ko block missing' in record.message for record in caplog.records)

    def test_empty_facts_keeps_llm_pattern_paragraph_in_both_languages(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_BILINGUAL_REPORT),
        )

        report = generation.generate_persona_report(['B1'])

        assert report['taste_facts']['facts'] == []
        # _STUB_BILINGUAL_REPORT has no digits -> passes the interpretive guard.
        assert report['i18n']['ko']['pattern_paragraph'] == _STUB_BILINGUAL_REPORT['ko']['pattern_paragraph']
        assert report['i18n']['en']['pattern_paragraph'] == _STUB_BILINGUAL_REPORT['en']['pattern_paragraph']
        assert report['i18n']['ko']['description'] == _STUB_BILINGUAL_REPORT['ko']['description']
        assert report['i18n']['en']['description'] == _STUB_BILINGUAL_REPORT['en']['description']

    def test_old_flat_model_output_treated_as_requested_language_only(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
        monkeypatch.setattr(
            services, 'generate_content_with_fallback',
            lambda *a, **kw: _fake_gemini_response(_STUB_REPORT),
        )

        report = generation.generate_persona_report(['B1'], language='ko')

        assert report['persona_type'] == 'The Minimalist'
        # Old flat output only ever named one language -- both i18n slots get
        # filled with that same content rather than crashing on a missing key.
        assert report['i18n']['ko']['persona_type'] == 'The Minimalist'
        assert report['i18n']['en']['persona_type'] == 'The Minimalist'


# ---------------------------------------------------------------------------
# Tiered pattern grounding (2026-10-25): strict -> relaxed -> composition -> interpretive
# ---------------------------------------------------------------------------

_RC_TIERED = {
    **_RC,
    'report_fact_relaxed_min_shown': 2,
    'report_fact_relaxed_min_liked': 2,
    'report_fact_relaxed_min_ratio': 1.2,
}


class TestTieredFacts:

    def test_tier1_strict_unchanged(self):
        rows = _rows_by_id(
            _row('B1', style='brutalist'), _row('B2', style='brutalist'),
            _row('B3', style='brutalist'), _row('B4', style='other'),
            _row('B5', style='other'), _row('B6', style='other'),
        )
        result = compute_taste_facts(rows, ['B1', 'B2', 'B3', 'B4'], ['B5', 'B6'], _RC_TIERED)
        assert result['tier'] == 'strict'
        assert _fact_for(result, 'style', 'brutalist')['polarity'] == 'like'

    def test_tier2_relaxed_when_strict_empty(self):
        # style=x shown 2 (< strict min_shown 3), both liked; 2 others shown, 0 liked.
        rows = _rows_by_id(
            _row('B1', style='x'), _row('B2', style='x'),
            _row('B3', style='y'), _row('B4', style='z'),
        )
        result = compute_taste_facts(rows, ['B1', 'B2'], ['B3', 'B4'], _RC_TIERED)
        assert result['tier'] == 'relaxed'
        fact = _fact_for(result, 'style', 'x')
        assert fact is not None and fact['polarity'] == 'like'
        assert fact['shown'] == 2 and fact['liked'] == 2

    def test_tier3_composition_counts_are_real(self):
        # Liked and disliked all share style=x -> ratio 1, no like/dislike fact.
        rows = _rows_by_id(
            _row('B1', style='x'), _row('B2', style='x'), _row('B3', style='x'),
            _row('D1', style='x'), _row('D2', style='x'), _row('D3', style='x'),
        )
        result = compute_taste_facts(rows, ['B1', 'B2', 'B3'], ['D1', 'D2', 'D3'], _RC_TIERED)
        assert result['tier'] == 'composition'
        facts = result['facts']
        assert len(facts) == 1
        top = facts[0]
        assert top['polarity'] == 'composition'
        assert (top['axis'], top['value']) == ('style', 'x')
        assert top['liked_with'] == 3 and top['liked_total'] == 3
        assert top['liked_with'] == len(top['building_ids'])
        assert not any(bid.startswith('D') for bid in top['building_ids'])

    def test_tier4_none_when_single_like(self):
        rows = _rows_by_id(_row('B1', style='x'))
        result = compute_taste_facts(rows, ['B1'], [], _RC_TIERED)
        assert result['tier'] == 'none' and result['facts'] == []

    def test_tier4_none_when_no_shared_feature(self):
        rows = _rows_by_id(_row('B1', style='x'), _row('B2', style='y'))
        result = compute_taste_facts(rows, ['B1', 'B2'], [], _RC_TIERED)
        assert result['tier'] == 'none'


class TestPatternText:

    def test_composition_templates_exact(self):
        from apps.recommendation.services._pattern_text import build_fact_paragraph

        fact = {'polarity': 'composition', 'axis': 'style', 'value': 'brutalist', 'liked_with': 3, 'liked_total': 4}
        assert build_fact_paragraph([fact], 'ko') == '좋아요한 4곳 중 3곳이 brutalist 스타일의 건물이었어요.'
        assert build_fact_paragraph([fact], 'en') == '3 of the 4 buildings you liked had a brutalist style.'

    def test_interpretive_fallback_has_no_digits_and_generic_when_no_tags(self):
        from apps.recommendation.services._pattern_text import (
            GENERIC_EN, GENERIC_KO, build_fallback_paragraph,
        )

        freq = {'style': {'brutalist': 2}, 'atmosphere': {'calm': 1}}
        ko, kind = build_fallback_paragraph([], freq, 'ko')
        en, _ = build_fallback_paragraph([], freq, 'en')
        assert kind == 'interpretive'
        assert ko == '고르신 건물들을 보면 brutalist, calm 쪽에 끌리는 취향이 보여요.'
        assert en == 'Looking at the buildings you chose, you seem drawn to brutalist and calm.'
        assert build_fallback_paragraph([], {}, 'ko') == (GENERIC_KO, 'generic')
        assert build_fallback_paragraph([], {}, 'en') == (GENERIC_EN, 'generic')

    def test_like_dislike_templates_and_two_number_cap(self):
        from apps.recommendation.services._pattern_text import build_fact_paragraph

        likes = [
            {'polarity': 'like', 'axis': 'style', 'value': f'v{i}', 'ratio_display': 2, 'others_rarely_liked': False}
            for i in range(3)
        ]
        dis = {'polarity': 'dislike', 'axis': 'program', 'value': 'office', 'dislike_word': 'mostly'}
        ko = build_fact_paragraph(likes + [dis], 'ko')
        assert ko.startswith('보여드린 건물 중 ')
        assert ko.count('약 2배') == 2
        assert '대부분 넘기셨어요' in ko
        en = build_fact_paragraph(likes + [dis], 'en')
        assert en.startswith('Among the buildings shown, ')
        assert en.count('about 2x') == 2
        assert 'mostly swiped past' in en

    def test_qualitative_only_like_fact_has_no_number(self):
        from apps.recommendation.services._pattern_text import build_fact_paragraph

        fact = {'polarity': 'like', 'axis': 'style', 'value': 'x', 'ratio_display': 1, 'qualitative_only': True}
        assert not any(ch.isdigit() for ch in build_fact_paragraph([fact], 'ko'))
        assert '1x' not in build_fact_paragraph([fact], 'en')


def _stub_llm(monkeypatch, services, generation, ko_pattern, en_pattern):
    monkeypatch.setattr(generation, 'build_persona_prompt', lambda language: 'SYS')
    payload = json.loads(json.dumps(_STUB_BILINGUAL_REPORT))
    payload['ko']['pattern_paragraph'] = ko_pattern
    payload['en']['pattern_paragraph'] = en_pattern
    captured = {}

    def fake_generate(*args, **kwargs):
        captured['contents'] = kwargs['contents']
        return _fake_gemini_response(payload)

    monkeypatch.setattr(services, 'generate_content_with_fallback', fake_generate)
    return captured


_COMPOSITION_ROWS = [
    _row('B1', style='x'), _row('B2', style='x'), _row('B3', style='x'),
    _row('D1', style='x'), _row('D2', style='x'), _row('D3', style='x'),
]
_COMP_ARGS = (['B1', 'B2', 'B3'], ['D1', 'D2', 'D3'])


class TestGeneratePersonaReportTiers:

    def test_facts_path_pattern_source_and_mode(self, monkeypatch):
        from apps.recommendation.services import generation

        rows = [
            _row('B1', style='brutalist'), _row('B2', style='brutalist'),
            _row('B3', style='brutalist'), _row('B4', style='other'),
            _row('B5', style='other'), _row('B6', style='other'),
        ]
        services = _mock_cursor(monkeypatch, rows)
        captured = _stub_llm(monkeypatch, services, generation, 'KO text', 'EN text')
        report = generation.generate_persona_report(['B1', 'B2', 'B3', 'B4'], ['B5', 'B6'])
        assert json.loads(captured['contents'])['pattern_mode'] == 'facts'
        assert report['pattern_source'] == 'facts'
        assert report['taste_facts']['tier'] == 'strict'
        assert report['i18n']['ko']['pattern_paragraph'] == 'KO text'

    def test_relaxed_path(self, monkeypatch):
        from apps.recommendation.services import generation

        rows = [_row('B1', style='x'), _row('B2', style='x'), _row('B3', style='y'), _row('B4', style='z')]
        services = _mock_cursor(monkeypatch, rows)
        captured = _stub_llm(monkeypatch, services, generation, 'KO text', 'EN text')
        report = generation.generate_persona_report(['B1', 'B2'], ['B3', 'B4'])
        assert json.loads(captured['contents'])['pattern_mode'] == 'facts'
        assert report['pattern_source'] == 'relaxed'
        assert report['taste_facts']['tier'] == 'relaxed'

    def test_composition_path_numbers_real(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, _COMPOSITION_ROWS)
        captured = _stub_llm(
            monkeypatch, services, generation,
            '좋아요한 3곳 중 3곳이 x 스타일의 건물이었어요.', '3 of the 3 buildings you liked had a x style.',
        )
        report = generation.generate_persona_report(*_COMP_ARGS)
        sent = json.loads(captured['contents'])
        assert sent['pattern_mode'] == 'composition'
        assert sent['facts'][0]['liked_with'] == 3 and sent['facts'][0]['liked_total'] == 3
        assert report['pattern_source'] == 'composition'
        assert report['taste_facts']['facts'][0]['polarity'] == 'composition'
        assert 'D1' not in json.dumps(report)

    def test_composition_llm_with_invented_number_replaced(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, _COMPOSITION_ROWS)
        _stub_llm(monkeypatch, services, generation, '좋아요한 3곳 중 9곳이 x 건물이었어요.', 'ok no digits')
        report = generation.generate_persona_report(*_COMP_ARGS)
        assert report['i18n']['ko']['pattern_paragraph'] == '좋아요한 3곳 중 3곳이 x 스타일의 건물이었어요.'
        assert report['i18n']['en']['pattern_paragraph'] == 'ok no digits'
        assert report['pattern_source'] == 'fallback'

    def test_interpretive_path_prompt_mode_and_digit_guard(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        captured = _stub_llm(
            monkeypatch, services, generation,
            '고르신 건물들을 보면 3곳이 x예요.', 'Looking at the buildings you chose, you seem drawn to x.',
        )
        report = generation.generate_persona_report(['B1'])
        assert json.loads(captured['contents'])['pattern_mode'] == 'interpretive'
        for key in ('ko', 'en'):
            assert not any(ch.isdigit() for ch in report['i18n'][key]['pattern_paragraph'])
        assert report['i18n']['ko']['pattern_paragraph'] == '고르신 건물들을 보면 x 쪽에 끌리는 취향이 보여요.'
        assert report['i18n']['en']['pattern_paragraph'].startswith('Looking at the buildings you chose')
        assert report['pattern_source'] == 'fallback'

    def test_interpretive_clean_llm_text_kept(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        _stub_llm(monkeypatch, services, generation, '고르신 건물들을 보면 x에 끌려요.', 'Looking at the buildings you chose, x.')
        report = generation.generate_persona_report(['B1'])
        assert report['pattern_source'] == 'interpretive'
        assert report['pattern_paragraph'] == '고르신 건물들을 보면 x에 끌려요.'

    def test_blank_llm_fallback_both_languages_from_facts(self, monkeypatch, caplog):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, _COMPOSITION_ROWS)
        _stub_llm(monkeypatch, services, generation, '', '   ')
        rec_logger = logging.getLogger('apps.recommendation')
        rec_logger.addHandler(caplog.handler)
        try:
            report = generation.generate_persona_report(*_COMP_ARGS)
        finally:
            rec_logger.removeHandler(caplog.handler)
        assert report['i18n']['ko']['pattern_paragraph'] == '좋아요한 3곳 중 3곳이 x 스타일의 건물이었어요.'
        assert report['i18n']['en']['pattern_paragraph'] == '3 of the 3 buildings you liked had a x style.'
        assert report['pattern_source'] == 'fallback'
        assert any('deterministic fallback' in r.message for r in caplog.records)

    def test_blank_one_language_keeps_other_and_fills_blank(self, monkeypatch):
        from apps.recommendation.services import generation

        services = _mock_cursor(monkeypatch, [_row('B1', style='x')])
        _stub_llm(monkeypatch, services, generation, '', 'Looking at the buildings you chose, you like x.')
        report = generation.generate_persona_report(['B1'], language='en')
        assert report['i18n']['en']['pattern_paragraph'] == 'Looking at the buildings you chose, you like x.'
        assert report['i18n']['ko']['pattern_paragraph'] == '고르신 건물들을 보면 x 쪽에 끌리는 취향이 보여요.'
        assert report['pattern_paragraph'] == report['i18n']['en']['pattern_paragraph']

    def test_blank_llm_no_tags_uses_generic(self, monkeypatch):
        from apps.recommendation.services import generation
        from apps.recommendation.services._pattern_text import GENERIC_EN, GENERIC_KO

        services = _mock_cursor(monkeypatch, [_row('B1')])
        _stub_llm(monkeypatch, services, generation, '', '')
        report = generation.generate_persona_report(['B1'])
        assert report['i18n']['ko']['pattern_paragraph'] == GENERIC_KO
        assert report['i18n']['en']['pattern_paragraph'] == GENERIC_EN

    def test_blank_llm_with_dislike_fact_strips_ids(self, monkeypatch):
        from apps.recommendation.services import generation

        rows = [
            _row('B1', style='other'), _row('B2', style='other'), _row('B3', style='other'),
            _row('B4', style='brutalist'), _row('B5', style='brutalist'), _row('B6', style='brutalist'),
        ]
        services = _mock_cursor(monkeypatch, rows)
        _stub_llm(monkeypatch, services, generation, '', '')
        report = generation.generate_persona_report(['B1', 'B2', 'B3'], ['B4', 'B5', 'B6'])
        blob = json.dumps(report)
        for disliked_id in ('B4', 'B5', 'B6'):
            assert disliked_id not in blob
        assert '대부분 넘기셨어요' in report['i18n']['ko']['pattern_paragraph']
