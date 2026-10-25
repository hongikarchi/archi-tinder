#!/usr/bin/env python
"""
flow_doc.py -- build the "[Archibe]-전체흐름" QA page from a flow_capture run.

Input:
  <run dir>/manifest.json          written by flow_capture.py
  web-testing/flow_issues.json     issue cards, curated by hand (see schema below)
Output:
  <run dir>/flow.html              publish with the Artifact tool, img/ as files

Usage:
  python web-testing/flow_doc.py                     # latest run dir
  python web-testing/flow_doc.py --run web-testing/reports/flow/2026-10-17

flow_issues.json schema:
  {"issues": [{
     "id": "1", "title": "...", "status": "open" | "fixed" | "dismissed", "fixed_on": "YYYY-MM-DD",
     "what": "...", "why": "...",
     "fixes": [{"text": "...", "recommended": true}],
     "now": "...",                     # after-fix description (fixed only)
     "before": ["05", "2026-10-17:06"], # shot refs: "<id>" = this run, "<date>:<id>" = older run
     "after": ["05"],
     "flow": ["05", "06"]               # anchors into the flow sections
  }]}
"""

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOW_ROOT = HERE / 'reports' / 'flow'
ISSUES_PATH = HERE / 'flow_issues.json'

SLOW_MS = 1000  # standing product bar: every page under 1s

# Flow letters and screen IDs shared with [Archibe]-SPEC (화면 명세 tab). 'Z' = theme/language variants.
FLOWS = [
    ('A', '시작 · 가입', '로그아웃 상태에서 처음 만나는 화면들이에요. Google·카카오 로그인은 자동화할 수 없어 화면만 담았어요.'),
    ('B', '취향 찾기', '검색 탭에서 한 문장을 쓰면 태그와 카드 3장이 나오고, 스와이프를 거쳐 결과와 리포트까지 이어져요.'),
    ('C', '탐색', '앱을 열면 가장 먼저 보이는 탐색 탭과, 거기서 들어가는 건물·건축가 화면이에요.'),
    ('D', '소셜 · 공모전', '취향이 맞는 사람 찾기, 성향 검사, 공모전처럼 사람과 사람을 잇는 화면이에요.'),
    ('E', '프로필 · 설정', '내 기록과 계정을 다루는 화면이에요.'),
    ('Z', '다크 · 영어', '같은 화면을 다크 테마와 영어로 본 모습이에요.'),
]
SCREEN_OF = {}
for _ids, _scr in [
        ('01 02 65', 'A01'), ('03', 'A02'), ('04 05', 'A03'),
        ('06 07 08 09 10 11 31 32 33 63', 'B01'), ('12 13 14 15 16 17 18 19 20 21', 'B02'),
        ('22 23 24 25 26', 'B03'), ('27', 'B04'), ('28', 'B05'),
        ('29 30 64', 'C01'), ('38', 'C02'), ('39', 'C03'),
        ('34 35 36', 'D01'), ('49', 'D02'), ('51', 'D03'), ('52', 'D04'), ('37', 'D05'),
        ('40 41 61', 'E01'), ('48 62', 'E02'), ('50', 'E03'), ('47', 'E04'), ('42', 'E05'),
        ('43', 'E06'), ('44', 'E07'), ('45', 'E08'), ('46', 'E09'),
        ('53 54 55 56 57 58 59 60', 'Z')]:
    for _i in _ids.split():
        SCREEN_OF[_i] = _scr
LINKS = [('PRD', 'https://claude.ai/artifact/S8nvTvTXXg44eT33wBY3vN'),
         ('SPEC', 'https://claude.ai/artifact/Wmv6UGRp1ntPFw9V7FqmMu'),
         ('디자인시스템', 'https://claude.ai/artifact/G15yiY8beG7qUMYJXsgnD8')]


def esc(s):
    return html.escape(str(s or ''), quote=True)


def latest_run():
    runs = sorted(p for p in FLOW_ROOT.glob('*') if (p / 'manifest.json').exists())
    if not runs:
        sys.exit(f'no run with manifest.json under {FLOW_ROOT}')
    return runs[-1]


def load_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


# -- shot references ----------------------------------------------------------

