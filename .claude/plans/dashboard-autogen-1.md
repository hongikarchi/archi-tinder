# DASHBOARD-AUTOGEN-1 — Files tab + self-generating state.js

## 요약 (Korean TL;DR)
대시보드(`project/dashboard.html`)에 **파일 구조(Files) 탭** 추가 + `state.js`를 **생성 스크립트로 자동 생성**으로 전환.
지금은 reporter(LLM)가 컨텍스트 다 읽고 `state.js` 424줄을 손으로 옮겨적음 → 비싸고 `*/` 주석 백지 버그 위험.
해결: `tools/gen-state.js` 하나가 **둘 다** 처리 — `git ls-files`로 파일트리 + Task.md/gh/agent frontmatter로 감사데이터 자동 생성, mermaid×3 + milestones는 이전 `state.js`에서 그대로 복사.
LLM은 더 이상 JSON을 안 옮겨적음(콘텐츠=Task.md/다이어그램 작성만 사람 몫). `make dashboard` = 생성기 돌리고 열기 → 로컬 항상 최신. reporter-inline Step 4도 손-작성 대신 생성기 호출.
**서버 안 띄움** — `file://` 정적 유지(오프라인). 생성 시점 스냅샷 + `make dashboard`로 온디맨드 최신.

## Context
요청 2개: (1) 참조 repo `LFTH_CFD-v2.0`의 dashboard처럼 **전체 파일 구조 탭**을 우리 대시보드에도. (2) 지금 `state.js`가 정적이라 바뀔 때마다 reporter가 컨텍스트 읽고 새로 작성하는데 **자동 연동** 방법.
진단: 참조 repo는 dashboard를 **서버로 띄워** `/api/structure` API를 fetch함. 우리 대시보드는 `file://` 더블클릭 정적(+ `mermaid.min.js` 벤더링 = 오프라인 의도) → **로컬 API fetch 불가**. 따라서 트리 데이터를 `state.js`에 구워넣어야 함.
두 요청은 한 점으로 수렴: **생성 스크립트**. 파일트리는 그 스크립트의 한 출력(키)일 뿐. `state.js` 10개 키 중 6개는 결정론적 소스에서 자동 추출 가능, 4개(mermaid×3+milestones)는 손-큐레이트 → 생성기가 이전 파일에서 verbatim 복사하므로 평상시 **완전 자동**, 다이어그램 진짜 바뀔 때만 사람 손.

## Locked decisions (this session)
1. **트리거 = 온디맨드 스크립트 호출** (`make dashboard` 로컬 + reporter-inline Step 4). 서버/CI-writeback/git-hook 전부 제외 (브랜치 보호 + 1-clone-per-worker 충돌 회피). LLM은 생성기를 **호출만**, JSON을 작성하지 않음.
2. **트리 표시 = 폴더 접기/펴기** (collapsible). 네이티브 `<details>/<summary>`로 상태관리 없이 구현(~40줄).
3. **role 설명 = 모든 파일(335개)** 별도 파일 `project/file-roles.json`(`{path: desc}`)에 보관. 생성기가 `git ls-files`와 병합 + drift 리포트(설명 없는 새 파일 / 삭제된 orphan). 재생성해도 안 지워짐.
4. **최초 335개 = 에이전트 초안 → 사용자 검토.** 에이전트 ~10개가 파일군 나눠 병렬로 목적 읽고 한 줄 초안 → 사용자가 틀린 것만 수정.
- role 설명 언어: **한국어**(대시보드의 기존 done/now/next 제목이 한국어 = 일관성, Korea-first). 코드 식별자는 영어.

## Architecture — `tools/gen-state.js` (Node, stdlib만, 의존성 0)

데이터 흐름 (키별):

| state.js 키 | 소스 | 방식 |
|---|---|---|
| `meta.name` | 고정 상수 (또는 이전 값) | 그대로 |
| `meta.updatedAt` | `TZ=Asia/Seoul date` | 자동 |
| `meta.head` | `git rev-parse --short origin/develop` | 자동 |
| `meta.branch` | `git rev-parse --abbrev-ref HEAD` | 자동 |
| `done / now / next` | `Task.md` 파싱 (`## Done`/`## Now`/`## Next` → `###`/`####` 항목) | id/title/date/prs = 자동(정규식); **note = 첫 bullet 리프트** (아래 §note) |
| `agents` | **`.claude/agents/*.md`만** frontmatter (name/model/effort/description→role 첫문장). `.codex/agents/` 제외 | 자동 |
| `prs` | `gh pr list --base develop --state merged --limit 8 --json number,title,mergedAt` + KST 변환 | 자동 (★온라인/gh 필요; 실패 시 **이전 `prs` 유지**) |
| `fileTree` | `git ls-files` ∪ `project/file-roles.json` | 자동 (병합) |
| `systemFlow` `recommendationFlow` `agentFlow` | 이전 `state.js` | **verbatim 복사** |
| `milestones` | 이전 `state.js` | **verbatim 복사** |

