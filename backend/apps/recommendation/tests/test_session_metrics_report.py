"""
test_session_metrics_report.py — coverage for the session_metrics_report
management command (ANALYTICS-1).

Covers:
  - Empty DB: all three sections report zero/empty in both text and --json
    modes; --json output parses as valid JSON.
  - Seeded fixtures: bookmark provenance/rank-zone aggregates (incl. a
    malformed row with no provenance dict), image_load per-domain outcome +
    load_ms percentiles, confidence_update distributions, swipe per-session
    distribution / direction mix / cache_hit rate / db_call_count.
  - --days window excludes events created outside the window.
  - --json mode: json.loads succeeds and top-level keys match.
  - BACK-PERFORMANCE-5a (additive): _percentile math, per-stage timing
    aggregation, cache_hit split, session-position warmup buckets,
    malformed timing_breakdown exclusion + count.
"""
import io
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.recommendation.management.commands.session_metrics_report import (
    _cache_split_percentiles,
    _extract_timing,
    _percentile,
    _position_buckets,
    _stage_percentiles,
)
from apps.recommendation.models import AnalysisSession, Project, SessionEvent


def _run(*args):
    out = io.StringIO()
    call_command('session_metrics_report', *args, stdout=out)
    return out.getvalue()


# ── Empty DB ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_empty_db_text_mode_reports_warnings():
    output = _run()
    assert 'no bookmark events in window' in output
    assert 'no image_load events in window' in output
    assert 'no confidence_update events in window' in output
    assert 'no swipe events in window' in output


@pytest.mark.django_db
def test_empty_db_json_mode_parses_and_zero():
    output = _run('--json')
    data = json.loads(output)
    assert data['window_days'] == 30
    assert data['bookmarks']['total'] == 0
    assert data['bookmarks']['malformed'] == 0
    assert data['image_load']['total'] == 0
    assert data['sessions']['confidence_update']['total'] == 0
    assert data['sessions']['swipe']['total'] == 0
    assert data['sessions']['swipe']['session_count'] == 0


# ── Seeded fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def project(user_profile):
    return Project.objects.create(user=user_profile, name='Metrics Board')


@pytest.fixture
def session_a(user_profile, project):
    return AnalysisSession.objects.create(
        user=user_profile, project=project, phase='exploring',
    )


@pytest.fixture
def session_b(user_profile, project):
    return AnalysisSession.objects.create(
        user=user_profile, project=project, phase='exploring',
    )


@pytest.mark.django_db
def test_bookmarks_section_provenance_and_malformed(user_profile, session_a):
    # Well-formed: all provenance True, rank 3 -> primary zone, rank<=10.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='bookmark',
        payload={
            'card_id': 'bld_000001', 'action': 'save', 'rank': 3,
            'rank_zone': 'primary',
            'provenance': {
                'in_cosine_top10': True, 'in_gemini_top10': True, 'in_dpp_top10': True,
            },
        },
    )
    # Well-formed: all provenance False, rank 40 -> secondary zone.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='bookmark',
        payload={
            'card_id': 'bld_000002', 'action': 'save', 'rank': 40,
            'rank_zone': 'secondary',
            'provenance': {
                'in_cosine_top10': False, 'in_gemini_top10': False, 'in_dpp_top10': False,
            },
        },
    )
    # Malformed: missing provenance dict entirely.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='bookmark',
        payload={'card_id': 'bld_000003', 'action': 'save', 'rank': 5},
    )

    data = json.loads(_run('--json'))
    bookmarks = data['bookmarks']

    assert bookmarks['total'] == 3
    assert bookmarks['malformed'] == 1
    assert bookmarks['with_provenance'] == 2
    # Rates computed over the 2 well-formed events only: 1 true / 2 = 0.5 each.
    assert bookmarks['provenance_top10_rate']['in_cosine_top10'] == 0.5
    assert bookmarks['provenance_top10_rate']['in_gemini_top10'] == 0.5
    assert bookmarks['provenance_top10_rate']['in_dpp_top10'] == 0.5
    assert bookmarks['rank_zone']['primary'] == 1
    assert bookmarks['rank_zone']['secondary'] == 1
    # Malformed row has no rank_zone key -> counted unknown.
    assert bookmarks['rank_zone']['unknown'] == 1
    # rank<=10: rows with rank=3 and rank=5 (malformed still has a rank field).
    assert bookmarks['rank_le_10_count'] == 2

    text = _run()
    assert '── bookmarks' in text


