#!/usr/bin/env python3
"""
gen-design-preview.py — builds docs/design-preview/ page-mock bundle for the
Claude Design (claude.ai/design) sync (design initiative B2, 2026-08-15).

Each output HTML is a self-contained preview card:
  - first line: <!-- @dsCard group="..." --> marker (Design System pane index)
  - real token values inlined from frontend/src/tokens.css (4 themes)
  - a mini theme switcher (data-theme on <html>)
  - mobile-width (390px) centered frame per the mobile-first direction

Re-run after tokens.css changes: python tools/gen-design-preview.py
"""
import re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKENS = (ROOT / "frontend/src/tokens.css").read_text(encoding="utf-8")
OUT = ROOT / "docs/design-preview"
OUT.mkdir(parents=True, exist_ok=True)

BASE_CSS = f"""
{TOKENS}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ background: var(--color-bg); color: var(--color-text);
       font-family: var(--font-family); min-height: 100vh; }}
.canvas {{ display: flex; flex-direction: column; align-items: center;
           gap: 16px; padding: 24px 12px 48px; }}
.frame {{ width: 390px; max-width: 100%; background: var(--color-bg);
          border: 1px solid var(--color-border-soft); border-radius: 24px;
          overflow: hidden; position: relative; }}
.wide-frame {{ width: 960px; max-width: 100%; background: var(--color-bg);
          border: 1px solid var(--color-border-soft); border-radius: 16px;
          overflow: hidden; }}
.switcher {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }}
.switcher button {{ padding: 6px 14px; border-radius: 999px; cursor: pointer;
  border: 1px solid var(--color-border-soft); background: var(--color-surface);
  color: var(--color-text); font-family: inherit; font-size: 12px; font-weight: 600; }}
.note {{ max-width: 640px; font-size: 12px; line-height: 1.6;
         color: var(--color-text-muted); background: var(--color-surface);
         border: 1px solid var(--color-border); border-radius: 12px; padding: 12px 16px; }}
.tabbar {{ position: absolute; bottom: 0; left: 0; right: 0; height: 64px;
  background: var(--color-nav-bg); border-top: 1px solid var(--color-border);
  display: flex; align-items: center; justify-content: space-around;
  font-size: 11px; color: var(--color-nav-inactive); }}
.tabbar .on {{ color: var(--accent-1); font-weight: 600; }}
.btn-primary {{ background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  color: #fff; border: 0; border-radius: var(--radius-md); padding: 14px 16px;
  font-weight: 600; min-height: 44px; font-family: inherit; width: 100%; }}
.btn-secondary {{ background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  padding: 14px 16px; font-weight: 600; min-height: 44px; font-family: inherit; width: 100%; }}
.ink-btn {{ background: var(--color-text); color: var(--color-bg); border: 0;
  border-radius: var(--radius-md); padding: 14px 16px; font-weight: 600;
  min-height: 46px; font-family: inherit; width: 100%; }}
.ink-outline {{ background: transparent; color: var(--color-text);
  border: 1px solid var(--color-text); border-radius: var(--radius-md);
  padding: 14px 16px; font-weight: 600; min-height: 44px; font-family: inherit; width: 100%; }}
.paper {{ background: var(--color-surface); color: var(--color-text);
  border: 1px solid var(--color-border-soft); border-radius: 20px;
  padding: 26px 24px; box-shadow: 0 1px 0 rgba(0,0,0,0.05) inset,
  0 12px 28px rgba(0,0,0,0.18), 0 24px 56px rgba(0,0,0,0.18);
  display: flex; flex-direction: column; gap: 16px; }}
.wordmark {{ font-size: 24px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; }}
.mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; font-weight: 500; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--color-text-muted); }}
.pill {{ display: inline-flex; align-items: center; gap: 7px; padding: 10px 14px;
  border-radius: 999px; background: var(--color-surface-2);
  border: 1px solid var(--color-border-soft); color: var(--color-text-2);
  font-size: 13px; font-weight: 600; }}
"""