생성기 단계:
1. 이전 `state.js` 로드: `global.window={}; eval(fs.readFileSync('project/state.js'))` → `PRIOR = window.PROJECT_STATE`.
2. 자동 키 6개 생성 (위 표). `child_process`로 `git`/`gh`/`date` 호출.
3. `fileTree`: `git ls-files` → 평면 `[{path, role}]` (role = file-roles.json 매칭 or `''`). 트리화는 렌더러가 클라이언트에서.
4. carry-forward 4개 키 = `PRIOR`에서 그대로.
5. **drift 리포트** (stderr): 설명 없는 파일 N개 나열 + 삭제됐는데 남은 role 항목 M개 나열.
6. `project/state.js` 방출 — 헤더 주석 블록 보존(★`*/` 부분문자열 금지 — 글롭 경로는 `<slug>` placeholder), `window.PROJECT_STATE = {...}`.
7. self-check: 방출 파일 재-eval → 키 10개 존재 + `done/prs` 배열 assert. 실패 시 비-0 종료.

`fileTree` shape (참조 repo와 동일): `fileTree: [{ path: 'backend/apps/recommendation/engine.py', role: '추천 엔진 facade' }, ...]`.

### §note 파생 (honest-matching — "완전 자동" 정정)
`done/now/next`의 `note` 한 줄은 **사람이 큐레이트한 요약**이지 Task.md 본문의 기계 변환이 아님 (현 `done[0].note` 보면 명확). 그래서 id/title/date/prs만 정규식으로 깨끗이 추출되고 note는 판단이 필요. 해결 = **first-bullet 규칙**: Task.md 각 `###`/`####` 항목의 **첫 bullet을 standalone 요약으로 작성**하는 관례를 두고, 생성기는 그 bullet[0]을 `note`로 리프트. → 콘텐츠(좋은 요약)는 사람이 Task.md에 1회 작성(이미 쓰는 곳), 생성기는 기계적 리프트 = LLM JSON 전사 0, 품질 유지. reporter-inline SKILL.md에 이 관례 명문화. (대안 "첫 줄 무지성 리프트"는 품질↓ → 채택 안 함.)

### dirty-on-view 회피 (`make dashboard`가 tracked 파일 더럽히지 않게)
`make dashboard`가 매번 tracked `state.js`를 재생성하면 `git status`가 항상 dirty + feature-branch 맛 `state.js`를 실수로 커밋할 위험. 해결: `make dashboard`는 **gitignored `project/state.local.js`** 에 씀. `dashboard.html`은 `<script src="state.js">` 다음에 `<script src="state.local.js">`를 로드 → 있으면 override, 없으면 file://에서 조용히 404(예외 없이 state.js 유지). 즉 커밋용 `state.js`는 reporter-inline(PR 맥락)만 갱신, 로컬 뷰는 state.local.js로 항상 최신 + tracked 파일 무변경. (`.gitignore`에 `project/state.local.js` 추가.)

## Components to build
| 파일 | 작업 | 소유/위임 |
|---|---|---|
| `tools/gen-state.js` | **신규** — 생성기 (위 아키텍처) | meta/infra carve-out → **메인 세션 직접** |
| `project/file-roles.json` | **신규** — 335개 `{path: desc}` | **에이전트 초안 → 사용자 검토** |
| `project/dashboard.html` | Files 탭 추가: `TABS += {id:'files',label:'Files'}` (559–565), `<section class="panel" id="panel-files">` (297–301), `renderFiles()` 신규 — `<details>/<summary>` collapsible 트리 + role 컬럼 (~40줄), `init()`에서 호출 (613–621) | project/ 대시보드 툴 → **메인 세션 직접** (front-maker는 frontend/만 만짐) |
| `project/state.js` | 생성기 출력으로 전환 + 헤더 주석에 "build step: tools/gen-state.js" 명시, `fileTree` 키 추가 | 생성기가 씀 |
| `Makefile` | `dashboard:` 타겟 — `node tools/gen-state.js && open project/dashboard.html` | meta/infra → 직접 |
| `.claude/skills/reporter-inline/SKILL.md` | Step 4 = 손-작성 → `node tools/gen-state.js` 호출로 교체 (Step 2 Task.md 편집은 그대로 = 사람 콘텐츠) | docs/meta → 직접 |

## Per-file role 메커니즘 (요청대로 "바뀌면 그때만")
- `file-roles.json` = 단일 진실원. 생성기는 읽기만(절대 덮어쓰지 않음).
- 새 파일 추가 → 생성기 drift 리포트가 "설명 없음" 으로 플래그 → 사용자가 그 줄만 추가.
- 파일 삭제 → orphan 항목 플래그 → 사용자가 그 줄만 제거(안 해도 무해, 트리엔 안 뜸).
- 즉 335개는 1회, 이후 델타만. 스크립트가 델타를 짚어줌.

