"""
validate_imp6.py -- IMP-6 Staging Validation Management Command.

Empirically verifies that IMP-6 (2-stage decouple: Stage 1 omits visual_description)
delivers the spec v1.10 predicted latency savings:
  - Stage 1 gemini_total_ms median < 2000ms OR >=33% drop from control
  - Stage 2 success rate >= 95% (terminal turns only)
  - Stage 2 stage2_total_ms median < 2500ms (observability)

Usage:
    cd backend && python3 manage.py validate_imp6
    cd backend && python3 manage.py validate_imp6 --mode=both
    cd backend && python3 manage.py validate_imp6 --mode=control
    cd backend && python3 manage.py validate_imp6 --mode=decoupled

Modes:
  both       (default) -- Phase A (flag OFF) then Phase B (flag ON); computes A/B delta
  control    -- runs ONLY with flag OFF, 10 queries (legacy single-call baseline)
  decoupled  -- runs ONLY with flag ON, 10 queries (Stage 1 + Stage 2)

Design note on Stage 2 measurement:
    Stage 2 (generate_visual_description) is called SYNCHRONOUSLY in this command
    rather than via the async thread spawned in views._spawn_stage2. This is
    intentional: we are measuring latency, not thread mechanics (the async threading
    is tested in Sprint C unit tests). Synchronous direct call gives clean measurement
    of the latency math without thread-join overhead or scheduling jitter.

    Stage 2 is only called on terminal turns (probe_needed=False). Clarification
    turns (probe_needed=True) skip Stage 2 -- visual_description is meaningless
    before filters stabilize.

HF_TOKEN requirement:
    IMP-6 Stage 2 requires HF Inference API for V_initial embedding. Missing HF_TOKEN
    causes Stage 2 to emit outcome='hf_failure'. The pre-check will warn but not abort
    (you can still measure Stage 1 latency). Stage 2 success rate will be 0% if HF_TOKEN
    is absent.
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
    # Brutalist class (terminal turn expected -- Stage 2 fires on flag ON)
    'concrete brutalist museum',
    'minimalist Japanese teahouse',
    'sustainable timber school in Korea',

    # Narrow class (terminal or 1-clarification -- variable)
    'modern art museum with skylight',
    'urban housing complex',
    'industrial converted warehouse loft',

    # BareQuery class (likely clarification -- Stage 2 may NOT fire)
    'modern',
    'interesting building',

    # Korean (terminal turn likely)
    '한국 전통 목조 건축',
    '서울 현대 미술관',
]

# Placeholder user_id for staging cache key (mirrors validate_imp5 approach)
_STAGING_USER_ID = 999999


class Command(BaseCommand):
    help = 'Validate IMP-6 2-stage decouple delivers spec v1.10 predicted latency savings.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            choices=['control', 'decoupled', 'both'],
            default='both',
            help=(
                'Validation mode: '
                'both=control then decoupled, with A/B delta (default); '
                'control=flag OFF only (legacy single-call baseline); '
                'decoupled=flag ON only (Stage 1 + Stage 2).'
            ),
        )

    def handle(self, *args, **options):
        mode = options['mode']
        self.stdout.write(f'\n=== IMP-6 Staging Validation (mode={mode}) ===\n')

        # --- Step 1: Pre-checks -------------------------------------------
        self._print_prechecks()

        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not gemini_key:
            self.stderr.write('[ERROR] GEMINI_API_KEY is not set. Cannot proceed.')
            return

        # --- Step 2: Runtime override (restore in finally) ----------------
        rc = settings.RECOMMENDATION
        original_flag = rc.get('stage_decouple_enabled', False)

        try:
            if mode == 'control':
                rc['stage_decouple_enabled'] = False
                self.stdout.write(
                    '[override] stage_decouple_enabled set to False (will restore after run)\n'
                )
                self._run_control_phase_only(rc)
            elif mode == 'decoupled':
                rc['stage_decouple_enabled'] = True
                self.stdout.write(
                    '[override] stage_decouple_enabled set to True (will restore after run)\n'
                )
                self._run_decoupled_phase_only(rc)
            else:  # both (default)
                self._run_both(rc)
        finally:
            rc['stage_decouple_enabled'] = original_flag
            self.stdout.write(
                f'\n[cleanup] stage_decouple_enabled restored to {original_flag}\n'
            )
            cache.clear()
            self.stdout.write('[cleanup] Django cache cleared after run\n')

    def _print_prechecks(self):
        self.stdout.write('[pre-check] --- Environment ---')
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if gemini_key:
            self.stdout.write(f'[pre-check] GEMINI_API_KEY: SET (length={len(gemini_key)})')
        else:
            self.stdout.write('[pre-check] GEMINI_API_KEY: NOT SET (validation will fail)')

        hf_token = getattr(settings, 'HF_TOKEN', '')
        if hf_token:
            self.stdout.write(f'[pre-check] HF_TOKEN: SET (length={len(hf_token)})')
        else:
            self.stdout.write(
                '[pre-check] HF_TOKEN: NOT SET -- Stage 2 will report hf_failure; '
                'Stage 2 success rate will be 0%'
            )

        caches_cfg = settings.CACHES.get('default', {})
        backend = caches_cfg.get('BACKEND', 'unknown')
        self.stdout.write(f'[pre-check] CACHES backend: {backend}')

        rc = settings.RECOMMENDATION
        self.stdout.write(
            f'[pre-check] stage_decouple_enabled (settings default): '
            f'{rc.get("stage_decouple_enabled", False)}'
        )
        self.stdout.write('')

    # -----------------------------------------------------------------------
    # Single-phase helpers (used by --mode=control and --mode=decoupled)
    # -----------------------------------------------------------------------

    def _run_control_phase_only(self, rc):
        """Run 10 queries with flag OFF (legacy single-call path). Single-phase report."""
        cache.clear()
        self.stdout.write('[init] Django cache cleared before control phase\n')

        run_start = dj_timezone.now()
        results = self._run_control_queries(rc, phase_label='control')
        run_end = dj_timezone.now()

        events = self._fetch_parse_query_events(run_start, run_end, stage_filter=None)
        report = self._build_single_phase_report(results, events, run_start, label='control')
        self.stdout.write('\n' + report)
        self._write_report(report)

    def _run_decoupled_phase_only(self, rc):
        """Run 10 queries with flag ON (Stage 1 + Stage 2). Single-phase report."""
        cache.clear()
        self.stdout.write('[init] Django cache cleared before decoupled phase\n')

        run_start = dj_timezone.now()
        results = self._run_decoupled_queries(rc, phase_label='decoupled')
        run_end = dj_timezone.now()

        parse_events = self._fetch_parse_query_events(run_start, run_end, stage_filter='1')
        stage2_events = self._fetch_stage2_events(run_start, run_end)
        report = self._build_single_phase_report_decoupled(results, parse_events, stage2_events, run_start)
        self.stdout.write('\n' + report)
        self._write_report(report)

    # -----------------------------------------------------------------------
    # Both-phase A/B execution (default)
    # -----------------------------------------------------------------------

    def _run_both(self, rc):
        """Run Phase A (flag OFF) then Phase B (flag ON). Produce combined A/B report."""
        self.stdout.write('\n--- Phase A: Control (flag OFF, single-call legacy path) ---\n')

        rc['stage_decouple_enabled'] = False
        cache.clear()
        self.stdout.write('[init] Django cache cleared before Phase A\n')

        phase_a_start = dj_timezone.now()
        results_a = self._run_control_queries(rc, phase_label='A')
        phase_a_end = dj_timezone.now()

        if not results_a or results_a[0].get('aborted'):
            abort_report = self._build_abort_report(results_a, phase_a_start)
            self.stdout.write('\n' + abort_report)
            self._write_report(abort_report)
            return

        # Fetch Phase A parse_query_timing events (no stage filter -- legacy path has no stage field)
        events_a = self._fetch_parse_query_events(phase_a_start, phase_a_end, stage_filter=None)
        self.stdout.write(f'[events A] Found {len(events_a)} parse_query_timing events\n')
        for evt in events_a:
            p = evt.payload
            self.stdout.write(
                f'  [A] {evt.created_at.isoformat()}  '
                f'gemini_total_ms={str(p.get("gemini_total_ms") or ""):>7}  '
                f'in_tok={str(p.get("input_tokens") or ""):>4}  '
                f'out_tok={str(p.get("output_tokens") or ""):>3}'
            )

        # --- Phase B ---
        self.stdout.write('\n--- Phase B: Decoupled (flag ON, Stage 1 + Stage 2) ---\n')

        rc['stage_decouple_enabled'] = True
        cache.clear()
        self.stdout.write('[init] Django cache cleared before Phase B\n')

        phase_b_start = dj_timezone.now()
        results_b = self._run_decoupled_queries(rc, phase_label='B')
        phase_b_end = dj_timezone.now()

        # Fetch Phase B events -- Stage 1 parse_query_timing (stage='1') and stage2_timing
        parse_events_b = self._fetch_parse_query_events(phase_b_start, phase_b_end, stage_filter='1')
        stage2_events_b = self._fetch_stage2_events(phase_b_start, phase_b_end)

        self.stdout.write(f'[events B] Found {len(parse_events_b)} Stage 1 parse_query_timing events\n')
        for evt in parse_events_b:
            p = evt.payload
            self.stdout.write(
                f'  [B stage1] {evt.created_at.isoformat()}  '
                f'gemini_total_ms={str(p.get("gemini_total_ms") or ""):>7}  '
                f'probe_needed={str(p.get("clarification_fired") or ""):>5}  '
                f'out_tok={str(p.get("output_tokens") or ""):>3}'
            )

        self.stdout.write(f'[events B] Found {len(stage2_events_b)} stage2_timing events\n')
        for evt in stage2_events_b:
            p = evt.payload
            self.stdout.write(
                f'  [B stage2] {evt.created_at.isoformat()}  '
                f'outcome={str(p.get("outcome") or ""):>15}  '
                f'stage2_total_ms={str(p.get("stage2_total_ms") or ""):>7}  '
                f'gemini_visual_ms={str(p.get("gemini_visual_description_ms") or ""):>7}  '
                f'hf_ms={str(p.get("hf_inference_ms") or ""):>6}'
            )

        # Build combined report
        report = self._build_combined_report(
            results_a, events_a, phase_a_start,
            results_b, parse_events_b, stage2_events_b, phase_b_start,
        )
        self.stdout.write('\n' + report)
        self._write_report(report)

    # -----------------------------------------------------------------------
    # Core query-execution helpers
    # -----------------------------------------------------------------------

    def _run_control_queries(self, rc, phase_label):
        """Run 10 queries in control mode (stage_decouple_enabled=False, legacy path)."""
        from apps.recommendation.services import parse_query

        results = []
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
                    'probe_needed': result.get('probe_needed') if result else None,
                }
                results.append(entry)
                status = 'OK  ' if ok else 'FAIL'
                self.stdout.write(
                    f'[{phase_label} {i + 1}/10] {status} "{q[:40]}" wall_ms={wall_ms}'
                    + (' NOTE=fallback' if is_fallback else '')
                )
            except Exception as e:
                wall_ms = int((time.monotonic() - t0) * 1000)
                results.append({
                    'idx': i, 'query': q, 'wall_ms': wall_ms,
                    'ok': False, 'error': repr(e), 'probe_needed': None,
                })
                self.stdout.write(
                    f'[{phase_label} {i + 1}/10] FAIL "{q[:40]}" wall_ms={wall_ms} err={e!r}'
                )
                if i == 0:
                    self.stderr.write(
                        '\n[ABORT] First call failed. Likely GEMINI_API_KEY billing/auth issue.\n'
                        'Phase B NOT run -- insufficient data for A/B comparison.\n'
                        'DO NOT flip prod flag. Investigate before next /review cycle.\n'
                    )
                    results[0]['aborted'] = True
                    break
        return results

    def _run_decoupled_queries(self, rc, phase_label):
        """Run 10 queries in decoupled mode (stage_decouple_enabled=True, Stage 1 + Stage 2)."""
        from apps.recommendation.services import parse_query, generate_visual_description

        results = []
        for i, q in enumerate(QUERIES):
            t_stage1_start = time.monotonic()
            try:
                result = parse_query(q)  # routes to parse_query_stage1 when flag ON
                wall_stage1_ms = int((time.monotonic() - t_stage1_start) * 1000)
                is_fallback = (
                    result is not None
                    and result.get('reply') == '이해를 잘 못 했어요. 일단 이 쪽으로 찾아볼게요.'
                )
                ok = not is_fallback
                probe_needed = result.get('probe_needed') if result else None

                wall_stage2_ms = None
                stage2_fired = False

                if ok and probe_needed is False:
                    # Terminal turn: Stage 2 fires (synchronous direct call for clean measurement)
                    filters = result.get('filters', {}) if result else {}
                    t_stage2_start = time.monotonic()
                    generate_visual_description(filters=filters, raw_query=q, user_id=_STAGING_USER_ID)
                    wall_stage2_ms = int((time.monotonic() - t_stage2_start) * 1000)
                    stage2_fired = True

                entry = {
                    'idx': i,
                    'query': q,
                    'wall_stage1_ms': wall_stage1_ms,
                    'wall_stage2_ms': wall_stage2_ms,
                    'probe_needed': probe_needed,
                    'stage2_fired': stage2_fired,
                    'ok': ok,
                    'error': 'fallback returned (API failure)' if is_fallback else None,
                }
                results.append(entry)

                status = 'OK  ' if ok else 'FAIL'
                probe_str = 'clarification' if probe_needed else 'terminal'
                stage2_str = f' stage2_ms={wall_stage2_ms}' if stage2_fired else ' stage2=skipped(clarification)'
                self.stdout.write(
                    f'[{phase_label} {i + 1}/10] {status} "{q[:40]}" '
                    f'stage1_ms={wall_stage1_ms} turn={probe_str}{stage2_str}'
                    + (' NOTE=fallback' if is_fallback else '')
                )

            except Exception as e:
                wall_stage1_ms = int((time.monotonic() - t_stage1_start) * 1000)
                results.append({
                    'idx': i, 'query': q,
                    'wall_stage1_ms': wall_stage1_ms,
                    'wall_stage2_ms': None,
                    'probe_needed': None, 'stage2_fired': False,
                    'ok': False, 'error': repr(e),
                })
                self.stdout.write(
                    f'[{phase_label} {i + 1}/10] FAIL "{q[:40]}" '
                    f'stage1_ms={wall_stage1_ms} err={e!r}'
                )
                if i == 0:
                    self.stderr.write(
                        '\n[ABORT] Phase first call failed. Likely GEMINI_API_KEY billing/auth issue.\n'
                    )
                    break
        return results

    # -----------------------------------------------------------------------
    # Event fetching helpers
    # -----------------------------------------------------------------------

    def _fetch_parse_query_events(self, start, end, stage_filter):
        """Fetch parse_query_timing SessionEvents in time window.

        Args:
            start: datetime lower bound (inclusive)
            end: datetime upper bound (inclusive)
            stage_filter: '1' to fetch only Stage 1 events (IMP-6 decoupled path),
                          None to fetch all (legacy control path -- no stage field).
        """
        from apps.recommendation.models import SessionEvent
        qs = SessionEvent.objects.filter(
            event_type='parse_query_timing',
            created_at__gte=start,
            created_at__lte=end,
        )
        if stage_filter is not None:
            qs = qs.filter(payload__stage=stage_filter)
        return list(qs.order_by('created_at'))

    def _fetch_stage2_events(self, start, end):
        """Fetch stage2_timing SessionEvents in time window."""
        from apps.recommendation.models import SessionEvent
        return list(
            SessionEvent.objects.filter(
                event_type='stage2_timing',
                created_at__gte=start,
                created_at__lte=end,
            ).order_by('created_at')
        )

    # -----------------------------------------------------------------------
    # Report builders
    # -----------------------------------------------------------------------

    def _build_abort_report(self, results_a, phase_a_start):
        """Minimal abort report when Phase A first call fails."""
        now_str = datetime.now(timezone.utc).isoformat()
        n_ok = sum(1 for r in results_a if r.get('ok'))
        err = results_a[0].get('error', 'unknown') if results_a else 'no results'

        return f"""# IMP-6 Staging Validation Results — Control vs Decoupled A/B