class ShotIndex:
    """Resolves "05" (this run) and "2026-10-17:05" (older run) to shot dicts.

    Images from older runs are copied into this run's img/ as prev-<date>-<file>
    so the published artifact carries them.
    """

    def __init__(self, run_dir, manifest):
        self.run_dir = run_dir
        self.by_id = {s['id']: s for s in manifest['shots']}
        self.other = {}

    def get(self, ref):
        if ':' not in ref:
            return self.by_id.get(ref)
        date, sid = ref.split(':', 1)
        if date not in self.other:
            m = load_json(FLOW_ROOT / date / 'manifest.json', {'shots': []})
            self.other[date] = {s['id']: s for s in m['shots']}
        shot = self.other[date].get(sid)
        if not shot or not shot.get('img'):
            return None
        src = FLOW_ROOT / date / shot['img']
        name = f"prev-{date}-{Path(shot['img']).name}"
        dst = self.run_dir / 'img' / name
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return {**shot, 'img': f'img/{name}', 'img_debug': None, '_date': date}


# -- metrics ------------------------------------------------------------------

def shot_stats(shot):
    m = shot.get('metrics') or {}
    api = m.get('api') or []
    api_max = max((a.get('ms') or 0 for a in api), default=0)
    return {
        'ready': m.get('ready_ms'),
        'api_n': len(api),
        'api_max': api_max,
        'errors': len(m.get('console_errors') or []),
        'failed': len(m.get('failed') or []),
        'longtasks': m.get('longtasks'),
    }


def badges(shot):
    st = shot_stats(shot)
    out = []
    if shot.get('skipped'):
        return '<span class="b b-muted">건너뜀</span>'
    if not shot.get('ok', True):
        out.append('<span class="b b-bad">캡처 실패</span>')
    if st['ready'] is not None:
        # ready_ms includes the scenario's scripted waits, so it is context, not a verdict.
        out.append(f'<span class="b b-muted">단계 {st["ready"] / 1000:.1f}초</span>')
    if st['api_n']:
        cls = 'b-bad' if st['api_max'] > SLOW_MS else 'b-muted'
        out.append(f'<span class="b {cls}">API {st["api_n"]}개 · 최대 {st["api_max"]:,}ms</span>')
    if st['errors']:
        out.append(f'<span class="b b-bad">콘솔 오류 {st["errors"]}</span>')
    if st['failed']:
        out.append(f'<span class="b b-bad">실패 요청 {st["failed"]}</span>')
    lt = st['longtasks']
    if lt and lt.get('count'):
        out.append(f'<span class="b b-warn">끊김 {lt["count"]}회 · {lt.get("total_ms", 0):,}ms</span>')
    return ''.join(out)


def problem_lines(shot):
    """Console errors / failed requests, shown under the caption."""
    m = shot.get('metrics') or {}
    rows = []
    if shot.get('error'):
        rows.append(f'캡처 오류: {shot["error"]}')
    for e in (m.get('console_errors') or [])[:3]:
        rows.append(f'콘솔: {e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)}')
    for f in (m.get('failed') or [])[:3]:
        if isinstance(f, dict):
            rows.append(f'요청 실패: {f.get("status", "")} {f.get("method", "")} {f.get("path", "")}'.strip())
        else:
            rows.append(f'요청 실패: {f}')
    if not rows:
        return ''
    items = ''.join(f'<li>{esc(r[:240])}</li>' for r in rows)
    return f'<ul class="probs">{items}</ul>'


# -- html pieces --------------------------------------------------------------

def figure(shot, anchor=True, numbered=True):
    if not shot:
        return ''
    sid = shot['id']
    img = shot.get('img')
    dbg = shot.get('img_debug')
    fid = f' id="s{esc(sid)}"' if anchor else ''
    v = shot.get('variant') or {}
    tags = []
    scr = SCREEN_OF.get(sid)
    if scr and scr != 'Z' and not shot.get('_date'):
        tags.append(f'<span class="tag scr">{esc(scr)}</span>')
    if v.get('theme') == 'dark':
        tags.append('<span class="tag">다크</span>')
    if v.get('lang') == 'en':
        tags.append('<span class="tag">English</span>')
    if v.get('account') == 'none':
        tags.append('<span class="tag">로그인 전</span>')
    if v.get('account') == 'fresh':
        tags.append('<span class="tag">새 계정</span>')
    if shot.get('_date'):
        tags.append(f'<span class="tag">{esc(shot["_date"])} 촬영</span>')
    no = f'<span class="no">{esc(sid)}</span>' if numbered else ''
    if img:
        pic = (f'<button class="pic" type="button" data-src="{esc(img)}" '
               f'data-dbg="{esc(dbg or "")}" aria-label="{esc(shot.get("title_ko"))} 크게 보기">'
               f'<img src="{esc(img)}" alt="{esc(shot.get("title_ko"))}" loading="lazy"></button>')
    else:
        pic = '<div class="pic nopic">사진 없음</div>'
    dbg_btn = (f'<button class="dbg" type="button" aria-pressed="false" '
               f'data-src="{esc(img)}" data-dbg="{esc(dbg)}">디버그 화면</button>') if dbg else ''
    return (f'<figure class="shot"{fid}>{pic}<figcaption>'
            f'<div class="meta">{no}{"".join(tags)}{dbg_btn}</div>'
            f'<h4>{esc(shot.get("title_ko"))}</h4><p>{esc(shot.get("caption_ko"))}</p>'
            f'<div class="badges">{badges(shot)}</div>{problem_lines(shot)}'
            f'</figcaption></figure>')


