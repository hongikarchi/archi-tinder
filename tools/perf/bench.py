"""In-process perf baseline harness (parse-query -> session create -> swipes -> result).

Run (from repo):   cd backend && python ../tools/perf/bench.py [--seed N] [--swipes 20] [--out DIR]
Also works with:   cd backend && python manage.py shell < <this file>   (uses defaults)

Talks to the REAL local DBs (backend/.env, Neon child dev branch) via DRF APIClient
in-process. Writes only through normal app code paths for user `perf_bench_user`.
Never touches prod. Does not modify repo files.
"""
import os, sys, re, json, time, random, statistics, threading, logging, argparse, datetime

BACKEND = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")) if "__file__" in globals() else os.getcwd()
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "perf-bench-out")

try:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=1234)
    ap.add_argument('--swipes', type=int, default=20)
    ap.add_argument('--sleep', type=float, default=0.3)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--label', default='baseline')
    ARGS = ap.parse_args() if __name__ == '__main__' and 'manage.py' not in sys.argv[0] else ap.parse_args([])
except SystemExit:
    raise
OUT = ARGS.out
os.makedirs(OUT, exist_ok=True)

os.chdir(BACKEND)
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from django.core.cache import cache, caches
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.contrib.auth.models import User
from rest_framework.test import APIClient

settings.PERF_TIMING_ENABLED = True
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

QUERIES = ["제주도 돌로 지은 명상 공간", "따뜻한 목재 주택", "서울 도심 오피스"]
LIKE_RATIO_N = 12  # of 20 -> 60% like; scaled for other swipe counts
MAIN_TID = threading.get_ident()

# ───────────────────────── instrumentation ─────────────────────────
class State:
    cur = None           # current request record
    reqs = []
    bg_stages = []       # stages logged from non-main threads
S = State()

class PerfHandler(logging.Handler):
    def emit(self, rec):
        try:
            ep, stg, ms, extra = rec.args
        except Exception:
            return
        item = {'endpoint': ep, 'stage': stg, 'ms': float(ms), 'extra': (extra or '').strip()}
        if rec.thread == MAIN_TID and S.cur is not None:
            S.cur['stages'].append(item)
        else:
            item['during'] = S.cur['label'] if S.cur else None
            item['bg'] = True
            S.bg_stages.append(item)

pl = logging.getLogger('perf_timing')
pl.setLevel(logging.INFO)
pl.addHandler(PerfHandler())
pl.propagate = False

# cache op counting (patch backend CLASS: caches are thread-local instances)
_tl = threading.local()
CACHE_METHODS = ['get', 'set', 'delete', 'get_many', 'set_many', 'incr', 'add', 'delete_many']
CACHE_CLS = type(caches['default'])
cache_bg_ops = {'n': 0}
def _wrap(name, orig):
    def w(self, *a, **k):
        depth = getattr(_tl, 'depth', 0)
        if depth == 0:
            if threading.get_ident() == MAIN_TID and S.cur is not None:
                c = S.cur['cache_ops']; c[name] = c.get(name, 0) + 1
            else:
                cache_bg_ops['n'] += 1
        _tl.depth = depth + 1
        try:
            return orig(self, *a, **k)
        finally:
            _tl.depth = depth
    return w
for _m in CACHE_METHODS:
    _o = getattr(CACHE_CLS, _m, None)
    if _o is not None:
        setattr(CACHE_CLS, _m, _wrap(_m, _o))

# DB commit counting (a commit is a network round trip not visible as a query)
_orig_commit = BaseDatabaseWrapper._commit
def _commit(self):
    if threading.get_ident() == MAIN_TID and S.cur is not None:
        c = S.cur['commits']; c[self.alias] = c.get(self.alias, 0) + 1
    return _orig_commit(self)
BaseDatabaseWrapper._commit = _commit