SWITCHER_JS = """
<div class="switcher" id="sw"></div>
<script>
const themes = [["github-light","GitHub Light"],["ayu-light","Ayu Light"],["github-dark","GitHub Dark"],["synthwave-84","SynthWave '84"]];
const sw = document.getElementById('sw');
themes.forEach(([id, label]) => { const b = document.createElement('button');
  b.textContent = label; b.onclick = () => document.documentElement.setAttribute('data-theme', id);
  sw.appendChild(b); });
</script>
"""

def page(fname, group, title, body, note=""):
    html = f"""<!-- @dsCard group="{group}" -->
<!doctype html><html data-theme="github-light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{BASE_CSS}</style></head>
<body><div class="canvas">
<h3 style="margin:0;font-size:14px;letter-spacing:0.04em;text-transform:uppercase;color:var(--color-text-muted)">{title}</h3>
{SWITCHER_JS}
{f'<div class="note">{note}</div>' if note else ''}
{body}
</div></body></html>"""
    (OUT / fname).parent.mkdir(parents=True, exist_ok=True)
    (OUT / fname).write_text(html, encoding="utf-8")
    print("wrote", fname)

# ── 0. Brief — the user's working notes ─────────────────────────────────────
page("brief.html", "Brief", "Working Brief (2026-08-15)", """
<div class="note" style="max-width:520px;font-size:13px;color:var(--color-text)">
<b>이번 디자인 세션의 목표 (user notes)</b>
<ol style="line-height:1.9;padding-left:18px;margin:8px 0 0">
<li>메인 페이지들 전체를 깔아놓고 layout / font 애매한 부분 정리</li>
<li>Persona Report 데스크탑 구성 문제 — 여백 없음 + 가로로 김. 모바일 연동성 고려</li>
<li><b>모바일 중심 가운데 기준 레이아웃</b>으로 방향 전환 검토</li>
<li>로그인 페이지 중점 수정</li>
<li>화면 이동 시나리오 점검 (Flow 카드 참조)</li>
</ol>
<p style="color:var(--color-text-muted);margin:10px 0 0">모든 카드는 실제 tokens.css 값을 사용. 테마 버튼으로 4테마 확인.
여기서 확정된 방향은 컴포넌트 단위로 코드에 반영(승인분만, 한 번에 하나).</p>
</div>""")

# ── 1. Foundations ──────────────────────────────────────────────────────────
sw_colors = "".join(
    f'<div style="display:flex;flex-direction:column;gap:4px;align-items:center">'
    f'<div style="width:56px;height:40px;border-radius:8px;background:var({v});border:1px solid var(--color-border)"></div>'
    f'<span style="font-size:9px;color:var(--color-text-muted)">{v}</span></div>'
    for v in ["--color-bg","--color-surface","--color-surface-2","--color-surface-3",
              "--color-text","--color-text-muted","--color-text-dim",
              "--accent-1","--accent-2","--accent-3","--color-destructive"])
page("foundations.html", "Foundations", "Tokens — Colors · Type · Shape", f"""
<div style="display:flex;gap:10px;flex-wrap:wrap;max-width:640px;justify-content:center">{sw_colors}</div>
<div style="max-width:640px;width:100%;display:flex;flex-direction:column;gap:6px;margin-top:8px">
<div style="font-size:48px;font-weight:700">H1 48 · 취향을 아카이브</div>
<div style="font-size:30px;font-weight:600">H2 30 · Heading Two</div>
<div style="font-size:18px;font-weight:400">Body 18 · 건축 카드를 스와이프해 취향에 반응하세요.</div>
<div style="font-size:14px;font-weight:500;color:var(--color-text-muted)">Caption 14 · weight cap 700, single family</div>
<div style="display:flex;gap:12px;margin-top:10px;align-items:center">
<div style="width:64px;height:40px;background:var(--color-surface-2);border-radius:8px;display:grid;place-items:center;font-size:10px">sm 8</div>
<div style="width:64px;height:40px;background:var(--color-surface-2);border-radius:12px;display:grid;place-items:center;font-size:10px">md 12</div>
<div style="width:64px;height:40px;background:var(--color-surface-2);border-radius:20px;display:grid;place-items:center;font-size:10px">lg 20</div>
<div style="width:64px;height:40px;background:var(--color-surface-2);border-radius:24px;display:grid;place-items:center;font-size:10px">xl 24</div>
<div style="width:64px;height:40px;background:var(--color-surface-2);border-radius:999px;display:grid;place-items:center;font-size:10px">pill</div>
</div></div>""",
note="motion: fast 180ms · normal 220ms · slow 400ms · flip 500ms / ease cubic-bezier(.4,0,.2,1)")