## Phasing / PR 구성 (권장 2 PR, 1로 축소 가능 = 사용자 콜)
- **PR 1 — 엔진(요청 #2 자동연동):** `tools/gen-state.js` + `Makefile dashboard` + `.gitignore`(state.local.js) + reporter-inline Step 4 교체 + `state.js` 생성기 출력(+`fileTree` 키, role은 아직 비어있어도 graceful). 순수 tools/meta → app-test 불필요(frontend/backend 런타임 표면 0).
  - **착수 전 (cheap verify):** 실제 `Task.md`의 `## Done`/`## Next` 헤더를 먼저 덤프 → PR-인용 변종 전부 커버 확인 (`(PR #N \`sha\`)` vs `(PRs #170 6f54cc3 / #171 ...)` 등 — explorer가 보고한 이상형 말고 실물). 파서가 done/now/next를 **수용 가능하게** 뽑는지(note=첫bullet 포함) 실 Task.md로 증명.
  - 검증: 생성기 2회 실행 출력 동일(타임스탬프 제외) + `state.js` parse OK + 기존 5탭 회귀 없음 + `agents[]`가 현 로스터와 일치(개수/필드, 삭제된 git-manager/reporter 부활 없음).
- **PR 2 — Files 탭(요청 #1 가시화):** `project/file-roles.json`(에이전트 초안 335 + 검토) + `dashboard.html` Files 탭(collapsible+role). **게이트: PR1에서 파서가 실 Task.md로 검증된 뒤에만 ~10-에이전트 335 fan-out 착수** (비싼 단계 = 싼 토대 검증 후). 큰 아티팩트(335 role) 격리 리뷰. 검증: playwright MCP로 `file://.../dashboard.html` 열어 Files 탭 접기/펴기 + role 표시 스크린샷.

## Execution & delegation
- 메인 세션 직접: `tools/gen-state.js`, `Makefile`, `dashboard.html`(project/ = 대시보드 툴, frontend/ 아님 → maker 범위 밖), `reporter-inline` SKILL.md.
- 에이전트 fan-out: `file-roles.json` 초안 — ~10 에이전트 병렬(general-purpose, sonnet), 각 ~33 파일, 파일 목적 읽고 `{path: 한줄설명}` 청크 반환 → 메인이 병합 → 사용자 검토.
- git: `git-commit` 스킬(PR별 커밋) → 명시적 publish 트리거 후 `git-publish` 스킬(feature→develop 스쿼시).
- 브랜치: `feature/claude-dashboard-autogen` (현재 develop @ fefa830에서 분기).

## Verification (end-to-end)
1. **생성기 결정론**: `node tools/gen-state.js` 두 번 실행 → 출력 동일(타임스탬프 제외). `state.js` self-check 통과.
2. **carry-forward**: 실행 후 `systemFlow/recommendationFlow/agentFlow/milestones`가 이전과 byte-동일(다이어그램 안 지워짐 증명).
3. **오프라인 graceful**: `gh` 없이 실행 → `prs`가 이전 값 유지, 크래시 없음.
4. **drift 리포트**: 임의 새 파일 `touch` → 생성기가 "설명 없음"으로 플래그 확인.
5. **대시보드**: playwright MCP로 `file://` dashboard.html 열기 → 5개 기존 탭 + Files 탭 렌더 확인, 폴더 접기/펴기 동작, role 컬럼 표시, mermaid 탭 회귀 없음.
6. **reporter-inline**: 스킬 따라 Step 4가 생성기 호출로 동작, 산출 `state.js` parse OK.

## Notes
- 기존 `state.js` 헤더 주석("no fetch, no server, no build step")은 build step 생기므로 갱신 — 단 `file://` 로드/오프라인은 유지(생성은 build 시점, 로드는 여전히 정적).
- 참조 repo의 `buildTree/renderTree`는 **패러프레이즈만 봄** → 베끼지 말고 자체 작성(`<details>` 네이티브 = 더 단순).
- 실행 시 이 플랜을 repo `.claude/plans/dashboard-autogen-1.md`로 복사 (audit-trail 관례).
- Honors [[feedback_publish_gate]] (publish 트리거 필요) · [[feedback_autonomous_work]] · [[feedback_plan_mode_korean_review]] · [[feedback_agent_model_selection]](에이전트 sonnet).
- 이전 플랜 내용(FULL-REFACTOR-1)은 완료/머지(develop @ fefa830)되어 [[project_full_refactor_1_status]]에 종결 기록됨 — 이 파일은 새 작업으로 덮어씀.
