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

현재는 읽기 전용 API이므로 도메인 라우터에서 조회 쿼리를 처리한다. 쓰기와 복잡한 업무 규칙을 추가할 때 해당 도메인의 service/repository로 분리한다. 도메인 테이블은 한 곳에서만 정의하고 Alembic은 집계 metadata를 읽는다.

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
- `GET /api/reports`, `GET /api/reports/{id}`, `GET /api/equipment/{id}/manuals`

목록은 데이터가 없으면 빈 배열 또는 `{items: [], next_cursor: null}`을 반환한다. 개별 ID가 없으면 `404`다. 목록 기본 `limit`은 50, 상한은 200이다. 플랜트·그룹·설비·센서 ID는 `VARCHAR(30)` 코드이고 다른 `bigint` ID는 JSON 문자열로 응답한다. 상세 계약은 [API 명세](../plan/be-api.md)를 따른다.

초기 마이그레이션은 ERD에서 필드가 정의된 26개 테이블을 만든다. 후속 마이그레이션은 코드형 ID와 센서 사양, `sensor_signal` 48건, `sensor_data_1m` 및 `equipment_run_state_1m` TimescaleDB 하이퍼테이블을 만든다. `d4e6c2a9b105`는 전류 IT와 전압 ET를 각각 독립 센서로 연결하고 UT 센서를 제거한다. 최종 센서와 신호는 각각 48건이다. `sensor_data_1s/1h/1d`와 `sensor_alarm_config`는 아직 만들지 않는다. 로그인, 보고서 쓰기, 알람 판정·SSE와 채팅의 다른 업무 기능은 이후 단계다. Docker FE는 구현된 조회 API와 설비 ID 채팅에 연결되며 미구현 기능은 준비 중으로 표시한다.

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
export DATABASE_URL='postgresql+asyncpg://test_user:test_password@127.0.0.1:15432/test_db'
uv run --frozen alembic upgrade head
uv run --frozen ruff check app migrations tests
uv run --frozen pytest -q
```

통합 테스트에는 TimescaleDB와 pgvector가 활성화되고 `alembic upgrade head`가 적용된 별도 테스트 PostgreSQL을 사용한다. `DATABASE_URL`을 명시해서 `.env`의 개발·운영 DB에 연결하지 않도록 한다. 테스트 행은 트랜잭션에서만 생성하고 종료 시 롤백한다.

## CI

`.github/workflows/build.yaml`은 `main`의 `BE/**` 또는 워크플로 변경과 `main`에서의 수동 실행에 동작한다. Python 3.12와 고정된 uv 의존성으로 Ruff 및 전체 pytest를 실행한다. 테스트 DB는 작업마다 새로 생성하는 `timescale/timescaledb:2.32.0-pg17` 서비스이며, pgvector 활성화 후 Alembic으로 스키마와 기준 데이터를 준비한다. 저장된 `.env`, DB 덤프, 실제 AI 서비스는 사용하지 않는다.

검증이 통과하면 운영 Dockerfile로 `linux/amd64` 이미지를 빌드하고 `deploy/ci-smoke.sh`로 실제 기본 실행 명령의 `/health`, 계층 및 P1 설비 조회를 확인한다. 모든 검증이 성공한 뒤에만 `HARBOR_USERNAME`·`HARBOR_PASSWORD`로 로그인하여 `harbor.skala-us.com/u3-2/backend:<commit SHA>`를 게시한다. 배포 매니페스트나 실행 중인 서비스는 변경하지 않는다.

이미지 검사 스크립트는 같은 Docker 네트워크의 `db:5432`에 `ci_backend` DB·사용자 및 `ci_backend_only` 비밀번호로 준비된 일회용 DB만 대상으로 한다.

```bash
bash BE/deploy/ci-smoke.sh <backend-image> <disposable-db-network>
```