# ── 2. Login (중점 수정 대상) ────────────────────────────────────────────────
page("pages/login.html", "Pages", "Login — paper card deck (중점 수정)", """
<div class="frame" style="height:760px;display:grid;place-items:center;padding:16px">
 <div style="width:100%;max-width:340px;position:relative">
  <div class="paper" style="position:absolute;inset:0;transform:translateY(10px) scale(0.96);opacity:.55"></div>
  <div class="paper" style="position:relative;height:520px">
   <div style="display:flex;justify-content:space-between;align-items:center">
     <span class="wordmark">ARCHIBE</span>
     <span class="mono">한국어 · EN</span></div>
   <h2 style="margin:0;font-size:26px;font-weight:700;line-height:1.16">처음 방문하셨나요?</h2>
   <p style="margin:0;font-size:15px;color:var(--color-text-2)">왼쪽 또는 오른쪽으로 스와이프해보세요._</p>
   <div style="display:flex;align-items:center;justify-content:center;gap:16px;flex:1">
     <span style="font-size:22px;color:var(--color-text-dim)">&#8592;</span>
     <div style="width:84px;height:112px;border-radius:10px;background:var(--color-surface-2);border:1px solid var(--color-border-soft);box-shadow:0 6px 18px rgba(0,0,0,0.18);padding:10px">
       <span style="font-size:7px;font-weight:700;letter-spacing:0.28em;color:var(--color-text-muted)">ARCHIBE</span></div>
     <span style="font-size:22px;color:var(--color-text)">&#8594;</span></div>
   <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
     <button class="ink-outline">← 기존 계정</button>
     <button class="ink-btn">새 프로필 →</button></div>
   <p style="margin:0;font-size:11px;line-height:1.55;color:var(--color-text-dim)">건축 카드를 스와이프해 취향에 반응하세요 · 10~15장이면 취향 프로필이 완성돼요.</p>
  </div>
 </div>
</div>""",
note="현 상태 충실 재현. 유저 노트: 이 페이지 중점 수정. 명함/paper 컨셉은 유지 전제 — 구성·타이포·스텝 흐름을 여기서 실험.")