@pytest.mark.django_db
def test_image_load_section_domains_and_percentiles(user_profile, session_a):
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='image_load',
        payload={'domain': 'r2.example.com', 'context': 'card', 'outcome': 'success', 'load_ms': 100},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='image_load',
        payload={'domain': 'r2.example.com', 'context': 'card', 'outcome': 'success', 'load_ms': 300},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='image_load',
        payload={'domain': 'r2.example.com', 'context': 'detail', 'outcome': 'failure', 'load_ms': None},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='image_load',
        payload={'domain': 'r2.example.com', 'context': 'card', 'outcome': 'timeout', 'load_ms': None},
    )

    data = json.loads(_run('--json'))
    image_load = data['image_load']

    assert image_load['total'] == 4
    assert image_load['malformed'] == 0

    by_domain = image_load['by_domain']['r2.example.com']
    assert by_domain['count'] == 4
    assert by_domain['load_ms_p50'] == 100
    assert by_domain['load_ms_p95'] == 300
    assert by_domain['outcome_rate']['success'] == 0.5
    assert by_domain['outcome_rate']['failure'] == 0.25
    assert by_domain['outcome_rate']['timeout'] == 0.25

    by_context_card = image_load['by_context']['card']
    assert by_context_card['count'] == 3
    assert by_context_card['load_ms_p50'] == 100

    by_context_detail = image_load['by_context']['detail']
    assert by_context_detail['count'] == 1
    assert by_context_detail['load_ms_p50'] is None  # only null load_ms in this group


@pytest.mark.django_db
def test_sessions_section_confidence_update_and_swipe(user_profile, session_a, session_b):
    # confidence_update: 3 events, one with null silhouette.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='confidence_update',
        payload={'n_likes_at_decision': 3, 'cluster_count_used': 1, 'silhouette_score': 0.5},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='confidence_update',
        payload={'n_likes_at_decision': 5, 'cluster_count_used': 2, 'silhouette_score': 0.7},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='confidence_update',
        payload={'n_likes_at_decision': 8, 'cluster_count_used': 2, 'silhouette_score': None},
    )

    # swipe: 5 events across 2 sessions, mixed directions/cache_hit/db_call_count.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={'direction': 'like', 'cache_hit': True, 'db_call_count': 2},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={'direction': 'like', 'cache_hit': False, 'db_call_count': 4},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={'direction': 'dislike', 'cache_hit': None, 'db_call_count': 3},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_b, event_type='swipe',
        payload={'direction': 'like', 'cache_hit': True, 'db_call_count': 1},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_b, event_type='swipe',
        payload={'direction': 'dislike', 'cache_hit': True, 'db_call_count': 5},
    )

    data = json.loads(_run('--json'))
    sessions = data['sessions']

    cu = sessions['confidence_update']
    assert cu['total'] == 3
    assert cu['malformed'] == 0
    assert cu['n_likes_at_decision']['min'] == 3
    assert cu['n_likes_at_decision']['median'] == 5
    assert cu['n_likes_at_decision']['max'] == 8
    assert cu['cluster_count_used_distribution'] == {'1': 1, '2': 2}
    assert cu['silhouette_score_median'] == 0.6

    sw = sessions['swipe']
    assert sw['total'] == 5
    assert sw['malformed'] == 0
    assert sw['session_count'] == 2
    # session_a has 3 swipes, session_b has 2 -> distribution over [3, 2]
    assert sw['swipes_per_session']['min'] == 2
    assert sw['swipes_per_session']['max'] == 3
    assert sw['direction'] == {'like': 3, 'dislike': 2}
    # cache_hit: 3 true / 4 non-null (one null excluded) = 0.75
    assert sw['cache_hit_rate'] == 0.75
    assert sw['db_call_count']['min'] == 1
    assert sw['db_call_count']['max'] == 5

    text = _run()
    assert '── sessions' in text


