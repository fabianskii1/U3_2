# SKADI FE

React + TypeScript 기반 회전기계설비 모니터링 FE입니다. 로컬 개발은 Mock 모드, Docker 배포는 BE 연결 모드입니다. 원격 채팅은 설비 ID 조회를 지원하며 로그인은 아직 구현하지 않았습니다.

## Docker에서 BE와 함께 실행

프로젝트 루트에서 실행합니다.

```bash
docker compose --env-file DB/.env up -d --build
```

FE는 `http://127.0.0.1:5173`에서 열립니다. Nginx가 같은 origin의 `/api/` 요청을 Compose의 `be:8000`으로 전달합니다. `DB/.env`의 `FE_PORT`로 호스트 포트를 변경할 수 있습니다. Docker 빌드는 `VITE_API_MODE=remote`, `VITE_API_BASE_URL=/api`를 사용합니다.

이미지의 `BACKEND_UPSTREAM` 기본값은 EKS Service 이름에 맞춘 `backend:8000`입니다. Nginx 공식 이미지의 시작 템플릿으로 이 값을 적용하며, Compose는 `BACKEND_UPSTREAM=be:8000`을 설정합니다. `/api/` 경로와 쿼리 문자열을 그대로 전달하고 스트리밍 프록시 버퍼링은 끕니다.

## 이미지 CI

`.github/workflows/build-fe.yaml`은 `main`의 `fe/**` 변경 또는 `main`에서의 수동 실행에 동작합니다. Node.js 22에서 `npm ci`, Mock 모드의 전체 Vitest, 프로덕션 빌드를 통과한 뒤 `linux/amd64` 이미지를 만들고 실제 Nginx 컨테이너에서 정적 자산, SPA 새로고침, API 프록시와 upstream 설정 변경을 검사합니다. 검사가 모두 성공해야 기존 `HARBOR_USERNAME`/`HARBOR_PASSWORD`로 `harbor.skala-us.com/u3-2/frontend:<commit SHA>`를 게시합니다. 배포 중인 이미지 태그는 자동으로 변경하지 않습니다.

동일한 이미지 검사를 로컬에서 실행하려면 프로젝트 루트에서 다음을 실행합니다. 테스트용 API는 같은 이미지의 Nginx로 만들고, 외부 연결이 없는 임시 Docker 네트워크와 컨테이너는 종료 시 삭제합니다.

```bash
docker buildx build --platform linux/amd64 --load -t skadi-fe-ci:local -f fe/deploy/Dockerfile fe
bash fe/deploy/ci-smoke.sh skadi-fe-ci:local
```

현재 BE에서 연결되는 화면은 계층·설비 상세·트렌드·알람 이력·보고서 목록/상세와 설비 ID 조회 채팅입니다. 울산CLX 플랜트, CUD-01 그룹, 펌프 6대와 센서 48개가 기준 데이터로 들어 있습니다. 알람·보고서는 데이터가 없으면 빈 목록으로 표시됩니다. 실시간 활성 알람, 알람 SSE, 보고서 작성·편집 및 채팅의 보고서 작업은 준비 중입니다.

## 실행

Node.js 22.12 이상 또는 이에 대응하는 최신 LTS와 npm을 사용합니다. 검증 환경은 Node.js 26입니다.

```bash
cd fe
npm ci
npm run dev
```

기본 주소는 `http://127.0.0.1:5173`입니다. 이 포트를 다른 프로그램이 사용하면 `npm run dev -- --port 5174`처럼 변경합니다. 데이터 복원은 같은 브라우저 프로필과 같은 origin에서 동작합니다.

## 구현 범위

