#!/usr/bin/env python3
"""DB/search quality regression harness — machine layer (no LLM judging).

Measures the three legs of "search returns the right buildings":
  A. vocab    — per-axis value dictionaries from the buildings DB (+ drift diff)
  B. parser   — live Gemini parse_query battery: mapping validity, concept drop,
                null-fallback rate (N repeat runs per query, nondeterminism-aware)
  C. search   — full parse->search_by_filters_scored run: tag match@10,
                positive placement of ground-truth-tagged buildings, vd gap
  D. images   — cover URL health for top-10 results (magic-byte sniff, thumb detect)

Output: tools/qc_runs/qc_<ts>.json + printed MD summary + diff vs previous run.
Exit 1 when a FAIL-grade issue or a >5pt metric regression is found (CI-able).

Usage (from backend/, venv python; needs .env with buildings DB + Gemini key):
    .venv/Scripts/python tools/db_qc.py                     # full battery
    .venv/Scripts/python tools/db_qc.py --parser-runs 1     # cheap parser pass
    .venv/Scripts/python tools/db_qc.py --skip-parser       # no Gemini parse phase
    .venv/Scripts/python tools/db_qc.py --only courtyard-brick,piloti-house
Judgment layer (image verdicts) is NOT here — the run JSON carries top-10
building ids + cover/gallery URLs per query for a separate visual-judge pass.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connections  # noqa: E402

from apps.recommendation import engine, services  # noqa: E402

RUNS_DIR = BACKEND_DIR / 'tools' / 'qc_runs'
DEFAULT_QUERIES = BACKEND_DIR / 'tools' / 'db_qc_queries.json'

# Axis -> (DB column, kind). Mirrors engine_filters semantics:
#   exact  = hard WHERE equality (program)
#   ilike  = single TEXT column ILIKE %v%
#   array  = TEXT[] EXISTS unnest ILIKE %v%
AXIS_COLUMNS = {
    'program': ('program', 'exact'),
    'material': ('material_visual', 'array'),
    'style': ('style', 'ilike'),
    'atmosphere': ('atmosphere', 'ilike'),
    'color_tone': ('color_tone', 'ilike'),
    'typology_primary': ('typology_primary', 'ilike'),
    'location_country': ('location_country', 'ilike'),
    'location_city': ('location_city', 'ilike'),
}
# Hard-WHERE axes in scored search (engine_filters._REQUIRED_SLATE_FIELDS_SET):
# an unmatchable value here empties the search entirely (worst failure class).
HARD_AXES = frozenset(('program', 'material', 'style', 'location_country'))

# Array axes dumped as vocabularies in phase A.
VOCAB_AXES = {
    'program': ('program', 'text'),
    'style': ('style', 'text'),
    'atmosphere': ('atmosphere', 'text'),
    'color_tone': ('color_tone', 'text'),
    'typology_primary': ('typology_primary', 'text'),
    'typology_tags': ('typology_tags', 'array'),
    'architectural_elements': ('architectural_elements', 'array'),
    'material_visual': ('material_visual', 'array'),
}

METADATA_TAG_FIELDS = (
    'axis_typology', 'axis_style', 'axis_atmosphere', 'axis_color_tone',
    'axis_material_visual', 'axis_typology_primary', 'axis_typology_tags',
    'axis_architectural_elements',
)

REGRESSION_PT = 5.0


def _cursor():
    return connections['buildings'].cursor()


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


# ---------------------------------------------------------------- phase A
def dump_vocab() -> dict:
    out = {}
    with _cursor() as cur:
        for axis, (col, kind) in VOCAB_AXES.items():
            if kind == 'text':
                cur.execute(
                    f'SELECT {col}, COUNT(*) FROM canonical_v2_buildings '
                    f'WHERE is_publishable = true AND {col} IS NOT NULL '
                    f'GROUP BY 1 ORDER BY 2 DESC'
                )
            else:
                cur.execute(
                    f'SELECT v, COUNT(*) FROM canonical_v2_buildings, unnest({col}) v '
                    f'WHERE is_publishable = true GROUP BY 1 ORDER BY 2 DESC'
                )
            out[axis] = {str(v): c for v, c in cur.fetchall()}
        cur.execute('SELECT COUNT(*) FROM canonical_v2_buildings WHERE is_publishable = true')
        out['_total_publishable'] = cur.fetchone()[0]
    return out


# BACK-PARSER-VOCAB-1: axes covered by the live-vocab prompt grounding + snapshot
# fallback in apps.recommendation.services.vocab. Mirrors _VOCAB_SNAPSHOT's axis set.
_SNAPSHOT_AXES = ('style', 'atmosphere', 'color_tone', 'typology_primary', 'architectural_elements')

# ASSISTANT example JSON objects in _CHAT_PHASE_SYSTEM_PROMPT start with this marker.
_ASSISTANT_LINE_RE = re.compile(r'^ASSISTANT:\s*(\{.*\})\s*$', re.MULTILINE)


def diff_vocab_vs_snapshot(vocab_dump: dict) -> list[str]:
    """Compare live per-axis VALUES (vocab_dump, from dump_vocab()) against
    services.vocab._VOCAB_SNAPSHOT. Returns a list of WARN strings (empty = no drift).

    Non-fatal -- this is a snapshot-refresh reminder, not a hard gate. Import is
    local to keep db_qc's module-load path free of the recommendation app's
    services package until main() actually needs it (mirrors the existing
    `from apps.recommendation import engine, services` import at module top,
    so this is really just documentation of intent).
    """
    from apps.recommendation.services.vocab import _VOCAB_SNAPSHOT

    warnings = []
    for axis in _SNAPSHOT_AXES:
        live_values = set(vocab_dump.get(axis, {}).keys())
        snapshot_values = set(_VOCAB_SNAPSHOT.get(axis, []))
        added = live_values - snapshot_values
        removed = snapshot_values - live_values
        if added:
            warnings.append(f'vocab drift: {axis} has NEW live values not in snapshot: {sorted(added)}')
        if removed:
            warnings.append(f'vocab drift: {axis} snapshot values missing from live DB: {sorted(removed)}')
    return warnings


def check_few_shot_conformance() -> list[str]:
    """Parse every 'ASSISTANT: {...}' example JSON object embedded in
    _CHAT_PHASE_SYSTEM_PROMPT, collect axis values from filters/filter_delta.set
    for the 5 grounded axes + program, and WARN for any value not present in the
    live vocab (or PROGRAM_VALUES for program). Case-sensitive compare; case
    mismatches are reported separately from genuinely-missing values.

    Non-fatal, no Gemini calls -- runs entirely against static prompt text +
    get_axis_vocab()/PROGRAM_VALUES. Returns a list of WARN strings (empty = clean).
    """
    from apps.recommendation.services._prompts import _CHAT_PHASE_SYSTEM_PROMPT, PROGRAM_VALUES
    from apps.recommendation import services

    live_vocab = services.get_axis_vocab()
    axes = _SNAPSHOT_AXES + ('program',)
    allowed = {axis: live_vocab.get(axis, []) for axis in _SNAPSHOT_AXES}
    allowed['program'] = PROGRAM_VALUES

    warnings = []
    for i, m in enumerate(_ASSISTANT_LINE_RE.finditer(_CHAT_PHASE_SYSTEM_PROMPT)):
        raw = m.group(1)
        try:
            obj = json.loads(raw)
        except Exception as e:  # noqa: BLE001 — one bad example must not kill the scan
            warnings.append(f'few-shot #{i}: JSON parse failed ({e})')
            continue

        candidates = []
        f = obj.get('filters')
        if isinstance(f, dict):
            candidates.append(f)
        fd = obj.get('filter_delta')
        if isinstance(fd, dict) and isinstance(fd.get('set'), dict):
            candidates.append(fd['set'])

        for axis in axes:
            for src in candidates:
                value = src.get(axis)
                if not isinstance(value, str) or not value.strip():
                    continue
                axis_allowed = allowed.get(axis, [])
                if value in axis_allowed:
                    continue
                case_hit = next(
                    (v for v in axis_allowed if isinstance(v, str) and v.lower() == value.lower()),
                    None,
                )
                if case_hit:
                    warnings.append(
                        f"few-shot #{i}: {axis}={value!r} case mismatch "
                        f"(live vocab has {case_hit!r})"
                    )
                else:
                    warnings.append(
                        f"few-shot #{i}: {axis}={value!r} not in live vocab/PROGRAM_VALUES"
                    )
    return warnings


# ---------------------------------------------------------------- phase B
_match_cache: dict[tuple[str, str], int] = {}


def matchable_count(axis: str, value: str) -> int | None:
    """How many publishable buildings the engine's own predicate would match.

    None = axis not checkable (year bounds, unknown key).
    """
    spec = AXIS_COLUMNS.get(axis)
    if spec is None or not isinstance(value, str) or not value.strip():
        return None
    key = (axis, value.lower())
    if key in _match_cache:
        return _match_cache[key]
    col, kind = spec
    with _cursor() as cur:
        if kind == 'exact':
            cur.execute(
                'SELECT COUNT(*) FROM canonical_v2_buildings '
                f'WHERE is_publishable = true AND {col} = %s', [value])
        elif kind == 'array':
            cur.execute(
                'SELECT COUNT(*) FROM canonical_v2_buildings '
                'WHERE is_publishable = true AND EXISTS '
                f'(SELECT 1 FROM unnest({col}) m WHERE m ILIKE %s)', [f'%{value}%'])
        else:
            cur.execute(
                'SELECT COUNT(*) FROM canonical_v2_buildings '
                f'WHERE is_publishable = true AND {col} ILIKE %s', [f'%{value}%'])
        n = cur.fetchone()[0]
    _match_cache[key] = n
    return n


def _is_null_fallback(filters: dict) -> bool:
    return not any(v is not None and v != '' for v in (filters or {}).values())


def _concept_present(concept: dict, filters: dict) -> bool:
    accepts = [a.lower() for a in concept.get('accept', [])]
    for v in (filters or {}).values():
        if isinstance(v, str) and any(a in v.lower() for a in accepts):
            return True
    return False


def run_parser_battery(queries: list[dict], runs: int) -> dict:
    per_query = {}
    for q in queries:
        rows = []
        for _ in range(runs):
            t0 = time.time()
            try:
                parsed = services.parse_query([{'role': 'user', 'text': q['query']}])
                filters = {k: v for k, v in (parsed.get('filters') or {}).items()
                           if v is not None}
                rows.append({
                    'filters': filters,
                    'elapsed_s': round(time.time() - t0, 2),
                    'null_fallback': _is_null_fallback(filters),
                    'error': None,
                })
            except Exception as e:  # noqa: BLE001 — battery must survive one bad run
                rows.append({'filters': {}, 'elapsed_s': round(time.time() - t0, 2),
                             'null_fallback': True, 'error': str(e)[:200]})
        ok_rows = [r for r in rows if not r['null_fallback']]

        unmatchable = []
        for r in ok_rows:
            for axis, value in r['filters'].items():
                n = matchable_count(axis, value) if isinstance(value, str) else None
                if n == 0:
                    sev = 'HARD-EMPTY' if axis in HARD_AXES else 'SOFT-SILENT'
                    unmatchable.append({'axis': axis, 'value': value, 'severity': sev})
        # dedupe
        seen = set()
        unmatchable = [u for u in unmatchable
                       if (k := (u['axis'], u['value'].lower())) not in seen
                       and not seen.add(k)]

        concept_drop = {}
        for c in q.get('concepts', []):
            present = sum(1 for r in ok_rows if _concept_present(c, r['filters']))
            concept_drop[c['name']] = {
                'present_runs': present, 'ok_runs': len(ok_rows),
                'drop_rate': round(1 - present / len(ok_rows), 2) if ok_rows else None,
            }

        per_query[q['id']] = {
            'runs': rows,
            'null_fallback_rate': round(
                sum(r['null_fallback'] for r in rows) / len(rows), 2),
            'unmatchable_values': unmatchable,
            'concept_drop': concept_drop,
            'elapsed_p50': round(statistics.median(r['elapsed_s'] for r in rows), 2),
        }

    all_rows = [r for pq in per_query.values() for r in pq['runs']]
    return {
        'per_query': per_query,
        'summary': {
            'total_runs': len(all_rows),
            'null_fallback_rate': round(
                sum(r['null_fallback'] for r in all_rows) / len(all_rows), 3)
            if all_rows else None,
            'queries_with_unmatchable': sum(
                1 for pq in per_query.values() if pq['unmatchable_values']),
            'queries_with_hard_empty': sum(
                1 for pq in per_query.values()
                if any(u['severity'] == 'HARD-EMPTY' for u in pq['unmatchable_values'])),
        },
    }


# ---------------------------------------------------------------- phase C
def _building_matches(concept: dict, metadata: dict) -> bool:
    accepts = [a.lower() for a in concept.get('accept', [])]
    for field in METADATA_TAG_FIELDS:
        v = metadata.get(field)
        vals = v if isinstance(v, list) else [v]
        for item in vals:
            if isinstance(item, str) and any(a in item.lower() for a in accepts):
                return True
    return False


def _vd_mentions(concept: dict, metadata: dict) -> bool:
    vd = (metadata.get('visual_description') or '').lower()
    return any(a in vd for a in
               [x.lower() for x in concept.get('vd_accept', concept.get('accept', []))])


def truth_total(concept: dict) -> int | None:
    axis, pattern = concept.get('truth_axis'), concept.get('truth_pattern')
    if not axis or not pattern:
        return None
    col_kind = VOCAB_AXES.get(axis)
    if col_kind is None:
        return None
    col, kind = col_kind
    with _cursor() as cur:
        if kind == 'array':
            cur.execute(
                'SELECT COUNT(*) FROM canonical_v2_buildings '
                'WHERE is_publishable = true AND EXISTS '
                f'(SELECT 1 FROM unnest({col}) v WHERE v ILIKE %s)', [pattern])
        else:
            cur.execute(
                'SELECT COUNT(*) FROM canonical_v2_buildings '
                f'WHERE is_publishable = true AND {col} ILIKE %s', [pattern])
        return cur.fetchone()[0]


def _truth_matches(concept: dict, metadata: dict) -> bool:
    axis, pattern = concept.get('truth_axis'), concept.get('truth_pattern')
    if not axis or not pattern:
        return False
    needle = pattern.strip('%').lower()
    v = metadata.get(f'axis_{axis}', metadata.get(axis))
    vals = v if isinstance(v, list) else [v]
    return any(isinstance(x, str) and needle in x.lower() for x in vals)


def run_search_battery(queries: list[dict], limit: int) -> dict:
    per_query = {}
    for q in queries:
        t0 = time.time()
        parsed = services.parse_query([{'role': 'user', 'text': q['query']}])
        filters = {k: v for k, v in (parsed.get('filters') or {}).items() if v is not None}
        results = []
        if filters or (parsed.get('raw_query') or '').strip():
            results = engine.search_by_filters_scored(
                filters,
                raw_query=parsed.get('raw_query') or q['query'],
                filter_priority=parsed.get('filter_priority') or [],
                limit=limit,
                image_focus=parsed.get('image_focus'),
            )
        is_fallback = not results
        elapsed = round(time.time() - t0, 2)

        concepts_out = {}
        for c in q.get('concepts', []):
            top10 = results[:10]
            tag_hits10 = sum(1 for r in top10 if _building_matches(c, r['metadata']))
            positive_ranks = [i + 1 for i, r in enumerate(results)
                              if _truth_matches(c, r['metadata'])]
            vd_only = sum(
                1 for r in results
                if _vd_mentions(c, r['metadata']) and not _building_matches(c, r['metadata']))
            concepts_out[c['name']] = {
                'tag_match_at_10': round(tag_hits10 / max(len(top10), 1), 2),
                'truth_total_in_db': truth_total(c),
                'positives_returned': len(positive_ranks),
                'positives_in_top10': sum(1 for r in positive_ranks if r <= 10),
                'positive_ranks': positive_ranks[:20],
                'vd_mention_without_tag': vd_only,
            }

        per_query[q['id']] = {
            'parsed_filters': filters,
            'is_fallback': is_fallback,
            'n_results': len(results),
            'elapsed_s': elapsed,
            'concepts': concepts_out,
            'top10': [{
                'canonical_bld_id': r['canonical_bld_id'],
                'name': r['name'],
                'image_url': r.get('image_url') or '',
                'gallery_sample': [u for u in (r.get('gallery') or [])
                                   if 'divisare' in u][:3],
            } for r in results[:10]],
        }
    return {'per_query': per_query}


# ---------------------------------------------------------------- phase D
_IMG_MAGIC = (b'\xff\xd8', b'\x89PNG', b'GIF8', b'RIFF')


def _check_image(url: str) -> dict:
    if not url:
        return {'url': url, 'ok': False, 'why': 'empty'}
    if '/thumbs/' in url or re.search(r'[?&]w=2\d\d(&|$)', url):
        return {'url': url, 'ok': False, 'why': 'thumbnail-url'}
    req = urllib.request.Request(
        url, headers={'Range': 'bytes=0-2047', 'User-Agent': 'Mozilla/5.0 (qc-harness)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            head = resp.read(2048)
    except Exception as e:  # noqa: BLE001
        return {'url': url, 'ok': False, 'why': f'fetch-error: {str(e)[:80]}'}
    if head.lstrip()[:1] in (b'<',):
        return {'url': url, 'ok': False, 'why': 'html-response'}
    if not any(head.startswith(m) for m in _IMG_MAGIC):
        return {'url': url, 'ok': False, 'why': 'not-image-bytes'}
    return {'url': url, 'ok': True, 'why': None}


def run_image_health(search_out: dict) -> dict:
    jobs = []
    for qid, pq in search_out['per_query'].items():
        for r in pq['top10']:
            jobs.append((qid, r['canonical_bld_id'], r['image_url']))
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_check_image, u): (qid, bid) for qid, bid, u in jobs}
        for fut in concurrent.futures.as_completed(futs):
            qid, bid = futs[fut]
            results.append({'query': qid, 'building': bid, **fut.result()})
    bad = [r for r in results if not r['ok']]
    return {
        'checked': len(results),
        'health_rate': round(1 - len(bad) / len(results), 3) if results else None,
        'failures': bad,
    }


# ---------------------------------------------------------------- diff + report
def _flatten_metrics(run: dict) -> dict[str, float]:
    m = {}
    ps = run.get('parser', {}).get('summary', {})
    if ps.get('null_fallback_rate') is not None:
        m['parser.null_fallback_rate'] = ps['null_fallback_rate'] * 100
    for qid, pq in run.get('search', {}).get('per_query', {}).items():
        for cname, c in pq.get('concepts', {}).items():
            m[f'search.{qid}.{cname}.tag_match_at_10'] = c['tag_match_at_10'] * 100
    ih = run.get('images', {})
    if ih.get('health_rate') is not None:
        m['images.health_rate'] = ih['health_rate'] * 100
    return m


def diff_vs_previous(current: dict) -> dict | None:
    prev_files = sorted(RUNS_DIR.glob('qc_*.json'))
    if not prev_files:
        return None
    prev = json.loads(prev_files[-1].read_text(encoding='utf-8'))
    cur_m, prev_m = _flatten_metrics(current), _flatten_metrics(prev)
    deltas, regressions = {}, []
    for k, v in cur_m.items():
        if k in prev_m:
            d = round(v - prev_m[k], 1)
            deltas[k] = d
            lower_is_better = 'fallback' in k
            if (d > REGRESSION_PT if lower_is_better else d < -REGRESSION_PT):
                regressions.append({'metric': k, 'delta_pt': d})
    return {'previous_run': prev_files[-1].name, 'deltas': deltas,
            'regressions': regressions}


def print_summary(run: dict) -> None:
    print('\n== DB QC scorecard ==')
    ps = run.get('parser', {}).get('summary')
    if ps:
        print(f"parser: {ps['total_runs']} runs | null-fallback "
              f"{ps['null_fallback_rate']:.0%} | unmatchable-value queries "
              f"{ps['queries_with_unmatchable']} (HARD-EMPTY {ps['queries_with_hard_empty']})")
        for qid, pq in run['parser']['per_query'].items():
            for u in pq['unmatchable_values']:
                print(f"  !! {qid}: {u['axis']}={u['value']!r} matches 0 buildings "
                      f"[{u['severity']}]")
            for cname, c in pq['concept_drop'].items():
                if c['drop_rate']:
                    print(f"  -- {qid}: concept '{cname}' dropped in "
                          f"{c['drop_rate']:.0%} of runs")
    for qid, pq in run.get('search', {}).get('per_query', {}).items():
        parts = [f"{c}:{v['tag_match_at_10']:.0%}@10"
                 + (f" pos_top10={v['positives_in_top10']}/{v['truth_total_in_db']}"
                    if v['truth_total_in_db'] is not None else '')
                 for c, v in pq['concepts'].items()]
        fb = ' FALLBACK' if pq['is_fallback'] else ''
        print(f"search {qid}: {' | '.join(parts)}{fb}")
    ih = run.get('images', {})
    if ih:
        print(f"images: health {ih['health_rate']:.0%} ({len(ih['failures'])} bad "
              f"of {ih['checked']})")
    d = run.get('diff')
    if d:
        print(f"diff vs {d['previous_run']}: "
              + (f"{len(d['regressions'])} REGRESSION(S): {d['regressions']}"
                 if d['regressions'] else 'no regressions'))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--queries', default=str(DEFAULT_QUERIES))
    ap.add_argument('--parser-runs', type=int, default=5)
    ap.add_argument('--limit', type=int, default=100)
    ap.add_argument('--skip-parser', action='store_true')
    ap.add_argument('--skip-images', action='store_true')
    ap.add_argument('--only', default='', help='comma-separated query ids')
    args = ap.parse_args()

    queries = json.loads(Path(args.queries).read_text(encoding='utf-8'))['queries']
    if args.only:
        wanted = {x.strip() for x in args.only.split(',')}
        queries = [q for q in queries if q['id'] in wanted]
        if not queries:
            print(f'no queries match --only {args.only}', file=sys.stderr)
            return 2

    # BACK-LLM-PROVIDER-1: stamp provider/model so A/B matrix runs are self-describing.
    _is_openai = settings.LLM_PROVIDER == 'openai'
    run: dict = {'ts': _now_stamp(), 'n_queries': len(queries),
                 'parser_runs': 0 if args.skip_parser else args.parser_runs,
                 'llm_provider': settings.LLM_PROVIDER,
                 'llm_model': settings.OPENAI_TEXT_MODEL if _is_openai else settings.GEMINI_TEXT_MODEL}
    t0 = time.time()

    print('[A] vocab dump...', flush=True)
    _vocab_dump = dump_vocab()
    run['vocab_counts'] = {k: len(v) if isinstance(v, dict) else v
                           for k, v in _vocab_dump.items()}
    # BACK-PARSER-VOCAB-1: store actual VALUES per axis (list) alongside counts,
    # and non-fatally WARN when live values differ from the snapshot fallback.
    run['vocab_values'] = {
        k: sorted(v.keys()) for k, v in _vocab_dump.items() if isinstance(v, dict)
    }
    run['vocab_snapshot_drift'] = diff_vocab_vs_snapshot(_vocab_dump)
    for w in run['vocab_snapshot_drift']:
        print(f'  WARN {w}')
    run['few_shot_conformance'] = check_few_shot_conformance()
    for w in run['few_shot_conformance']:
        print(f'  WARN {w}')

    if not args.skip_parser:
        print(f'[B] parser battery ({len(queries)} x {args.parser_runs} Gemini calls)...',
              flush=True)
        run['parser'] = run_parser_battery(queries, args.parser_runs)

    print(f'[C] search battery ({len(queries)} queries)...', flush=True)
    run['search'] = run_search_battery(queries, args.limit)

    if not args.skip_images:
        print('[D] image health...', flush=True)
        run['images'] = run_image_health(run['search'])

    run['elapsed_s'] = round(time.time() - t0, 1)
    run['diff'] = diff_vs_previous(run)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RUNS_DIR / f"qc_{run['ts']}.json"
    out_path.write_text(json.dumps(run, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    print_summary(run)
    print(f"\nrun saved: {out_path}  ({run['elapsed_s']}s)")

    hard_fail = (
        run.get('parser', {}).get('summary', {}).get('queries_with_hard_empty', 0) > 0
        or bool(run.get('diff') and run['diff']['regressions'])
    )
    return 1 if hard_fail else 0


if __name__ == '__main__':
    sys.exit(main())