@pytest.mark.django_db
def test_days_window_excludes_old_events(user_profile, session_a):
    # In-window event.
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='bookmark',
        payload={
            'card_id': 'bld_000001', 'action': 'save', 'rank': 1,
            'rank_zone': 'primary',
            'provenance': {'in_cosine_top10': True, 'in_gemini_top10': True, 'in_dpp_top10': True},
        },
    )
    # Out-of-window event: auto_now_add ignores created_at kwarg at create time,
    # so push it into the past via a follow-up queryset.update().
    old_event = SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='bookmark',
        payload={
            'card_id': 'bld_000002', 'action': 'save', 'rank': 2,
            'rank_zone': 'primary',
            'provenance': {'in_cosine_top10': True, 'in_gemini_top10': True, 'in_dpp_top10': True},
        },
    )
    SessionEvent.objects.filter(pk=old_event.pk).update(
        created_at=timezone.now() - timedelta(days=60)
    )

    data = json.loads(_run('--days', '30', '--json'))
    assert data['bookmarks']['total'] == 1

    data_wide = json.loads(_run('--days', '90', '--json'))
    assert data_wide['bookmarks']['total'] == 2


@pytest.mark.django_db
def test_json_top_level_keys():
    output = _run('--json')
    data = json.loads(output)
    assert set(data.keys()) == {
        'window_days', 'generated_for', 'bookmarks', 'image_load', 'sessions',
    }
    assert set(data['sessions'].keys()) == {'confidence_update', 'swipe'}


# ── BACK-PERFORMANCE-5a: pure-helper unit tests (no DB) ──────────────────────

class TestPercentileMath:
    """_percentile is nearest-rank: ceil(pct/100 * n) - 1, clamped."""

    def test_empty_returns_none(self):
        assert _percentile([], 50) is None

    def test_single_sample(self):
        assert _percentile([42], 50) == 42
        assert _percentile([42], 95) == 42
        assert _percentile([42], 100) == 42

    def test_two_samples_p50_is_lower(self):
        # [100, 300] -> p50: ceil(0.5*2)-1=0 -> 100; p95: ceil(0.95*2)-1=1 -> 300
        assert _percentile([100, 300], 50) == 100
        assert _percentile([100, 300], 95) == 300

    def test_odd_count(self):
        # [10, 20, 30] -> p50: ceil(1.5)-1=1 -> 20
        assert _percentile([10, 20, 30], 50) == 20
        assert _percentile([10, 20, 30], 95) == 30

    def test_even_count_four(self):
        # [1,2,3,4] -> p50: ceil(2.0)-1=1 -> 2; p95: ceil(3.8)-1=3 -> 4
        assert _percentile([1, 2, 3, 4], 50) == 2
        assert _percentile([1, 2, 3, 4], 95) == 4


class TestExtractTiming:
    """_extract_timing validates all 5 keys are present and numeric."""

    _VALID = {
        'timing_breakdown': {
            'lock_ms': 10, 'embed_ms': 20, 'select_ms': 30,
            'prefetch_ms': 5, 'total_ms': 100,
        }
    }

    def test_valid_returns_dict(self):
        result = _extract_timing(self._VALID)
        assert result == {
            'lock_ms': 10.0, 'embed_ms': 20.0, 'select_ms': 30.0,
            'prefetch_ms': 5.0, 'total_ms': 100.0,
        }

    def test_non_dict_payload_returns_none(self):
        assert _extract_timing("bad") is None
        assert _extract_timing(None) is None
        assert _extract_timing(42) is None

    def test_missing_timing_breakdown_returns_none(self):
        assert _extract_timing({'direction': 'like'}) is None

    def test_non_dict_breakdown_returns_none(self):
        assert _extract_timing({'timing_breakdown': 'fast'}) is None
        assert _extract_timing({'timing_breakdown': None}) is None

    def test_missing_key_returns_none(self):
        partial = dict(self._VALID['timing_breakdown'])
        del partial['total_ms']
        assert _extract_timing({'timing_breakdown': partial}) is None

    def test_non_numeric_value_returns_none(self):
        bad = dict(self._VALID['timing_breakdown'])
        bad['embed_ms'] = 'slow'
        assert _extract_timing({'timing_breakdown': bad}) is None

    def test_bool_rejected(self):
        bad = dict(self._VALID['timing_breakdown'])
        bad['lock_ms'] = True
        assert _extract_timing({'timing_breakdown': bad}) is None

    def test_float_values_accepted(self):
        payload = {
            'timing_breakdown': {
                'lock_ms': 1.5, 'embed_ms': 2.5, 'select_ms': 3.5,
                'prefetch_ms': 0.5, 'total_ms': 99.9,
            }
        }
        result = _extract_timing(payload)
        assert result is not None
        assert result['total_ms'] == 99.9