def issue_card(issue, idx, mode):
    """mode 'after' = fixed summary card, 'record' = full problem record."""
    status = issue.get('status', 'open')
    if status == 'fixed':
        st = f'<span class="st st-done">고쳤어요 ({esc(issue.get("fixed_on", ""))})</span>'
    elif status == 'dismissed':
        st = f'<span class="st st-done">문제 아님 ({esc(issue.get("fixed_on", ""))})</span>'
    else:
        st = '<span class="st st-open">확인 필요</span>'
    head = (f'<div class="ihead"><span class="inum">문제 {esc(issue["id"])}</span>{st}</div>'
            f'<h3>{esc(issue["title"])}</h3>')
    if mode == 'after':
        body = f'<dl><dt>이제 어떻게 되나</dt><dd>{esc(issue.get("now"))}</dd></dl>'
        shots = [idx.get(r) for r in issue.get('after', [])]
        before = [idx.get(r) for r in issue.get('before', [])]
        bgrid = ''.join(figure(b, anchor=False, numbered=False) for b in before if b)
        bgrid = f'<div class="grid">{bgrid}</div>' if bgrid else ''
        link = (f'<details class="before"><summary>고치기 전 기록 보기</summary>'
                f'<dl><dt>무엇이 일어났나</dt><dd>{esc(issue.get("what"))}</dd>'
                f'<dt>왜 문제였나</dt><dd>{esc(issue.get("why"))}</dd></dl>{bgrid}</details>')
        anchor = f' id="issue{esc(issue["id"])}"'
    else:
        fixes = ''.join(
            f'<li>{"<b class=rec>추천</b> " if f.get("recommended") else ""}{esc(f.get("text"))}</li>'
            for f in issue.get('fixes', []))
        body = (f'<dl><dt>무엇이 일어나나</dt><dd>{esc(issue.get("what"))}</dd>'
                f'<dt>왜 문제가 될 수 있나</dt><dd>{esc(issue.get("why"))}</dd>'
                f'<dt>고치는 방법 후보</dt><dd><ol class="fixes">{fixes}</ol></dd></dl>')
        shots = [idx.get(r) for r in issue.get('before', [])]
        flow = ', '.join(f'<a href="#s{esc(r)}">{esc(r)}</a>' for r in issue.get('flow', []))
        link = f'<p class="links">흐름에서 보기: {flow}</p>' if flow else ''
        anchor = f' id="issue{esc(issue["id"])}"'
    grid = ''.join(figure(s, anchor=False, numbered=False) for s in shots if s)
    grid = f'<div class="grid">{grid}</div>' if grid else ''
    return f'<article class="issue"{anchor}>{head}{body}{grid}{link}</article>'


def perf_table(shots):
    calls = []
    for s in shots:
        for a in (s.get('metrics') or {}).get('api') or []:
            calls.append((a.get('ms') or 0, a, s))
    calls.sort(key=lambda x: -x[0])
    rows = ''.join(
        f'<tr class="{"slow" if ms > SLOW_MS else ""}"><td class="num">{ms:,}</td>'
        f'<td><code>{esc(a.get("method"))} {esc(a.get("path"))}</code></td>'
        f'<td class="num">{esc(a.get("status"))}</td>'
        f'<td><a href="#s{esc(s["id"])}">{esc(s["id"])}</a> {esc(s.get("title_ko"))}</td></tr>'
        for ms, a, s in calls[:12])
    if not rows:
        return ''
    return ('<div class="tablewrap"><table><thead><tr><th>ms</th><th>요청</th><th>상태</th>'
            f'<th>화면</th></tr></thead><tbody>{rows}</tbody></table></div>')


