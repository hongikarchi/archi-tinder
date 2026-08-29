#!/usr/bin/env python3
"""
design-diff.py — compare each Claude Design board against the running app,
property by property, and report what the port missed.

Why this exists: three separate misses in the 2026-08-29 port (the Archibe
logo, the trigger card's top row, the login credentials card) all came from a
human reading a mock, summarising it into a dispatch, and losing detail in the
summary. This tool removes the summarising step — it reads computed styles off
both sides and diffs values.

Usage:
    python tools/design-diff.py                 # all mapped boards
    python tools/design-diff.py login-credentials profile
    python tools/design-diff.py --json out.json

Requires: the dev server on :5173 (mocks are served from /__mocks/), and
Playwright (`pip install playwright && playwright install chromium`).
"""
import argparse, json, re, sys
from pathlib import Path

APP = "http://localhost:5173"
MOCKS = f"{APP}/__mocks"

# board -> (route, needs_auth). Overlay boards map to the page that hosts them;
# their overlay itself is not reachable without interaction, so we diff the host
# page's base layer and flag the overlay as manual-only.
ROUTES = {
    "discovery": ("/discovery", True),
    "taste-swipe": ("/swipe", True),
    "results": ("/result/1", True),
    "persona-report": ("/board/1/report", True),
    "profile": ("/user/me", True),
    "user-other": ("/user/2", True),
    "board-detail": ("/board/1", True),
    "liked-projects": ("/liked-projects", True),
    "building-detail": ("/buildings/1", True),
    "architect": ("/architects/1", True),
    "office": ("/office/1", True),
    "upload": ("/upload", True),
    "notifications": ("/notifications", True),
    "settings": ("/settings", True),
    "settings-account": ("/settings/account", True),
    "settings-appearance": ("/settings/appearance", True),
    "settings-edit-profile": ("/settings/edit-profile", True),
    "settings-notifications": ("/settings/notifications", True),
    "llm-search": ("/search", True),
    "llm-search-update": ("/search", True),
    "login": ("/login", False),
}

# Login sub-states and overlays need a UI interaction to reach. Diffing them
# automatically would require scripting each flow; report them as manual.
MANUAL_ONLY = {
    "login-credentials", "login-consent", "login-profile", "login-returning",
}

# Properties worth comparing. Deliberately excludes anything positional
# (top/left/width) — the mock is a 1440x900 fixed canvas and the app is fluid,
# so geometry differs by design. These are the properties that carry design
# intent and that the port kept getting wrong.
PROPS = [
    "padding", "justifyContent", "alignItems", "gap", "flexDirection",
    "backgroundColor", "backgroundImage", "color", "borderColor", "borderRadius",
    "borderWidth", "fontSize", "fontWeight", "letterSpacing", "lineHeight",
    "textTransform", "textAlign", "opacity", "boxShadow",
]