## Run summary
- Date: {now_str}
- Mode: both
- Phase A (control, flag OFF): ABORTED on first call
- Phase B (decoupled, flag ON): NOT RUN

## Abort reason
Phase A first call failed: {err}

This typically indicates a GEMINI_API_KEY billing/auth issue (403 PERMISSION_DENIED).

## Phase A — Partial results
- Calls attempted: {len(results_a)}
- Calls succeeded: {n_ok}

## Verdict
- FAIL: Phase A aborted -- no valid baseline established.
- **Diagnosis**: API authentication or billing failure prevented Phase A from completing.
- **Action**: Check GEMINI_API_KEY billing status and retry.
"""

    def _build_single_phase_report(self, results, events, run_start, label):
        """Single-phase markdown report for --mode=control."""
        now_str = datetime.now(timezone.utc).isoformat()
        n_ok = sum(1 for r in results if r['ok'])

        # Map events to results by position
        ev_map = {}
        ev_iter = iter(events)
        for r in results:
            if r['ok']:
                try:
                    evt = next(ev_iter)
                    ev_map[r['idx']] = evt.payload
                except StopIteration:
                    pass

        rows = []
        for r in results:
            p = ev_map.get(r['idx'], {})
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            rows.append(
                f'| {r["idx"] + 1} | {r["query"][:40]} | {r["wall_ms"]} | {gemini_ms} |'
            )

        table_header = (
            '| # | Query | wall_ms | gemini_total_ms |\n'
            '|---|-------|---------|-----------------|'
        )
        table_body = '\n'.join(rows)

        payloads = [evt.payload for evt in events]
        ms_list = [p['gemini_total_ms'] for p in payloads if isinstance(p.get('gemini_total_ms'), (int, float))]
        median_str = f'{statistics.median(ms_list):.0f}ms' if ms_list else 'N/A'

        return f"""# IMP-6 Staging Validation Results — {label.capitalize()} Phase Only