def norm_sql(sql):
    s = re.sub(r"'[^']*'", "'?'", sql)
    s = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "?", s)
    s = re.sub(r"\(\s*(%s\s*,\s*)+%s\s*\)", "(%s,…)", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", "?", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:400]

def make_wrapper(alias):
    def wrapper(execute, sql, params, many, context):
        t0 = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            ms = (time.perf_counter() - t0) * 1000
            if S.cur is not None:
                S.cur['queries'].append({'alias': alias, 'ms': round(ms, 2), 'sql': norm_sql(sql if isinstance(sql, str) else str(sql))})
    return wrapper

def do_request(label, kind, fn):
    rec = {'label': label, 'kind': kind, 'stages': [], 'queries': [], 'cache_ops': {}, 'commits': {}}
    S.cur = rec
    wr = [connections[a].execute_wrapper(make_wrapper(a)) for a in ('default', 'buildings')]
    for w in wr: w.__enter__()
    t0 = time.perf_counter()
    try:
        resp = fn()
    finally:
        rec['wall_ms'] = round((time.perf_counter() - t0) * 1000, 2)
        for w in reversed(wr): w.__exit__(None, None, None)
        S.cur = None
    rec['status'] = getattr(resp, 'status_code', None)
    S.reqs.append(rec)
    return resp, rec

# ───────────────────────── RTT measurement ─────────────────────────
def measure_rtts():
    out = {}
    for alias in ('default', 'buildings'):
        conn = connections[alias]
        with conn.cursor() as c:
            c.execute('SELECT 1')  # warm
            ts = []
            for _ in range(20):
                t0 = time.perf_counter(); c.execute('SELECT 1'); c.fetchall()
                ts.append((time.perf_counter() - t0) * 1000)
        out[alias] = {'select1_ms_median': round(statistics.median(ts), 2), 'min': round(min(ts), 2), 'max': round(max(ts), 2)}
    ts = []
    for _ in range(20):
        t0 = time.perf_counter(); cache.get('perf_bench_rtt_probe'); ts.append((time.perf_counter() - t0) * 1000)
    out['cache_get_ms_median'] = round(statistics.median(ts), 4)
    out['cache_backend'] = settings.CACHES['default']['BACKEND']
    fresh = []
    for _ in range(3):
        connections['buildings'].close()
        t0 = time.perf_counter()
        with connections['buildings'].cursor() as c:
            c.execute('SELECT 1')
        fresh.append((time.perf_counter() - t0) * 1000)
    out['buildings_fresh_connect_ms'] = [round(x, 1) for x in fresh]
    return out

# ───────────────────────── flow ─────────────────────────
def get_client():
    user, _ = User.objects.get_or_create(username='perf_bench_user', defaults={'email': 'perf_bench_user@example.invalid'})
    from apps.accounts.models import UserProfile
    prof = getattr(user, 'profile', None)
    if prof is None:
        prof = UserProfile.objects.filter(user=user).first() or UserProfile.objects.create(user=user, display_name='perf_bench_user')
    if getattr(prof, 'is_guest', False):
        prof.is_guest = False; prof.save(update_fields=['is_guest'])  # avoid 3-board guest gate
    c = APIClient(); c.force_authenticate(user=user)
    return c

def cid(card):
    return (card or {}).get('canonical_bld_id') or (card or {}).get('building_id')

def swipe_plan(rng, n):
    likes = round(n * 0.6)
    plan = ['like'] * likes + ['dislike'] * (n - likes)
    rng.shuffle(plan)
    return plan

def run_swipes(client, sid, first_card, prefetch_ids, tag, n, rng, notes):
    plan = swipe_plan(rng, n)
    card = first_card
    buf = [x for x in prefetch_ids if x]
    for i, action in enumerate(plan):
        bid = cid(card)
        if not bid:
            notes.append(f'{tag}: no next card at swipe {i}; stopped'); break
        body = {'canonical_bld_id': bid, 'action': action, 'idempotency_key': f'swp_{sid}_{bid}',
                'client_buffer_ids': buf[:10]}
        resp, rec = do_request(f'{tag}#s{i+1}', f'swipe_{action}', lambda: client.post(f'/api/v1/analysis/sessions/{sid}/swipes/', body, format='json'))
        rec['swipe_idx'] = i + 1; rec['tag'] = tag
        if resp.status_code != 200:
            notes.append(f'{tag}: swipe {i+1} -> HTTP {resp.status_code} {str(getattr(resp, "data", ""))[:150]}'); break
        d = resp.data
        rec['phase'] = (d.get('progress') or {}).get('phase')
        rec['completed'] = bool(d.get('is_analysis_completed'))
        card = d.get('next_image')
        buf = [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))]
        if rec['completed'] or d.get('session_status') == 'completed':
            if d.get('can_continue'):
                # frontend would call extend to keep going
                resp2, rec2 = do_request(f'{tag}#extend', 'swipe_extend', lambda: client.post(f'/api/v1/analysis/sessions/{sid}/swipes/', {'extend': True, 'client_buffer_ids': [b for b in buf if b]}, format='json'))
                rec2['tag'] = tag
                if resp2.status_code != 200:
                    notes.append(f'{tag}: extend -> HTTP {resp2.status_code}'); break
                d = resp2.data; card = d.get('next_image'); buf = [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))]
            else:
                notes.append(f'{tag}: session completed after {i+1} swipes (can_continue=False); stopped'); break
        time.sleep(ARGS.sleep)
    return

