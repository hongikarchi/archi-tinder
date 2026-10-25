#!/usr/bin/env python
"""
flow_capture.py -- walk every ArchiTinder user flow on a phone-sized browser and
record screenshots + metrics (see flow_scenarios.py for the scenario data).

    python web-testing/flow_capture.py [--browser webkit|chromium] [--only 01,05-09]
                                       [--stage swipe] [--no-debug] [--perf] [--out DIR]

LOCAL ONLY. Talks to the already-running dev servers:
    frontend  http://localhost:5174   (Vite, proxies /api and /media)
    backend   http://localhost:8001
It never starts or stops a server and never opens another port. If either port is
down it aborts with a message. dev-login is throttled (5/min) so we log in ONCE
per run and reuse the tokens for every context.

Output (default web-testing/reports/flow/<YYYY-MM-DD>/):
    img/<id>-<slug>.jpg          viewport screenshot (JPEG q80)
    img/<id>-<slug>.debug.jpg    same screen with the debug overlay (unless --no-debug / --perf)
    manifest.json                run info + stages + one record per shot
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flow_scenarios import SCENARIOS, STAGES  # noqa: E402

# -- Constants -----------------------------------------------------------------

BASE_URL = 'http://localhost:5174'
BACKEND_URL = 'http://localhost:8001'
DEVICE = 'iPhone 13'
VIEWPORT = [390, 844]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, 'backend', '.env')
DEFAULT_OUT_ROOT = os.path.join(ROOT, 'web-testing', 'reports', 'flow')

THEME_KEYS = {'light': 'github-light', 'dark': 'github-dark'}   # localStorage archithon_theme
SETTLE_NET_MS = 6000     # cap for "network idle-ish"
SETTLE_IMG_MS = 5000     # cap for "images loaded"
ACTION_TIMEOUT_MS = 12000
SWIPE_Y = 400            # y of the drag on the swipe card (x = viewport centre)

# The DebugOverlay (components/DebugOverlay.jsx) has no id: match its inline style.
HIDE_DEBUG_JS = r"""() => {
  if (document.getElementById('flowqa-hide-dbg')) return;
  const st = document.createElement('style');
  st.id = 'flowqa-hide-dbg';
  st.textContent = 'div[style*="z-index: 9999"][style*="monospace"]{visibility:hidden!important}';
  document.head.appendChild(st);
}"""
SHOW_DEBUG_JS = "() => { const st = document.getElementById('flowqa-hide-dbg'); if (st) st.remove(); }"

# Replaces every email address in visible text and input values with a placeholder.
REDACT_JS = r"""() => {
  const re = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (re.test(n.nodeValue)) n.nodeValue = n.nodeValue.replace(re, 'test@example.com');
    re.lastIndex = 0;
  }
  for (const el of document.querySelectorAll('input, textarea')) {
    if (re.test(el.value)) el.value = el.value.replace(re, 'test@example.com');
    re.lastIndex = 0;
  }
}"""


def log(msg: str) -> None:
    print(msg, flush=True)


# -- Preflight / auth ------------------------------------------------------------

def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def read_dev_login_secret() -> Optional[str]:
    """DEV_LOGIN_SECRET from backend/.env. Read here only, never printed."""
    if not os.path.exists(ENV_PATH):
        return None
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('DEV_LOGIN_SECRET='):
                return line.split('=', 1)[1].strip().strip('"').strip("'") or None
    return None


def post_json(path: str, body: dict) -> tuple:
    """POST JSON to the local backend. Returns (status, parsed_json_or_None)."""
    req = urllib.request.Request(
        BACKEND_URL + path, data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, None


def dev_login() -> dict:
    """One dev-login per run -> {access, refresh, user_id}. Exits on failure."""
    secret = read_dev_login_secret()
    if not secret:
        sys.exit('ABORT: DEV_LOGIN_SECRET missing in backend/.env (dev-login unavailable).')
    status, data = post_json('/api/v1/auth/dev-login/', {'secret': secret})
    if status == 429:   # throttled (5/min): wait out the window once
        log('dev-login throttled; waiting 62s ...')
        time.sleep(62)
        status, data = post_json('/api/v1/auth/dev-login/', {'secret': secret})
    if status != 200 or not data:
        sys.exit(f'ABORT: dev-login returned HTTP {status} (throttle 5/min? DEBUG off?).')
    return {'access': data['access'], 'refresh': data['refresh'],
            'user_id': str(data['user']['user_id'])}


def register_fresh() -> Optional[dict]:
    """Throwaway unverified account (id-only signup). None if the endpoint is gone."""
    handle = f'flowqa{random.randint(100000, 999999)}'
    status, data = post_json('/api/v1/auth/register/', {
        'id': handle, 'password': secrets.token_urlsafe(14) + 'aZ9',
        'affiliation': '', 'onboarding_role': 'student',
        'consent_accepted': True, 'consent_policy_version': '1.0'})
    if status in (404, 405) or not data or 'access' not in data:
        log(f'  fresh account unavailable (register -> HTTP {status})')
        return None
    return {'access': data['access'], 'refresh': data['refresh'],
            'user_id': str(data['user']['user_id'])}


# -- Small helpers -----------------------------------------------------------------

def git(*args) -> str:
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ''


def parse_only(spec: str) -> set:
    ids = set()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            ids.update(f'{n:02d}' for n in range(int(a), int(b) + 1))
        else:
            ids.add(f'{int(part):02d}')
    return ids


def clean_path(url: str) -> str:
    """URL -> path only (no host, no query/fragment: tokens never leak into reports)."""
    m = re.match(r'^[a-z]+://[^/]+(/[^?#]*)?', url)
    return (m.group(1) or '/') if m else url.split('?')[0].split('#')[0]


def is_selector(sel: str) -> bool:
    """Heuristic: CSS / engine-prefixed selector vs plain visible text."""
    return bool(re.match(
        r'^([#.\[*]|(role|text|css|xpath|id|data-testid)=|//|[a-z][a-z0-9-]*([\[.#:>\s,]|$))', sel))


# -- Per-page metrics collector --------------------------------------------------------

class Metrics:
    """Listens on one Page; reset() starts a new scenario window."""

    def __init__(self, page):
        self.page = page
        self.reset()
        page.on('request', self._on_request)
        page.on('response', self._on_response)
        page.on('requestfailed', self._on_failed)
        page.on('console', self._on_console)
        page.on('pageerror', lambda e: self.console_errors.append('pageerror: ' + str(e)[:300]))

    def reset(self):
        self.api, self.failed, self.console_errors = [], [], []
        self._t0 = {}

    def _on_request(self, req):
        self._t0[req] = time.time()

    def _on_response(self, resp):
        req = resp.request
        path = clean_path(resp.url)
        ms = int((time.time() - self._t0.pop(req, time.time())) * 1000)
        if path.startswith('/api/'):   # not Vite modules like /src/api/*.js
            self.api.append({'method': req.method, 'path': path, 'status': resp.status, 'ms': ms})
        if resp.status >= 400:
            self.failed.append({'method': req.method, 'path': path, 'status': resp.status})

    def _on_failed(self, req):
        err = (req.failure or '')
        if 'ERR_ABORTED' in str(err) or 'cancelled' in str(err).lower() or 'aborted' in str(err).lower():
            return   # navigation / unmount cancellations are noise
        self.failed.append({'method': req.method, 'path': clean_path(req.url), 'status': None,
                            'error': str(err)[:120]})

    def _on_console(self, msg):
        if msg.type == 'error':
            self.console_errors.append(msg.text[:300])


# -- Runner ---------------------------------------------------------------------------------

class Runner:
    def __init__(self, args, pw):
        self.args, self.pw = args, pw
        self.state = {}          # remembered values: session_id, board_id, ...
        self.tokens = {}         # account -> tokens (main from dev-login, fresh lazily)
        self.ctxs = {}           # (account, theme, lang) -> (context, page, Metrics)
        self.cdp = {}
        self.browser_name = 'chromium'
        self.hold_active = False
        self.me_mock = None      # dict of fields patched into GET /auth/me/

    # --- browser / contexts ---

    def launch(self):
        want = 'chromium' if self.args.perf else self.args.browser
        if want == 'webkit':
            try:
                self.browser = self.pw.webkit.launch(headless=True)
                self.browser_name = 'webkit'
                return
            except Exception as e:
                log(f'WARNING: webkit not launchable ({str(e).splitlines()[0][:80]}); falling back to chromium')
        self.browser = self.pw.chromium.launch(headless=True)
        self.browser_name = 'chromium'

    def device_kwargs(self) -> dict:
        dev = dict(self.pw.devices[DEVICE])
        if self.browser_name == 'chromium':
            dev.pop('default_browser_type', None)
        return dev

    def get_page(self, account: str, theme: str, lang: str):
        key = (account, theme, lang)
        if key in self.ctxs:
            return self.ctxs[key]
        ctx = self.browser.new_context(**self.device_kwargs(), locale='ko-KR', timezone_id='Asia/Seoul')
        ctx.set_default_timeout(ACTION_TIMEOUT_MS)
        # Storage seeded before any page script runs. "if absent" so the app's own writes win later.
        seed = {'archithon_theme': THEME_KEYS[theme], 'archithon_language': lang,
                'archithon_tutorial_dismissed': 'true'}
        js = ['try{']
        for k, v in seed.items():
            js.append(f"if(localStorage.getItem({json.dumps(k)})===null)localStorage.setItem({json.dumps(k)},{json.dumps(v)});")
        tok = self.tokens.get(account)
        if tok:
            js.append(f"if(localStorage.getItem('archithon_access')===null){{"
                      f"localStorage.setItem('archithon_access',{json.dumps(tok['access'])});"
                      f"localStorage.setItem('archithon_refresh',{json.dumps(tok['refresh'])});}}"
                      f"if(sessionStorage.getItem('archithon_user')===null)"
                      f"sessionStorage.setItem('archithon_user',{json.dumps(tok['user_id'])});")
        if not self.args.perf and not self.args.no_debug:
            # DebugOverlay mounts only if the flag is set at MainLayout render time, so it is ON
            # for the whole run; clean shots hide it with HIDE_DEBUG_CSS instead.
            js.append("window.__debugMode=true;")
        if self.args.perf:
            js.append("window.__lt={count:0,total:0};try{new PerformanceObserver(l=>{for(const e of l.getEntries()){"
                      "window.__lt.count++;window.__lt.total+=e.duration;}}).observe({entryTypes:['longtask']});}catch(e){}")
        js.append('}catch(e){}')
        ctx.add_init_script(''.join(js))
        page = ctx.new_page()
        if self.args.perf:
            cdp = ctx.new_cdp_session(page)
            cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
            self.cdp[key] = cdp
        page.route('**/api/v1/auth/me/', self._me_route)
        entry = (ctx, page, Metrics(page))
        self.ctxs[key] = entry
        return entry

    def _me_route(self, route):
        """Pass-through, optionally patching fields of the /auth/me/ response."""
        if not self.me_mock or route.request.method != 'GET':
            return route.continue_()
        try:
            resp = route.fetch()
            body = resp.json()
            body.update(self.me_mock)
            route.fulfill(response=resp, json=body)
        except Exception:
            route.continue_()

    # --- settle ---

    def settle(self, page):
        """Network idle-ish + images loaded, both capped. Never raises."""
        try:
            page.wait_for_load_state('networkidle', timeout=SETTLE_NET_MS)
        except Exception:
            pass
        try:
            page.wait_for_function(
                """() => [...document.images].filter(i => {
                        const r = i.getBoundingClientRect();
                        return r.width > 40 && r.height > 40 && r.bottom > 0 && r.top < innerHeight;
                     }).every(i => i.complete && i.naturalWidth > 0)""",
                timeout=SETTLE_IMG_MS)
        except Exception:
            pass
        try:
            page.wait_for_timeout(350)   # entrance animations
        except Exception:
            pass

    # --- actions ---

    def fmt(self, s: str) -> str:
        return re.sub(r'\{(\w+)\}', lambda m: str(self.state.get(m.group(1), m.group(0))), s)

    def locate(self, page, sel: str):
        sel = self.fmt(sel)
        if sel.startswith('xy='):
            return None
        loc = page.locator(sel) if is_selector(sel) else page.get_by_text(sel)
        # Comma lists ("a, b") are fine in CSS; take the first match to avoid strict-mode errors.
        return loc.first

    def goto(self, page, path: str):
        page.goto(BASE_URL + self.fmt(path), wait_until='domcontentloaded')

    def drag(self, page, direction: str, hold: bool = False):
        cx = VIEWPORT[0] // 2
        dx = 260 if direction == 'right' else -260
        steps = 6 if hold else 10
        page.mouse.move(cx, SWIPE_Y)
        page.mouse.down()
        for i in range(1, steps + 1):
            page.mouse.move(cx + dx * i / 10, SWIPE_Y + i * 2)
            page.wait_for_timeout(16)
        if hold:
            self.hold_active = True
            return
        page.mouse.up()
        # The card fly-out animation swallows the next drag; wait for the swipe POST (or timeout).
        try:
            page.wait_for_response(lambda r: '/swipes/' in r.url and r.request.method == 'POST', timeout=2500)
        except Exception:
            pass
        page.wait_for_timeout(900)

    def act(self, page, a: dict):
        if 'goto' in a:
            self.goto(page, a['goto'])
        elif 'click' in a:
            sel = self.fmt(a['click'])
            try:
                if sel.startswith('xy='):
                    x, y = (float(v) for v in sel[3:].split(','))
                    page.mouse.click(x, y)
                else:
                    loc = self.locate(page, sel)
                    loc.click(force=bool(a.get('force')), timeout=a.get('timeout', 5000 if a.get('optional') else ACTION_TIMEOUT_MS))
            except (PWTimeout, PWError):
                if not a.get('optional'):
                    raise
            page.wait_for_timeout(250)
        elif 'fill' in a:
            sel, val = a['fill']
            loc = self.locate(page, sel)
            loc.click()
            loc.fill(val)
        elif 'wait' in a:
            w = a['wait']
            if isinstance(w, (int, float)):
                page.wait_for_timeout(int(w))
            else:
                self.locate(page, w).wait_for(state='visible', timeout=a.get('timeout', ACTION_TIMEOUT_MS))
        elif 'find_architect' in a:
            # Open board tiles 1..8 until a building detail page has a clickable architect.
            board = self.fmt('/board/{board_id}')
            for n in range(8):
                if page.locator('button[class*=architectLink]').count():
                    break
                self.goto(page, board)
                tiles = page.locator('div[class*=tile]')
                tiles.first.wait_for(state='visible', timeout=20000)
                if n >= tiles.count():
                    break
                tiles.nth(n).click()
                page.wait_for_timeout(2200)
            page.locator('button[class*=architectLink]').first.click(timeout=5000)
            page.wait_for_url('**/architects/*', timeout=10000)
            page.wait_for_timeout(1500)
        elif 'wait_url' in a:
            page.wait_for_url('**' + a['wait_url'] + '*', timeout=a.get('timeout', 30000))
        elif 'scroll' in a:
            page.evaluate("""px => {
                const els = [document.scrollingElement, ...document.querySelectorAll('*')].filter(e => e &&
                    e.scrollHeight > e.clientHeight + 40 && e.clientHeight > 300 &&
                    (e === document.scrollingElement || /(auto|scroll)/.test(getComputedStyle(e).overflowY)));
                els.sort((x, y) => (y.scrollHeight - y.clientHeight) - (x.scrollHeight - x.clientHeight));
                if (els[0]) els[0].scrollBy({top: px, behavior: 'instant'});
            }""", a['scroll'])
            page.wait_for_timeout(350)
        elif 'swipe' in a:
            for _ in range(int(a.get('n', 1))):
                self.drag(page, a['swipe'])
        elif 'hold' in a:
            self.drag(page, a['hold'], hold=True)
        elif 'release' in a:
            if self.hold_active:
                page.mouse.up()
                self.hold_active = False
        elif 'swipe_gallery' in a:
            page.mouse.move(VIEWPORT[0] // 2, 450)
            page.mouse.wheel(0, 700 if a['swipe_gallery'] == 'up' else -700)
            page.wait_for_timeout(600)
        elif 'key' in a:
            page.keyboard.press(a['key'])
            page.wait_for_timeout(300)
        elif 'remember' in a:
            name, rx = a['remember']
            m = re.search(rx, clean_path(page.url))
            if m:
                self.state[name] = m.group(1)
        elif 'mock_me' in a:
            self.me_mock = dict(a['mock_me'])
        elif 'unmock_me' in a:
            self.me_mock = None
            page.evaluate("sessionStorage.removeItem('archithon_onboarding_required')")
        else:
            raise ValueError(f'unknown action {a}')

    # --- one scenario ---

    def shoot(self, page, path: str, full: bool, debug: bool = False):
        if not debug:
            try:
                page.evaluate(HIDE_DEBUG_JS)
            except Exception:
                pass
        # dev-login maps to a real Google-linked account: mask every email address on screen
        # (text nodes + input values) so shots are safe to publish.
        try:
            page.evaluate(REDACT_JS)
        except Exception:
            pass
        page.screenshot(path=path, type='jpeg', quality=80, full_page=full)

    def run_scenario(self, sc: dict, img_dir: str) -> dict:
        account = sc.get('account', 'main')
        theme, lang = sc.get('theme', 'light'), sc.get('lang', 'ko')
        base = f"{sc['id']}-{sc['slug']}"
        rec = {
            'id': sc['id'], 'slug': sc['slug'], 'stage': sc['stage'], 'title_ko': sc['title_ko'],
            'caption_ko': sc['caption_ko'], 'url': None, 'img': None, 'img_debug': None, 'tag': 'phone',
            'variant': {'theme': theme, 'lang': lang, 'account': account},
            'ok': True, 'skipped': False, 'error': None,
            'metrics': {'ready_ms': 0, 'api': [], 'console_errors': [], 'failed': [], 'longtasks': None},
        }
        if account == 'fresh' and 'fresh' not in self.tokens:
            self.tokens['fresh'] = register_fresh()
        if account in ('main', 'fresh') and not self.tokens.get(account):
            rec.update(ok=False, skipped=True, error=f'account "{account}" unavailable')
            return rec

        ctx, page, met = self.get_page(account, theme, lang)
        met.reset()
        if self.args.perf:
            try:
                page.evaluate('window.__lt={count:0,total:0}')
            except Exception:
                pass
        t0 = time.time()
        try:
            if sc.get('route'):
                self.goto(page, sc['route'])
            for a in sc.get('actions', []):
                self.act(page, a)
            if not sc.get('no_settle'):   # e.g. a 3s toast would expire during settle
                self.settle(page)
            if sc.get('requires'):
                if page.locator(sc['requires']).count() == 0:
                    rec.update(ok=False, skipped=True, error=f"precondition missing: {sc['requires']}")
        except Exception as e:
            rec.update(ok=False, error=str(e).splitlines()[0][:300] if str(e) else repr(e))
            self.hold_active = False
        rec['metrics']['ready_ms'] = int((time.time() - t0) * 1000)

        # Remember the swipe session id from API traffic (placeholder {session_id}).
        for c in met.api:
            m = re.match(r'^/api/v1/analysis/sessions/([0-9a-f-]{36})/', c['path'])
            if m:
                self.state['session_id'] = m.group(1)

        # Screenshots -- always try, even after a failure, so the log shows what was on screen.
        full = bool(sc.get('full_page'))
        try:
            rec['url'] = clean_path(page.url)
            rel = f'img/{base}.jpg'
            self.shoot(page, os.path.join(img_dir, f'{base}.jpg'), full)
            rec['img'] = rel
            if sc.get('debug', True) and not self.args.no_debug and not self.args.perf and not rec['skipped']:
                page.evaluate(SHOW_DEBUG_JS)
                rel_d = f'img/{base}.debug.jpg'
                self.shoot(page, os.path.join(img_dir, f'{base}.debug.jpg'), full, debug=True)
                rec['img_debug'] = rel_d
        except Exception as e:
            rec['error'] = rec['error'] or f'screenshot failed: {str(e)[:150]}'
            rec['ok'] = False

        m = rec['metrics']
        m['api'], m['console_errors'], m['failed'] = met.api, met.console_errors, met.failed
        if self.args.perf:
            try:
                lt = page.evaluate('window.__lt')
                m['longtasks'] = {'count': int(lt['count']), 'total_ms': int(lt['total'])}
            except Exception:
                m['longtasks'] = {'count': 0, 'total_ms': 0}
        return rec


# -- main ---------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description='ArchiTinder phone flow capture (local only).')
    ap.add_argument('--browser', choices=['webkit', 'chromium'], default='webkit')
    ap.add_argument('--only', help='scenario ids, e.g. 01,05-09')
    ap.add_argument('--stage', help='stage key, e.g. swipe')
    ap.add_argument('--no-debug', action='store_true', help='skip the debug-overlay shots')
    ap.add_argument('--perf', action='store_true', help='chromium + 4x CPU throttle + long-task counts')
    ap.add_argument('--out', help='output dir (default web-testing/reports/flow/<date>/)')
    args = ap.parse_args()

    # Preflight: both dev servers must already be running. We never start them.
    down = [f'{n} ({p})' for n, p in (('frontend', 5174), ('backend', 8001)) if not port_open('localhost', p)]
    if down:
        sys.exit('ABORT: dev server(s) not reachable on localhost: ' + ', '.join(down) +
                 '. Start them yourself (make frontend / make backend); this tool never does.')

    todo = list(SCENARIOS)
    if args.only:
        wanted = parse_only(args.only)
        todo = [s for s in todo if s['id'] in wanted]
    if args.stage:
        todo = [s for s in todo if s['stage'] == args.stage]
    if not todo:
        sys.exit('No scenarios selected.')

    date = dt.date.today().isoformat()
    out = args.out or os.path.join(DEFAULT_OUT_ROOT, date)
    img_dir = os.path.join(out, 'img')
    os.makedirs(img_dir, exist_ok=True)

    started = dt.datetime.now().astimezone()
    t_start = time.time()
    shots = []
    with sync_playwright() as pw:
        r = Runner(args, pw)
        r.launch()
        needs_main = any(s.get('account', 'main') == 'main' for s in todo)
        if needs_main:
            r.tokens['main'] = dev_login()
        log(f'browser={r.browser_name} device={DEVICE} scenarios={len(todo)} out={out}')
        for sc in todo:
            rec = r.run_scenario(sc, img_dir)
            shots.append(rec)
            flag = 'SKIP' if rec['skipped'] else ('ok  ' if rec['ok'] else 'FAIL')
            log(f"  [{flag}] {rec['id']} {rec['slug']:<26} {rec['metrics']['ready_ms']:>5} ms"
                + (f"  -- {rec['error']}" if rec['error'] else ''))
        r.browser.close()

    finished = dt.datetime.now().astimezone()
    counts = {'total': len(shots),
              'ok': sum(1 for s in shots if s['ok']),
              'failed': sum(1 for s in shots if not s['ok'] and not s['skipped']),
              'skipped': sum(1 for s in shots if s['skipped'])}
    manifest = {
        'run': {'date': date, 'started_at': started.isoformat(timespec='seconds'),
                'finished_at': finished.isoformat(timespec='seconds'), 'base_url': BASE_URL,
                'browser': r.browser_name, 'device': DEVICE, 'viewport': VIEWPORT,
                'git_sha': git('rev-parse', '--short', 'HEAD'),
                'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
                'perf': bool(args.perf), 'counts': counts},
        'stages': STAGES,
        'shots': shots,
    }
    with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # One-line summary
    api = [(c['ms'], c['path']) for s in shots for c in s['metrics']['api']]
    slow = {}
    for ms, p in api:
        slow[p] = max(slow.get(p, 0), ms)
    top = sorted(slow.items(), key=lambda kv: -kv[1])[:5]
    errs = sum(len(s['metrics']['console_errors']) for s in shots)
    log(f"SUMMARY total={counts['total']} ok={counts['ok']} failed={counts['failed']} skipped={counts['skipped']} "
        f"console_errors={errs} time={time.time() - t_start:.0f}s "
        f"slowest_api=[{', '.join(f'{p} {ms}ms' for p, ms in top)}] out={out}")


if __name__ == '__main__':
    main()