# Extract a comparable signature for every visible element.
#
# Two element populations, because they need different join keys:
#   textual — has own text; joined across mock/app by that text
#   iconic  — no text (buttons, icon wrappers, toggles); joined by an SVG
#             path signature, since an icon's `d` attribute is identical in
#             the mock and the app when it is the same icon
#
# The first version of this tool only did the textual pass. That is exactly
# how it missed the top-right language/theme toggle and the top-left icon
# cluster on 20 boards — they carry almost no text, so they were invisible to
# a text-keyed diff. Structural elements must be compared structurally.
EXTRACT = """
(props) => {
  const textual = [];
  const iconic = [];
  for (const el of document.querySelectorAll('*')) {
    if (['SCRIPT','STYLE','META','LINK','HEAD','HTML','DEFS','TITLE'].includes(el.tagName)) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') continue;

    let own = '';
    for (const n of el.childNodes) if (n.nodeType === 3) own += n.nodeValue;
    own = own.replace(/\\s+/g, ' ').trim();

    const box = { w: Math.round(r.width), h: Math.round(r.height),
                  x: Math.round(r.x), y: Math.round(r.y) };

    if (own) {
      // The mock wraps button labels in bare <span class="ko|en"> for its
      // language switcher; the app puts the text straight in the <button>.
      // Comparing that span against the app's button reports the button's own
      // padding/background/radius as differences that do not exist. So when an
      // element is a styleless wrapper, attribute its text to the nearest
      // ancestor that actually carries styling.
      let host = el;
      for (let i = 0; i < 3; i++) {
        const hs = getComputedStyle(host);
        const bare = hs.backgroundColor === 'rgba(0, 0, 0, 0)' &&
                     hs.padding === '0px' && hs.borderWidth === '0px' &&
                     (hs.borderRadius === '0px' || hs.borderRadius === '');
        if (!bare || !host.parentElement) break;
        const p = host.parentElement;
        // only climb while the parent's text is still just this text
        if ((p.innerText || '').replace(/\\s+/g, ' ').trim() !== own) break;
        host = p;
      }
      const hstyle = {};
      const hcs = getComputedStyle(host);
      for (const p of props) hstyle[p] = hcs[p];
      textual.push({ tag: host.tagName, text: own, style: hstyle, ...box });
      continue;
    }

    const style = {};
    for (const p of props) style[p] = cs[p];
    // Iconic: an element that owns exactly one <svg>, or is one. Key on the
    // concatenated `d`/shape attributes — stable across mock and app.
    let svg = null;
    if (el.tagName === 'svg') svg = el;
    else if (el.children.length === 1 && el.children[0].tagName === 'svg') svg = el.children[0];
    if (!svg) continue;
    const parts = [];
    for (const s of svg.querySelectorAll('path,circle,rect,line,polyline,polygon')) {
      parts.push(s.getAttribute('d') || s.getAttribute('points') ||
                 [s.getAttribute('cx'), s.getAttribute('cy'), s.getAttribute('r'),
                  s.getAttribute('x'), s.getAttribute('y')].filter(Boolean).join(','));
    }
    const sig = parts.join('|').slice(0, 220);
    if (!sig) continue;
    iconic.push({ tag: el.tagName, sig, style, ...box });
  }
  return { textual, iconic };
}
"""

# Values that legitimately differ and would drown the signal.
def normalize(prop, v):
    if v is None:
        return v
    v = str(v).strip()
    # colors: collapse rgb/rgba spacing
    v = re.sub(r"\s+", " ", v)
    if prop == "lineHeight" and v.endswith("px"):
        return v  # keep — px line-height is a real difference
    if prop == "boxShadow":
        # shadows carry many decimals; compare coarsely
        return re.sub(r"(\d+\.\d{2})\d+", r"\1", v)
    return v


IGNORE_TEXT = {
    "한국어", "ENGLISH", "Dev login", "Dev Login",
    "디스커버리", "Discovery", "취향", "Taste", "프로필", "Profile",
}


def index_by(nodes, key):
    idx = {}
    for n in nodes:
        k = n.get(key)
        if not k or (key == "text" and (len(k) < 2 or k in IGNORE_TEXT)):
            continue
        idx.setdefault(k, []).append(n)
    return idx


def _deltas(m, a):
    out = []
    for p in PROPS:
        mv, av = normalize(p, m["style"].get(p)), normalize(p, a["style"].get(p))
        if mv != av:
            out.append({"prop": p, "mock": mv, "app": av})
    return out


