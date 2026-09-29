#!/usr/bin/env python3
"""
design-capture.py — screenshot every Claude Design board and its live app
route as PNG pairs, for visual (pixel-level) comparison.

Complements tools/design-diff.py: that tool diffs computed style properties;
this one produces image pairs a vision model (or a human) can judge directly,
catching what a property diff cannot — composition, spacing rhythm, anything
expressed through layout rather than a single CSS value.

Both sides render at 1440x900, github-light, Korean — the mocks' defaults —
so differences are design differences, not environment differences.

Usage:
    python tools/design-capture.py [board ...]        # default: all mapped
    python tools/design-capture.py --out DIR          # default: <scratchpad>/shots

Requires the dev server on :5173 (CORS pins the port) and Python Playwright.
"""
import argparse, re, sys
from pathlib import Path

APP = "http://localhost:5173"

# Same route map as design-diff.py. Overlay boards and login sub-states need
# UI interaction to reach and are deliberately absent — they stay manual.
ROUTES = {
    "discovery": "/discovery",
    "taste-swipe": "/swipe",
    "results": "/result/1",
    "persona-report": "/board/1/report",
    "profile": "/user/me",
    "user-other": "/user/2",
    "board-detail": "/board/1",
    "liked-projects": "/liked-projects",
    "building-detail": "/buildings/1",
    "architect": "/architects/1",
    "office": "/office/1",
    "upload": "/upload",
    "notifications": "/notifications",
    "settings": "/settings",
    "settings-account": "/settings/account",
    "settings-appearance": "/settings/appearance",
    "settings-edit-profile": "/settings/edit-profile",
    "settings-notifications": "/settings/notifications",
    "llm-search": "/search",
    "llm-search-update": "/search",
    "login": "/login",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("boards", nargs="*")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "web-testing" / "design-shots"
    out.mkdir(parents=True, exist_ok=True)

    targets = args.boards or list(ROUTES)
    bad = [b for b in targets if b not in ROUTES]
    if bad:
        print(f"unmapped (manual-only): {', '.join(bad)}")
        targets = [b for b in targets if b in ROUTES]

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.new_page()

        # Auth + pin theme/language to the mocks' defaults BEFORE any app page
        # applies a saved preference.
        page.goto(f"{APP}/login", wait_until="networkidle", timeout=20000)
        page.evaluate("""() => {
            localStorage.setItem('archithon_theme', 'github-light');
            localStorage.setItem('archithon_language', 'ko');
        }""")
        btn = page.get_by_text(re.compile(r"^Dev login$", re.I))
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(2500)
        print(f"auth: {'ok' if '/login' not in page.url else 'FAILED (protected routes will show /login)'}")
        # Re-pin after login in case the profile fetch overwrote them.
        page.evaluate("""() => {
            localStorage.setItem('archithon_theme', 'github-light');
            localStorage.setItem('archithon_language', 'ko');
        }""")

        # Resolve REAL ids from the authenticated session — /result/1, /board/1,
        # /buildings/1, /architects/1, /office/1 were fantasy ids that landed on
        # not-found/error pages and made 7 boards unjudgeable in the first run.
        ids = page.evaluate("""async () => {
            const H = { headers: { Authorization: 'Bearer ' + localStorage.getItem('archithon_access') } };
            const j = async (u) => { try { const r = await fetch('/api/v1' + u, H); return r.ok ? await r.json() : null; } catch { return null; } };
            const out = {};
            const projects = await j('/projects/');
            const list = Array.isArray(projects) ? projects : (projects && projects.results) || [];
            if (list.length) {
                const pid = (p) => p.id || p.project_id || p.backend_id; out.board = pid(list[0]);
                const withReport = list.find(p => p.final_report || p.finalReport);
                out.reportBoard = pid(withReport || list[0]);
                const withSession = list.find(p => p.session_id || p.sessionId);
                if (withSession) out.session = withSession.session_id || withSession.sessionId;
            }
            const feed = await j('/discovery/feed/?limit=1');
            const card = feed && (feed.cards || feed.results || feed)[0];
            if (card) out.building = card.canonical_bld_id || card.image_id || card.building_id;
            return out;
        }""") or {}
        print(f"resolved ids: {ids}")
        if ids.get('board'):
            ROUTES['board-detail'] = f"/board/{ids['board']}"
            ROUTES['persona-report'] = f"/board/{ids.get('reportBoard', ids['board'])}/report"
        if ids.get('session'):
            ROUTES['results'] = f"/result/{ids['session']}"
        if ids.get('building'):
            ROUTES['building-detail'] = f"/buildings/{ids['building']}"

        for b in targets:
            route = ROUTES[b]
            if b == 'login':
                # A logged-in context redirects /login away. Capture it in a
                # FRESH context with no stored auth.
                fresh = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                fp = fresh.new_page()
                try:
                    fp.goto(f"{APP}/__mocks/login.html", wait_until="networkidle", timeout=20000)
                    fp.wait_for_timeout(400)
                    fp.screenshot(path=str(out / "login--mock.png"))
                    fp.goto(f"{APP}/login", wait_until="networkidle", timeout=20000)
                    fp.wait_for_timeout(1600)
                    fp.screenshot(path=str(out / "login--app.png"))
                    print("  login: ok (fresh context)")
                except Exception as e:
                    print(f"  login: FAILED — {e}")
                fresh.close()
                continue
            try:
                page.goto(f"{APP}/__mocks/{b}.html", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(400)
                page.screenshot(path=str(out / f"{b}--mock.png"))
            except Exception as e:
                print(f"  {b}: mock capture FAILED — {e}")
                continue
            try:
                page.goto(f"{APP}{route}", wait_until="networkidle", timeout=25000)
                page.wait_for_timeout(1600)  # let data + fonts settle
                page.screenshot(path=str(out / f"{b}--app.png"))
                print(f"  {b}: ok")
            except Exception as e:
                print(f"  {b}: app capture FAILED — {e}")

        browser.close()

    print(f"\npairs -> {out}")


if __name__ == "__main__":
    sys.exit(main())
