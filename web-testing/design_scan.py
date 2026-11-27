"""Mobile design baseline scan: impeccable detector + axe-core on rendered pages.

Opens each route of the local app (5174) in a logged-in Chromium at 390x844, then runs
`impeccable detect --cdp` (anti-pattern / slop rules on the rendered DOM) and axe-core
(WCAG 2 A/AA) against it. Writes per-route JSON + a screenshot and a summary.json.

Usage:
    python web-testing/design_scan.py [--out DIR] [--env PATH] [--theme light|dark] [--only /a,/b] [--base URL]

Reads DEV_LOGIN_SECRET from backend/.env (never printed). Needs the dev servers up
(frontend 5174, backend 8001). Read-only against the app apart from one dev-login.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = 'http://localhost:5174'
BACKEND_URL = 'http://localhost:8001'
VIEWPORT = (390, 844)
CDP_PORT = 9333
AXE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js'
DETECT = os.path.expanduser('~/.claude/skills/impeccable/scripts/impeccable')
THEME_KEYS = {'light': 'github-light', 'dark': 'github-dark'}

# Route ids (from flow run 2026-10-26) that exist in the dev DB.
ROUTES = [
    '/login', '/discovery', '/search', '/people', '/messages', '/competitions',
    '/notifications', '/user/me', '/user/30', '/assessment', '/upload',
    '/settings', '/settings/edit-profile', '/settings/account',
    '/settings/notifications', '/settings/appearance',
    '/buildings/bld_029735', '/architects/arch_005323',
    '/board/f0aff221-7b62-4d3c-a96b-b6f1c215e69c',
    '/result/7bc0e6f3-052d-483c-b784-e71024fe4ac1',
]
LOGGED_OUT = {'/login'}


def read_secret(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('DEV_LOGIN_SECRET='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    sys.exit('ABORT: DEV_LOGIN_SECRET missing')


def dev_login(secret):
    req = urllib.request.Request(
        BACKEND_URL + '/api/v1/auth/dev-login/', data=json.dumps({'secret': secret}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f'ABORT: dev-login HTTP {e.code}')
    return {'access': d['access'], 'refresh': d['refresh'], 'user_id': str(d['user']['user_id'])}


def slug(path):
    return re.sub(r'[^a-z0-9]+', '-', path.lower()).strip('-')[:40] or 'root'


def init_js(tok, theme):
    seed = {'archithon_theme': THEME_KEYS[theme], 'archithon_language': 'ko',
            'archithon_tutorial_dismissed': 'true'}
    js = ['try{']
    for k, v in seed.items():
        js.append(f'localStorage.setItem({json.dumps(k)},{json.dumps(v)});')
    if tok:
        js.append(f"localStorage.setItem('archithon_access',{json.dumps(tok['access'])});"
                  f"localStorage.setItem('archithon_refresh',{json.dumps(tok['refresh'])});"
                  f"sessionStorage.setItem('archithon_user',{json.dumps(tok['user_id'])});")
    js.append('}catch(e){}')
    return ''.join(js)


def run_detect():
    p = subprocess.run(['sh', DETECT, 'detect', '--json', '--cdp', str(CDP_PORT)],
                       capture_output=True, text=True, encoding='utf-8', timeout=180)
    try:
        return json.loads(p.stdout or '[]'), None
    except json.JSONDecodeError:
        return [], (p.stderr or p.stdout)[-500:]


def run_axe(page):
    page.add_script_tag(url=AXE_URL)
    return page.evaluate("""async () => {
        const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}});
        return r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help,
            count: v.nodes.length, targets: v.nodes.slice(0, 5).map(n => n.target.join(' '))}));
    }""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'web-testing', 'reports', 'design',
                                                  datetime.date.today().isoformat()))
    ap.add_argument('--env', default=os.path.join(ROOT, 'backend', '.env'))
    ap.add_argument('--theme', default='light', choices=list(THEME_KEYS))
    ap.add_argument('--only', default='')
    ap.add_argument('--base', default=BASE_URL, help='frontend origin, e.g. http://localhost:5173')
    args = ap.parse_args()
    routes = [r for r in args.only.split(',') if r] or ROUTES
    out = os.path.join(args.out, args.theme)
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    tok = dev_login(read_secret(args.env))
    summary = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[f'--remote-debugging-port={CDP_PORT}'])
        dev = dict(pw.devices['iPhone 13'])
        dev.pop('default_browser_type', None)
        dev['viewport'] = {'width': VIEWPORT[0], 'height': VIEWPORT[1]}
        for route in routes:
            ctx = browser.new_context(**dev, locale='ko-KR', timezone_id='Asia/Seoul')
            ctx.add_init_script(init_js(None if route in LOGGED_OUT else tok, args.theme))
            page = ctx.new_page()
            rec = {'route': route, 'slug': slug(route)}
            try:
                page.goto(args.base + route, wait_until='domcontentloaded', timeout=30000)
                try:
                    page.wait_for_load_state('networkidle', timeout=12000)
                except Exception:
                    pass
                time.sleep(1.5)
                rec['final_path'] = re.sub(r'^https?://[^/]+', '', page.url).split('?')[0]
                page.screenshot(path=os.path.join(out, 'img', rec['slug'] + '.jpg'), type='jpeg', quality=75)
                rec['detect'], err = run_detect()
                if err:
                    rec['detect_error'] = err
                rec['axe'] = run_axe(page)
            except Exception as e:
                rec['error'] = str(e).splitlines()[0][:200]
            with open(os.path.join(out, rec['slug'] + '.json'), 'w', encoding='utf-8') as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
            summary.append({'route': route, 'final_path': rec.get('final_path'),
                            'detect': len(rec.get('detect') or []), 'axe': sum(v['count'] for v in rec.get('axe') or []),
                            'error': rec.get('error') or rec.get('detect_error', '')[:120]})
            print(f"{route:55} detect={summary[-1]['detect']:3} axe={summary[-1]['axe']:3} {summary[-1]['error']}")
            ctx.close()
        browser.close()
    with open(os.path.join(out, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