def diff_board(page, board, route, needs_auth, verbose=False):
    findings = {"board": board, "route": route, "missing_text": [],
                "missing_icons": [], "style_deltas": [], "error": None}

    try:
        page.goto(f"{MOCKS}/{board}.html", wait_until="networkidle", timeout=20000)
        mock = page.evaluate(EXTRACT, PROPS)
    except Exception as e:
        findings["error"] = f"mock load failed: {e}"
        return findings

    try:
        page.goto(f"{APP}{route}", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(1200)  # let data settle
        app = page.evaluate(EXTRACT, PROPS)
    except Exception as e:
        findings["error"] = f"app load failed: {e}"
        return findings

    # --- textual pass -------------------------------------------------
    m_idx, a_idx = index_by(mock["textual"], "text"), index_by(app["textual"], "text")
    for text, m_nodes in m_idx.items():
        a_nodes = a_idx.get(text)
        if not a_nodes:
            # Text in the mock but nowhere in the app. Placeholder data
            # (building names, sample users) lands here too — expected noise,
            # so the text is kept verbatim so a human can tell them apart.
            findings["missing_text"].append({"text": text[:70], "tag": m_nodes[0]["tag"]})
            continue
        d = _deltas(m_nodes[0], a_nodes[0])
        if d:
            findings["style_deltas"].append({"text": text[:50], "tag": m_nodes[0]["tag"], "deltas": d})

    # --- iconic pass --------------------------------------------------
    # An icon missing here means a whole control is absent from the app — the
    # class of miss that a text-only diff cannot see.
    mi, ai = index_by(mock["iconic"], "sig"), index_by(app["iconic"], "sig")
    for sig, m_nodes in mi.items():
        a_nodes = ai.get(sig)
        m0 = m_nodes[0]
        if not a_nodes:
            findings["missing_icons"].append({
                "sig": sig[:60], "tag": m0["tag"],
                "at": f"({m0['x']},{m0['y']})", "size": f"{m0['w']}x{m0['h']}",
                "where": _quadrant(m0),
            })
            continue
        d = _deltas(m0, a_nodes[0])
        if d:
            findings["style_deltas"].append({
                "text": f"[icon {_quadrant(m0)} {m0['w']}x{m0['h']}]",
                "tag": m0["tag"], "deltas": d})

    return findings


def _quadrant(n):
    """Rough placement label so an icon finding is locatable by eye."""
    vert = "top" if n["y"] < 200 else ("bottom" if n["y"] > 700 else "mid")
    horiz = "left" if n["x"] < 480 else ("right" if n["x"] > 960 else "center")
    return f"{vert}-{horiz}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("boards", nargs="*", help="board names; default = all mapped")
    ap.add_argument("--json", help="write full findings to this path")
    ap.add_argument("--max-deltas", type=int, default=6, help="style deltas printed per element")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    targets = args.boards or list(ROUTES)
    unknown = [b for b in targets if b not in ROUTES]
    if unknown:
        manual = [b for b in unknown if b in MANUAL_ONLY or b.startswith("overlay-")]
        if manual:
            print(f"manual-only (needs UI interaction to reach): {', '.join(manual)}")
        rest = [b for b in unknown if b not in manual]
        if rest:
            print(f"unmapped: {', '.join(rest)}")
        targets = [b for b in targets if b in ROUTES]

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # dev-login once; the session persists across navigations in this context
        try:
            page.goto(f"{APP}/login", wait_until="networkidle", timeout=20000)
            btn = page.get_by_text(re.compile(r"^Dev login$", re.I))
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(2500)
                print(f"auth: {'ok' if '/login' not in page.url else 'FAILED — protected pages will redirect'}")
        except Exception as e:
            print(f"auth: skipped ({e})")

        for b in targets:
            route, needs_auth = ROUTES[b]
            print(f"  diffing {b} -> {route}", flush=True)
            results.append(diff_board(page, b, route, needs_auth))

        browser.close()

    print("\n" + "=" * 70)
    for r in results:
        if r["error"]:
            print(f"\n## {r['board']}  ERROR: {r['error']}")
            continue
        n_missing = len(r["missing_text"])
        n_icons = len(r.get("missing_icons", []))
        n_delta = len(r["style_deltas"])
        if not n_missing and not n_icons and not n_delta:
            print(f"\n## {r['board']}  — clean")
            continue
        print(f"\n## {r['board']}  ({n_icons} controls missing, {n_delta} elements differ, {n_missing} text missing)")
        # Controls first — a missing control is a missing feature, not a nuance.
        for m in r.get("missing_icons", [])[:14]:
            print(f"   NO CONTROL  {m['where']:14} {m['size']:>9}  <{m['tag'].lower()}>")
        if n_icons > 14:
            print(f"   ... and {n_icons - 14} more controls")
        for m in r["missing_text"][:12]:
            print(f"   MISSING  <{m['tag'].lower()}> {m['text']}")
        if n_missing > 12:
            print(f"   ... and {n_missing - 12} more")
        for d in r["style_deltas"][:12]:
            print(f"   DIFF     <{d['tag'].lower()}> {d['text']}")
            for x in d["deltas"][:args.max_deltas]:
                print(f"              {x['prop']}: mock={x['mock']}  app={x['app']}")
        if n_delta > 12:
            print(f"   ... and {n_delta - 12} more elements")

    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nfull findings -> {args.json}")

    print(f"\nmanual-only boards (UI interaction required): {', '.join(sorted(MANUAL_ONLY))}")
    print("overlay-* boards are also manual-only.")


if __name__ == "__main__":
    sys.exit(main())