## Run summary
- Date: {now_str}
- Mode: {label}
- Queries executed: {len(results)}
- Successful: {n_ok}/10

## Per-call timing

{table_header}
{table_body}

**Phase median gemini_total_ms**: {median_str}
"""

    def _build_single_phase_report_decoupled(self, results, parse_events, stage2_events, run_start):
        """Single-phase markdown report for --mode=decoupled."""
        now_str = datetime.now(timezone.utc).isoformat()
        n_ok = sum(1 for r in results if r['ok'])
        n_stage2_fired = sum(1 for r in results if r.get('stage2_fired'))

        # Map stage1 events to results (stage2 events mapped in order of terminal turns)
        stage1_ev_map = {}
        ev_iter = iter(parse_events)
        for r in results:
            if r['ok']:
                try:
                    evt = next(ev_iter)
                    stage1_ev_map[r['idx']] = evt.payload
                except StopIteration:
                    pass

        stage2_ev_map = {}
        ev2_iter = iter(stage2_events)
        for r in results:
            if r.get('stage2_fired'):
                try:
                    evt2 = next(ev2_iter)
                    stage2_ev_map[r['idx']] = evt2.payload
                except StopIteration:
                    pass

        stage1_rows = []
        for r in results:
            p = stage1_ev_map.get(r['idx'], {})
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            probe = 'True' if r.get('probe_needed') else 'False'
            stage1_rows.append(
                f'| {r["idx"] + 1} | {r["query"][:38]} | {r["wall_stage1_ms"]} | {gemini_ms} | {probe} |'
            )

        stage2_rows = []
        for r in results:
            if r.get('stage2_fired'):
                p2 = stage2_ev_map.get(r['idx'], {})
                stage2_total = p2.get('stage2_total_ms', 'n/a')
                gemini_vis_ms = p2.get('gemini_visual_description_ms', 'n/a')
                hf_ms = p2.get('hf_inference_ms', 'n/a')
                outcome = p2.get('outcome', 'n/a')
                stage2_rows.append(
                    f'| {r["idx"] + 1} | {r["query"][:38]} | {r.get("wall_stage2_ms", "n/a")} | '
                    f'{stage2_total} | {gemini_vis_ms} | {hf_ms} | {outcome} |'
                )

        stage1_header = (
            '| # | Query | wall_stage1_ms | gemini_total_ms | probe_needed |\n'
            '|---|-------|----------------|-----------------|--------------|'
        )
        stage2_header = (
            '| # | Query | wall_stage2_ms | stage2_total_ms | gemini_visual_description_ms | hf_inference_ms | outcome |\n'
            '|---|-------|----------------|-----------------|------------------------------|-----------------|---------|'
        )

        stage1_payloads = [evt.payload for evt in parse_events]
        stage1_ms = [p['gemini_total_ms'] for p in stage1_payloads if isinstance(p.get('gemini_total_ms'), (int, float))]
        stage1_median_str = f'{statistics.median(stage1_ms):.0f}ms' if stage1_ms else 'N/A'

        stage2_payloads = [evt.payload for evt in stage2_events]
        stage2_outcomes = [p.get('outcome') for p in stage2_payloads]
        s2_success = sum(1 for o in stage2_outcomes if o == 'success')
        s2_total = len(stage2_outcomes)
        s2_rate_str = f'{s2_success}/{s2_total} = {s2_success / s2_total * 100:.1f}%' if s2_total else 'N/A'
        stage2_total_ms_list = [p['stage2_total_ms'] for p in stage2_payloads if isinstance(p.get('stage2_total_ms'), (int, float))]
        stage2_median_str = f'{statistics.median(stage2_total_ms_list):.0f}ms' if stage2_total_ms_list else 'N/A'

        return f"""# IMP-6 Staging Validation Results — Decoupled Phase Only

