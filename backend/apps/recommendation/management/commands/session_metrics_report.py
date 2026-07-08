"""
Management command: session_metrics_report

First analytics reader for the write-only SessionEvent telemetry (spec §6).
Aggregates bookmark provenance / rank-zone stats, image_load outcome +
latency percentiles, and session-level (confidence_update + swipe)
distributions over a rolling time window.

Query discipline: every section filters on (event_type, created_at) --
the composite index defined on SessionEvent.Meta.indexes -- then pulls
payloads via .values_list('payload', flat=True) and aggregates in PYTHON.
payload is a JSONField with no functional index, so no query-side key
lookups are attempted (see apps.recommendation.event_log.
aggregate_session_clustering_stats for the established pattern this
command follows).

Every payload key is read via .get() with a safe default -- a session's
payload shape can vary across app versions, and malformed / missing keys
must never crash the report. Sections that encounter payloads without an
expected key attribute (e.g. bookmark with no 'provenance' dict) count
those rows in a `malformed` bucket instead of raising.

NOTE: event_type 'session_end' has ZERO emitters anywhere in the codebase
(verified against apps/recommendation) -- this command intentionally does
not reference it. A session's activity window is derived from the
created_at range of its own events (confidence_update / swipe), not from
a session_end event that is never written.

Usage:
    python manage.py session_metrics_report
    python manage.py session_metrics_report --days 7
    python manage.py session_metrics_report --json
    python manage.py session_metrics_report --days 7 --json
"""
import json
import math
import statistics
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.recommendation.models import SessionEvent

DEFAULT_DAYS = 30


def _percentile(sorted_values, pct):
    """Nearest-rank percentile over an already-sorted list of numbers.

    Returns None for an empty list. `pct` is 0-100 (e.g. 50 for p50, 95 for p95).
    Standard nearest-rank method: index = ceil(pct/100 * n) - 1, clamped to
    [0, n-1] (e.g. [100, 300] -> p50=100, p95=300).
    """
    if not sorted_values:
        return None
    n = len(sorted_values)
    idx = max(0, min(n - 1, math.ceil((pct / 100.0) * n) - 1))
    return sorted_values[idx]


def _median(values):
    if not values:
        return None
    return statistics.median(values)


def _fraction_true(count_true, count_total):
    if count_total <= 0:
        return None
    return count_true / count_total


def _build_bookmarks_section(since):
    """event_type='bookmark' aggregation.

    Wires the 'objective primary metric' named in SessionEvent's docstring
    (models.py ~155-158): top-10 bookmark rate broken down by provenance
    source, plus the primary/secondary rank_zone split.
    """
    payloads = SessionEvent.objects.filter(
        event_type='bookmark', created_at__gte=since,
    ).values_list('payload', flat=True)

    total = 0
    malformed = 0
    with_provenance = 0
    provenance_true = {'in_cosine_top10': 0, 'in_gemini_top10': 0, 'in_dpp_top10': 0}
    rank_zone_counts = {'primary': 0, 'secondary': 0, 'unknown': 0}
    rank_le_10 = 0

    for payload in payloads:
        total += 1
        if not isinstance(payload, dict):
            malformed += 1
            continue

        provenance = payload.get('provenance')
        if isinstance(provenance, dict):
            with_provenance += 1
            for key in provenance_true:
                if provenance.get(key) is True:
                    provenance_true[key] += 1
        else:
            malformed += 1

        rank_zone = payload.get('rank_zone')
        if rank_zone in ('primary', 'secondary'):
            rank_zone_counts[rank_zone] += 1
        else:
            rank_zone_counts['unknown'] += 1

        rank = payload.get('rank')
        if isinstance(rank, (int, float)) and not isinstance(rank, bool) and rank <= 10:
            rank_le_10 += 1

    provenance_rates = {
        key: _fraction_true(count, with_provenance)
        for key, count in provenance_true.items()
    }

    return {
        'total': total,
        'malformed': malformed,
        'with_provenance': with_provenance,
        'provenance_top10_rate': provenance_rates,
        'rank_zone': rank_zone_counts,
        'rank_le_10_count': rank_le_10,
    }


def _outcome_rates(outcome_counts, group_total):
    return {
        outcome: _fraction_true(count, group_total)
        for outcome, count in outcome_counts.items()
    }