class TestStagePercentiles:
    """_stage_percentiles computes p50/p95/max/count per stage."""

    def test_empty_list_returns_zero_count(self):
        result = _stage_percentiles([])
        for key in ('lock_ms', 'embed_ms', 'select_ms', 'prefetch_ms', 'total_ms'):
            assert result[key]['count'] == 0
            assert result[key]['p50'] is None
            assert result[key]['p95'] is None
            assert result[key]['max'] is None

    def test_single_sample(self):
        timing = {
            'lock_ms': 10.0, 'embed_ms': 50.0, 'select_ms': 20.0,
            'prefetch_ms': 5.0, 'total_ms': 100.0,
        }
        result = _stage_percentiles([timing])
        assert result['total_ms']['p50'] == 100.0
        assert result['total_ms']['p95'] == 100.0
        assert result['total_ms']['max'] == 100.0
        assert result['total_ms']['count'] == 1
        assert result['embed_ms']['p50'] == 50.0

    def test_two_samples_known_values(self):
        t1 = {
            'lock_ms': 10.0, 'embed_ms': 100.0, 'select_ms': 20.0,
            'prefetch_ms': 5.0, 'total_ms': 700.0,
        }
        t2 = {
            'lock_ms': 30.0, 'embed_ms': 300.0, 'select_ms': 60.0,
            'prefetch_ms': 15.0, 'total_ms': 1500.0,
        }
        result = _stage_percentiles([t1, t2])
        # [700, 1500] sorted; p50 = nearest-rank index 0 = 700
        assert result['total_ms']['p50'] == 700.0
        assert result['total_ms']['p95'] == 1500.0
        assert result['total_ms']['max'] == 1500.0
        assert result['total_ms']['count'] == 2
        assert result['embed_ms']['p50'] == 100.0
        assert result['embed_ms']['max'] == 300.0


class TestCacheSplitPercentiles:
    """_cache_split_percentiles separates hit vs miss rows."""

    def _make_timing(self, total_ms, embed_ms=10.0):
        return {
            'lock_ms': 5.0, 'embed_ms': embed_ms, 'select_ms': 10.0,
            'prefetch_ms': 2.0, 'total_ms': total_ms,
        }

    def test_empty_both_buckets(self):
        result = _cache_split_percentiles([])
        assert result['hit']['total_ms']['count'] == 0
        assert result['miss']['total_ms']['count'] == 0

    def test_hit_and_miss_separated(self):
        rows = [
            (self._make_timing(700.0), True),
            (self._make_timing(800.0), True),
            (self._make_timing(1400.0), False),
            (self._make_timing(1500.0), False),
            (self._make_timing(900.0), None),   # excluded from both buckets
        ]
        result = _cache_split_percentiles(rows)
        assert result['hit']['total_ms']['count'] == 2
        assert result['hit']['total_ms']['p50'] == 700.0  # [700,800] p50=idx0=700
        assert result['hit']['total_ms']['p95'] == 800.0
        assert result['miss']['total_ms']['count'] == 2
        assert result['miss']['total_ms']['p50'] == 1400.0
        assert result['miss']['total_ms']['p95'] == 1500.0

    def test_none_cache_hit_excluded(self):
        rows = [
            (self._make_timing(500.0), None),
            (self._make_timing(600.0), None),
        ]
        result = _cache_split_percentiles(rows)
        assert result['hit']['total_ms']['count'] == 0
        assert result['miss']['total_ms']['count'] == 0


