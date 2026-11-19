# DB 계획: 알람 원본, 상태, 우선순위 근거

## 목표와 기준 자료

- `plan/alarm/data/`의 2026년 11월 1분 센서 CSV(P1~P6), P1~P6 setpoint CSV 264행, P1~P4 알람 10행, P1~P4 정답지를 검증 자료로 사용한다. P5·P6는 setpoint가 있지만 알람 0건인 정상 대조군이다.
- 현재 DB는 `sensor_data_1m`, `equipment_run_state_1m`, `alarm`, `alarm_intake`를 사용한다. 실제 운영 스키마와 Alembic 버전을 먼저 대조한다. 2026-11-17 덤프에는 후속 `is_active`, `cof_score`, `alarm_intake`가 없으므로 덤프만 기준으로 삼지 않는다.
- 알람 원본, 센서 초과 구간, 조치 완료, 우선순위 평가를 별개 사실로 보존한다. 예시 CSV의 `alarm_end_time`은 **조치 완료 시각**, `sensor_end_time`은 정상 운전 중 판정값의 **복귀 시각**이다. 어느 쪽도 별도 근거 없이 알람 해제 시각으로 바꾸지 않는다.
- `alarm.occurred_at`은 `alarm_start_time`으로 이름을 바꾸고, `measured_value`·`threshold_value`는 제거한다. 기존 행의 발생 시각은 컬럼 이름 변경으로 보존한다. 측정값·판정 경계는 `alarm`에 저장하지 않는다.

## 데이터 매핑과 적재

1. 센서 CSV의 `REF-01`/`CDU-01`/`P1` 표기와 알람·setpoint CSV의 `PLANT-01`/`CDU`/`P-1` 표기를 실제 `plant`·`equipment_group`·`equipment` 키에 매핑하는 표를 확정한다. 원본 표기는 보존한다.
2. `sensor_signal.source_column`과 센서 ID의 연결, 단위, 380 V 기준, KST 시각을 검증한다. **P1~P6의 기존 시계열과 운전 상태 행 전체를 삭제한 뒤** 현재 `P1_2026-11.csv`~`P6_2026-11.csv`를 등록한다. 대상은 여섯 설비의 `sensor_signal`에 연결된 `sensor_data_1m`과 여섯 설비의 `equipment_run_state_1m` 행이며, 다른 설비 데이터는 건드리지 않는다. 삭제 전에 여섯 CSV의 헤더·월별 43,200행·시간 중복·센서 매핑을 모두 검증하고, 가능하면 스테이징 후 삭제와 재등록을 한 트랜잭션으로 처리해 실패 시 기존 데이터가 복구되도록 한다. 기존 `BE/scripts/import_cdu_1m.py`는 72개 연간 파일 경로와 다른 헤더를 기대하고 기존 값 충돌 시 거부하므로 이번 교체 작업에 맞게 별도 경로/모드를 구현한다.
3. Setpoint CSV를 알람보다 먼저 적재한다. `setpoint_id`를 버전이 포함된 고유 키로 보존하고 설비·센서 FK, 방향(`HIGH`/`LOW`), 연산자(`>=`/`<=`), 계산 종류(`FIXED`, `BASELINE_RATIO`, `BASELINE_OFFSET`, `EXPECTED_OFFSET`), 숫자 파라미터, 참조 코드, 단위, 연속 판정 분, 유효 시작/종료 시각을 저장한다. `effective_from`은 필수, `effective_to`는 nullable로 두고 `NULL`을 무기한 유효로 해석한다. 동일 센서·방향·등급의 유효 기간 중첩을 검사한다.
4. 알람 CSV의 문자열 `alarm_id`는 외부 원본 ID로 보존한다. 현재 `alarm.alarm_id`는 bigint 내부 키이므로 외부 ID를 그대로 PK에 넣지 않는다. 원본 ID 유니크 키 또는 별도 매핑 테이블로 재실행 중복을 막고, 모든 `setpoint_id`가 유효한 설정을 가리키는지 검증한다.
5. CSV의 `alarm_type=예측` 6행과 `임계치 초과` 4행, `alarm_level=경고`, `alarm_score`를 현재 `alarm_type=Setpoint`, 0~4 정수 등급, `cof_score`와 명시적으로 매핑한다. 예측/임계치 유형을 보존하고 같은 센서·setpoint의 두 이벤트를 서로 다른 알람 ID로 유지한다. 원본 알람을 화면용 Setpoint 범주로 묶는 규칙은 별도로 기록한다.
6. `alarm.alarm_start_time`은 감지 시작, `sensor_start_time`은 실제 센서 경계 초과 시작으로 분리한다. 빈 `sensor_start_time`/`sensor_end_time`은 `NULL`로 유지한다. 조치 및 센서 회복 시간을 저장할 위치를 정답지와 대조한다.

## Setpoint 계산과 버전