# -- page ---------------------------------------------------------------------

CSS = r"""
/* Layout: one reading column of sections; screenshots in a phone-proportioned grid. */
:root{
  --bg:#f3f5f8; --surface:#ffffff; --ink:#1b2430; --muted:#5b6778; --line:#d6dde6;
  --accent:#0969da; --accent-soft:#e3eefb;
  --ok:#1a7f37; --ok-soft:#e2f3e7; --warn:#9a6700; --warn-soft:#fbefd2;
  --bad:#c0362c; --bad-soft:#fbe4e1; --nav:rgba(243,245,248,0.92);
  --f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  --f-num:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f141b; --surface:#161d26; --ink:#e3e9f0; --muted:#94a1b2; --line:#2a3441;
  --accent:#58a6ff; --accent-soft:#16283e;
  --ok:#56d364; --ok-soft:#14301c; --warn:#e3b341; --warn-soft:#352a10;
  --bad:#ff7b72; --bad-soft:#3b1a19; --nav:rgba(15,20,27,0.92); color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f141b; --surface:#161d26; --ink:#e3e9f0; --muted:#94a1b2; --line:#2a3441;
  --accent:#58a6ff; --accent-soft:#16283e;
  --ok:#56d364; --ok-soft:#14301c; --warn:#e3b341; --warn-soft:#352a10;
  --bad:#ff7b72; --bad-soft:#3b1a19; --nav:rgba(15,20,27,0.92); color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.7 var(--f-body);word-break:keep-all;overflow-wrap:anywhere}
a{color:var(--accent)}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.wrap{max-width:76rem;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 72px;display:grid;gap:40px}
.intro h1{font-size:clamp(1.6rem,4vw,2.2rem);line-height:1.25;margin:0 0 8px;font-weight:700;text-wrap:balance}
.intro p{margin:0;max-width:64ch;color:var(--muted)}
.facts{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.facts span{background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:3px 12px;font-size:.85rem}
.facts .bad{background:var(--bad-soft);color:var(--bad);border-color:transparent}
.facts .ok{background:var(--ok-soft);color:var(--ok);border-color:transparent}
.note{background:var(--accent-soft);border-radius:12px;padding:14px 16px;font-size:.93rem;max-width:80ch}
section{display:grid;gap:16px;min-width:0}
.sec{border-top:2px solid var(--ink);padding-top:12px;display:grid;gap:2px}
.sec h2{font-size:1.3rem;margin:0;text-wrap:balance}
.secno{font-family:var(--f-num);font-weight:600;color:var(--accent);font-size:.8rem;letter-spacing:.06em;text-transform:uppercase}
.sec p{margin:0;color:var(--muted);max-width:70ch}
.issue{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 16px;display:grid;gap:10px;min-width:0}
.ihead{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.inum{font-family:var(--f-num);font-weight:600;font-size:.78rem;background:var(--ink);color:var(--bg);border-radius:999px;padding:1px 10px}
.st{font-size:.78rem;border-radius:999px;padding:1px 10px}
.st-open{background:var(--warn-soft);color:var(--warn)}
.st-done{background:var(--ok-soft);color:var(--ok)}
.issue h3{margin:0;font-size:1.06rem;line-height:1.45}
.issue dl{margin:0;display:grid;gap:4px}
.issue dt{font-weight:700;font-size:.85rem;color:var(--accent);margin-top:6px}
.issue dd{margin:0;max-width:72ch}
.fixes{margin:4px 0 0;padding-left:1.3em;display:grid;gap:6px}
.rec{font-size:.72rem;background:var(--accent);color:var(--surface);border-radius:999px;padding:1px 8px;margin-right:2px}
.links{margin:0;font-size:.85rem;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:22px 16px;align-items:start;min-width:0}
.shot{margin:0;display:grid;gap:8px;min-width:0}
.pic{display:block;width:100%;padding:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--surface);cursor:zoom-in}
.pic img{display:block;width:100%;height:auto}
.nopic{aspect-ratio:393/852;display:grid;place-items:center;color:var(--muted);cursor:default}
.meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.no{font-family:var(--f-num);font-weight:600;font-size:.85rem;font-variant-numeric:tabular-nums}
.tag{font-size:.72rem;border-radius:999px;padding:1px 8px;background:var(--accent-soft);color:var(--accent)}
.dbg{margin-left:auto;font:inherit;font-size:.72rem;border:1px solid var(--line);background:var(--surface);color:var(--muted);border-radius:999px;padding:1px 8px;cursor:pointer}
.dbg[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
figcaption h4{margin:2px 0 2px;font-size:.97rem}
figcaption p{margin:0;font-size:.87rem;color:var(--muted)}
.badges{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.b{font-family:var(--f-num);font-size:.7rem;border-radius:6px;padding:0 6px;font-variant-numeric:tabular-nums}
.b-ok{background:var(--ok-soft);color:var(--ok)}
.b-warn{background:var(--warn-soft);color:var(--warn)}
.b-bad{background:var(--bad-soft);color:var(--bad)}
.b-muted{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
.probs{margin:6px 0 0;padding-left:1.1em;font-size:.78rem;color:var(--bad);font-family:var(--f-num)}
.tablewrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{text-align:left;padding:7px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.75rem;color:var(--muted);font-weight:600}
td.num{font-family:var(--f-num);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
tr.slow td.num:first-child{color:var(--bad);font-weight:600}
code{font-family:var(--f-num);font-size:.8rem}
dialog{border:0;padding:0;background:transparent;max-width:min(96vw,520px);max-height:94vh}
dialog::backdrop{background:rgb(0 0 0 / .78)}
dialog img{display:block;max-width:100%;max-height:90vh;width:auto;border-radius:12px}
dialog .close{position:absolute;top:8px;right:8px;font:inherit;font-size:.85rem;border:0;border-radius:999px;padding:4px 12px;background:var(--surface);color:var(--ink);cursor:pointer}
@media (max-width:640px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
/* Doc nav: house format shared with [Archibe]-PRD (title left, section anchors right). */
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--nav)}
.docnav{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--nav);backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line);
  margin-inline:calc(-1 * max(16px,env(safe-area-inset-left,0px)));padding-inline:max(16px,env(safe-area-inset-left,0px))}
.docnav .in{display:flex;align-items:center;gap:20px;height:52px;max-width:76rem;margin:0 auto}
.docnav .t{font-weight:700;white-space:nowrap}
.docnav .links{display:flex;gap:16px;overflow-x:auto;scrollbar-width:none;margin-left:auto}
.docnav .links::-webkit-scrollbar{display:none}
.docnav .links a{font-size:.8rem;color:var(--muted);text-decoration:none;white-space:nowrap}
.docnav .links a:hover{color:var(--ink)}
.btnrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.btnrow a{font-size:.88rem;font-weight:600;text-decoration:none;border-radius:12px;padding:8px 14px;border:1px solid var(--accent);color:var(--accent)}
.glance{border:2px solid var(--ink);border-radius:14px;padding:16px 18px;background:var(--surface);display:grid;gap:8px}
.glance h2{font-size:1.05rem;margin:0}
.glance ul{margin:0;padding-left:1.1em;display:grid;gap:4px}
.howto{background:var(--accent-soft);border-radius:12px;padding:14px 16px;font-size:.93rem}
.howto b{display:block;margin-bottom:4px}
.howto p{margin:0;max-width:80ch}
.group{display:grid;gap:12px}
.group h3{margin:6px 0 0;font-size:1.05rem}
.scr{background:var(--ink);color:var(--bg)}
.shot,.issue,section{scroll-margin-top:70px}
.empty{background:var(--ok-soft);color:var(--ok);border-radius:12px;padding:14px 16px;margin:0}
details.before{border-top:1px dashed var(--line);padding-top:8px}
details.before summary{cursor:pointer;font-size:.85rem;color:var(--accent)}
details.before[open]{display:grid;gap:10px}
details.howto summary{cursor:pointer;font-weight:600}
details.howto p{margin:8px 0 0}
"""