class TestPositionBuckets:
    """_position_buckets assigns warmup (pos 1-2) vs warmed (pos 3+) per session."""

    def _make_timing(self, total_ms, embed_ms=20.0):
        return {
            'lock_ms': 5.0, 'embed_ms': embed_ms, 'select_ms': 10.0,
            'prefetch_ms': 2.0, 'total_ms': total_ms,
        }

    def test_empty_input(self):
        result = _position_buckets([])
        assert result['warmup']['total_ms']['count'] == 0
        assert result['warmed']['total_ms']['count'] == 0

    def test_single_session_positions(self):
        # 4 swipes in session 1; positions 1,2=warmup; 3,4=warmed
        now = timezone.now()
        rows = [
            (1, now, self._make_timing(1000.0)),
            (1, now + timedelta(seconds=5), self._make_timing(800.0)),
            (1, now + timedelta(seconds=10), self._make_timing(600.0)),
            (1, now + timedelta(seconds=15), self._make_timing(500.0)),
        ]
        result = _position_buckets(rows)
        assert result['warmup']['total_ms']['count'] == 2
        assert result['warmed']['total_ms']['count'] == 2
        # warmup: [1000, 800] sorted -> p50=800; warmed: [600, 500] sorted -> p50=500
        assert result['warmup']['total_ms']['p50'] == 800.0
        assert result['warmed']['total_ms']['p50'] == 500.0

    def test_two_sessions_interleaved_timestamps(self):
        # Verify created_at ordering is per-session, not global.
        # session_a: swipes at t=0,t=10 (positions 1,2 both warmup)
        # session_b: swipes at t=5,t=15,t=25 (positions 1,2,3 -> 2 warmup + 1 warmed)
        # Global order by t would be: a1, b1, a2, b2, b3
        # Per-session: a positions = 1,2; b positions = 1,2,3
        t = timezone.now()
        rows = [
            ('session_a', t + timedelta(seconds=0), self._make_timing(1000.0, embed_ms=100.0)),
            ('session_b', t + timedelta(seconds=5), self._make_timing(900.0, embed_ms=90.0)),
            ('session_a', t + timedelta(seconds=10), self._make_timing(850.0, embed_ms=85.0)),
            ('session_b', t + timedelta(seconds=15), self._make_timing(800.0, embed_ms=80.0)),
            ('session_b', t + timedelta(seconds=25), self._make_timing(400.0, embed_ms=40.0)),
        ]
        result = _position_buckets(rows)
        # warmup: a-pos1(1000), a-pos2(850), b-pos1(900), b-pos2(800) = 4 events
        assert result['warmup']['total_ms']['count'] == 4
        # warmed: b-pos3(400) = 1 event
        assert result['warmed']['total_ms']['count'] == 1
        assert result['warmed']['total_ms']['p50'] == 400.0
        assert result['warmed']['embed_ms']['p50'] == 40.0

    def test_null_session_id_excluded_from_buckets(self):
        # Rows with session_id=None must not appear in position buckets.
        # (In _build_swipe_stats only non-None session_id rows are forwarded.)
        # _position_buckets itself receives non-None session_ids;
        # pass session_id='__no_session__' to simulate an edge case if needed.
        result = _position_buckets([])
        assert result['warmup']['total_ms']['count'] == 0


# ── BACK-PERFORMANCE-5a: DB-backed integration tests ─────────────────────────

def _make_swipe_payload(total_ms, embed_ms=50.0, cache_hit=True, direction='like'):
    return {
        'direction': direction,
        'cache_hit': cache_hit,
        'timing_breakdown': {
            'lock_ms': 10.0, 'embed_ms': embed_ms, 'select_ms': 20.0,
            'prefetch_ms': 5.0, 'total_ms': total_ms,
        },
    }