- 대시보드: 설비 수, 정상 설비, 활성 Setpoint 알람, 대응 우선순위, 설비·심각도별 알람 건수.
- 설비 현황: Plant → Unit → Equipment 탐색, 2D 예시 배치, 태그 현재값, 선택 센서 강조, 최근 활성 알람.
- 공통 설비 선택: 상단 context-bar의 Plant·Unit·Equipment 선택과 왼쪽 계층 메뉴를 동기화. 상위 변경 시 하위 선택·태그를 해제하며 URL·뒤로 가기·새로고침으로 복원.
- 설비 탐색 패널: 상단 왼쪽 버튼으로 접기·펼치기. 닫으면 업무 화면을 확장하고, 열림 상태는 브라우저에 보관.
- 트렌드: 센서·시작/종료 시각·조회 간격(자동/1초/1분/1시간/1일) 선택, 간격별 데모 시계열, 기준선과 초과 구간, 추세 설명.
- 알람: 현재 상태를 매초 조회하고 설비·발생 기간·심각도로 필터링. 재조회 중 기존 데이터를 유지.
- 보고서: 목록, 생성·수정, 입력 후 800ms 자동 저장, 페이지 이동 시 즉시 저장 시도, 수동 저장, 버전 충돌 비교.
- 보고서 복원: Zustand 편집본을 입력 즉시 localStorage에 기록. 저장 완료된 보고서는 Mock 서버 파일에도 기록.
- 채팅: 선택 조건·활성 보고서 초안을 API로 전달. 규칙 기반 데모로 초안 생성, 특정 필드 수정, 저장, 화면 링크 제공. 대화 초기화·응답 중지 지원.
- 화면: 전체 최소 너비 1280px, 채팅 기본 너비 300px, 최소 200px. 드래그 또는 구분선에 포커스 후 방향키로 조절. 최대는 작업 영역 확보를 위해 520px.

## 채팅 데모

트렌드 화면의 현재 조회 대상은 `src/features/trend/index.ts`의 `useTrendStore`로 읽습니다. 컴포넌트에서는 selector를 사용하고, 외부 함수에서는 `useTrendStore.getState()`로 접근합니다. `sensor_id`는 선택 센서 ID이며, `sensor_start_time`과 `sensor_end_time`은 API 조회 범위와 같은 `+09:00` 날짜·시간 문자열입니다. 기본 선택·URL 복원·센서 및 기간 변경을 동기화하며, 설비 미선택 또는 화면 이탈 시 조회 필드는 `null`입니다. 잘못된 기간에서는 시간·간격 필드가 `null`입니다. `sensor_interval`은 실제 적용된 간격(`1s`, `1m`, `1h`, `1d` 등)을 저장합니다. 선택 모드는 URL의 `interval`에 보관하며, 자동은 최대 약 500개 지점을 목표로 중간 간격도 선택합니다. 수동 조회는 최대 10,000개 지점으로 제한하며 기간을 줄이거나 간격을 늘리도록 안내합니다. 개발 환경의 Redux DevTools에서는 `SKADI` 연결의 State → `Trend`로 확인합니다. 같은 State 안의 `Selection`은 Plant·Unit·Equipment 선택, `Hierarchy UI`는 왼쪽 패널, `Chat UI`는 채팅 패널 상태입니다. 모든 Zustand 스토어가 하나의 DevTools 연결을 공유하므로 패널 조작 후에도 전체 상태를 함께 볼 수 있습니다.

```text
지금 알람 뭐부터 봐야 해?
원유 공급 펌프 A 진동 현황 보여줘
최근 7일 진동 추이 보여줘
보고서 초안 생성해줘
추정 원인을 "축 정렬 불량 의심"으로 수정해줘
조치 내역을 "센서 체결 상태 점검 권장"으로 수정해줘
보고서 저장해줘
```

수정할 내용을 따옴표로 지정하는 것은 현재 Mock 응답 파서의 제약입니다. 실제 자연어 이해나 RAG 진단은 구현하지 않았습니다. Agent 응답이 도착하기 전에 사용자가 추가 편집했다면 수정안을 적용하지 않고 재요청을 안내합니다. 생성·수정 요청은 저장된 텍스트를 직접 덮어쓰는 대신 공통 편집본과 저장 큐를 거칩니다.

## 데이터 보존과 충돌

- 브라우저 복구본: `skadi-report-drafts-v1` 키. 동일한 브라우저 프로필에서 재접속하면 미저장 입력도 복원합니다. 브라우저 데이터 삭제 또는 비공개 세션 종료 시 이 복구본은 유지되지 않습니다.
- 서버 저장본: `FE/.data/reports.json`. 개발 서버를 재시작해도 유지합니다. 저장 실패 시 로컬 초안을 보존하고 오류를 표시합니다.
- `localRevision`과 `savedRevision`으로 미저장 여부를 판단하며, 저장 중 추가 입력한 내용은 다음 요청으로 저장합니다.
- 서버의 `version`을 검사하여 충돌 시 HTTP 409를 반환합니다. 사용자가 서버 내용과 현재 초안을 비교하여 선택할 수 있습니다.
- 완료/승인 업무 흐름은 아직 없으며 현재 저장은 초안 저장입니다.

## API 연결 경계

