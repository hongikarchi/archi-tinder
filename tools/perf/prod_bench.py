"""Client-side perf bench against a DEPLOYED backend over HTTP (what a Korean user feels).

Flow per run: guest login (1 guest = max 3 boards) -> for each of 3 fixed Korean queries:
parse-query -> session create -> N swipes (seeded like/dislike) -> result.
Reuses one keep-alive HTTP session like a browser. Writes JSON + markdown summary.

WRITES REAL ROWS on the target (1 guest user, 3 sessions/boards, swipes, LLM calls per run).
Only run against prod with explicit approval.

Usage: python tools/perf/prod_bench.py --base https://archi-tinder.up.railway.app --label before [--runs 2] [--swipes 20]
"""
import argparse, datetime, json, os, random, re, statistics, time
import requests

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True)
ap.add_argument('--label', default='run')
ap.add_argument('--runs', type=int, default=2)
ap.add_argument('--swipes', type=int, default=20)
ap.add_argument('--sleep', type=float, default=0.5)
ap.add_argument('--seed', type=int, default=1234)
ap.add_argument('--out', default=os.path.join(os.path.expanduser('~'), 'perf-bench-out'))
A = ap.parse_args()
API = A.base.rstrip('/') + '/api/v1'
QUERIES = ['제주도 돌로 지은 명상 공간', '따뜻한 목재 주택', '서울 도심 오피스']
recs, notes = [], []


_ST_RE = re.compile(r'([A-Za-z0-9_-]+)(?:;desc="?[^;,"]*"?)?;dur=([\d.]+)')


def parse_server_timing(header):
    """Server-Timing header -> {'total': ms, 'db': ms, ...}. Missing/garbled header -> {}."""
    out = {}
    for name, dur in _ST_RE.findall(header or ''):
        try:
            out[name] = float(dur)
        except ValueError:
            pass
    return out


def call(s, kind, method, path, **kw):
    t0 = time.perf_counter()
    r = s.request(method, API + path, timeout=120, **kw)
    ms = (time.perf_counter() - t0) * 1000
    st = parse_server_timing(r.headers.get('Server-Timing'))
    recs.append({'kind': kind, 'ms': round(ms, 1), 'status': r.status_code, 'label': A.label,
                 'srv_total': st.get('total'), 'srv_db': st.get('db')})
    return r


def cid(card):
    return (card or {}).get('canonical_bld_id') or (card or {}).get('building_id')


def one_run(ri, rng):
    s = requests.Session()
    r = call(s, 'guest_login', 'POST', '/auth/guest/', json={
        'display_name': f'perfbench{ri}', 'consent_accepted': True, 'consent_policy_version': '1.0'})
    if r.status_code not in (200, 201):
        notes.append(f'run{ri}: guest login HTTP {r.status_code} {r.text[:150]}'); return
    s.headers['Authorization'] = 'Bearer ' + r.json()['access']
    for qi, q in enumerate(QUERIES):
        r = call(s, 'parse_query', 'POST', '/parse-query/', json={'query': q})
        if r.status_code != 200:
            notes.append(f'run{ri} q{qi}: parse HTTP {r.status_code}'); continue
        d = r.json()
        body = {'name': f'perfbench-{A.label}-{ri}-{qi}', 'filters': d.get('structured_filters') or {},
                'filter_priority': d.get('filter_priority') or [], 'seed_ids': [],
                'raw_query': d.get('raw_query') or q, 'force_new': True}
        for k in ('visual_description', 'image_focus'):
            if d.get(k):
                body[k] = d[k]
        r = call(s, 'session_create', 'POST', '/analysis/sessions/', json=body)
        if r.status_code not in (200, 201):
            notes.append(f'run{ri} q{qi}: create HTTP {r.status_code} {r.text[:150]}'); continue
        d = r.json(); sid = d['session_id']
        card = d.get('next_image'); buf = [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))]
        plan = ['like'] * round(A.swipes * 0.6) + ['dislike'] * (A.swipes - round(A.swipes * 0.6))
        rng.shuffle(plan)
        for i, action in enumerate(plan):
            time.sleep(A.sleep)
            bid = cid(card)
            if not bid:
                notes.append(f'run{ri} q{qi}: no card at swipe {i}'); break
            r = call(s, 'swipe', 'POST', f'/analysis/sessions/{sid}/swipes/', json={
                'canonical_bld_id': bid, 'action': action, 'idempotency_key': f'swp_{sid}_{bid}',
                'client_buffer_ids': [b for b in buf if b]})
            if r.status_code != 200:
                notes.append(f'run{ri} q{qi}: swipe {i+1} HTTP {r.status_code}'); break
            d = r.json()
            if d.get('is_analysis_completed') or d.get('session_status') == 'completed':
                if not d.get('can_continue'):
                    break
                r = call(s, 'swipe_extend', 'POST', f'/analysis/sessions/{sid}/swipes/', json={
                    'extend': True, 'client_buffer_ids': [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))]})
                if r.status_code != 200:
                    break
                d = r.json()
            card = d.get('next_image'); buf = [cid(d.get('prefetch_image')), cid(d.get('prefetch_image_2'))]
        call(s, 'session_result', 'GET', f'/analysis/sessions/{sid}/result/')


def pct(v, p):
    v = sorted(v); return v[max(0, min(len(v) - 1, int(round(p / 100 * len(v) + 0.5)) - 1))]


rng = random.Random(A.seed)
for ri in range(A.runs):
    one_run(ri, rng)
    if ri < A.runs - 1:
        time.sleep(21)  # guest_login throttle 3/min
os.makedirs(A.out, exist_ok=True)
stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
lines = [f'# prod bench {A.label} {stamp} base={A.base}', '', '| endpoint | n | p50 ms | p95 ms | max ms | non-2xx | srv total p50 | srv db p50 |', '|---|---|---|---|---|---|---|---|']
for k in ['guest_login', 'parse_query', 'session_create', 'swipe', 'swipe_extend', 'session_result']:
    ok = [r for r in recs if r['kind'] == k and r['status'] < 300]
    v = [r['ms'] for r in ok]
    bad = sum(1 for r in recs if r['kind'] == k and r['status'] >= 300)

    def srv_p50(field):
        x = [r[field] for r in ok if r.get(field) is not None]
        return f'{statistics.median(x):.0f}' if x else '-'
    if v or bad:
        lines.append(f'| {k} | {len(v)} | {statistics.median(v):.0f} | {pct(v, 95):.0f} | {max(v):.0f} | {bad} | {srv_p50("srv_total")} | {srv_p50("srv_db")} |' if v else f'| {k} | 0 | - | - | - | {bad} | - | - |')
lines += ['', 'notes: ' + ('; '.join(notes) or 'none')]
open(os.path.join(A.out, f'prod_{A.label}.md'), 'w', encoding='utf-8').write('\n'.join(lines))
json.dump({'recs': recs, 'notes': notes}, open(os.path.join(A.out, f'prod_{A.label}.json'), 'w'), indent=1)
print('\n'.join(lines))
