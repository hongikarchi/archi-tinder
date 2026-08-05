#!/usr/bin/env python3
"""
ab_screenshot.py -- standalone, one-off Playwright script.

NOT part of the web-testing/ E2E runner (run.py / runner/). Ad-hoc tool for
capturing full-page screenshots of the 4 seeded LLM A/B persona-report
boards (Gemini vs GPT x Brutalist vs Minimal). Safe to delete after use.

Written in Python (not Node) because this repo's web-testing/ has the
`playwright` PIP package installed (1.60.0, chromium binary present) but no
Node `playwright` package in node_modules -- this avoids pulling a fresh npm
dependency just for a one-off screenshot task. A Node (.mjs) sibling with the
same logic is kept alongside this file for reference / future use once a
Node Playwright install exists, but this .py file is what actually ran.

Usage (from web-testing/, with backend + frontend dev servers running):
    python ab_screenshot.py
"""
import json
import os
import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5174")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
OUT_DIR = os.path.join(REPO_ROOT, "llm-ab-screens")

BOARDS = [
    {"name": "[GEMINI] Brutalist Persona", "id": "f8d47370-3e62-44a4-9aef-7bff5ae71bfa", "file": "gemini-brutalist.png"},
    {"name": "[GEMINI] Minimal Persona", "id": "1f2bc245-15db-4308-aba9-25da33c800a0", "file": "gemini-minimal.png"},
    {"name": "[GPT] Brutalist Persona", "id": "5564efca-a196-4b1e-947f-21c2c05ed683", "file": "gpt-brutalist.png"},
    {"name": "[GPT] Minimal Persona", "id": "61a8d611-2bc8-4d3b-b83e-3bf473ee2a99", "file": "gpt-minimal.png"},
]

# Bonus detail-page shots: one gemini + one gpt board.
DETAIL_BOARDS = [
    {"name": "[GEMINI] Brutalist Persona", "id": "f8d47370-3e62-44a4-9aef-7bff5ae71bfa", "file": "gemini-brutalist-detail.png"},
    {"name": "[GPT] Brutalist Persona", "id": "5564efca-a196-4b1e-947f-21c2c05ed683", "file": "gpt-brutalist-detail.png"},
]


