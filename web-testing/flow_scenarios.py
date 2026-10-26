"""
flow_scenarios.py -- pure data for flow_capture.py (no imports, no logic).

STAGES    ordered list of {key, title_ko, desc_ko}; drives the manifest + gallery.
SCENARIOS ordered list of dicts. They run IN ORDER and may depend on state left
          by earlier ones (e.g. a swipe session, then its result page).

Scenario keys
  id          2-digit sequential string ("01", "02", ...)
  slug        file-name slug -> img/<id>-<slug>.jpg
  stage       one of STAGES[*].key
  title_ko    short screen name
  caption_ko  one or two plain Korean sentences (haeyo-che): what we did / what is visible
  route       path opened BEFORE the actions; None = stay on the current page
  actions     list of small dicts (see below)
  account     "main" (dev-login user, default) | "fresh" (throwaway unverified user) | "none" (logged out)
  theme       "light" (default) | "dark"
  lang        "ko" (default) | "en"
  debug       True (default) = also capture the debug-overlay shot (<id>-<slug>.debug.jpg)
  full_page   optional, True = full-page screenshot
  requires    optional selector; if absent after the actions' settle, scenario is recorded as skipped

Action vocabulary (everything is optional-timeout, capped inside the runner)
  {"goto": "/path"}                path may use {session_id} / {board_id} placeholders
  {"click": "<css | role= | text= | plain Korean text>"}   (+ "force": true, "optional": true)
  {"fill": ["<selector>", "value"]}
  {"wait": "<selector or text>" | <ms int>}                 (+ "timeout": ms)
  {"scroll": <px>}                 scrolls the main scroll container (and window)
  {"swipe": "left"|"right"}        mouse drag on the swipe card (+ "n": count)
  {"hold": "left"|"right"}         drag half way and keep the button down (stamp preview)
  {"release": true}                release a previous hold
  {"key": "Escape"}
  {"remember": ["board_id", "<url regex with one group>"]}   store a value from the current URL
  {"mock_me": {...}}               override fields of GET /auth/me/ (for screens normal accounts skip)
  {"unmock_me": true}

Placeholders
  Selector shortcuts used below:
    PERSON = first people-card that is not the dev user
"""

# A people-card (flip card) that is not the dev-login user ("TestUser").
PERSON_CARD = 'article:has([aria-label$="프로필 보기"]):not(:has([aria-label^="TestUser"]))'

STAGES = [
    {"key": "login", "title_ko": "로그인·가입",
     "desc_ko": "로그아웃 상태에서 처음 만나는 화면들이에요. Google·카카오 로그인은 자동화할 수 없어 화면만 담았어요."},
    {"key": "taste-start", "title_ko": "취향 시작",
     "desc_ko": "한 문장을 입력하면 태그를 읽고 건물 카드 3장을 보여줘요. 이 카드로 스와이프를 시작해요."},
    {"key": "swipe", "title_ko": "스와이프·갤러리",
     "desc_ko": "카드를 넘기며 취향을 알려주는 화면이에요. 카드 상세와 사진 갤러리도 열어봤어요."},
    {"key": "result", "title_ko": "결과·리포트·보드",
     "desc_ko": "스와이프가 끝나면 취향 리포트와 추천 건물이 나와요. 보드와 보드 리포트도 확인했어요."},
    {"key": "discovery", "title_ko": "탐색",
     "desc_ko": "앱을 열면 가장 먼저 보이는 탐색 탭이에요."},
    {"key": "search", "title_ko": "검색",
     "desc_ko": "문장으로 건물을 찾는 AI 검색이에요. 결과가 나올 때까지 시간이 걸릴 수 있어요."},
    {"key": "social", "title_ko": "소셜",
     "desc_ko": "취향이 비슷한 사람, 다른 사용자의 프로필, 건축가와 건물 상세 화면이에요."},
    {"key": "profile", "title_ko": "프로필·설정",
     "desc_ko": "내 프로필과 설정, 알림, 화면 설정 같은 계정 관련 화면이에요."},
    {"key": "competitions", "title_ko": "공모전",
     "desc_ko": "소셜 탭 안의 공모전 목록과 상세 화면이에요."},
    {"key": "variants", "title_ko": "경우의 수",
     "desc_ko": "다크 테마, 영어 화면, 빈 상태, 없는 주소, 로그아웃 상태 접근처럼 달라지는 경우를 모았어요."},
]