# ── 3. Discovery ────────────────────────────────────────────────────────────
page("pages/discovery.html", "Pages", "Discovery — swipe deck", """
<div class="frame" style="height:760px">
 <div style="text-align:center;padding:14px;font-weight:700">Disc<span style="color:var(--accent-1)">overy</span></div>
 <div style="display:grid;place-items:center;padding:0 20px">
  <div style="width:100%;max-width:330px;position:relative;height:540px">
   <div style="position:absolute;inset:0;border-radius:20px;background:var(--color-surface);border:1px solid var(--color-border-soft);transform:scale(.90) translateY(20px);transform-origin:bottom center"></div>
   <div style="position:absolute;inset:0;border-radius:20px;background:var(--color-surface-2);border:1px solid var(--color-border-soft);transform:scale(.95) translateY(10px);transform-origin:bottom center"></div>
   <div style="position:absolute;inset:0;border-radius:20px;overflow:hidden;box-shadow:0 25px 50px rgba(0,0,0,.5);background:linear-gradient(160deg,#6b7f8a 0%,#3c4a52 60%,#1c2328 100%)">
    <div style="position:absolute;inset:0;background:linear-gradient(180deg,transparent 30%,rgba(0,0,0,.82))"></div>
    <div style="position:absolute;left:0;right:0;bottom:0;padding:18px;color:#fff">
      <div style="font-size:22px;font-weight:700">The Krantz-fontaine House</div>
      <div style="font-size:13px;font-style:italic;color:rgba(255,255,255,.6)">Atelier d'architecture — Belgium</div>
      <div style="height:1px;background:rgba(255,255,255,.15);margin:10px 0"></div>
      <div style="display:flex;justify-content:space-between">
        <div><div style="font-size:10px;letter-spacing:.06em;color:rgba(255,255,255,.5)">YEAR</div><div style="font-size:13px;font-weight:600">2006</div></div>
        <div><div style="font-size:10px;letter-spacing:.06em;color:rgba(255,255,255,.5)">LOCATION</div><div style="font-size:13px;font-weight:600">Uccle</div></div>
        <div><div style="font-size:10px;letter-spacing:.06em;color:rgba(255,255,255,.5)">PROGRAM</div><div style="font-size:13px;font-weight:600">Housing</div></div>
      </div></div>
   </div>
  </div>
  <div style="font-size:11px;color:var(--color-text-dim);margin-top:10px">← skip · tap card · save → · arrow keys supported</div>
 </div>
 <div class="tabbar"><span class="on">디스커버리</span><span>취향</span><span>프로필</span></div>
</div>""",
note="카드 §8.6 언어(하단 블랙 그라디언트 + 3열 info). 정적 사다리 + 그림자 홀더는 UX-14에서 확정.")

# ── 4. Persona Report (문제 재현) ────────────────────────────────────────────
page("pages/persona-report.html", "Pages", "Persona Report — desktop 문제 + mobile 제안", """
<div class="wide-frame" style="padding:8px 10px">
 <div style="font-size:11px;color:var(--color-destructive);font-weight:600;margin-bottom:6px">현 데스크탑: 여백 없음 · 가로로 김 (문제 재현)</div>
 <div style="display:flex;gap:8px">
  <div style="flex:1.2;background:var(--color-surface);border-radius:10px;padding:8px">
    <div style="font-size:12px;font-weight:700">Taste Radar</div>
    <svg viewBox="0 0 100 100" style="width:100%;height:120px">
      <polygon points="50,8 88,35 76,85 24,85 12,35" fill="none" stroke="var(--color-border)"/>
      <polygon points="50,20 76,40 66,74 34,74 26,42" style="fill:color-mix(in srgb,var(--accent-1) 20%,transparent);stroke:var(--accent-1)"/></svg></div>
  <div style="flex:2;background:var(--color-surface);border-radius:10px;padding:8px;font-size:11px;line-height:1.4">당신은 절제된 재료와 빛의 리듬을 선호하는 타입… (본문이 화면 전체 폭으로 늘어져 행 길이가 과도)</div>
  <div style="flex:1;background:var(--color-surface);border-radius:10px;padding:8px;font-size:11px">
    <span class="pill" style="font-size:10px;padding:4px 8px">Museum</span> <span class="pill" style="font-size:10px;padding:4px 8px">Housing</span></div>
 </div>
</div>
<div class="frame" style="padding:20px;display:flex;flex-direction:column;gap:14px">
 <div style="font-size:11px;color:var(--accent-1);font-weight:600">제안: 모바일 중심 가운데 1열 (max-width 480 중앙 정렬, 데스크탑도 동일 기둥)</div>
 <div style="background:var(--color-surface);border-radius:16px;padding:16px">
   <div style="font-size:13px;font-weight:700;margin-bottom:8px">Taste Radar</div>
   <svg viewBox="0 0 100 100" style="width:70%;display:block;margin:0 auto">
     <polygon points="50,8 88,35 76,85 24,85 12,35" fill="none" stroke="var(--color-border)"/>
     <polygon points="50,20 76,40 66,74 34,74 26,42" style="fill:color-mix(in srgb,var(--accent-1) 20%,transparent);stroke:var(--accent-1)"/></svg></div>
 <div style="background:var(--color-surface);border-radius:16px;padding:16px;font-size:14px;line-height:1.65">당신은 절제된 재료와 빛의 리듬을 선호하는 타입이에요. 좁은 행 폭이 읽기 편함.</div>
 <div><span class="pill">Museum</span> <span class="pill">Housing</span> <span class="pill">Chapel</span></div>
 <button class="btn-primary">이미지 카드로 저장</button>
</div>""",
note="위 = 현재 데스크탑 문제 재현, 아래 = 모바일 중심 가운데-기둥 제안. 여기서 방향 확정 후 코드 반영.")