@pytest.mark.django_db
def test_timing_breakdown_per_stage_in_json(user_profile, session_a):
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=700.0, embed_ms=100.0),
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=1500.0, embed_ms=300.0),
    )

    data = json.loads(_run('--json'))
    sw = data['sessions']['swipe']

    # Two valid timing samples
    assert sw['timing_malformed'] == 0
    tb = sw['timing_breakdown']
    # total_ms: [700, 1500] sorted; p50 = idx0 = 700
    assert tb['total_ms']['p50'] == 700.0
    assert tb['total_ms']['p95'] == 1500.0
    assert tb['total_ms']['max'] == 1500.0
    assert tb['total_ms']['count'] == 2
    assert tb['embed_ms']['p50'] == 100.0
    assert tb['embed_ms']['max'] == 300.0


@pytest.mark.django_db
def test_timing_malformed_counted_and_excluded(user_profile, session_a):
    # Well-formed
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=700.0),
    )
    # Malformed: timing_breakdown is a string
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={'direction': 'like', 'cache_hit': True, 'timing_breakdown': 'fast'},
    )
    # Malformed: missing 'total_ms' key
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={
            'direction': 'like',
            'timing_breakdown': {
                'lock_ms': 10, 'embed_ms': 20, 'select_ms': 30, 'prefetch_ms': 5,
                # total_ms absent
            },
        },
    )
    # Malformed: non-numeric value
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={
            'direction': 'like',
            'timing_breakdown': {
                'lock_ms': 10, 'embed_ms': 'slow', 'select_ms': 30,
                'prefetch_ms': 5, 'total_ms': 100,
            },
        },
    )

    data = json.loads(_run('--json'))
    sw = data['sessions']['swipe']

    # 4 total, 0 payload-malformed (all are dicts), 3 timing-malformed
    assert sw['total'] == 4
    assert sw['malformed'] == 0
    assert sw['timing_malformed'] == 3
    # Only 1 valid sample contributes to aggregates
    assert sw['timing_breakdown']['total_ms']['count'] == 1
    assert sw['timing_breakdown']['total_ms']['p50'] == 700.0


@pytest.mark.django_db
def test_cache_hit_split_in_json(user_profile, session_a):
    # 2 cache-hit swipes
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=700.0, cache_hit=True),
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=800.0, cache_hit=True),
    )
    # 2 cache-miss swipes
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=1400.0, cache_hit=False),
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=1500.0, cache_hit=False),
    )

    data = json.loads(_run('--json'))
    split = data['sessions']['swipe']['timing_breakdown_by_cache']

    hit = split['hit']['total_ms']
    assert hit['count'] == 2
    assert hit['p50'] == 700.0  # [700,800] nearest-rank p50 = idx0 = 700
    assert hit['p95'] == 800.0

    miss = split['miss']['total_ms']
    assert miss['count'] == 2
    assert miss['p50'] == 1400.0
    assert miss['p95'] == 1500.0


