"""
validate_imp5.py -- IMP-5 Staging Validation Management Command.

Empirically verifies that Gemini explicit context caching (IMP-5) delivers
the spec-predicted latency savings:
  - >=50% latency drop on cache_hit=True vs cache_hit=False
  - >=95% cache hit rate on calls 2-10 (post-warmup)

Usage:
    cd backend && python3 manage.py validate_imp5
    cd backend && python3 manage.py validate_imp5 --mode=control
    cd backend && python3 manage.py validate_imp5 --mode=both

Modes:
  cached  (default) -- runs ONLY with flag ON, 10 queries (original behaviour)
  control           -- runs ONLY with flag OFF, 10 queries (uncached baseline)
  both              -- Phase A (flag OFF) then Phase B (flag ON); computes A/B delta

This command:
1. Pre-checks environment (GEMINI_API_KEY, CACHES backend, settings defaults)
2. Temporarily overrides IMP-5 flag in-process (restores original in finally block)
3. Runs 10 varied parse_query calls per phase and measures latency
4. Reads emitted parse_query_timing SessionEvents from the DB
5. Computes statistics and outputs a markdown report
6. Writes the report to backend/_validation_imp5.md
"""
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone


QUERIES = [
    'concrete brutalist museum',
    'minimalist Japanese teahouse',
    'curved fluid contemporary library',
    'sustainable timber school',
    'colorful playful childcare center',
    'monumental classical courthouse',
    'industrial steel converted warehouse loft',
    'organic biophilic office tower',
    'desert earthen housing complex',
    'glass crystalline pavilion',
]