def _build_image_load_section(since):
    """event_type='image_load' aggregation, grouped by domain and by context."""
    payloads = SessionEvent.objects.filter(
        event_type='image_load', created_at__gte=since,
    ).values_list('payload', flat=True)

    total = 0
    malformed = 0

    def _new_group():
        return {'count': 0, 'outcomes': {'success': 0, 'failure': 0, 'timeout': 0}, 'load_ms': []}

    by_domain = {}
    by_context = {}

    for payload in payloads:
        total += 1
        if not isinstance(payload, dict):
            malformed += 1
            continue

        domain = payload.get('domain') or 'unknown'
        context = payload.get('context') or 'unknown'
        outcome = payload.get('outcome')
        load_ms = payload.get('load_ms')

        domain_group = by_domain.setdefault(domain, _new_group())
        context_group = by_context.setdefault(context, _new_group())

        domain_group['count'] += 1
        context_group['count'] += 1

        if outcome in ('success', 'failure', 'timeout'):
            domain_group['outcomes'][outcome] += 1
            context_group['outcomes'][outcome] += 1

        if isinstance(load_ms, (int, float)) and not isinstance(load_ms, bool):
            domain_group['load_ms'].append(load_ms)
            context_group['load_ms'].append(load_ms)

    def _finalize(groups):
        finalized = {}
        for key, group in groups.items():
            sorted_ms = sorted(group['load_ms'])
            finalized[key] = {
                'count': group['count'],
                'outcome_rate': _outcome_rates(group['outcomes'], group['count']),
                'load_ms_p50': _percentile(sorted_ms, 50),
                'load_ms_p95': _percentile(sorted_ms, 95),
            }
        return finalized

    return {
        'total': total,
        'malformed': malformed,
        'by_domain': _finalize(by_domain),
        'by_context': _finalize(by_context),
    }


def _build_confidence_update_stats(since):
    payloads = SessionEvent.objects.filter(
        event_type='confidence_update', created_at__gte=since,
    ).values_list('payload', flat=True)

    total = 0
    malformed = 0
    n_likes_values = []
    cluster_count_distribution = {}
    silhouette_scores = []

    for payload in payloads:
        total += 1
        if not isinstance(payload, dict):
            malformed += 1
            continue

        n_likes = payload.get('n_likes_at_decision')
        if isinstance(n_likes, (int, float)) and not isinstance(n_likes, bool):
            n_likes_values.append(n_likes)

        cluster_count = payload.get('cluster_count_used')
        if cluster_count is not None:
            key = str(cluster_count)
            cluster_count_distribution[key] = cluster_count_distribution.get(key, 0) + 1

        silhouette = payload.get('silhouette_score')
        if isinstance(silhouette, (int, float)) and not isinstance(silhouette, bool):
            silhouette_scores.append(silhouette)

    return {
        'total': total,
        'malformed': malformed,
        'n_likes_at_decision': {
            'min': min(n_likes_values) if n_likes_values else None,
            'median': _median(n_likes_values),
            'max': max(n_likes_values) if n_likes_values else None,
        },
        'cluster_count_used_distribution': cluster_count_distribution,
        'silhouette_score_median': _median(silhouette_scores),
    }


def _build_swipe_stats(since):
    rows = SessionEvent.objects.filter(
        event_type='swipe', created_at__gte=since,
    ).values_list('payload', 'session_id')

    total = 0
    malformed = 0
    per_session_counts = {}
    direction_counts = {}
    cache_hit_true = 0
    cache_hit_total = 0
    db_call_counts = []

    for payload, session_id in rows:
        total += 1
        if not isinstance(payload, dict):
            malformed += 1
            continue

        key = session_id if session_id is not None else '__no_session__'
        per_session_counts[key] = per_session_counts.get(key, 0) + 1

        direction = payload.get('direction') or 'unknown'
        direction_counts[direction] = direction_counts.get(direction, 0) + 1

        cache_hit = payload.get('cache_hit')
        if cache_hit is not None:
            cache_hit_total += 1
            if cache_hit is True:
                cache_hit_true += 1

        db_call_count = payload.get('db_call_count')
        if isinstance(db_call_count, (int, float)) and not isinstance(db_call_count, bool):
            db_call_counts.append(db_call_count)

    session_counts = list(per_session_counts.values())
    sorted_session_counts = sorted(session_counts)

    return {
        'total': total,
        'malformed': malformed,
        'session_count': len(per_session_counts),
        'swipes_per_session': {
            'min': min(session_counts) if session_counts else None,
            'median': _median(session_counts),
            'p95': _percentile(sorted_session_counts, 95),
            'max': max(session_counts) if session_counts else None,
        },
        'direction': direction_counts,
        'cache_hit_rate': _fraction_true(cache_hit_true, cache_hit_total),
        'db_call_count': {
            'min': min(db_call_counts) if db_call_counts else None,
            'median': _median(db_call_counts),
            'max': max(db_call_counts) if db_call_counts else None,
        },
    }


def _build_sessions_section(since):
    return {
        'confidence_update': _build_confidence_update_stats(since),
        'swipe': _build_swipe_stats(since),
    }