JS = r"""
const dlg = document.getElementById('zoom'), big = document.getElementById('zoomimg');
document.addEventListener('click', e => {
  const pic = e.target.closest('.pic[data-src]');
  if (pic) { big.src = pic.querySelector('img').src; dlg.showModal(); return; }
  const d = e.target.closest('.dbg');
  if (d) {
    const fig = d.closest('.shot'), img = fig.querySelector('.pic img');
    const on = d.getAttribute('aria-pressed') !== 'true';
    d.setAttribute('aria-pressed', on ? 'true' : 'false');
    img.src = on ? d.dataset.dbg : d.dataset.src;
    return;
  }
  if (e.target === dlg || e.target.closest('.close')) dlg.close();
});
"""


def build(run_dir):
    manifest = load_json(run_dir / 'manifest.json')
    issues = (load_json(ISSUES_PATH, {'issues': []}) or {}).get('issues', [])
    run = manifest['run']
    shots = manifest['shots']
    idx = ShotIndex(run_dir, manifest)

    captured = [s for s in shots if s.get('img') and not s.get('skipped')]
    n_err = sum(shot_stats(s)['errors'] + shot_stats(s)['failed'] for s in shots)
    n_slow = sum(1 for s in shots if shot_stats(s)['api_max'] > SLOW_MS)
    open_issues = [i for i in issues if i.get('status') not in ('fixed', 'dismissed')]
    fixed = [i for i in issues if i.get('status') in ('fixed', 'dismissed')]

    facts = [f'<span>{esc(run["date"])}</span>',
             f'<span>캡처 {len(captured)}장</span>',
             f'<span>{esc(run.get("device", ""))} · {esc(run.get("browser", ""))}</span>',
             f'<span class="{"bad" if n_err else "ok"}">오류·실패 요청 {n_err}건</span>',
             f'<span class="{"bad" if n_slow else "ok"}">1초 넘는 요청이 있는 화면 {n_slow}곳</span>']
    if issues:
        facts.append(f'<span>확인 필요 {len(open_issues)} · 고침 {len(fixed)}</span>')
    if run.get('counts', {}).get('failed'):
        facts.append(f'<span class="bad">캡처 실패 {run["counts"]["failed"]}</span>')

    engine = '아이폰과 같은 사파리 엔진(WebKit)' if run.get('browser') == 'webkit' \
        else '크롬 엔진을 아이폰 화면처럼 설정'
    perf_note = ' 이번 회차는 휴대폰처럼 CPU를 4배 느리게 해서 끊김(50ms 넘는 작업)도 쟀어요.' if run.get('perf') else ''
    note = (f'<p>이 컴퓨터의 개발 서버(localhost:5174)에서 '
            f'테스트 계정으로 자동 로그인해 찍었어요. 진짜 폰이 아니라 {engine}으로 '
            f'{esc(run.get("device", ""))} 크기({run.get("viewport", [390, 844])[0]}×{run.get("viewport", [390, 844])[1]})를 띄웠어요. '
            f'‘단계’ 시간은 자동 대기 시간까지 포함한 값이고, API 시간은 개발 서버 기준이라 실제 서비스보다 느리게 나와요. 화면끼리 비교하는 용도로 보세요.{perf_note} '
            f'사진 아래 ‘디버그 화면’을 누르면 개발자용 표시(API 시간, 미리 불러오기 시간)가 켜진 같은 화면을 볼 수 있어요. '
            f'코드 버전 {esc(run.get("git_sha", ""))} ({esc(run.get("branch", ""))}).</p>')

    y, mo, d = run['date'].split('-')
    nice = f'{int(y)}년 {int(mo)}월 {int(d)}일'
    links = ''.join(f'<a href="{u}">{esc(n)}</a>' for n, u in LINKS)
    intro = (f'<div class="intro"><h1>[Archibe]-전체흐름</h1>'
             f'<p>휴대폰 웹에서 로그인부터 취향 찾기, 탐색, 소셜, 프로필까지 실제로 눌러 보며 찍은 기록이에요. '
             f'흐름 글자(A–E)와 화면 번호는 SPEC의 화면 명세와 같아요. 사진을 누르면 크게 볼 수 있어요.</p>'
             f'<div class="facts">{"".join(facts)}</div><div class="btnrow">{links}</div></div>')

    def letter_of(shot):
        scr = SCREEN_OF.get(shot['id'])
        if scr:
            return scr[0]
        return 'Z' if shot.get('stage') == 'variants' else None

    groups = []  # (letter, title, desc, shots)
    for letter, title, desc in FLOWS:
        mine = [s for s in shots if letter_of(s) == letter]
        if mine:
            groups.append((letter, title, desc, mine))
    unmapped = [s for s in shots if letter_of(s) is None]
    if unmapped:
        groups.append(('Y', '기타', '흐름에 아직 묶지 않은 화면이에요.', unmapped))

    one = f': {esc(open_issues[0]["title"])}' if len(open_issues) == 1 else ''
    n_flows = len([g for g in groups if g[0] in 'ABCDE'])
    glance = (f'<section class="glance" id="glance"><h2>한눈에 · {esc(nice)}</h2><ul>'
              f'<li><b>화면 {len(captured)}장</b>을 흐름 {n_flows}개로 나눠 찍었어요.</li>'
              f'<li><b>남은 문제 {len(open_issues)}개</b>{one}</li>'
              f'<li><b>이번에 고쳐진 것 {len(fixed)}개</b>는 맨 아래에 모았어요.</li>'
              f'<li><b>1초 넘는 요청이 있는 화면 {n_slow}곳</b>, 오류·실패 요청 {n_err}건이에요(개발 서버 기준).</li>'
              f'</ul></section>')
    howto = f'<section class="howto" id="howto"><b>어떻게 찍었나</b>{note}</section>'

    open_html = ''.join(issue_card(i, idx, 'record') for i in open_issues) or \
        '<p class="empty">지금 남은 문제는 없어요.</p>'
    remain = ('<section id="remain"><header class="sec"><span class="secno">먼저 보기</span>'
              '<h2>지금 남은 일</h2><p>문제마다 무엇이 일어나는지, 왜 헷갈릴 수 있는지, 고칠 방법 후보를 적었어요.</p></header>'
              f'<div class="group"><h3>1. 앱에 남은 문제</h3>{open_html}</div></section>')

    def label(letter):
        return '경우의 수' if letter == 'Z' else ('기타' if letter == 'Y' else f'흐름 {letter}')

    flow_html = ''.join(
        f'<section id="flow-{letter.lower()}"><header class="sec">'
        f'<span class="secno">{label(letter)}</span><h2>{esc(title)}</h2><p>{esc(desc)}</p></header>'
        f'<div class="grid">{"".join(figure(s) for s in mine)}</div></section>'
        for letter, title, desc, mine in groups)

    table = perf_table(shots)
    perf = ('<section id="perf"><header class="sec"><span class="secno">속도</span>'
            '<h2>가장 느린 요청</h2><p>이번 회차에서 오래 걸린 API 요청 12개예요. '
            f'{SLOW_MS:,}ms를 넘으면 빨간색이에요. 개발 서버 기준이라 실제보다 느려요.</p></header>'
            f'{table}</section>') if table else ''
    done = ''
    if fixed:
        cards = ''.join(issue_card(i, idx, 'after') for i in fixed)
        done = ('<section id="fixed"><header class="sec"><span class="secno">고친 것</span>'
                '<h2>이번에 고쳐진 것</h2><p>정해 주신 대로 고친 뒤 다시 찍은 화면이에요. '
                '고치기 전 모습은 카드마다 접어 뒀어요.</p></header>'
                f'{cards}</section>')

    anchors = [('glance', '한눈에'), ('remain', '남은 일')]
    anchors += [(f'flow-{l.lower()}', l if l in 'ABCDE' else label(l)) for l, _, _, _ in groups]
    anchors += ([('perf', '속도')] if perf else []) + ([('fixed', '고친 것')] if done else [])
    nav = ('<nav class="docnav" aria-label="목차"><div class="in"><span class="t">[Archibe]-전체흐름</span>'
           '<div class="links">' + ''.join(f'<a href="#{k}">{esc(v)}</a>' for k, v in anchors) +
           '</div></div></nav>')
    body = nav + intro + glance + howto + remain + flow_html + perf + done

    page = (
        '<title>[Archibe]-전체흐름</title>\n'
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;600;700'
        '&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">\n'
        f'<style>{CSS}</style>\n'
        f'<div class="wrap">{body}</div>\n'
        '<dialog id="zoom" aria-label="크게 보기"><button class="close" type="button">닫기</button>'
        '<img id="zoomimg" alt=""></dialog>\n'
        f'<script>{JS}</script>\n')
    out = run_dir / 'flow.html'
    out.write_text(page, encoding='utf-8', newline='\n')
    print(f'wrote {out} — shots {len(shots)}, issues {len(issues)} '
          f'(open {len(open_issues)}, fixed {len(fixed)}), errors {n_err}, slow {n_slow}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--run', type=Path, help='run dir (default: latest under reports/flow)')
    args = ap.parse_args()
    build(args.run.resolve() if args.run else latest_run())


if __name__ == '__main__':
    main()