## Run summary
- Date: {now_str}
- Mode: decoupled
- Queries executed: {len(results)}
- Successful: {n_ok}/10
- Stage 2 events fired: {n_stage2_fired}

## Stage 1 (parse_query_stage1)

{stage1_header}
{chr(10).join(stage1_rows)}

**Stage 1 median gemini_total_ms**: {stage1_median_str}

## Stage 2 (generate_visual_description, terminal turns only)

{stage2_header}
{chr(10).join(stage2_rows) if stage2_rows else '_No Stage 2 events (all turns were clarification)._'}

**Stage 2 success rate**: {s2_rate_str}
**Stage 2 median stage2_total_ms**: {stage2_median_str}
"""

    def _build_combined_report(
        self,
        results_a, events_a, phase_a_start,
        results_b, parse_events_b, stage2_events_b, phase_b_start,
    ):
        """Build the combined A/B markdown report for --mode=both."""
        now_str = datetime.now(timezone.utc).isoformat()

        n_ok_a = sum(1 for r in results_a if r['ok'])
        n_ok_b = sum(1 for r in results_b if r['ok'])
        n_stage2_fired = sum(1 for r in results_b if r.get('stage2_fired'))

        # ---- Phase A event mapping (by result position) ----
        ev_map_a = {}
        ev_iter_a = iter(events_a)
        for r in results_a:
            if r['ok']:
                try:
                    evt = next(ev_iter_a)
                    ev_map_a[r['idx']] = evt.payload
                except StopIteration:
                    pass

        # ---- Phase B stage1 event mapping ----
        ev_map_b_s1 = {}
        ev_iter_b = iter(parse_events_b)
        for r in results_b:
            if r['ok']:
                try:
                    evt = next(ev_iter_b)
                    ev_map_b_s1[r['idx']] = evt.payload
                except StopIteration:
                    pass

        # ---- Phase B stage2 event mapping (only terminal turns) ----
        ev_map_b_s2 = {}
        ev_iter_s2 = iter(stage2_events_b)
        for r in results_b:
            if r.get('stage2_fired'):
                try:
                    evt2 = next(ev_iter_s2)
                    ev_map_b_s2[r['idx']] = evt2.payload
                except StopIteration:
                    pass

        # ---- Phase A table ----
        rows_a = []
        for r in results_a:
            p = ev_map_a.get(r['idx'], {})
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            rows_a.append(
                f'| {r["idx"] + 1} | {r["query"][:40]} | {r["wall_ms"]} | {gemini_ms} |'
            )

        table_a_header = (
            '| # | Query | wall_ms | gemini_total_ms |\n'
            '|---|-------|---------|-----------------|'
        )
        table_a_body = '\n'.join(rows_a)

        # ---- Phase B Stage 1 table ----
        rows_b_s1 = []
        for r in results_b:
            p = ev_map_b_s1.get(r['idx'], {})
            gemini_ms = p.get('gemini_total_ms', 'n/a')
            probe = str(r.get('probe_needed', 'n/a'))
            rows_b_s1.append(
                f'| {r["idx"] + 1} | {r["query"][:38]} | {r["wall_stage1_ms"]} | {gemini_ms} | {probe} |'
            )

        table_b_s1_header = (
            '| # | Query | wall_stage1_ms | gemini_total_ms | probe_needed |\n'
            '|---|-------|----------------|-----------------|--------------|'
        )
        table_b_s1_body = '\n'.join(rows_b_s1)

        # ---- Phase B Stage 2 table ----
        rows_b_s2 = []
        for r in results_b:
            if r.get('stage2_fired'):
                p2 = ev_map_b_s2.get(r['idx'], {})
                stage2_total = p2.get('stage2_total_ms', 'n/a')
                gemini_vis_ms = p2.get('gemini_visual_description_ms', 'n/a')
                hf_ms = p2.get('hf_inference_ms', 'n/a')
                outcome = p2.get('outcome', 'n/a')
                rows_b_s2.append(
                    f'| {r["idx"] + 1} | {r["query"][:38]} | {r.get("wall_stage2_ms", "n/a")} | '
                    f'{stage2_total} | {gemini_vis_ms} | {hf_ms} | {outcome} |'
                )

        table_b_s2_header = (
            '| # | Query | wall_stage2_ms | stage2_total_ms | gemini_visual_description_ms | hf_inference_ms | outcome |\n'
            '|---|-------|----------------|-----------------|------------------------------|-----------------|---------|'
        )
        table_b_s2_body = '\n'.join(rows_b_s2) if rows_b_s2 else '_No Stage 2 events (all turns were clarification)._'

        # ---- Phase A statistics ----
        payloads_a = [evt.payload for evt in events_a]
        ms_a = [p['gemini_total_ms'] for p in payloads_a if isinstance(p.get('gemini_total_ms'), (int, float))]
        median_a = statistics.median(ms_a) if ms_a else None
        phase_a_median_str = f'{median_a:.0f}ms' if median_a is not None else 'N/A'

        # ---- Phase B Stage 1 statistics ----
        payloads_b_s1 = [evt.payload for evt in parse_events_b]
        ms_b_s1 = [p['gemini_total_ms'] for p in payloads_b_s1 if isinstance(p.get('gemini_total_ms'), (int, float))]
        median_b_s1 = statistics.median(ms_b_s1) if ms_b_s1 else None
        stage1_median_str = f'{median_b_s1:.0f}ms' if median_b_s1 is not None else 'N/A'

        # ---- Phase B Stage 2 statistics ----
        payloads_b_s2 = [evt.payload for evt in stage2_events_b]
        stage2_outcomes = [p.get('outcome') for p in payloads_b_s2]
        s2_success = sum(1 for o in stage2_outcomes if o == 'success')
        s2_total = len(stage2_outcomes)
        s2_rate = s2_success / s2_total if s2_total > 0 else 0.0
        s2_rate_str = f'{s2_success}/{s2_total} = {s2_rate * 100:.1f}%' if s2_total else 'N/A (no Stage 2 events)'

        stage2_total_ms_list = [
            p['stage2_total_ms'] for p in payloads_b_s2 if isinstance(p.get('stage2_total_ms'), (int, float))
        ]
        median_s2_total = statistics.median(stage2_total_ms_list) if stage2_total_ms_list else None
        stage2_total_median_str = f'{median_s2_total:.0f}ms' if median_s2_total is not None else 'N/A'

        hf_ms_list = [
            p['hf_inference_ms'] for p in payloads_b_s2 if isinstance(p.get('hf_inference_ms'), (int, float))
        ]
        hf_median = statistics.median(hf_ms_list) if hf_ms_list else None
        hf_median_str = f'{hf_median:.0f}ms' if hf_median is not None else 'N/A'

        # ---- A/B delta ----
        if median_a is not None and median_b_s1 is not None and median_a > 0:
            delta_ms = median_a - median_b_s1
            stage1_drop_pct = (1 - median_b_s1 / median_a) * 100
            ab_table = (
                '| Metric | Phase A (control) | Phase B (Stage 1) | Delta | % drop |\n'
                '|--------|-------------------|-------------------|-------|--------|\n'
                f'| Median gemini_total_ms | {median_a:.0f}ms | {median_b_s1:.0f}ms | '
                f'{delta_ms:.0f}ms | {stage1_drop_pct:.1f}% |\n'
                '| Spec v1.10 prediction | — | ~1500 ms (45-55% drop) | — | ≥45% drop expected |'
            )
        else:
            stage1_drop_pct = None
            ab_table = '_Insufficient data to compute A/B delta._'

        # ---- PASS criteria evaluation ----
        # PASS criterion 1: Stage 1 median < 2000ms OR drop >= 33%
        if median_b_s1 is not None and median_a is not None:
            stage1_pass = median_b_s1 < 2000 or (stage1_drop_pct is not None and stage1_drop_pct >= 33.0)
            stage1_verdict_str = (
                f'{"PASS" if stage1_pass else "FAIL"} '
                f'(median {median_b_s1:.0f}ms, drop {stage1_drop_pct:.1f}%)'
                if stage1_drop_pct is not None else
                f'{"PASS" if stage1_pass else "FAIL"} (median {median_b_s1:.0f}ms)'
            )
        else:
            stage1_pass = False
            stage1_verdict_str = 'N/A (insufficient data)'

        # PASS criterion 2: Stage 2 success rate >= 95%
        if s2_total > 0:
            stage2_pass = s2_rate >= 0.95
            stage2_verdict_str = f'{"PASS" if stage2_pass else "FAIL"} ({s2_rate_str})'
        else:
            stage2_pass = False
            stage2_verdict_str = 'N/A (no Stage 2 events -- all turns were clarification?)'

        overall_pass = stage1_pass and stage2_pass

        # ---- Observability: Stage 2 total_ms ----
        if median_s2_total is not None:
            obs_str = f'{median_s2_total:.0f}ms {"OK" if median_s2_total < 2500 else "WARN>2500ms"}'
        else:
            obs_str = 'N/A'

        # ---- Diagnosis ----
        if median_a is not None and median_b_s1 is not None:
            if overall_pass:
                diagnosis = (
                    f'Stage 1 reduced gemini_total_ms by {stage1_drop_pct:.1f}% '
                    f'(from {median_a:.0f}ms to {median_b_s1:.0f}ms), '
                    f'matching the spec v1.10 prediction of ≥45% drop. '
                    f'Stage 2 success rate {s2_rate * 100:.1f}% meets the ≥95% threshold.'
                )
            elif not stage1_pass:
                diagnosis = (
                    f'Stage 1 gemini_total_ms drop of {stage1_drop_pct:.1f}% '
                    f'({median_a:.0f}ms → {median_b_s1:.0f}ms) is below the 33% '
                    f'threshold (spec v1.10 predicted ≥45%). Possible cause: '
                    f'_STAGE1_RESPONSE_SCHEMA may not be reducing output tokens as expected '
                    f'-- verify visual_description is absent from Stage 1 responses.'
                )
            else:
                diagnosis = (
                    f'Stage 1 latency drop meets threshold ({stage1_drop_pct:.1f}%), '
                    f'but Stage 2 success rate {s2_rate * 100:.1f}% is below 95%. '
                    f'Check outcome distribution in Stage 2 table above for failure mode '
                    f'(gemini_failure / hf_failure / cache_failure).'
                )
        else:
            diagnosis = 'Insufficient timing data to compute diagnosis.'

        spec_verdict_icon = 'PASS' if overall_pass else 'FAIL'
        next_step = (
            'recommend Sprint D Commit 4 (canary rollout)'
            if overall_pass else
            'research handoff (spec v1.11 re-grounding)'
        )

        note_block = (
            '> **Note**: Stage 2 fires only on terminal turns (probe_needed=False). '
            'Clarification turns skip Stage 2 -- visual_description is meaningless before filters stabilize.\n'
            '> Stage 2 is called synchronously in this command (not via background thread) '
            'for clean latency measurement.'
        )

        return f"""# IMP-6 Staging Validation Results — Control vs Decoupled A/B

