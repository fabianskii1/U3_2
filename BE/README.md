# SKADI BE

FastAPI + SQLAlchemy async + Alembic. Python 3.12. API base: `http://127.0.0.1:8000/api`; OpenAPI: `http://127.0.0.1:8000/docs`.

Swagger `/docs`는 계층, 설비, 시계열, 알람, 고장·정비 이력, 보고서, 매뉴얼, 운영 상태별로 API를 묶어 표시한다.

## 코드 구조

- `app/main.py`: 앱 생성, 공통 오류 처리, 도메인 라우터 등록
- `app/common/query.py`: ID·시각 직렬화, 기간 검증, 커서 페이지 처리
- `app/db/base.py`: 공유 SQLAlchemy metadata·컬럼 도우미
- `app/db/models.py`: 도메인 테이블 등록을 위한 Alembic 집계 지점
- `app/modules/{hierarchy,equipment,telemetry,alarms,histories,reports,manuals}/router.py`: 현재 제공하는 도메인별 조회 API
- `app/modules/{hierarchy,equipment,alarms,histories,reports,manuals,users,chat,request_logs}/models.py`: 각 도메인이 소유한 SQLAlchemy 테이블

도메인 테이블은 한 곳에서만 정의하고 Alembic은 집계 metadata를 읽는다.

설비 상세의 센서 `current_value`와 `measured_at`은 응답 시각 이전에 저장된 최신 1분 데이터를 조회한다. 저장값이 없으면 `null`을 반환한다.

## Docker 실행

프로젝트 루트에서 `DB/.env`에 비밀번호를 설정한 뒤 실행한다.

```bash
docker compose --env-file DB/.env up -d --build
docker compose --env-file DB/.env ps -a
curl http://127.0.0.1:8000/health
```

Compose는 DB 준비 후 `migrate` 서비스에서 `alembic upgrade head`를 실행하고 BE·AI·FE를 시작한다. DB 호스트 포트는 `5433`, API 호스트 포트는 `8000`, FE 호스트 포트는 `5173`이다. 컨테이너 사이에서는 DB 호스트 `db:5432`, AI 호스트 `ai:8001`을 사용하며 FE의 `/api/`는 `be:8000`으로 프록시한다. 호스트 포트는 루프백 주소에만 바인딩되고 AI 포트는 외부에 열지 않는다.

## 로컬 실행