- 고정값 96행은 `parameter`와 단위로 경계를 구성한다. 나머지 168행은 참조값이 필요하다. `B_PS`·`B_PD`·`B_AMP`·`B_RPM`의 기준선과 `E_TF`·`E_TB`의 기대값 산출 정의·시점·버전을 분석기에서 확인하고, 입력 근거를 재현 가능하게 저장한다. 참조값이 없으면 경계를 임의로 산출하지 않는다.
- 데이터에는 8개 센서 열, 48개 센서 ID, 264개 고유 setpoint ID가 있다. `filter_minutes`는 3분 240행, 10분 24행이다. 실제 판정에서는 정상 `RUNNING` 구간과 연속 샘플 조건, 유효 기간 `[effective_from, effective_to)`를 적용한다. `effective_to IS NULL`이면 상한이 없으며, 값이 있으면 `effective_to > effective_from`을 강제한다. 임의의 100년 후 시각을 채우지 않는다.
- 설정이 나중에 바뀌어도 과거 알람의 적용 규칙을 찾을 수 있도록 당시 `setpoint_id`를 참조한다. 동적 기준의 실제 계산값·참조값은 `alarm`에 저장하지 않으므로, 필요한 경우 별도 판정 근거/평가 이력 저장소에서 보존하거나 분석기 결과를 조회한다. 값이 없으면 과거 경계를 재현할 수 있다고 주장하지 않는다.

## 스키마·무결성 작업

- 기존 `alarm`의 설비·센서 FK, `alarm_level` 범위, 유한 CoF 제약을 유지한다. Alembic에서 `occurred_at`을 `alarm_start_time`으로 **rename**하고 `measured_value`·`threshold_value`를 drop한다. Setpoint 테이블과 원본 이벤트 ID, 탐지 유형, setpoint FK, 초과/회복/조치 시간, 평가 시각·버전이 현재 테이블에 없으면 필요한 필드만 추가한다. 기존 코드·쿼리·인덱스·테스트의 옛 컬럼 참조를 함께 변경한다.
- `alarm_intake.source_event_id`와 `request_digest`의 멱등성은 유지한다. 수신 이벤트가 생성한 알람 ID와 그 시점의 선택 알람 ID·보고서 스냅샷을 추적할 수 있어야 한다.
- 현재 `alarm_intake.response` JSON에는 초기 보고서가 포함된다. 사용자에게 다시 보여줄 결과의 입력 시각, 점수, 정렬 규칙 버전, 근거 알람 ID를 고정하고 조회 시점 재계산과 구분한다.
- `equipment_id`·`sensor_id` 소속, 외부 ID 중복, 발생/회복/조치 시각 순서, KST→UTC 변환을 검증한다. 데이터의 회복 시각이 조치 완료보다 뒤인 경우도 허용한다. Setpoint 유효 기간의 중첩 검사에서 `NULL` 종료는 무한대로 취급한다.
- 활성 알람과 기간별 이력 조회에 필요한 인덱스를 실제 쿼리 계획으로 결정한다. 삭제된 설비/센서의 과거 알람 표시 정책을 정하고 이력의 참조 무결성을 유지한다.

## 검증 기준

- Setpoint 264행(펌프당 44행), 외부 알람 10행(예측 6·임계치 초과 4), P5·P6 알람 0행, 펌프별 43,200분 및 총 259,200행을 원본과 대조한다. 시계열 신호값은 총 2,073,600행(8개 신호 × 259,200분)이며, 교체 후 P1~P6에 기존 기간 데이터가 남지 않아야 한다. 알람 10행의 `setpoint_id`는 모두 유효하다.
- 2026-11-19 14:00 KST의 원본 알람 10행을 P1~P4 네 설비로 집계하고, 예측과 임계치 초과가 동일 센서·setpoint를 가리키는 경우 중복 설비/조건으로 세지 않는다. 설비별 최고 점수 P1 1.60 > P2 1.20 > P3 1.00 > P4 0.83을 재현한다.
- 동일 파일로 교체를 다시 실행해도 중복이 생기지 않고 원본 ID·시간·점수·NULL이 보존된다. 새 CSV 검증 또는 적재 실패 시 여섯 설비의 기존 시계열이 유지되는지 확인한다. 컬럼 rename 후 기존 알람 발생 시각이 보존되고 제거한 두 값은 더 이상 API에 요구되지 않는지 검증한다. 마이그레이션 결과를 기록한다.

## 개발 DB 적용 명령

아래 명령은 `BE/` 디렉터리에서 실행한다. 마이그레이션 `ab27c93e4501`은 유효 기간 중첩 방지에 `btree_gist`를 사용한다. 기존 실측·기준값을 복구하려면 마이그레이션 전 DB 백업이 필요하다.

```sh
python -m alembic upgrade head
python -m scripts.import_cdu_alarm_fixture --data ../plan/alarm/data
python -m scripts.import_cdu_alarm_fixture --data ../plan/alarm/data --apply
```

두 번째 명령은 CSV와 DB 설비 매핑을 점검한다. 세 번째 명령은 P1~P6의 두 시계열 테이블 행을 전체 기간에서 교체하고 setpoint와 알람을 적재한다. CSV의 조치 완료 시각과 센서 복귀 시각만으로 현재 활성 여부를 판정할 수 없으므로 적재된 알람의 `is_active`는 미확인(`NULL`)으로 유지한다.