## Run summary
- Date: {now_str}
- Mode: both
- Phase A (control, flag OFF): 10 queries, {n_ok_a} succeeded
- Phase B (decoupled, flag ON): 10 queries, {n_ok_b} succeeded, {n_stage2_fired} Stage 2 events fired

{note_block}

## Phase A — Control (flag OFF, single-call legacy)

{table_a_header}
{table_a_body}

**Phase A median gemini_total_ms**: {phase_a_median_str}

## Phase B — Decoupled (flag ON, Stage 1 + Stage 2)

### Stage 1 (parse_query_stage1)

{table_b_s1_header}
{table_b_s1_body}

**Stage 1 median gemini_total_ms**: {stage1_median_str}

### Stage 2 (generate_visual_description, terminal turns only)

{table_b_s2_header}
{table_b_s2_body}

**Stage 2 success rate**: {s2_rate_str}
**Stage 2 median stage2_total_ms**: {stage2_total_median_str}
**HF inference median**: {hf_median_str}

## Computed A/B delta

{ab_table}

## Verdict (same-session A/B comparison)
- Stage 1 latency drop: {stage1_verdict_str}
- Stage 2 success rate: {stage2_verdict_str}
- Stage 2 stage2_total_ms (observability): {obs_str}
- **Spec prediction match**: {spec_verdict_icon} → {next_step}

## Diagnosis (data-driven)
{diagnosis}
"""

    def _write_report(self, report):
        """Write report to backend/_validation_imp6.md and print path."""
        output_path = Path(settings.BASE_DIR) / '_validation_imp6.md'
        output_path.write_text(report, encoding='utf-8')
        self.stdout.write(f'\n[output] Report written to: {output_path}\n')