`.env.example`을 참고해 `.env.local`에 다음을 설정하면 Mock API 대신 실제 서버를 사용합니다.

```dotenv
VITE_API_MODE=remote
VITE_API_BASE_URL=https://your-api.example.com/api
```

원격 서버는 브라우저 origin에 대한 CORS를 허용해야 합니다. 원격 API 계약은 [BE API 명세](../plan/be-api.md)를 따르며, `src/shared/api/be-adapter.ts`에서 BE의 `snake_case` 응답을 현재 화면 모델로 변환합니다. 플랜트·그룹·설비·센서 ID는 문자열 코드이고, 나머지 DB `bigint` ID는 JSON 문자열로 받습니다. Mock 모드의 합성 데이터 계약은 유지합니다.

현재 원격 모드의 알람 화면은 `/api/alarms/history`를 1분 간격으로 조회하고, 설비 상세는 `/api/equipment/{equipment_id}`를 10초 간격으로 조회합니다. 상단 갱신 시각은 설비 상세에서는 해당 설비의 마지막 성공 조회 시각을 표시합니다. 활성 알람과 SSE는 아직 사용하지 않습니다. 보고서 생성·수정은 준비 중입니다. 채팅은 `/api/chat/sessions`와 `/api/chat/stream`을 통해 AI 설비 ID 조회에 연결됩니다. 서버의 센서 임계값이 없으면 기준선과 초과 판정을 표시하지 않습니다.

아래 표는 **Mock 모드**의 기존 경로다. 원격 모드 경로와 요청·응답 형식은 [BE API 명세](../plan/be-api.md)를 따른다.

| 메서드 | 경로                                             | 용도                                                 |
| ------ | ------------------------------------------------ | ---------------------------------------------------- |
| GET    | `/api/hierarchy`                                 | Plant·Unit·Equipment·태그 목록                       |
| GET    | `/api/alarms`                                    | 전체 활성 알람 스냅샷과 기준 시각                    |
| GET    | `/api/equipment/:id`                             | 설비와 태그 현재값                                   |
| GET    | `/api/trend?sensor_id=…&from=…&to=…&interval=1h` | 센서·기간별 시계열                                   |
| GET    | `/api/reports`                                   | 서버 저장 보고서 목록                                |
| GET    | `/api/reports/:id`                               | 보고서 조회                                          |
| PUT    | `/api/reports/:id`                               | 예상 버전과 요청 ID를 포함한 생성·수정               |
| POST   | `/api/chat`                                      | 질문·화면/초안 맥락에 대한 답변과 구조화된 작업 결과 |

Mock API는 Vite 개발 서버 및 `vite preview`에서만 제공하는 로컬 개발 기능입니다. `dist/`를 정적 배포하는 경우 실제 API 서버가 필요합니다. JSON 파일 저장은 운영용 DB가 아닙니다. 실제 서버에서는 요청 ID 기반 멱등 처리와 권한 검증이 필요합니다.

## 폴더 책임

```text
src/app/           앱 조합, 라우터, 공통 레이아웃, 기능 간 연결
src/pages/         라우트별 화면 조합
src/features/      계층·설비·알람·트렌드·보고서·채팅 기능
src/shared/        공통 UI, HTTP 클라이언트, 외부 API 데이터 계약
mock/              로컬 HTTP API와 합성 데이터·규칙 기반 채팅
e2e/              Playwright 사용자 흐름 검증
```

API 계약의 스키마/타입만 `shared/api/contracts`에서 공유합니다. 실제 우선순위 계산, 초안 편집, 자동 저장 등의 업무 규칙은 각 기능 또는 Mock 서버에 둡니다. 아직 사용하지 않는 계획상의 UI 파일은 생성하지 않았습니다.

## 검증

```bash
npm run test
npx playwright install chromium
npm run test:e2e
npm run build
npm run preview
```

- Vitest: URL 계층 복원, 하위 조건 해제, Agent 수정 충돌, 브라우저 초안 복구, 저장 직렬화, 저장 실패·지연 저장, Mock 채팅 계약.
- Playwright: 설비 딥링크, 1초 폴링, 보고서 생성·채팅 수정·페이지 이동·새로고침·새 브라우저 컨텍스트 복구, 패널 너비, HTTP 409 충돌 해결, 잘못된 날짜 처리.
- E2E는 포트 5199의 별도 서버와 `.data-e2e/`를 사용하여 개발 데이터와 분리합니다. 의존성 캐시도 개발용 `node_modules/.vite-dev/`와 E2E용 `node_modules/.vite-e2e/`로 분리합니다.
- FE 테스트는 규칙 기반 응답을 사용합니다. 실제 AI 품질 평가는 실제 모델 연결 후 정답 데이터셋으로 별도 수행해야 합니다.

