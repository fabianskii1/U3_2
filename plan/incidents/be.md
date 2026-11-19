# BE 계획: 사건 조회 API와 알람·트렌드·보고서 연계

## 현재 상태

- `alarms` 모듈에 수신(`POST /api/alarms/intake`), 우선순위(`GET /api/alarms/priorities`), 이력(`GET /api/alarms/history`)이 있다. 알람에 사건 개념은 없다.
- `histories` 모듈은 `error_type`, `error_history`, `maintenance_history`를 조회한다. 세 테이블 모두 비어 있다.
- `report`는 `error_history_id`와 `report_suspected_causes(error_type_id)`를 가진다. 사건·알람과 직접 연결되지는 않는다.
- 스키마와 적재는 [DB 계획](db.md)을 따른다. 요약하면 사건 4건과 후보 10행을 새로 넣고, 기존 알람 10행의 시각·CoF를 갱신하며, 알람에 `incident_id`·`peak_level`을 연결한다.

## 신규 모듈 `app/modules/incidents`

1. `models.py`: `incident`, `incident_candidate`. `alarm.incident_id`·`peak_level`은 `alarms/models.py`에 추가한다.
2. `GET /api/incidents`
   - 필터: `plant_id`, `equipment_group_id`, `equipment_id`, `from`/`to`(`incident_start_time` 기준, `valid_range` 재사용), `min_level`, `actionable`, `status`, `as_of`
   - 정렬: `incident_start_time DESC`, 기존 `app.common.query.page` 커서 페이지네이션
   - 항목: 사건 ID·설비, 네 시각, `status`, `peak_level`, 선행 센서(ID·이름), 진단명, `top_cof`, `top_pof`, `incident_score`, 대응 등급·사유, 조치 필요, 알람 수
   - `status`는 `as_of`(기본값은 서버 현재 시각)와 비교해 계산한다. `incident_start_time > as_of`면 `upcoming`, 종료 전이면 `ongoing`, 종료 후면 `closed`다.
3. `GET /api/incidents/{incident_id}`
   - 사건 요약
   - `candidates`: rank 순으로 고장명, 점수 구성요소, `is_diagnosis`, `is_top_risk`, `evidence` 원문
   - `alarms`: 시작 시각 순으로 `alarm_id`, `source_alarm_id`, 센서, setpoint, `event_type`, `alarm_level`, `peak_level`, CoF, 감지·센서 구간
   - `trend_window`: `incident_start_time - 24h` ~ `min(incident_end_time, as_of) + 6h`, 그리고 관련 신호 ID(선행 센서 + 알람 센서). 알람은 모두 사건 구간 안에 있다.
   - `data_coverage`: 구간의 `sensor_data_1m` 보유 여부(`full`/`partial`/`none`)
4. Pydantic 응답 스키마와 OpenAPI 예시(`INC-P1-202611190600`, 알람 4개)를 추가한다.

## 기존 API 변경

- **알람 이력** `GET /api/alarms/history`: 응답에 `incident_id`, `peak_level`을 추가하고 `incident_id` 필터를 지원한다.
- **우선순위** `GET /api/alarms/priorities`:
  - 정렬 규칙(CoF ↓, 등급 ↓, 시작 시각 ↑, ID ↑)은 바꾸지 않는다.
  - 알람 CoF 갱신으로 결과가 P1 1.67 > P2 1.0 > P3 1.0 > P4 0.83이 된다. P2·P3 동점은 시작 시각(04:00 < 08:00)으로 가른다. 설비 순서는 같고 점수만 바뀌므로, 테스트 기대값과 [알람 BE 계획](../alarm/be.md) 완료 기준의 점수를 고친다.
  - 설비별 대표 알람 항목에 `incident_id`, 진단명, `incident_score`를 추가해 화면·채팅이 사건으로 이동할 수 있게 한다. 사건 점수(P1 7.3 > P2 0.8 > P4 0.6 > P3 0.4)는 순위에 쓰지 않는다.
- **트렌드** `/api/trend`: 요청 구간과 겹치는 사건(ID, 구간, 진단명, 최고 등급, 상태)을 `incidents` 필드로 함께 반환한다.
- **설비 화면**: 별도 필드를 추가하지 않고 FE가 `GET /api/incidents?equipment_id=`를 호출한다.

## 보고서 연계

- 보고서 생성 요청에 선택 입력 `incident_id`를 받는다. `report.incident_id` FK 추가 여부는 DB 계획 5번(`error_history` 연결)과 함께 정한다.
- 사건 기반 초안:
  - 설비·공정: 사건 설비
  - 증상(`report_symptoms`): 연결 알람의 센서별 구간, 선행 센서
  - 의심 원인(`report_suspected_causes`): 후보 rank 순 `error_type_id`
  - 위험(`risk`): 대응 등급·사유, PoF, 최고 등급
- 진단은 추정이다. 원인 필드를 확정 문장으로 채우지 않는다.

## 수신 계약 (후속)

- 알람 수신 API(`POST /api/alarms/intake`)에 선택 입력 `incident_id`, `peak_level`을 추가할지 정한다.
- 실시간 분석기용 `POST /api/incidents/intake`는 이번 범위에서 설계만 한다. 알람 intake와 같은 멱등성(`source_event_id` + digest)·트랜잭션 규칙을 따른다.

## 테스트

- 적재: 검증 전용 실행의 diff 출력(시작 6행, 종료 10행, 센서 복귀 8행, CoF 6행), `--apply` 재실행 시 변경 0건, CSV·DB 알람 ID 불일치나 사건 연결 불일치가 있으면 전체 롤백
- 사건 목록: 필터, 커서, `as_of`별 `status`(11-10 → P3만 `ongoing`, 11-18 → P2·P3·P4 `ongoing`이고 P1은 `upcoming`, 11-21 → 모두 `closed`), 빈 결과
- 사건 상세: 후보 순서, P3 후보 1개, 알람별 `peak_level`, `data_coverage=full`
- 우선순위: P1 1.67 > P2 1.0 > P3 1.0 > P4 0.83, 동점 처리, 대표 알람의 `incident_id`
- 기존 BE 테스트 전체 통과(우선순위 점수 기대값은 새 값으로 갱신)