@pytest.mark.django_db
def test_position_buckets_in_json(user_profile, session_a, session_b):
    """Positions derived per-session by created_at order (interleaved across 2 sessions)."""
    # session_a: 4 swipes → positions 1,2 (warmup), 3,4 (warmed)
    # session_b: 2 swipes → positions 1,2 (both warmup)
    # We insert in mixed created_at order to verify per-session sort.
    now = timezone.now()

    e_a1 = SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=1000.0, embed_ms=100.0),
    )
    e_b1 = SessionEvent.objects.create(
        user=user_profile, session=session_b, event_type='swipe',
        payload=_make_swipe_payload(total_ms=900.0, embed_ms=90.0),
    )
    e_a2 = SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=850.0, embed_ms=85.0),
    )
    e_b2 = SessionEvent.objects.create(
        user=user_profile, session=session_b, event_type='swipe',
        payload=_make_swipe_payload(total_ms=800.0, embed_ms=80.0),
    )
    e_a3 = SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=600.0, embed_ms=60.0),
    )
    e_a4 = SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=500.0, embed_ms=50.0),
    )

    # Force created_at order to be unambiguous
    base = now
    SessionEvent.objects.filter(pk=e_a1.pk).update(created_at=base + timedelta(seconds=0))
    SessionEvent.objects.filter(pk=e_b1.pk).update(created_at=base + timedelta(seconds=5))
    SessionEvent.objects.filter(pk=e_a2.pk).update(created_at=base + timedelta(seconds=10))
    SessionEvent.objects.filter(pk=e_b2.pk).update(created_at=base + timedelta(seconds=15))
    SessionEvent.objects.filter(pk=e_a3.pk).update(created_at=base + timedelta(seconds=20))
    SessionEvent.objects.filter(pk=e_a4.pk).update(created_at=base + timedelta(seconds=25))

    data = json.loads(_run('--json'))
    pos = data['sessions']['swipe']['timing_breakdown_by_position']

    # warmup: a-pos1(1000) + a-pos2(850) + b-pos1(900) + b-pos2(800) = 4 events
    assert pos['warmup']['total_ms']['count'] == 4
    # warmed: a-pos3(600) + a-pos4(500) = 2 events
    assert pos['warmed']['total_ms']['count'] == 2
    # warmed [500, 600] sorted; p50 = idx0 = 500
    assert pos['warmed']['total_ms']['p50'] == 500.0
    assert pos['warmed']['total_ms']['p95'] == 600.0
    assert pos['warmed']['embed_ms']['p50'] == 50.0


@pytest.mark.django_db
def test_json_swipe_new_keys_present(user_profile, session_a):
    """--json output includes all new timing keys in sessions.swipe."""
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=700.0),
    )
    data = json.loads(_run('--json'))
    sw = data['sessions']['swipe']
    assert 'timing_malformed' in sw
    assert 'timing_breakdown' in sw
    assert 'timing_breakdown_by_cache' in sw
    assert 'timing_breakdown_by_position' in sw
    # All 5 stages present in timing_breakdown
    for stage in ('lock_ms', 'embed_ms', 'select_ms', 'prefetch_ms', 'total_ms'):
        assert stage in sw['timing_breakdown']


@pytest.mark.django_db
def test_text_output_includes_timing_section(user_profile, session_a):
    """Text mode renders timing breakdown headers for non-empty swipe section."""
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload=_make_swipe_payload(total_ms=700.0),
    )
    text = _run()
    assert 'timing_malformed' in text
    assert 'timing_breakdown (per-stage p50/p95/max)' in text
    assert 'timing_breakdown by cache_hit split' in text
    assert 'timing_breakdown by session position' in text


@pytest.mark.django_db
def test_existing_swipe_section_unchanged(user_profile, session_a, session_b):
    """Existing swipe keys (direction, cache_hit_rate, etc.) still present and correct."""
    SessionEvent.objects.create(
        user=user_profile, session=session_a, event_type='swipe',
        payload={'direction': 'like', 'cache_hit': True, 'db_call_count': 2,
                 'timing_breakdown': {
                     'lock_ms': 10, 'embed_ms': 50, 'select_ms': 20,
                     'prefetch_ms': 5, 'total_ms': 700,
                 }},
    )
    SessionEvent.objects.create(
        user=user_profile, session=session_b, event_type='swipe',
        payload={'direction': 'dislike', 'cache_hit': False, 'db_call_count': 4,
                 'timing_breakdown': {
                     'lock_ms': 20, 'embed_ms': 100, 'select_ms': 40,
                     'prefetch_ms': 10, 'total_ms': 1500,
                 }},
    )

    data = json.loads(_run('--json'))
    sw = data['sessions']['swipe']

    # Existing keys must still be present and correct
    assert sw['total'] == 2
    assert sw['malformed'] == 0
    assert sw['session_count'] == 2
    assert sw['direction'] == {'like': 1, 'dislike': 1}
    assert sw['cache_hit_rate'] == 0.5
    assert sw['db_call_count']['min'] == 2
    assert sw['db_call_count']['max'] == 4