# ── 5. Taste swipe ──────────────────────────────────────────────────────────
page("pages/taste-swipe.html", "Pages", "Taste — session swipe", """
<div class="frame" style="height:700px;padding:14px">
 <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:700">
   <span>Taste found</span><span style="color:var(--color-text-muted)">100%</span></div>
 <div style="height:4px;border-radius:2px;background:var(--color-progress-track);margin:8px 0">
   <div style="height:100%;width:100%;border-radius:2px;background:var(--accent-1)"></div></div>
 <button class="btn-primary" style="margin-bottom:12px">Finish &amp; View Report →</button>
 <div class="paper" style="height:500px;justify-content:space-between">
   <div style="display:flex;justify-content:space-between;align-items:center">
     <span class="wordmark" style="font-size:12px;letter-spacing:.18em">ARCHIBE</span>
     <span class="mono">TASTE FOUND</span></div>
   <div style="text-align:center">
     <div style="font-size:22px;font-weight:700">취향이 충분히 모였어요!</div>
     <div style="font-size:13px;color:var(--color-text-muted);margin-top:8px">지금 결과를 확인하거나 계속 탐색할 수 있어요</div></div>
   <div class="mono" style="text-align:center">← 계속 탐색 · 결과 보기 →</div>
 </div>
</div>""",
note="수렴 액션 카드 = paper 언어(FLOW-2 확정). 진행바/CTA = accent 토큰.")

# ── 6. Profile ──────────────────────────────────────────────────────────────
page("pages/profile.html", "Pages", "User Profile", """
<div class="frame" style="height:760px">
 <div style="padding:12px 16px;border-bottom:1px solid var(--color-border-soft);display:flex;justify-content:space-between;align-items:center">
   <div><div style="font-size:17px;font-weight:700">Profile</div>
        <div style="font-size:12px;color:var(--color-text-muted)">@archibe_user</div></div>
   <div style="display:flex;gap:8px;color:var(--color-text-dim);font-size:16px">🔔 ⤴ ⚙</div></div>
 <div style="display:flex;flex-direction:column;align-items:center;padding:22px 16px 0">
   <div style="position:relative">
     <div style="position:absolute;inset:-6px;border-radius:50%;background:linear-gradient(135deg,var(--accent-1),var(--accent-2));opacity:.55;filter:blur(12px)"></div>
     <div style="position:relative;width:108px;height:108px;border-radius:50%;background:var(--color-surface);border:2px solid var(--color-border-soft)"></div></div>
   <div style="font-size:24px;font-weight:700;margin-top:12px">김아키</div>
   <div class="mono" style="margin-top:2px">@archibe_user</div>
   <div style="font-size:13px;color:var(--color-text-muted);margin-top:2px">건축학도 · 홍익대</div>
   <div style="display:flex;gap:0;margin-top:14px;align-items:center">
     <div style="padding:6px 14px;text-align:center"><div style="font-size:18px;font-weight:700">12</div><div style="font-size:12px;color:var(--color-text-dim)">Boards</div></div>
     <div style="width:1px;height:28px;background:var(--color-border)"></div>
     <div style="padding:6px 14px;text-align:center"><div style="font-size:18px;font-weight:700">5</div><div style="font-size:12px;color:var(--color-text-dim)">Studios</div></div>
     <div style="width:1px;height:28px;background:var(--color-border)"></div>
     <div style="padding:6px 14px;text-align:center"><div style="font-size:18px;font-weight:700">87</div><div style="font-size:12px;color:var(--color-text-dim)">Liked</div></div></div>
   <div style="display:flex;gap:10px;margin-top:10px"><span class="pill">@instagram</span><span class="pill">email</span></div>
   <div style="display:flex;gap:22px;margin-top:18px;width:100%;justify-content:center;border-bottom:1px solid var(--color-border)">
     <div style="padding:10px 4px;font-weight:700;border-bottom:2px solid var(--color-text)">Boards</div>
     <div style="padding:10px 4px;color:var(--color-text-muted)">Studios</div>
     <div style="padding:10px 4px;color:var(--color-text-muted)">Liked</div>
     <div style="padding:10px 4px;color:var(--color-text-muted)">Created</div></div>
   <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px 0;width:100%">
     <div style="height:110px;border-radius:16px;background:var(--color-surface-2)"></div>
     <div style="height:110px;border-radius:16px;background:var(--color-surface-2)"></div></div>
 </div>
 <div class="tabbar"><span>디스커버리</span><span>취향</span><span class="on">프로필</span></div>
</div>""",
note="B1 확정 상태 재현(accent halo, ink underline 탭, 링크필). 인스타식 구성은 phase13 결정.")