class Command(BaseCommand):
    help = 'Validate IMP-5 Gemini context caching delivers spec-predicted latency savings.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=['cached', 'control', 'both'],
            default='cached',
            help=(
                'Validation mode: '
                'cached=flag ON only (default, backward-compat); '
                'control=flag OFF only (uncached baseline); '
                'both=control then cached, with proper A/B delta computed.'
            ),
        )

    def handle(self, *args, **options):
        mode = options['mode']
        self.stdout.write(f'\n=== IMP-5 Staging Validation (mode={mode}) ===\n')

        # --- Step 1: Pre-checks -------------------------------------------
        self._print_prechecks()

        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not gemini_key:
            self.stderr.write('[ERROR] GEMINI_API_KEY is not set. Cannot proceed.')
            return

        # --- Step 2: Runtime override (restore in finally) ----------------
        rc = settings.RECOMMENDATION
        original_flag = rc.get('context_caching_enabled', False)

        try:
            if mode == 'cached':
                rc['context_caching_enabled'] = True
                self.stdout.write(
                    '[override] context_caching_enabled set to True (will restore after run)\n'
                )
                self._run_single_phase(flag_value=True, label='cached')
            elif mode == 'control':
                rc['context_caching_enabled'] = False
                self.stdout.write(
                    '[override] context_caching_enabled set to False (will restore after run)\n'
                )
                self._run_single_phase(flag_value=False, label='control')
            else:  # both
                self._run_both(rc)
        finally:
            rc['context_caching_enabled'] = original_flag
            self.stdout.write(
                f'\n[cleanup] context_caching_enabled restored to {original_flag}\n'
            )

    def _print_prechecks(self):
        self.stdout.write('[pre-check] --- Environment ---')
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if gemini_key:
            self.stdout.write(f'[pre-check] GEMINI_API_KEY: SET (length={len(gemini_key)})')
        else:
            self.stdout.write('[pre-check] GEMINI_API_KEY: NOT SET (validation will fail)')

        caches_cfg = settings.CACHES.get('default', {})
        backend = caches_cfg.get('BACKEND', 'unknown')
        self.stdout.write(f'[pre-check] CACHES backend: {backend}')

        rc = settings.RECOMMENDATION
        self.stdout.write(
            f'[pre-check] context_caching_enabled (settings default): '
            f'{rc.get("context_caching_enabled", False)}'
        )
        self.stdout.write(
            f'[pre-check] context_caching_ttl_seconds: '
            f'{rc.get("context_caching_ttl_seconds", 3600)}'
        )
        self.stdout.write('')

    # -----------------------------------------------------------------------
    # Single-phase execution (used by --mode=cached and --mode=control)
    # -----------------------------------------------------------------------

    def _run_single_phase(self, flag_value, label):
        """Run 10 queries in a single phase (flag ON or OFF). Produces legacy-format report."""
        from apps.recommendation.models import SessionEvent
        from apps.recommendation.services import parse_query

        # Clear Django cache for deterministic cold start
        cache.clear()
        self.stdout.write(
            f'[init] Django cache cleared — call 1 is a deterministic cold start (mode={label})\n'
        )

        run_start = dj_timezone.now()

        results = []
        aborted = False

        for i, q in enumerate(QUERIES):
            t0 = time.monotonic()
            try:
                result = parse_query(q)
                wall_ms = int((time.monotonic() - t0) * 1000)
                is_fallback = (
                    result is not None
                    and result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'
                )
                ok = not is_fallback
                entry = {
                    'idx': i,
                    'query': q,
                    'wall_ms': wall_ms,
                    'ok': ok,
                    'error': 'fallback returned (API failure)' if is_fallback else None,
                }
                results.append(entry)
                status = 'OK  ' if ok else 'FAIL'
                self.stdout.write(
                    f'[{i + 1}/10] {status} "{q[:40]}" wall_ms={wall_ms}'
                    + (' NOTE=fallback' if is_fallback else '')
                )
            except Exception as e:
                wall_ms = int((time.monotonic() - t0) * 1000)
                results.append({
                    'idx': i, 'query': q, 'wall_ms': wall_ms,
                    'ok': False, 'error': repr(e),
                })
                self.stdout.write(
                    f'[{i + 1}/10] FAIL "{q[:40]}" wall_ms={wall_ms} err={e!r}'
                )
                if i == 0:
                    self.stderr.write(
                        '\n[ABORT] First call failed. Likely GEMINI_API_KEY billing/auth issue.\n'
                        'DO NOT flip prod flag. Investigate before next /review cycle.\n'
                    )
                    aborted = True
                    break

        # Query events with both bounds for safety
        run_end = dj_timezone.now()
        self.stdout.write('\n[events] Querying SessionEvent table for parse_query_timing...')
        recent_events = list(
            SessionEvent.objects.filter(
                event_type='parse_query_timing',
                created_at__gte=run_start,
                created_at__lte=run_end,
            ).order_by('created_at')
        )

        self.stdout.write(f'[events] Found {len(recent_events)} parse_query_timing events\n')

        for evt in recent_events:
            p = evt.payload
            self.stdout.write(
                f'  {evt.created_at.isoformat()}  '
                f'mode={str(p.get("caching_mode") or ""):8} '
                f'hit={str(p.get("cache_hit")):5} '
                f'cached_in={str(p.get("cached_input_tokens") or ""):>4} '
                f'gemini_total_ms={str(p.get("gemini_total_ms") or ""):>7} '
                f'in_tok={str(p.get("input_tokens") or ""):>4} '
                f'out_tok={str(p.get("output_tokens") or ""):>3}'
            )

        # Build and write report
        report = self._build_report(
            results, recent_events, run_start, aborted,
            flag_value=flag_value, label=label,
        )

        self.stdout.write('\n' + report)

        output_path = Path(settings.BASE_DIR) / '_validation_imp5.md'
        output_path.write_text(report, encoding='utf-8')
        self.stdout.write(f'\n[output] Report written to: {output_path}\n')

    # -----------------------------------------------------------------------
    # Both-phase A/B execution
    # -----------------------------------------------------------------------

    def _run_both(self, rc):
        """Run Phase A (flag OFF) then Phase B (flag ON). Produce combined A/B report."""
        from apps.recommendation.models import SessionEvent
        from apps.recommendation.services import parse_query

        self.stdout.write('\n--- Phase A: Control (flag OFF, uncached baseline) ---\n')

        rc['context_caching_enabled'] = False
        cache.clear()
        self.stdout.write('[init] Django cache cleared before Phase A\n')

        phase_a_start = dj_timezone.now()
        results_a = []
        aborted_a = False

        for i, q in enumerate(QUERIES):
            t0 = time.monotonic()
            try:
                result = parse_query(q)
                wall_ms = int((time.monotonic() - t0) * 1000)
                is_fallback = (
                    result is not None
                    and result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'
                )
                ok = not is_fallback
                entry = {
                    'idx': i,
                    'query': q,
                    'wall_ms': wall_ms,
                    'ok': ok,
                    'error': 'fallback returned (API failure)' if is_fallback else None,
                }
                results_a.append(entry)
                status = 'OK  ' if ok else 'FAIL'
                self.stdout.write(
                    f'[A {i + 1}/10] {status} "{q[:40]}" wall_ms={wall_ms}'
                    + (' NOTE=fallback' if is_fallback else '')
                )
            except Exception as e:
                wall_ms = int((time.monotonic() - t0) * 1000)
                results_a.append({
                    'idx': i, 'query': q, 'wall_ms': wall_ms,
                    'ok': False, 'error': repr(e),
                })
                self.stdout.write(
                    f'[A {i + 1}/10] FAIL "{q[:40]}" wall_ms={wall_ms} err={e!r}'
                )
                if i == 0:
                    self.stderr.write(
                        '\n[ABORT] Phase A first call failed. '
                        'Likely GEMINI_API_KEY billing/auth issue.\n'
                        'Phase B NOT run — insufficient data for A/B comparison.\n'
                        'DO NOT flip prod flag.\n'
                    )
                    aborted_a = True
                    break

        phase_a_end = dj_timezone.now()

        if aborted_a:
            abort_report = self._build_abort_report(results_a, phase_a_start)
            self.stdout.write('\n' + abort_report)
            output_path = Path(settings.BASE_DIR) / '_validation_imp5.md'
            output_path.write_text(abort_report, encoding='utf-8')
            self.stdout.write(f'\n[output] Abort report written to: {output_path}\n')
            return

        # Fetch Phase A events (bounded to phase window)
        self.stdout.write('\n[events A] Querying Phase A SessionEvents...')
        events_a = list(
            SessionEvent.objects.filter(
                event_type='parse_query_timing',
                created_at__gte=phase_a_start,
                created_at__lt=phase_a_end,
            ).order_by('created_at')
        )
        self.stdout.write(f'[events A] Found {len(events_a)} events\n')
        for evt in events_a:
            p = evt.payload
            self.stdout.write(
                f'  [A] {evt.created_at.isoformat()}  '
                f'mode={str(p.get("caching_mode") or ""):8} '
                f'hit={str(p.get("cache_hit")):5} '
                f'gemini_total_ms={str(p.get("gemini_total_ms") or ""):>7}'
            )

        # Verify Phase A anomalies: expect caching_mode='none', cache_hit not True
        anomalies_a = []
        for evt in events_a:
            p = evt.payload
            if p.get('caching_mode') not in ('none', None):
                anomalies_a.append(
                    f'  Event at {evt.created_at.isoformat()}: '
                    f'expected caching_mode=none, got {p.get("caching_mode")!r}'
                )
            if p.get('cache_hit') is True:
                anomalies_a.append(
                    f'  Event at {evt.created_at.isoformat()}: '
                    f'cache_hit=True in control phase (unexpected)'
                )
        if anomalies_a:
            self.stdout.write('[WARNING] Phase A anomalies detected:')
            for a in anomalies_a:
                self.stdout.write(a)
        else:
            self.stdout.write('[OK] Phase A: all events have caching_mode=none (as expected)\n')

        # --- Phase B ---
        self.stdout.write('\n--- Phase B: Cached (flag ON, with explicit cache) ---\n')

        rc['context_caching_enabled'] = True
        cache.clear()  # ensure Phase A state does not influence Phase B
        self.stdout.write('[init] Django cache cleared before Phase B — cold start on call 1\n')

        phase_b_start = dj_timezone.now()
        results_b = []

        for i, q in enumerate(QUERIES):
            t0 = time.monotonic()
            try:
                result = parse_query(q)
                wall_ms = int((time.monotonic() - t0) * 1000)
                is_fallback = (
                    result is not None
                    and result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'
                )
                ok = not is_fallback
                entry = {
                    'idx': i,
                    'query': q,
                    'wall_ms': wall_ms,
                    'ok': ok,
                    'error': 'fallback returned (API failure)' if is_fallback else None,
                }
                results_b.append(entry)
                status = 'OK  ' if ok else 'FAIL'
                self.stdout.write(
                    f'[B {i + 1}/10] {status} "{q[:40]}" wall_ms={wall_ms}'
                    + (' NOTE=fallback' if is_fallback else '')
                )
            except Exception as e:
                wall_ms = int((time.monotonic() - t0) * 1000)
                results_b.append({
                    'idx': i, 'query': q, 'wall_ms': wall_ms,
                    'ok': False, 'error': repr(e),
                })
                self.stdout.write(
                    f'[B {i + 1}/10] FAIL "{q[:40]}" wall_ms={wall_ms} err={e!r}'
                )

        phase_b_end = dj_timezone.now()

        # Fetch Phase B events
        self.stdout.write('\n[events B] Querying Phase B SessionEvents...')
        events_b = list(
            SessionEvent.objects.filter(
                event_type='parse_query_timing',
                created_at__gte=phase_b_start,
                created_at__lte=phase_b_end,
            ).order_by('created_at')
        )
        self.stdout.write(f'[events B] Found {len(events_b)} events\n')
        for evt in events_b:
            p = evt.payload
            self.stdout.write(
                f'  [B] {evt.created_at.isoformat()}  '
                f'mode={str(p.get("caching_mode") or ""):8} '
                f'hit={str(p.get("cache_hit")):5} '
                f'cached_in={str(p.get("cached_input_tokens") or ""):>4} '
                f'gemini_total_ms={str(p.get("gemini_total_ms") or ""):>7}'
            )

        # Build combined report
        report = self._build_combined_report(
            results_a, events_a, phase_a_start,
            results_b, events_b, phase_b_start,
            anomalies_a,
        )

        self.stdout.write('\n' + report)

        output_path = Path(settings.BASE_DIR) / '_validation_imp5.md'
        output_path.write_text(report, encoding='utf-8')
        self.stdout.write(f'\n[output] Combined A/B report written to: {output_path}\n')

    # -----------------------------------------------------------------------
    # Report builders
    # -----------------------------------------------------------------------

    def _build_report(self, results, events, run_start, aborted, flag_value=True, label='cached'):
        """Build the markdown validation report for single-phase modes."""
        now_str = datetime.now(timezone.utc).isoformat()
        n_ok = sum(1 for r in results if r['ok'])
        n_fail = len(results) - n_ok

        # Map event index to each result row (by position in events list)
        event_by_idx = {}
        event_iter = iter(events)
        for r in results:
            if r['ok']:
                try:
                    evt = next(event_iter)
                    event_by_idx[r['idx']] = evt.payload
                except StopIteration:
                    pass

        # Build per-call timing table rows
        table_rows = []
        for r in results:
            p = event_by_idx.get(r['idx'], {})
            caching_mode = p.get('caching_mode', 'n/a')
            cache_hit = p.get('cache_hit', 'n/a')
            cached_tokens = p.get('cached_input_tokens', 'n/a')
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            q_short = r['query'][:38]
            table_rows.append(
                f'| {r["idx"] + 1} | {q_short} | {r["wall_ms"]} | '
                f'{caching_mode} | {cache_hit} | {cached_tokens} | {gemini_ms} |'
            )

        table_header = (
            '| # | Query | wall_ms | caching_mode | cache_hit | '
            'cached_input_tokens | gemini_total_ms |\n'
            '|---|-------|---------|--------------|-----------|'
            '---------------------|-----------------|'
        )
        table_body = '\n'.join(table_rows)

        # Aggregate statistics from events
        all_payloads = [evt.payload for evt in events]

        # Separate hit=True vs hit=False groups
        hit_true_ms = [
            p['gemini_total_ms'] for p in all_payloads
            if isinstance(p.get('gemini_total_ms'), (int, float))
            and p.get('cache_hit') is True
        ]
        hit_false_ms = [
            p['gemini_total_ms'] for p in all_payloads
            if isinstance(p.get('gemini_total_ms'), (int, float))
            and p.get('cache_hit') is False
        ]

        # Post-warmup calls: calls 2-10 (idx 1-9) = events after first
        post_warmup_events = all_payloads[1:] if len(all_payloads) > 1 else []
        post_warmup_hits = sum(
            1 for p in post_warmup_events if p.get('cache_hit') is True
        )
        post_warmup_total = len(post_warmup_events)

        # Generate stats block
        stats_lines = []
        verdict_pass = True
        verdict_reasons = []

        if aborted:
            stats_lines.append('- **Run aborted after first call failed.**')
            verdict_pass = False
            verdict_reasons.append('Run aborted on first call — likely API billing/auth failure')
        elif n_ok < 10:
            stats_lines.append(f'- **Only {n_ok}/10 calls succeeded.**')
            verdict_pass = False
            verdict_reasons.append(f'Only {n_ok}/10 calls succeeded')

        # Cache hit rate post-warmup
        if post_warmup_total > 0:
            hit_rate_pct = round(post_warmup_hits / post_warmup_total * 100, 1)
            hit_rate_ok = hit_rate_pct >= 95.0
            icon = 'OK' if hit_rate_ok else 'FAIL'
            stats_lines.append(
                f'- **Cache hit rate post-warmup (calls 2-10)**: '
                f'{post_warmup_hits}/{post_warmup_total} = {hit_rate_pct}% '
                f'{icon} (target >=95%)'
            )
            if not hit_rate_ok:
                verdict_pass = False
                verdict_reasons.append(
                    f'Cache hit rate {hit_rate_pct}% is below 95% threshold'
                )
        else:
            stats_lines.append('- **Cache hit rate post-warmup**: N/A (insufficient events)')

        # Latency reduction stats
        if hit_true_ms and hit_false_ms:
            median_hit = statistics.median(hit_true_ms)
            median_nohit = statistics.median(hit_false_ms)
            reduction_ms = median_nohit - median_hit
            reduction_pct = round(reduction_ms / median_nohit * 100, 1) if median_nohit > 0 else 0
            lat_ok = reduction_pct >= 50.0
            icon = 'OK' if lat_ok else 'FAIL'
            stats_lines.append(
                f'- **Median gemini_total_ms on cache_hit=True**: {median_hit:.0f}ms'
            )
            stats_lines.append(
                f'- **Median gemini_total_ms on cache_hit=False**: {median_nohit:.0f}ms'
            )
            stats_lines.append(
                f'- **Latency reduction on cache_hit**: '
                f'{reduction_ms:.0f}ms / {reduction_pct}% drop '
                f'{icon} (target >=50%)'
            )
            if not lat_ok:
                verdict_pass = False
                verdict_reasons.append(
                    f'Latency reduction {reduction_pct}% is below 50% threshold'
                )
        elif hit_true_ms and not hit_false_ms:
            # All calls were cache hits
            median_hit = statistics.median(hit_true_ms)
            uncached_baseline = 3200  # known uncached baseline ~3200ms from spec
            lat_ok = median_hit < 1800
            icon = 'OK' if lat_ok else 'FAIL'
            stats_lines.append(
                f'- **Median gemini_total_ms on cache_hit=True**: {median_hit:.0f}ms'
            )
            stats_lines.append(
                f'- **No cold baseline observed** (all calls reported cache_hit=True). '
                f'Comparing against known uncached baseline ~{uncached_baseline}ms.'
            )
            reduction_pct = round((uncached_baseline - median_hit) / uncached_baseline * 100, 1)
            stats_lines.append(
                f'- **Effective latency reduction vs baseline**: '
                f'{reduction_pct}% drop {icon} (target >=50%)'
            )
            if not lat_ok:
                verdict_pass = False
                verdict_reasons.append(
                    f'Median cache-hit latency {median_hit:.0f}ms exceeds 1800ms target'
                )
        elif not hit_true_ms and hit_false_ms:
            stats_lines.append(
                '- **All calls reported cache_hit=False.** Caching appears broken.'
            )
            verdict_pass = False
            verdict_reasons.append('All calls reported cache_hit=False — caching not working')
        else:
            stats_lines.append('- **No timing data available** — all events missing or failed.')
            verdict_pass = False
            verdict_reasons.append('No timing data available')

        # Spec prediction match
        if verdict_pass:
            stats_lines.append('- **Spec prediction match**: OK — delivers as predicted')
        else:
            stats_lines.append('- **Spec prediction match**: FAIL — does NOT match prediction')

        stats_block = '\n'.join(stats_lines)

        # Verdict block
        if verdict_pass:
            verdict_block = (
                '- OK IMP-5 implementation works as specified.\n'
                '- **Recommend**: prod flag flip (`context_caching_enabled=True` in production env).\n'
                '- **Caveat**: production multi-worker deploy MUST first swap `CACHES` to '
                'django-redis (per services.py settings comment block).'
            )
        else:
            causes = '\n'.join(f'  - {r}' for r in verdict_reasons) if verdict_reasons else '  - Unknown'
            verdict_block = (
                '- FAIL IMP-5 does NOT match spec prediction.\n'
                f'- Possible causes:\n{causes}\n'
                '- **Recommend**: do NOT flip prod flag. Investigate before next /review cycle.'
            )

        wall_note = (
            '> **Note on wall_ms for call 1**: wall_ms on the first call includes '
            '`caches.create()` HTTP round-trip (outside `gemini_total_ms` window). '
            'Expect wall_ms[1] >> gemini_total_ms[1]; calls 2-10 wall_ms ~= gemini_total_ms.'
        )

        report = f"""# IMP-5 Staging Validation Results

## Run summary
- Date: {now_str}
- Mode: {label}
- Queries executed: {len(results)}
- Successful: {n_ok}/10
- Failed: {n_fail}/10
- context_caching_enabled (runtime override): {flag_value}

{wall_note}

## Per-call timing
{table_header}
{table_body}

## Aggregated statistics
{stats_block}

## Verdict
{verdict_block}
"""
        return report

    def _build_abort_report(self, results_a, phase_a_start):
        """Minimal abort report when Phase A first call fails."""
        now_str = datetime.now(timezone.utc).isoformat()
        n_ok = sum(1 for r in results_a if r['ok'])
        err = results_a[0].get('error', 'unknown') if results_a else 'no results'

        return f"""# IMP-5 Staging Validation Results — Control vs Cached A/B

## Run summary
- Date: {now_str}
- Mode: both
- Phase A (control, flag OFF): ABORTED on first call
- Phase B (cached, flag ON): NOT RUN

## Abort reason
Phase A first call failed: {err}

This typically indicates a GEMINI_API_KEY billing/auth issue (403 PERMISSION_DENIED).

## Phase A — Partial results
- Calls attempted: {len(results_a)}
- Calls succeeded: {n_ok}

## Verdict (same-session A/B comparison)
- FAIL: Phase A aborted — no valid baseline established.
- **Diagnosis**: API authentication or billing failure prevented Phase A from completing.
- **Recommend prod flag flip**: no
- **Action**: Check GEMINI_API_KEY billing status and retry.
"""

    def _build_combined_report(
        self,
        results_a, events_a, phase_a_start,
        results_b, events_b, phase_b_start,
        anomalies_a,
    ):
        """Build the combined A/B markdown report for --mode=both."""
        now_str = datetime.now(timezone.utc).isoformat()

        n_ok_a = sum(1 for r in results_a if r['ok'])
        n_ok_b = sum(1 for r in results_b if r['ok'])

        # ---- Map events to result rows by position ----
        def _map_events(results, events):
            event_by_idx = {}
            event_iter = iter(events)
            for r in results:
                if r['ok']:
                    try:
                        evt = next(event_iter)
                        event_by_idx[r['idx']] = evt.payload
                    except StopIteration:
                        pass
            return event_by_idx

        ev_map_a = _map_events(results_a, events_a)
        ev_map_b = _map_events(results_b, events_b)

        # ---- Phase A table ----
        rows_a = []
        for r in results_a:
            p = ev_map_a.get(r['idx'], {})
            caching_mode = p.get('caching_mode', 'n/a')
            cache_hit = p.get('cache_hit', 'n/a')
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            rows_a.append(
                f'| {r["idx"] + 1} | {r["query"][:38]} | {r["wall_ms"]} | '
                f'{caching_mode} | {cache_hit} | {gemini_ms} |'
            )

        table_a_header = (
            '| # | Query | wall_ms | caching_mode | cache_hit | gemini_total_ms |\n'
            '|---|-------|---------|--------------|-----------|-----------------|'
        )
        table_a_body = '\n'.join(rows_a)

        # ---- Phase B table ----
        rows_b = []
        for r in results_b:
            p = ev_map_b.get(r['idx'], {})
            caching_mode = p.get('caching_mode', 'n/a')
            cache_hit = p.get('cache_hit', 'n/a')
            cached_tokens = p.get('cached_input_tokens', 'n/a')
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            rows_b.append(
                f'| {r["idx"] + 1} | {r["query"][:38]} | {r["wall_ms"]} | '
                f'{caching_mode} | {cache_hit} | {cached_tokens} | {gemini_ms} |'
            )

        table_b_header = (
            '| # | Query | wall_ms | caching_mode | cache_hit | '
            'cached_input_tokens | gemini_total_ms |\n'
            '|---|-------|---------|--------------|-----------|'
            '---------------------|-----------------|'
        )
        table_b_body = '\n'.join(rows_b)

        # ---- Phase A stats ----
        payloads_a = [evt.payload for evt in events_a]
        # For control phase, all should be cache_hit=None or False
        # Use all events for Phase A median (no warmup concept for uncached baseline)
        ms_a_all = [
            p['gemini_total_ms'] for p in payloads_a
            if isinstance(p.get('gemini_total_ms'), (int, float))
        ]
        median_a = statistics.median(ms_a_all) if ms_a_all else None

        # ---- Phase B stats ----
        payloads_b = [evt.payload for evt in events_b]
        # Post-warmup: calls 2-10 (events index 1-9)
        post_warmup_b = payloads_b[1:] if len(payloads_b) > 1 else []
        ms_b_postwarmup = [
            p['gemini_total_ms'] for p in post_warmup_b
            if isinstance(p.get('gemini_total_ms'), (int, float))
        ]
        median_b = statistics.median(ms_b_postwarmup) if ms_b_postwarmup else None

        # Cache hit rate Phase B post-warmup
        b_hits_postwarmup = sum(1 for p in post_warmup_b if p.get('cache_hit') is True)
        b_total_postwarmup = len(post_warmup_b)
        hit_rate_pct_b = (
            round(b_hits_postwarmup / b_total_postwarmup * 100, 1)
            if b_total_postwarmup > 0 else None
        )

        # ---- A/B delta ----
        if median_a is not None and median_b is not None:
            delta_ms = median_a - median_b
            delta_pct = round(delta_ms / median_a * 100, 1) if median_a > 0 else 0.0
            spec_ok = delta_pct >= 50.0 and (1400 <= median_b <= 1800)
            spec_match_icon = 'OK' if spec_ok else 'FAIL'
            # Hit rate check
            hit_rate_ok = hit_rate_pct_b is not None and hit_rate_pct_b >= 95.0
        else:
            delta_ms = None
            delta_pct = None
            spec_ok = False
            spec_match_icon = 'N/A'
            hit_rate_ok = False

        # ---- Anomaly section ----
        anomaly_block = ''
        if anomalies_a:
            anomaly_lines = '\n'.join(f'- {a.strip()}' for a in anomalies_a)
            anomaly_block = f'\n**Phase A anomalies detected:**\n{anomaly_lines}\n'

        # ---- Computed A/B table ----
        if median_a is not None and median_b is not None:
            delta_row = (
                f'| Median gemini_total_ms | {median_a:.0f}ms | {median_b:.0f}ms | '
                f'{delta_ms:.0f}ms | {delta_pct:.1f}% |'
            )
            spec_row = '| Spec prediction | — | 1400-1800ms | — | ≥50% drop expected |'
            ab_table = (
                '| Metric | Phase A (control) | Phase B (cached, post-warmup) | Delta | % drop |\n'
                '|--------|-------------------|-------------------------------|-------|--------|\n'
                f'{delta_row}\n'
                f'{spec_row}'
            )
        else:
            ab_table = '_Insufficient data to compute A/B delta._'

        # ---- Verdict block ----
        if median_a is not None and median_b is not None:
            spec_range_ok = 1400 <= median_b <= 1800
            if spec_ok:
                verdict_match = f'OK — {delta_pct:.1f}% drop, Phase B median {median_b:.0f}ms in [1400-1800ms]'
                diagnosis = (
                    f'Phase B (cached) reduced latency by {delta_pct:.1f}% vs Phase A (uncached), '
                    f'from {median_a:.0f}ms to {median_b:.0f}ms (post-warmup). '
                    'Both the ≥50% threshold and the 1400-1800ms target range are satisfied.'
                )
                recommend_flip = 'yes'
                cost_note = (
                    f'At {median_b:.0f}ms vs {median_a:.0f}ms, the {delta_pct:.1f}% reduction '
                    'is material for user-perceived latency. Cached tokens reduce input cost as well.'
                )
            elif delta_pct is not None and delta_pct >= 50.0 and not spec_range_ok:
                verdict_match = (
                    f'PARTIAL — ≥50% drop achieved ({delta_pct:.1f}%), '
                    f'but Phase B median {median_b:.0f}ms is outside [1400-1800ms] target'
                )
                diagnosis = (
                    f'Latency reduction of {delta_pct:.1f}% exceeds the 50% threshold, '
                    f'but the cached median ({median_b:.0f}ms) falls outside the predicted 1400-1800ms range. '
                    'Consider whether the spec range was set under different network conditions.'
                )
                recommend_flip = 'yes (reduction is real, range is a soft target)'
                cost_note = f'At {median_b:.0f}ms vs {median_a:.0f}ms, the improvement is real.'
            else:
                pct_str = f'{delta_pct:.1f}%' if delta_pct is not None else 'N/A'
                verdict_match = f'FAIL — only {pct_str} drop (target ≥50%)'
                diagnosis = (
                    f'Phase B median ({median_b:.0f}ms) is not sufficiently lower than '
                    f'Phase A baseline ({median_a:.0f}ms). '
                    'IMP-5 caching is not delivering the expected latency savings.'
                )
                recommend_flip = 'no'
                cost_note = ''
        else:
            verdict_match = 'N/A — insufficient data'
            diagnosis = 'One or both phases produced insufficient timing data.'
            recommend_flip = 'no'
            cost_note = ''

        hit_rate_str = (
            f'{b_hits_postwarmup}/{b_total_postwarmup} = {hit_rate_pct_b}%'
            if hit_rate_pct_b is not None else 'N/A'
        )
        hit_rate_verdict = (
            f'{"OK" if hit_rate_ok else "FAIL"} (target ≥95%)'
            if hit_rate_pct_b is not None else 'N/A'
        )

        phase_a_median_str = f'{median_a:.0f}ms' if median_a is not None else 'N/A'
        phase_b_median_str = f'{median_b:.0f}ms' if median_b is not None else 'N/A'

        wall_note = (
            '> **Note on wall_ms for Phase B call 1**: wall_ms on Phase B call 1 includes '
            '`caches.create()` HTTP round-trip (outside `gemini_total_ms` window). '
            'Phase A has no such inflation. '
            'Phase B post-warmup stats exclude call 1 to isolate pure cached-inference latency.'
        )

        cost_section = f'\n- **Cost framing**: {cost_note}' if cost_note else ''

        report = f"""# IMP-5 Staging Validation Results — Control vs Cached A/B

## Run summary
- Date: {now_str}
- Mode: both
- Phase A (control, flag OFF): 10 queries, {n_ok_a} succeeded
- Phase B (cached, flag ON):   10 queries, {n_ok_b} succeeded

{wall_note}

## Phase A — Control (flag OFF, uncached baseline)
{anomaly_block}
{table_a_header}
{table_a_body}

**Phase A median gemini_total_ms**: {phase_a_median_str}

## Phase B — Cached (flag ON, with explicit cache)

{table_b_header}
{table_b_body}

**Phase B median gemini_total_ms (post-warmup, calls 2-10)**: {phase_b_median_str}
**Phase B cache hit rate (calls 2-10)**: {hit_rate_str} — {hit_rate_verdict}

## Computed A/B delta

{ab_table}

## Verdict (same-session A/B comparison)
- {spec_match_icon} Spec prediction match: {verdict_match}
- **Diagnosis**: {diagnosis}
- **Recommend prod flag flip**: {recommend_flip}{cost_section}
"""
        return report