## 다음 연결 작업

1. 실제 API·알람 우선순위·설비 상태 집계 규칙 확정 및 연결.
2. 실제 2D 배경·좌표 데이터 연결. 현재는 실제 위치가 아닌 예시 배치입니다.
3. 설비 ID 조회 이외의 Agent 기능, 근거 문서 검색과 응답 토큰 단위 스트리밍 연결.
4. 과거 알람 이력과 서버 페이지 분할 연결. 현재 알람은 활성 스냅샷, 목록은 클라이언트 필터·페이지 분할입니다.
5. 로그인·역할별 권한·보고서 완료 처리 추가.

데모 시계열은 합성 값이며 1시간 간격, 최대 366일 조회를 지원합니다. 날짜는 KST 기준으로 해석하고 표시합니다.

## 개발 서버 실행 문제

`Port 5173 is already in use`는 이미 서버가 실행 중이라는 뜻입니다. 실행 중인 터미널에서 Ctrl+C로 종료한 후 `npm run dev`를 실행하세요. 점유 프로세스를 확인하려면 `lsof -nP -iTCP:5173 -sTCP:LISTEN`을 사용합니다.

빈 화면에서 개발자 도구에 `504 (Outdated Optimize Dep)`가 보이면, 기존 개발 서버를 종료하고 `npm run dev -- --force`로 의존성 캐시를 다시 생성한 뒤 페이지를 새로고침하세요. 보고서 복원용 브라우저 저장소를 삭제할 필요는 없습니다.

## 개발용 상태 확인

`npm run dev`에서만 아래 도구가 활성화됩니다.

- **TanStack Query Devtools**: 화면 왼쪽 아래의 TanStack 버튼을 누릅니다. queryKey, 응답 데이터, 캐시, 조회 상태와 갱신 여부를 확인할 수 있습니다.
- **Zustand**: 브라우저에 Redux DevTools 확장을 설치하고 페이지를 새로고침한 뒤 개발자 도구의 Redux 탭을 엽니다. 스토어 선택에서 `Skadi/Selection`, `Skadi/Hierarchy UI`, `Skadi/Chat UI`, `Skadi/Chat Session`, `Skadi/Report Drafts`를 고를 수 있습니다.
- Redux DevTools 확장 없이도 앱은 정상 동작합니다. 상태 점검 연결만 생략됩니다.
- 프로덕션 빌드에서는 Query Devtools 동적 import와 UI를 제외하고, Zustand DevTools 연결을 비활성화합니다.

프로덕션 노출 여부는 `npm run build` 후 `TEST_PRODUCTION=1 npm run test:e2e`로 검증합니다. 개발 모드에서는 `npm run test:e2e -- --grep Devtools`로 연결과 UI를 검증합니다.

## Mock 공정 계층

기존 CDU1·CDU2 Plant 각각에 아래 P1~P6 유닛을 둡니다. 각 유닛에는 펌프 A/B 2대가 있으며 전체는 유닛 12개, 펌프 24대입니다.

| 유닛 | 역할                  | 하위 설비                         |
| ---- | --------------------- | --------------------------------- |
| P1   | 원유 공급             | 원유 공급 펌프 A/B                |
| P2   | 상압탑 상부 납사·환류 | 납사·환류 펌프 A/B                |
| P3   | 등유 측류             | 등유 측류 펌프 A/B                |
| P4   | 경유 측류             | 경유 측류 펌프 A/B                |
| P5   | 펌프어라운드·열 회수  | 인버터 구동 펌프어라운드 펌프 A/B |
| P6   | 탑 하부 잔사유        | 고온 잔사유 펌프 A/B              |

유닛 ID는 `P-01-P1`, `P-02-P1`처럼 Plant별로 구분합니다. 펌프는 `P-1101A`, 태그는 `P1101A-VIB` 형태입니다. 각 펌프에 진동·유체 온도·토출 압력 태그를 두고, P6 유체 온도는 360°C로 표현합니다. 공정과 임계값은 시연용 가정입니다. 기존 보고서·브라우저 초안은 삭제하지 않으며, 이전 설비 ID로 작성한 초안은 새 데이터의 펌프와 자동 연결하지 않습니다.