class Command(BaseCommand):
    help = (
        "Report analytics aggregates over the write-only SessionEvent telemetry: "
        "bookmark provenance / rank-zone rates, image_load outcome + latency "
        "percentiles, and confidence_update / swipe distributions. "
        "Windowed on created_at via --days (default %d)." % DEFAULT_DAYS
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_DAYS,
            help="Time window in days on created_at (default: %d)." % DEFAULT_DAYS,
        )
        parser.add_argument(
            "--json",
            dest="as_json",
            action="store_true",
            default=False,
            help="Emit a single machine-readable JSON object instead of styled text.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        as_json = options["as_json"]
        since = timezone.now() - timedelta(days=days)

        bookmarks = _build_bookmarks_section(since)
        image_load = _build_image_load_section(since)
        sessions = _build_sessions_section(since)

        if as_json:
            result = {
                "window_days": days,
                "generated_for": since.isoformat(),
                "bookmarks": bookmarks,
                "image_load": image_load,
                "sessions": sessions,
            }
            self.stdout.write(json.dumps(result, indent=2, default=str))
            return

        self.stdout.write(
            "session_metrics_report — window=%d days (since %s)" % (days, since.isoformat())
        )
        self.stdout.write("")

        self._write_bookmarks_block(bookmarks)
        self.stdout.write("")
        self._write_image_load_block(image_load)
        self.stdout.write("")
        self._write_sessions_block(sessions)

    # ── Text rendering ────────────────────────────────────────────────────────

    def _write_bookmarks_block(self, section):
        self.stdout.write("── bookmarks ─────────────────────────")
        if section['total'] == 0:
            self.stdout.write(self.style.WARNING(
                "no bookmark events in window — nothing to report"
            ))
            return
        self.stdout.write("total: %d" % section['total'])
        self.stdout.write("malformed: %d" % section['malformed'])
        self.stdout.write("with_provenance: %d" % section['with_provenance'])
        for key, rate in section['provenance_top10_rate'].items():
            self.stdout.write(
                "%s rate: %s" % (key, "n/a" if rate is None else "%.4f" % rate)
            )
        rz = section['rank_zone']
        self.stdout.write(
            "rank_zone: primary=%d secondary=%d unknown=%d"
            % (rz['primary'], rz['secondary'], rz['unknown'])
        )
        self.stdout.write("rank<=10 count: %d" % section['rank_le_10_count'])

    def _write_image_load_block(self, section):
        self.stdout.write("── image_load ─────────────────────────")
        if section['total'] == 0:
            self.stdout.write(self.style.WARNING(
                "no image_load events in window — nothing to report"
            ))
            return
        self.stdout.write("total: %d" % section['total'])
        self.stdout.write("malformed: %d" % section['malformed'])
        self.stdout.write("by domain:")
        for domain, stats in sorted(section['by_domain'].items()):
            self.stdout.write(
                "  %s: count=%d outcome_rate=%s p50=%s p95=%s"
                % (domain, stats['count'], stats['outcome_rate'],
                   stats['load_ms_p50'], stats['load_ms_p95'])
            )
        self.stdout.write("by context:")
        for context, stats in sorted(section['by_context'].items()):
            self.stdout.write(
                "  %s: count=%d outcome_rate=%s p50=%s p95=%s"
                % (context, stats['count'], stats['outcome_rate'],
                   stats['load_ms_p50'], stats['load_ms_p95'])
            )

    def _write_sessions_block(self, section):
        self.stdout.write("── sessions ─────────────────────────")
        cu = section['confidence_update']
        sw = section['swipe']

        if cu['total'] == 0:
            self.stdout.write(self.style.WARNING(
                "no confidence_update events in window — nothing to report"
            ))
        else:
            self.stdout.write("confidence_update total: %d" % cu['total'])
            self.stdout.write("confidence_update malformed: %d" % cu['malformed'])
            self.stdout.write("n_likes_at_decision: %s" % cu['n_likes_at_decision'])
            self.stdout.write(
                "cluster_count_used_distribution: %s" % cu['cluster_count_used_distribution']
            )
            self.stdout.write("silhouette_score_median: %s" % cu['silhouette_score_median'])

        self.stdout.write("")

        if sw['total'] == 0:
            self.stdout.write(self.style.WARNING(
                "no swipe events in window — nothing to report"
            ))
        else:
            self.stdout.write("swipe total: %d" % sw['total'])
            self.stdout.write("swipe malformed: %d" % sw['malformed'])
            self.stdout.write("session_count: %d" % sw['session_count'])
            self.stdout.write("swipes_per_session: %s" % sw['swipes_per_session'])
            self.stdout.write("direction: %s" % sw['direction'])
            cache_rate = sw['cache_hit_rate']
            self.stdout.write(
                "cache_hit_rate: %s" % ("n/a" if cache_rate is None else "%.4f" % cache_rate)
            )
            self.stdout.write("db_call_count: %s" % sw['db_call_count'])