SCENARIOS = [
    # ---------------------------------------------------------------- 1 login
    dict(id="01", slug="login", stage="login", title_ko="로그인",
         caption_ko="로그아웃 상태로 앱을 열었어요. Google·카카오로 계속하는 버튼이 보여요.",
         route="/login", account="none", actions=[], debug=False),
    dict(id="02", slug="login-guard", stage="login", title_ko="보호된 화면 접근",
         caption_ko="로그인하지 않고 ‘프로필’ 주소를 열었더니 로그인 화면으로 돌려보냈어요.",
         route="/user/me", account="none", actions=[], debug=False),
    dict(id="03", slug="kakao-callback", stage="login", title_ko="카카오 로그인 실패",
         caption_ko="카카오 인증 코드 없이 콜백 주소를 열었어요. 실패 안내 화면이 보여요.",
         route="/auth/kakao/callback", account="none", actions=[{"wait": 1500}], debug=False),
    dict(id="04", slug="onboarding", stage="login", title_ko="프로필 만들기",
         caption_ko="소셜 로그인 직후 보이는 프로필 만들기 화면이에요. ID와 소속, 목적, 동의를 받아요.",
         route="/onboarding", actions=[{"mock_me": {"onboarding_required": True}}, {"goto": "/onboarding"},
                                       {"wait": "text=프로필 만들기"}], debug=False),
    dict(id="05", slug="onboarding-filled", stage="login", title_ko="프로필 만들기 입력",
         caption_ko="목적을 고르고 동의에 체크했어요. ‘시작하기’ 버튼이 켜졌지만 누르지는 않았어요.",
         route=None, debug=False,
         actions=[{"click": "role=radio >> nth=0"}, {"click": "input[type=checkbox]"},
                  {"scroll": 400}, {"wait": 400}]),

    # ------------------------------------------------------------ 2 taste-start
    dict(id="06", slug="taste-empty", stage="taste-start", title_ko="취향 시작 첫 화면",
         caption_ko="검색 탭을 열었어요. 마음에 드는 건물을 한 문장으로 적어달라고 안내해요.",
         route="/search", actions=[{"unmock_me": True}, {"wait": "textarea"}]),
    dict(id="07", slug="taste-typing", stage="taste-start", title_ko="문장 입력",
         caption_ko="‘노출 콘크리트 미술관’이라고 입력했어요. 보내기 버튼이 활성화됐어요.",
         route=None, actions=[{"fill": ["textarea", "노출 콘크리트 미술관"]}, {"wait": 300}]),
    dict(id="08", slug="taste-cards", stage="taste-start", title_ko="태그와 카드 3장",
         caption_ko="‘보내기’를 눌렀어요. 읽어낸 태그와 어울리는 건물 카드가 쌓여서 보여요.",
         route=None,
         actions=[{"click": 'button[aria-label="보내기"]'},
                  {"wait": "text=이 세 장으로 스와이프 시작", "timeout": 60000}, {"wait": 800}]),
    dict(id="09", slug="taste-cta", stage="taste-start", title_ko="스와이프 시작 버튼",
         caption_ko="아래로 스크롤해서 ‘이 세 장으로 스와이프 시작’ 버튼과 ‘다시 찾기’를 확인했어요.",
         route=None, actions=[{"scroll": 500}, {"wait": 400}]),
    dict(id="10", slug="taste-report", stage="taste-start", title_ko="카드 신고",
         caption_ko="카드 위의 ‘!’ 버튼을 눌렀어요. 무엇이 잘못됐는지 고르는 창이 열려요.",
         route=None, actions=[{"scroll": -800}, {"scroll": 220}, {"click": 'button[aria-label="신고하기"]', "force": True},
                              {"wait": 700}]),
    dict(id="11", slug="taste-query-report", stage="taste-start", title_ko="태그 인식 신고",
         caption_ko="창을 닫고 ‘태그가 잘못 인식됐나요?’를 눌렀어요. 틀린 태그를 알려줄 수 있어요.",
         route=None, actions=[{"click": "text=닫기", "optional": True}, {"click": "text=태그가 잘못 인식됐나요?"},
                              {"wait": 700}]),
    dict(id="12", slug="taste-start-swiping", stage="taste-start", title_ko="스와이프 시작",
         caption_ko="창을 닫고 ‘이 세 장으로 스와이프 시작’을 눌렀어요. 첫 카드가 나타났어요.",
         route=None, actions=[{"click": "text=닫기", "optional": True}, {"scroll": 800},
                              {"click": "text=이 세 장으로 스와이프 시작"},
                              {"wait_url": "/swipe"}, {"wait": "text=탭해서 자세히 보기", "timeout": 30000}]),

    # ------------------------------------------------------------------ 3 swipe
    dict(id="13", slug="swipe-detail", stage="swipe", title_ko="카드 상세",
         caption_ko="카드를 한 번 눌렀어요. 유형·국가·도시·재료 같은 정보가 펼쳐져요.",
         route=None, actions=[{"click": "xy=195,420"}, {"wait": 800}]),
    dict(id="14", slug="swipe-gallery", stage="swipe", title_ko="사진 갤러리",
         caption_ko="‘갤러리 보기’를 눌렀어요. 건물 사진을 위아래로 넘겨볼 수 있어요.",
         route=None, actions=[{"click": "text=갤러리 보기 >> visible=true >> nth=0", "force": True}, {"wait": 3500}]),
    dict(id="15", slug="swipe-gallery-scrolled", stage="swipe", title_ko="갤러리 다음 사진",
         caption_ko="갤러리를 위로 넘겨 다음 사진을 봤어요.",
         route=None, actions=[{"swipe_gallery": "up"}, {"wait": 1500}]),
    dict(id="16", slug="swipe-hold-like", stage="swipe", title_ko="오른쪽으로 끄는 중",
         caption_ko="갤러리를 닫고 카드를 오른쪽으로 끌고 있어요. 좋아요 표시가 떠올라요.",
         route=None, actions=[{"click": "text=✕", "optional": True, "force": True}, {"wait": 500},
                              {"hold": "right"}, {"wait": 300}]),
    dict(id="17", slug="swipe-liked", stage="swipe", title_ko="좋아요 후 다음 카드",
         caption_ko="손을 놓았더니 카드가 오른쪽으로 날아가고 다음 카드가 나왔어요. 진행률이 올랐어요.",
         route=None, actions=[{"release": True}, {"wait": 1500}]),
    dict(id="18", slug="swipe-dislike-confirm", stage="swipe", title_ko="싫어요 확인",
         caption_ko="카드를 왼쪽으로 넘겼어요. ‘이 건물을 보지 않을까요?’ 하고 한 번 더 물어봐요.",
         route=None, actions=[{"swipe": "left"}, {"wait": "text=이 건물을 보지 않을까요?"}, {"wait": 400}]),
    dict(id="19", slug="swipe-dislike-done", stage="swipe", title_ko="건너뛰기",
         caption_ko="‘건너뛰기’를 눌렀어요. 그 건물은 빠지고 다음 카드가 나왔어요.",
         route=None, actions=[{"click": "text=건너뛰기"}, {"wait": 1500}]),
    dict(id="20", slug="swipe-progress", stage="swipe", title_ko="진행률",
         caption_ko="좋아요를 몇 번 더 눌렀어요. 위쪽 진행률이 올라가고 단계 이름이 바뀌었어요.",
         route=None, actions=[{"swipe": "right", "n": 5}, {"wait": 1200}]),
    dict(id="21", slug="swipe-exit", stage="swipe", title_ko="세션 나가기",
         caption_ko="왼쪽 위 ‘나가기’ 버튼을 눌렀어요. 새 프로젝트로 시작할지 홈으로 갈지 물어봐요.",
         route=None, actions=[{"click": 'button[aria-label="Exit session"]'}, {"wait": 800}]),

    # ----------------------------------------------------------------- 4 result
    dict(id="22", slug="result-top", stage="result", title_ko="결과 첫 카드",
         caption_ko="방금 스와이프한 세션의 결과예요. 카드 3장 중 첫 장에 페르소나 리포트가 있어요.",
         route=None, actions=[{"goto": "/result/{session_id}"}, {"wait": "text=페르소나 리포트", "timeout": 40000},
                              {"wait": 1500}]),
    dict(id="23", slug="result-taste", stage="result", title_ko="취향 패턴 카드",
         caption_ko="두 번째 카드로 넘겼어요. 왜 이런 취향인지와 취향 스펙트럼이 나와요.",
         route=None, actions=[{"click": 'button[aria-label="2번째 카드로 이동"]'}, {"wait": 1200}]),
    dict(id="24", slug="result-liked", stage="result", title_ko="취향 스펙트럼",
         caption_ko="두 번째 카드를 아래로 내려 취향 스펙트럼을 끝까지 봤어요.",
         route=None, actions=[{"scroll": 700}, {"wait": 900}]),
    dict(id="25", slug="result-recs", stage="result", title_ko="마무리 카드",
         caption_ko="세 번째 카드예요. 분석이 끝났다는 안내와 저장 버튼이 있어요.",
         route=None, actions=[{"click": 'button[aria-label="3번째 카드로 이동"]'}, {"wait": 1200}]),
    dict(id="26", slug="result-save", stage="result", title_ko="보드로 저장",
         caption_ko="‘저장하고 프로필로’를 눌렀어요. 보드 이름을 정하는 창이 열려요. 저장은 하지 않았어요.",
         route=None, actions=[{"click": "text=저장하고 프로필로"}, {"wait": 900}]),
    dict(id="27", slug="board-detail", stage="result", title_ko="보드 상세",
         caption_ko="내 프로필에서 보드 하나를 열었어요. 모아둔 건물 사진이 보여요.",
         route="/user/me", actions=[{"wait": "h2 >> nth=0"}, {"click": "h2 >> nth=0"},
                                    {"wait": 1800}, {"remember": ["board_id", r"/board/([^/?]+)"]}]),
    dict(id="28", slug="board-report", stage="result", title_ko="보드 리포트",
         caption_ko="보드의 리포트 화면이에요. 보드에 담긴 건물들로 취향을 정리해줘요.",
         route=None, actions=[{"goto": "/board/{board_id}/report"}, {"wait": 2500}]),

    # ------------------------------------------------------------- 5 discovery
    dict(id="29", slug="discovery", stage="discovery", title_ko="탐색",
         caption_ko="탐색 탭이에요. 건물 사진 카드를 넘기며 마음에 드는 건물을 모아요.",
         route="/discovery", actions=[{"wait": 2500}]),
    dict(id="30", slug="discovery-gallery", stage="discovery", title_ko="탐색 갤러리",
         caption_ko="카드의 ‘갤러리 보기’를 눌러 사진을 더 봤어요.",
         route=None, actions=[{"click": "xy=195,420"}, {"wait": 800},
                              {"click": "text=갤러리 보기 >> visible=true >> nth=0", "force": True}, {"wait": 3000}]),

    # --------------------------------------------------------------- 6 search
    dict(id="31", slug="search-empty", stage="search", title_ko="검색 첫 화면",
         caption_ko="검색 탭을 새로 열었어요. 입력창이 비어 있어요.",
         route="/search", actions=[{"wait": "textarea"}]),
    dict(id="32", slug="search-result", stage="search", title_ko="AI 검색 결과",
         caption_ko="‘일본의 목조 주택’을 검색했어요. AI가 태그를 읽고 건물을 찾아 보여줘요.",
         route=None, actions=[{"fill": ["textarea", "일본의 목조 주택"]}, {"click": 'button[aria-label="보내기"]'},
                              {"wait": "text=이 세 장으로 스와이프 시작", "timeout": 60000}, {"wait": 1000}]),
    dict(id="33", slug="search-find-again", stage="search", title_ko="다시 찾기",
         caption_ko="‘다시 찾기’를 눌렀어요. 같은 문장으로 다른 건물 3장을 보여줘요.",
         route=None, actions=[{"scroll": 600}, {"click": "text=다시 찾기"},
                              {"wait": 2500}]),

    # --------------------------------------------------------------- 7 social
    dict(id="34", slug="people", stage="social", title_ko="사람 찾기",
         caption_ko="소셜 탭이에요. 취향이 비슷한 사람들이 카드로 보여요.",
         route="/people", actions=[{"wait": f'{PERSON_CARD} >> nth=0'}, {"wait": 1200}]),
    dict(id="35", slug="people-flip", stage="social", title_ko="카드 뒤집기",
         caption_ko="사람 카드를 눌렀더니 뒤집혀서 소개가 나왔어요.",
         route=None, actions=[{"click": f'{PERSON_CARD} >> nth=0'}, {"wait": 900}]),
    dict(id="36", slug="people-filter", stage="social", title_ko="취향 유형 필터",
         caption_ko="‘영감 주는 사람’으로 바꿔봤어요.",
         route=None, actions=[{"click": "text=영감 주는 사람"}, {"wait": 1800}]),
    dict(id="37", slug="user-profile", stage="social", title_ko="다른 사용자 프로필",
         caption_ko="사람 카드의 이름을 눌러 프로필을 열었어요.",
         route="/people", actions=[{"wait": f'{PERSON_CARD} >> nth=0'}, {"click": f'{PERSON_CARD} >> nth=0'},
                                   {"wait": 700}, {"click": f'{PERSON_CARD} >> nth=0 >> [aria-label$="프로필 보기"]'},
                                   {"wait": 2500}]),
    dict(id="38", slug="building-detail", stage="social", title_ko="건물 상세",
         caption_ko="보드에서 건물 하나를 열었어요. 사진과 정보가 보여요.",
         route=None, actions=[{"goto": "/board/{board_id}"}, {"wait": "div[class*=tile] >> nth=0", "timeout": 20000},
                              {"click": "div[class*=tile] >> nth=0"}, {"wait": 2500},
                              {"remember": ["building_id", r"/buildings/([^/?]+)"]}]),
    dict(id="39", slug="architect", stage="social", title_ko="건축가 프로필",
         caption_ko="건물 상세에서 건축가 이름을 눌러 건축가 페이지로 갔어요.",
         route=None, actions=[{"find_architect": True}]),

    # --------------------------------------------------------------- 8 profile
    dict(id="40", slug="profile", stage="profile", title_ko="내 프로필",
         caption_ko="프로필 탭이에요. 보드, 스튜디오, 좋아요 개수와 취향 요약이 있어요.",
         route="/user/me", actions=[{"wait": "text=보드"}, {"wait": 1200}]),
    dict(id="41", slug="profile-liked", stage="profile", title_ko="좋아요 탭",
         caption_ko="프로필의 ‘좋아요’ 탭을 눌렀어요.",
         route=None, actions=[{"click": "text=좋아요 >> nth=-1"}, {"wait": 1500}]),
    dict(id="42", slug="settings", stage="profile", title_ko="설정",
         caption_ko="설정 화면이에요. 알림함, 프로필 편집, 계정, 알림 설정, 화면 설정으로 이동해요.",
         route="/settings", actions=[{"wait": "text=계정"}]),
    dict(id="43", slug="settings-edit-profile", stage="profile", title_ko="프로필 편집",
         caption_ko="‘프로필 편집’을 열었어요. 소속과 소개, 링크를 고칠 수 있어요.",
         route="/settings/edit-profile", actions=[{"wait": 1500}]),
    dict(id="44", slug="settings-account", stage="profile", title_ko="계정",
         caption_ko="‘계정’ 화면이에요. 핸들과 비밀번호를 바꾸고 발견 피드 노출을 정해요.",
         route="/settings/account", actions=[{"wait": 1500}]),
    dict(id="45", slug="settings-notifications", stage="profile", title_ko="알림 설정",
         caption_ko="알림 종류별로 앱 내 알림을 켜고 끌 수 있어요.",
         route="/settings/notifications", actions=[{"wait": 1500}]),
    dict(id="46", slug="settings-appearance", stage="profile", title_ko="화면 설정",
         caption_ko="테마와 글꼴, 언어를 고르는 화면이에요.",
         route="/settings/appearance", actions=[{"wait": 1500}]),
    dict(id="47", slug="notifications", stage="profile", title_ko="알림함",
         caption_ko="받은 알림이 시간순으로 쌓여 있어요.",
         route="/notifications", actions=[{"wait": 1500}]),
    dict(id="49", slug="assessment", stage="profile", title_ko="취향 진단",
         caption_ko="‘다시 진단받기’로 들어가는 취향 진단이에요. 문항마다 다섯 단계로 답해요.",
         route="/assessment", actions=[{"wait": 1500}]),
    dict(id="50", slug="upload-work", stage="profile", title_ko="작품 업로드",
         caption_ko="내 건축 작품을 올리는 화면이에요.",
         route="/upload", actions=[{"wait": 1500}]),

    # ------------------------------------------------------------ 9 competitions
    dict(id="51", slug="competitions", stage="competitions", title_ko="공모전 목록",
         caption_ko="소셜 탭의 ‘공모전’이에요. 지금은 진행 중인 공모전이 없다고 안내해요.",
         route="/competitions", actions=[{"wait": 2500}]),
    dict(id="52", slug="competition-detail", stage="competitions", title_ko="공모전 상세",
         caption_ko="목록의 첫 공모전을 열었어요.",
         route="/competitions", actions=[{"wait": 2000}, {"click": "a[href^='/competitions/'], article", "optional": True},
                                         {"wait": 2000}],
         requires="a[href^='/competitions/'], article"),

    # --------------------------------------------------------------- 10 variants
    dict(id="53", slug="dark-discovery", stage="variants", title_ko="다크 · 탐색",
         caption_ko="다크 테마로 탐색 탭을 열었어요.",
         route="/discovery", theme="dark", actions=[{"wait": 2500}]),
    dict(id="54", slug="dark-search", stage="variants", title_ko="다크 · 검색",
         caption_ko="다크 테마의 검색 첫 화면이에요.",
         route="/search", theme="dark", actions=[{"wait": "textarea"}]),
    dict(id="55", slug="dark-profile", stage="variants", title_ko="다크 · 프로필",
         caption_ko="다크 테마의 프로필이에요.",
         route="/user/me", theme="dark", actions=[{"wait": "text=보드 >> nth=0"}, {"wait": 1000}]),
    dict(id="56", slug="dark-login", stage="variants", title_ko="다크 · 로그인",
         caption_ko="다크 테마의 로그인 화면이에요.",
         route="/login", account="none", theme="dark", actions=[], debug=False),
    dict(id="57", slug="en-discovery", stage="variants", title_ko="영어 · 탐색",
         caption_ko="언어를 English로 바꿔 탐색 탭을 열었어요.",
         route="/discovery", lang="en", actions=[{"wait": 2500}]),
    dict(id="58", slug="en-search", stage="variants", title_ko="영어 · 검색",
         caption_ko="영어 화면의 검색 첫 화면이에요.",
         route="/search", lang="en", actions=[{"wait": "textarea"}]),
    dict(id="59", slug="en-profile", stage="variants", title_ko="영어 · 프로필",
         caption_ko="영어 화면의 프로필이에요.",
         route="/user/me", lang="en", actions=[{"wait": 2000}]),
    dict(id="60", slug="en-login", stage="variants", title_ko="영어 · 로그인",
         caption_ko="영어 화면의 로그인이에요.",
         route="/login", account="none", lang="en", actions=[], debug=False),
    dict(id="61", slug="empty-profile", stage="variants", title_ko="빈 상태 · 새 계정 프로필",
         caption_ko="방금 만든 새 계정의 프로필이에요. 보드와 좋아요가 하나도 없어요.",
         route="/user/me", account="fresh", actions=[{"wait": 2000}]),
    dict(id="63", slug="fresh-taste", stage="variants", title_ko="새 계정 · 취향 시작",
         caption_ko="이메일을 인증하지 않은 새 계정으로도 같은 문장을 보내봤어요. 인증 안내 없이 카드가 그대로 나와요.",
         route="/search", account="fresh",
         actions=[{"fill": ["textarea", "노출 콘크리트 미술관"]}, {"click": 'button[aria-label="보내기"]'},
                  {"wait": 4000}]),
    dict(id="64", slug="not-found", stage="variants", title_ko="없는 주소",
         caption_ko="존재하지 않는 주소를 열었어요. 탐색 화면으로 보내면서 ‘찾는 페이지가 없어요’ 안내를 잠깐 띄워요.",
         route="/this-page-does-not-exist", actions=[{"wait": "text=찾는 페이지가 없어요", "timeout": 8000}, {"wait": 300}],
         no_settle=True),
    dict(id="65", slug="logged-out-protected", stage="variants", title_ko="로그아웃 · 보호된 화면",
         caption_ko="로그아웃 상태로 ‘결과’ 주소를 열었어요. 로그인 화면으로 이동해요.",
         route="/result/00000000-0000-0000-0000-000000000000", account="none", actions=[], debug=False),
]