def read_dev_login_secret():
    env_path = os.path.join(REPO_ROOT, "backend", ".env")
    with open(env_path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^DEV_LOGIN_SECRET=(.+)$", text, re.MULTILINE)
    if not m:
        raise RuntimeError("DEV_LOGIN_SECRET not found in backend/.env")
    return m.group(1).strip()


def dev_login():
    secret = read_dev_login_secret()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/auth/dev-login/",
        data=json.dumps({"secret": secret}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    # ProtectedRoute (frontend/src/components/ProtectedRoute.jsx) gates on the
    # App.jsx `userId` React state, which is seeded from sessionStorage key
    # 'archithon_user' (see handleLogin in App.jsx: sessionStorage.setItem
    # ('archithon_user', id) where id = user.user_id). Setting only the
    # localStorage JWT keys is NOT sufficient -- the route guard checks this
    # sessionStorage key, not the token. Discovered empirically: without it,
    # every /board/:id/report navigation silently redirects to /login.
    user_id = str(data["user"]["user_id"])
    return data["access"], data["refresh"], user_id


def screenshot_scrollable_page(page, out_path):
    """
    Full-page screenshot workaround for this app's viewport-lock layout
    (frontend/src/index.css: `body { height: 100vh; overflow: hidden; }`,
    per CLAUDE.md "Viewport-lock layout"). The actual scrollable content
    lives in an inner `.page` div (BoardReportPage.module.css:
    `.page { height: calc(100vh - 64px); overflow-y: auto; }`), not in
    `document.body` -- so Playwright's `page.screenshot(full_page=True)`
    (which measures document/body scrollHeight) clips to the viewport
    (confirmed empirically: first pass produced 1280x900 images with content
    visibly cut off mid-slider).

    A second attempt tried `elementHandle.screenshot()` on the scroll
    container directly -- also wrong: Playwright's element screenshot
    captures the element's laid-out bounding box (clientHeight, 836px),
    NOT its scrollHeight (1621px, confirmed via _debug_scroll.py), because
    the element still has `overflow-y: auto` applied while screenshotting.

    Working fix: temporarily override the container's inline style so it
    is not clipped (height: auto, overflow: visible, matching its
    scrollHeight). Debugging (_debug_scroll2.py, deleted after use) showed
    the app shell nests MULTIPLE fixed-height/overflow:hidden divs between
    `.page` and `<body>` (an ancestor 2 levels up also had
    `height: 900px; overflow: hidden`, independent of index.css's
    `body { height: 100vh; overflow: hidden }`) -- so overriding only the
    scroll container and body/html was not enough; must walk the ENTIRE
    ancestor chain from the scroll container up to <html> and clear
    overflow/height on every element with `overflow: hidden` or a fixed
    pixel height. Then take the normal page.screenshot(full_page=True) --
    now document.body genuinely grows to match. No restore needed: each
    board is a fresh page.goto() navigation, which resets all DOM/style
    state anyway.
    """
    changed = page.evaluate(
        """
        () => {
          const candidates = Array.from(document.querySelectorAll('div'));
          let best = null;
          let bestHeight = 0;
          for (const el of candidates) {
            const style = getComputedStyle(el);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > bestHeight) {
              best = el;
              bestHeight = el.scrollHeight;
            }
          }
          if (!best) return false;
          let el = best;
          while (el) {
            const style = getComputedStyle(el);
            if (style.overflow === 'hidden' || style.overflowY === 'hidden' || /^\\d+px$/.test(style.height)) {
              el.style.height = 'auto';
              el.style.maxHeight = 'none';
              el.style.overflow = 'visible';
            }
            el = el.parentElement;
          }
          document.documentElement.style.height = 'auto';
          document.documentElement.style.overflow = 'visible';
          return true;
        }
        """
    )
    if changed:
        page.wait_for_timeout(200)  # let layout reflow settle
    page.screenshot(path=out_path, full_page=True)
    return changed


def wait_for_report(page):
    success_selector = 'img[src^="data:"], h1:has-text("The "), h2:has-text("The ")'
    try:
        page.wait_for_selector(success_selector, timeout=15000)
        return True, None
    except Exception:
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        if page.query_selector(success_selector):
            return True, None
        generate_btn = page.query_selector(
            'button:has-text("생성"), button:has-text("Generate"), button:has-text("생성하기")'
        )
        if generate_btn:
            return False, "generate empty-state (no pre-generated report) -- screenshotting anyway"
        return False, "no report image/heading found after networkidle+settle -- screenshotting anyway"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[ab_screenshot] dev-login...")
    access, refresh, user_id = dev_login()
    print(f"[ab_screenshot] tokens acquired (not printed), user_id={user_id}")

    results = []
    detail_results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Must be on the origin before localStorage/sessionStorage can be set for it.
        page.goto(FRONTEND_URL, wait_until="domcontentloaded")
        page.evaluate(
            "([access, refresh, userId]) => { "
            "localStorage.setItem('archithon_access', access); "
            "localStorage.setItem('archithon_refresh', refresh); "
            "sessionStorage.setItem('archithon_user', userId); }",
            [access, refresh, user_id],
        )

        for board in BOARDS:
            url = f"{FRONTEND_URL}/board/{board['id']}/report"
            print(f"[ab_screenshot] -> {board['name']} : {url}")
            page.goto(url, wait_until="domcontentloaded")
            ok, reason = wait_for_report(page)
            out_path = os.path.join(OUT_DIR, board["file"])
            screenshot_scrollable_page(page, out_path)
            results.append({**board, "url": url, "out_path": out_path, "ok": ok, "reason": reason})
            print(f"[ab_screenshot]    screenshot saved: {out_path} (ok={ok})")

        for board in DETAIL_BOARDS:
            url = f"{FRONTEND_URL}/board/{board['id']}"
            print(f"[ab_screenshot] (bonus) -> {board['name']} detail : {url}")
            try:
                page.goto(url, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(1000)
                out_path = os.path.join(OUT_DIR, board["file"])
                screenshot_scrollable_page(page, out_path)
                detail_results.append({**board, "url": url, "out_path": out_path, "ok": True})
                print(f"[ab_screenshot]    bonus screenshot saved: {out_path}")
            except Exception as e:
                detail_results.append({**board, "url": url, "ok": False, "reason": str(e)})
                print(f"[ab_screenshot]    bonus skipped: {e}")

        browser.close()

    print("\n=== SUMMARY ===")
    for r in results:
        status = "OK" if r["ok"] else f"FLAGGED ({r['reason']})"
        size = os.path.getsize(r["out_path"]) if os.path.exists(r["out_path"]) else 0
        print(f"{r['file']}: {status} -- {size} bytes")
    for r in detail_results:
        if r["ok"]:
            size = os.path.getsize(r["out_path"]) if os.path.exists(r["out_path"]) else 0
            print(f"{r['file']}: OK (bonus) -- {size} bytes")
        else:
            print(f"{r['file']}: SKIPPED ({r['reason']})")


if __name__ == "__main__":
    main()