# ── 7. Flow map ─────────────────────────────────────────────────────────────
page("flow.html", "Flow", "화면 이동 시나리오", """
<div class="note" style="max-width:680px;font-size:13px;color:var(--color-text)">
<b>신규 유저</b><br>
/login (paper deck: choice→credentials→profile→consent) → <b>Discovery</b> [+튜토리얼 1회, 신규 가입만]
→ 10 likes → TriggerCard(paper) → ←계속 / →<b>Taste</b>(/swipe)
→ 수렴 → ActionCard(paper) → →<b>Results</b>(/result) → Persona Report → 보드 저장<br><br>
<b>기존 유저</b><br>
/login(returning) → Discovery ↔ 취향(Taste) ↔ 프로필 [하단 탭 3개]<br>
프로필 → 보드 상세(/board/:id) → 리포트(/board/:id/report)<br>
카드 → 건물 상세(/buildings/:id) · 건축가(/architects/:id) · 사무소(/office/:id)<br><br>
<b>점검 포인트 (user)</b>: 탭 3개 체계에서 Results/Report의 귀속이 애매 — 취향 탭과 프로필 탭 사이 어디로 돌아가는지;
업로드(/upload)와 설정(/settings)의 진입 동선; 게스트→가입 전환 시점.
</div>""")

# ── 8. Components 압축 카드 ─────────────────────────────────────────────────
page("components.html", "Components", "Core components", """
<div style="max-width:420px;width:100%;display:flex;flex-direction:column;gap:12px">
 <button class="btn-primary">Primary CTA (§8.1)</button>
 <button class="btn-secondary">Secondary (§8.2)</button>
 <button class="ink-btn">Ink Primary (paper 언어)</button>
 <button class="ink-outline">Ink Secondary</button>
 <div style="display:flex;align-items:center;background:color-mix(in srgb,var(--color-surface) 72%,transparent);border:1px solid var(--color-border);border-radius:999px;padding:12px 18px;backdrop-filter:blur(12px)">
   <span style="color:var(--color-text-dim);font-size:14px">글래스 입력 — 3-state focus (§8.5)</span></div>
 <div style="display:flex;gap:10px"><span class="pill">link pill</span>
   <span class="pill" style="border-color:var(--accent-1);color:var(--accent-1)">hover state</span></div>
 <div style="align-self:center;background:color-mix(in srgb,var(--color-surface) 72%,transparent);border:1px solid var(--color-border);border-radius:999px;padding:10px 16px;backdrop-filter:blur(12px);font-size:13px">토스트 — bottom-center · 3s (§8.11)</div>
</div>""",
note="여기 확정값이 tokens.css/DESIGN.md의 소스. 변경 확정 시 §8 스펙 + 코드 동기화.")

print("done — bundle at", OUT)