```bash
cd BE
cp .env.example .env
# .env의 DATABASE_URL 비밀번호를 DB/.env와 동일하게 변경
uv sync --python 3.12
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 현재 제공하는 조회

- `GET /api/hierarchy`, `GET /api/equipment/{id}`
- `GET /api/trend`: `sensor_id` 또는 `signal_id`, 기간, 간격으로 적재된 1분 값 또는 1시간·1일 평균 조회
- `GET /api/alarms/history`, `GET /api/error-types`, `GET /api/error-histories`, `GET /api/maintenance-histories`
- `GET /api/alarms/priorities`: 활성 Setpoint 알람을 CoF 내림차순으로 조회하며 동점은 심각도, 발생 시각, 알람 ID 순으로 해결한다. 대시보드와 채팅이 같은 순위 서비스에 연결된다.
- `GET /api/alarms/{alarm_id}/initial-report`: 알람 수신 시 생성한 초기 보고서 스냅샷 조회
- `GET /api/reports`, `GET /api/reports/{id}`, `GET /api/equipment/{id}/manuals`

목록은 데이터가 없으면 빈 배열 또는 `{items: [], next_cursor: null}`을 반환한다. 개별 ID가 없으면 `404`다. 목록 기본 `limit`은 50, 상한은 200이다. 플랜트·그룹·설비·센서 ID는 `VARCHAR(30)` 코드이고 다른 `bigint` ID는 JSON 문자열로 응답한다. 상세 계약은 [API 명세](../plan/be-api.md)를 따른다.

초기 마이그레이션은 ERD에서 필드가 정의된 26개 테이블을 만든다. 후속 마이그레이션은 코드형 ID와 센서 사양, `sensor_signal` 48건, `sensor_data_1m` 및 `equipment_run_state_1m` TimescaleDB 하이퍼테이블을 만든다. `d4e6c2a9b105`는 전류 IT와 전압 ET를 각각 독립 센서로 연결하고 UT 센서를 제거한다. 최종 센서와 신호는 각각 48건이다. 설비 상세는 적재된 최신 관측값과 실제 측정 시각을 반환한다.

## 채팅 및 알람 수신

- 채팅 에이전트는 [AI/workflow](../AI/workflow/)에 있다. BE는 사용자 세션과 DB 조회 도구를 에이전트에 연결한다. Compose와 BE 이미지 빌드는 `agent_workflow` 빌드 컨텍스트로 이 패키지를 포함한다.
- `lookup_alias` 읽기 도구는 `plant`, `equipment_group`, `equipment`, `sensor`와 각 별칭 테이블의 현재 등록값으로 ID·이름·별칭을 찾는다. 동명이면 후보를 반환하고, 플랜트·공정·설비 범위를 적용할 수 있다. DB에서 정확히 일치하지 않는 설비 표현만 AI 식별 API에 전달하며, 이때도 후보 목록은 BE가 현재 DB에서 구성한다.
- `POST /api/chat/stream`은 Reflector에서 질문과 대상 표현을 추출하고, Action Planner에서 사용할 업무 도구를 선택한다. Executor가 조회한 결과를 `message.delta`, 딥링크 `citation`, `done`으로 보낸다. 설비 현황이나 추이의 대상이 확정되면 `navigate`도 보낸다. 추이의 기본 기간은 최근 7일이며, 센서별 지정 기간은 절대 시각으로 저장한다. “1호기”는 CDU 내부 펌프 목록으로 연결된다. “3번 펌프 전류”처럼 화면이 생략된 요청에는 설비 현황과 트렌드 링크를 제안한다. 설비 후보를 되물은 뒤 번호를 선택하면 이전 센서 조건을 사용한다.
- 채팅의 트렌드 링크는 센서별 절대 조회 기간을 `trend_view`에 저장한 뒤 `/trend?viewId=<UUID>`로 발급한다. `chat_result`가 AI 응답과 View를 연결한다. `POST /api/chat/trend-views`, `GET /api/chat/trend-views/{view_id}`, `GET /api/chat/messages/{message_id}/results`는 채팅 세션 쿠키로 접근을 확인한다. 동일 `request_id` 재전송은 저장된 응답을 재생한다.
- `POST /api/alarms/intake`는 모니터링 서비스가 보내는 Setpoint 관측을 받는다. Compose에서는 `DB/.env`, 로컬에서는 `BE/.env`에 `ALARM_INGEST_TOKEN`을 설정하고 요청에 `Authorization: Bearer <token>`을 포함한다. 입력에 고유한 `source_event_id`, 설비·센서 ID, 발생 시각, 상태, 관측값, 기준값과 단위를 담는다. CoF 점수는 수신 데이터에서 공급하며 생략 시 미평가로 표시한다.
- 새 이벤트를 수신하면 같은 플랜트의 CoF 평가 완료 활성 알람 1순위를 기준으로 초기 보고서 스냅샷을 저장한다. 동일 이벤트 재전송은 기존 응답을 돌려준다. 해제 이벤트에는 `is_active: false`와 원본 알람 이벤트의 `closes_source_event_id`를 함께 보낸다.
- 점검 근거는 등록 매뉴얼과 같은 설비의 저장 보고서·정비 이력을 조회한다. 정비 조치 보고서는 채팅에 검토용 초안으로 표시한다. 담당자 확정·저장, Wiki 사례 승인·게시, 외부 모니터 연결은 후속 연동이다.

## CDU 2026년 CSV 적재

먼저 `alembic upgrade head`를 적용한다. 프로젝트 루트의 CSV 폴더를 지정해 펌프 6대의 월별 파일 72개를 적재한다.

```bash
cd BE
uv run alembic upgrade head
uv run python -m scripts.import_cdu_1m --data ../data/CDU_2026_1min_MultiPump/data
```

한 CSV 행은 `sensor_data_1m`의 신호별 8행과 `equipment_run_state_1m`의 상태 1행이 된다. CSV의 오프셋 없는 시각은 KST로 해석한다. 파일별 트랜잭션이며 재실행 시 같은 값은 건너뛰고, 기존 값과 다른 중복 시각은 오류로 중단한다. 필요한 72개 파일과 48개 신호 매핑을 먼저 확인한다. 이 적재 명령은 Compose 시작 시 자동 실행되지 않는다.

`/api/trend`는 `[from, to)` 기간으로 조회한다. `1m`은 원본, `1h`·`1d`는 평균이며 일 경계는 KST다. IT와 ET는 각각의 `sensor_id`로 조회한다. 1초 데이터는 없으므로 `interval=1s`는 400을 반환한다. 실제 반환 지점이 10,000개를 넘으면 기간을 줄이거나 간격을 늘려야 한다. 원본에 품질 플래그가 없어 응답의 `quality`는 `null`이다.

## 검증

```bash
cd BE
uv run ruff check app migrations tests
uv run pytest -q
```

통합 테스트는 실행 중인 SKADI PostgreSQL을 사용한다. 테스트 행은 트랜잭션에서만 생성하고 종료 시 롤백한다.
