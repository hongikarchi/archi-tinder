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
"""
import io
import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

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