def main():
    t_start = time.time()
    notes = []
    rtts = measure_rtts()
    client = get_client()
    rng = random.Random(ARGS.seed)
    run_id = datetime.datetime.utcnow().strftime('%H%M%S')
    parsed_all = []

    # (a) parse-query, cold
    for qi, q in enumerate(QUERIES):
        resp, rec = do_request(f'parse#{qi}', 'parse_query', lambda: client.post('/api/v1/parse-query/', {'query': q}, format='json'))
        rec['tag'] = f'q{qi}'
        if resp.status_code != 200:
            notes.append(f'parse-query q{qi} -> HTTP {resp.status_code} {str(getattr(resp,"data",""))[:200]}'); parsed_all.append(None); continue
        d = resp.data
        rec['n_results'] = len(d.get('results') or []); rec['probe_needed'] = d.get('probe_needed')
        parsed_all.append({'raw_query': d.get('raw_query') or q, 'filters': d.get('structured_filters') or {},
                           'filter_priority': d.get('filter_priority') or [], 'visual_description': d.get('visual_description'),
                           'image_focus': d.get('image_focus'), 'seed_ids': []})

    # (b)(c)(d) sessions: pass 0 = cold caches, pass 1 = warm (same process, new sessions)
    for pas in (0, 1):
        pname = 'cold' if pas == 0 else 'warm'
        for qi, p in enumerate(parsed_all):
            if not p: continue
            tag = f'{pname}_q{qi}'
            body = {'name': f'bench-{run_id}-{pname}-{qi}', 'filters': p['filters'], 'filter_priority': p['filter_priority'],
                    'seed_ids': p['seed_ids'], 'raw_query': p['raw_query'], 'force_new': True}
            if p.get('visual_description'): body['visual_description'] = p['visual_description']
            if p.get('image_focus'): body['image_focus'] = p['image_focus']
            resp, rec = do_request(f'{tag}#create', 'session_create', lambda: client.post('/api/v1/analysis/sessions/', body, format='json'))
            rec['tag'] = tag; rec['pass'] = pname
            if resp.status_code not in (200, 201):
                notes.append(f'{tag}: session create -> HTTP {resp.status_code} {str(getattr(resp,"data",""))[:200]}'); continue
            d = resp.data; sid = d['session_id']
            time.sleep(ARGS.sleep)
            run_swipes(client, sid, d.get('next_image'), [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))], tag, ARGS.swipes, rng, notes)
            for r in S.reqs:
                if r.get('tag') == tag: r['pass'] = pname
            resp, rec = do_request(f'{tag}#result', 'session_result', lambda: client.get(f'/api/v1/analysis/sessions/{sid}/result/'))
            rec['tag'] = tag; rec['pass'] = pname
            if resp.status_code != 200:
                notes.append(f'{tag}: result -> HTTP {resp.status_code}')
    for r in S.reqs:
        if r['kind'] == 'parse_query': r['pass'] = 'cold'
    time.sleep(1.0)  # let last bg threads flush

    # ── derive per-request metrics ──
    d_rtt = rtts['default']['select1_ms_median']; b_rtt = rtts['buildings']['select1_ms_median']
    c_rtt = rtts['cache_get_ms_median']
    for r in S.reqs:
        qd = sum(1 for q in r['queries'] if q['alias'] == 'default'); qb = sum(1 for q in r['queries'] if q['alias'] == 'buildings')
        cd = r['commits'].get('default', 0); cb = r['commits'].get('buildings', 0)
        r['n_q_default'] = qd; r['n_q_buildings'] = qb
        r['n_roundtrips_default'] = qd + cd; r['n_roundtrips_buildings'] = qb + cb
        r['n_cache_ops'] = sum(r['cache_ops'].values())
        adj = (qd + cd) * max(d_rtt - 2, 0) + (qb + cb) * max(b_rtt - 2, 0) + r['n_cache_ops'] * (c_rtt - 1.5)
        r['est_prod_ms'] = round(r['wall_ms'] - adj, 1)
        r['sum_query_ms'] = round(sum(q['ms'] for q in r['queries']), 1)

    result = {'label': ARGS.label, 'ran_at_utc': datetime.datetime.utcnow().isoformat() + 'Z', 'seed': ARGS.seed,
              'swipes_per_session': ARGS.swipes, 'queries': QUERIES, 'rtts': rtts, 'notes': notes,
              'caveats': ['DB queries/cache ops in background threads (telemetry, async prefetch) are NOT captured per request; bg perf_timing stages are listed in bg_stages.',
                          'Cache backend locally is LocMem (REDIS_URL unset): local cache RTT ~0 so the model ADDS 1.5ms per cache op to approximate prod Redis.',
                          'Commits are counted as extra DB round trips (not visible as queries).',
                          'parse_query wall time includes real LLM latency, which is NOT reduced by the RTT model.'],
              'cache_bg_ops_total': cache_bg_ops['n'], 'requests': S.reqs, 'bg_stages': S.bg_stages,
              'duration_s': round(time.time() - t_start, 1)}
    with open(os.path.join(OUT, 'baseline.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    write_md(result)
    print('DONE', OUT, 'requests:', len(S.reqs), 'notes:', notes)

# ───────────────────────── report ─────────────────────────
def pct(vals, p):
    if not vals: return None
    v = sorted(vals); k = max(0, min(len(v) - 1, int(round(p / 100 * len(v) + 0.5)) - 1))
    return v[k]

def esc(x): return x[:220].replace('|', chr(92) + '|')

def med(vals): return statistics.median(vals) if vals else None
def f1(x): return '-' if x is None else (f'{x:.1f}' if isinstance(x, float) else str(x))

def write_md(res):
    R = res['requests']; L = []
    L.append(f"# Perf baseline ({res['label']})\n")
    L.append(f"Ran {res['ran_at_utc']} seed={res['seed']} swipes/session={res['swipes_per_session']} duration={res['duration_s']}s\n")
    rt = res['rtts']
    L.append('## Measured local RTTs\n')
    L.append(f"- default DB SELECT 1 median: **{rt['default']['select1_ms_median']} ms** (min {rt['default']['min']}, max {rt['default']['max']})")
    L.append(f"- buildings DB SELECT 1 median: **{rt['buildings']['select1_ms_median']} ms** (min {rt['buildings']['min']}, max {rt['buildings']['max']})")
    L.append(f"- cache.get median: **{rt['cache_get_ms_median']} ms** ({rt['cache_backend']})")
    L.append(f"- buildings fresh connect+SELECT 1 (x3): {rt['buildings_fresh_connect_ms']} ms\n")
    L.append('Model: est_prod_ms = wall - roundtrips_default*(rtt_d-2) - roundtrips_buildings*(rtt_b-2) - cache_ops*(cache_rtt-1.5); roundtrips = queries + commits.\n')
    L.append('## Per-endpoint summary\n')
    L.append('| endpoint | pass | n | wall p50 | wall p95 | wall max | q default (med) | q buildings (med) | RT def/bld (med) | cache ops (med) | est_prod p50 | est_prod p95 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
    groups = {}
    for r in R:
        groups.setdefault((r['kind'], r.get('pass', '-')), []).append(r)
    order = ['parse_query', 'session_create', 'swipe_like', 'swipe_dislike', 'swipe_extend', 'session_result']
    for kind in order:
        for pas in ('cold', 'warm', '-'):
            g = groups.get((kind, pas))
            if not g: continue
            w = [x['wall_ms'] for x in g]; e = [x['est_prod_ms'] for x in g]
            L.append(f"| {kind} | {pas} | {len(g)} | {f1(med(w))} | {f1(pct(w,95))} | {f1(max(w))} | {f1(med([x['n_q_default'] for x in g]))} | {f1(med([x['n_q_buildings'] for x in g]))} | {f1(med([x['n_roundtrips_default'] for x in g]))}/{f1(med([x['n_roundtrips_buildings'] for x in g]))} | {f1(med([x['n_cache_ops'] for x in g]))} | {f1(med(e))} | {f1(pct(e,95))} |")
    # all swipes combined per pass
    for pas in ('cold', 'warm'):
        g = [x for x in R if x['kind'].startswith('swipe_') and x.get('pass') == pas and x['kind'] != 'swipe_extend']
        if g:
            w = [x['wall_ms'] for x in g]; e = [x['est_prod_ms'] for x in g]
            L.append(f"| **swipe (all)** | {pas} | {len(g)} | {f1(med(w))} | {f1(pct(w,95))} | {f1(max(w))} | {f1(med([x['n_q_default'] for x in g]))} | {f1(med([x['n_q_buildings'] for x in g]))} | {f1(med([x['n_roundtrips_default'] for x in g]))}/{f1(med([x['n_roundtrips_buildings'] for x in g]))} | {f1(med([x['n_cache_ops'] for x in g]))} | {f1(med(e))} | {f1(pct(e,95))} |")
    L.append('')
    # swipe by index
    L.append('## Swipe by index (median wall ms / queries default+buildings, across sessions, cold | warm)\n')
    L.append('| swipe # | cold wall | cold q d+b | warm wall | warm q d+b |')
    L.append('|---|---|---|---|---|')
    for i in range(1, ARGS.swipes + 1):
        row = []
        for pas in ('cold', 'warm'):
            g = [x for x in R if x.get('swipe_idx') == i and x.get('pass') == pas]
            row += [f1(med([x['wall_ms'] for x in g])) if g else '-', (f"{f1(med([x['n_q_default'] for x in g]))}+{f1(med([x['n_q_buildings'] for x in g]))}") if g else '-']
        L.append(f"| {i} | " + ' | '.join(row) + ' |')
    L.append('')
    # stages
    L.append('## Top perf_timing stages per endpoint (main thread; median ms, count)\n')
    for kind in order:
        g = [x for x in R if x['kind'] == kind]
        if not g: continue
        st = {}
        for x in g:
            for s in x['stages']:
                st.setdefault(s['stage'], []).append(s['ms'])
        if not st:
            L.append(f'**{kind}**: no stages logged\n'); continue
        top = sorted(st.items(), key=lambda kv: -sum(kv[1]) / len(g))[:8]
        L.append(f'**{kind}** (avg total ms per request across {len(g)} requests)\n')
        L.append('| stage | median ms | calls total | avg ms/request |'); L.append('|---|---|---|---|')
        for name, v in top:
            L.append(f'| {name} | {f1(med(v))} | {len(v)} | {f1(sum(v)/len(g))} |')
        L.append('')
    bg = {}
    for s in res['bg_stages']: bg.setdefault(s['stage'], []).append(s['ms'])
    if bg:
        L.append('**Background-thread stages (not on request path)**\n')
        L.append('| stage | n | median ms |'); L.append('|---|---|---|')
        for k, v in sorted(bg.items(), key=lambda kv: -len(kv[1]))[:10]:
            L.append(f'| {k} | {len(v)} | {f1(med(v))} |')
        L.append('')
    # representative sequences
    def seq(r, title):
        L.append(f'## {title}: `{r["label"]}` wall={r["wall_ms"]} ms, est_prod={r["est_prod_ms"]} ms, commits={r["commits"]}\n')
        L.append('Round-trip sequence (execution order; alias, ms, SQL shape):\n')
        L.append('| # | alias | ms | SQL shape |'); L.append('|---|---|---|---|')
        for i, q in enumerate(r['queries'], 1):
            L.append(f"| {i} | {q['alias']} | {q['ms']} | `{esc(q['sql'])}` |")
        L.append('')
        shapes = {}
        for q in r['queries']:
            k = (q['alias'], q['sql']); shapes[k] = shapes.get(k, 0) + 1
        L.append('Deduplicated shapes:\n')
        L.append('| count | alias | shape |'); L.append('|---|---|---|')
        for (a, s), n in sorted(shapes.items(), key=lambda kv: -kv[1]):
            L.append(f"| {n} | {a} | `{esc(s)}` |")
        L.append(f"\nCache ops: {r['cache_ops']}\n")
        L.append('Stages: ' + ', '.join(f"{s['stage']}={s['ms']:.0f}ms" for s in r['stages']) + '\n')
    rep_like = [x for x in R if x['kind'] == 'swipe_like' and x.get('pass') == 'cold' and x.get('swipe_idx', 0) >= 3]
    rep_like = sorted(rep_like, key=lambda x: x['wall_ms'])
    if rep_like: seq(rep_like[len(rep_like) // 2], 'Representative like-swipe (cold pass, median wall, swipe>=3)')
    rep_c = [x for x in R if x['kind'] == 'session_create' and x.get('pass') == 'cold']
    if rep_c: seq(sorted(rep_c, key=lambda x: x['wall_ms'])[len(rep_c) // 2], 'Representative session-create (cold pass, median wall)')
    L.append('## Notes / caveats\n')
    for n in res['notes']: L.append(f'- NOTE: {n}')
    for c in res['caveats']: L.append(f'- {c}')
    L.append(f"- cache ops performed in background threads total: {res['cache_bg_ops_total']}")
    with open(os.path.join(OUT, 'baseline.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')

main()
