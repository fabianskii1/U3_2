# DB 계획: 이상 사건(Incident), 원인 후보, 알람 연결

## 목표와 기준 자료

`plan/incidents/data/`의 CSV 3개로 "알람 → 사건 → 원인 진단"을 DB에서 추적할 수 있게 한다. 모두 임시(합성) 데이터다.

| 파일 | 행 | 내용 | DB 반영 |
| --- | --- | --- | --- |
| `CDU_2026-11_incidents.csv` | 4 | P1~P4의 2026년 11월 사건(설비당 1건). 시작·감지·첫 알람·종료 시각, 최고 등급, 선행 센서, 진단, 최고 위험 고장, CoF·PoF, 사건 점수, 대응 등급, 조치 필요, 알람·트렌드 건수, 연결 알람 ID(`alarm_ids`) | 신규 `incident` |
| `CDU_2026-11_incident_candidates.csv` | 10 | 사건별 원인 후보(P1·P2·P4 3개, P3 1개). 규칙 점수, 확률, 속도·영향, CoF, PoF, 최종 점수, 진단·최고 위험 여부, 근거 | 신규 `incident_candidate` |
| `CDU_2026-11_alarms.csv` | 10 | P1~P4 알람(예측 6, 임계치 초과 4). 기존 알람 컬럼에 `incident_id`, `incident_score`, `peak_level`, `sensor_name` 추가. P5·P6는 0건 | 기존 `alarm` 10행 값 갱신 + `incident_id`·`peak_level` 연결 |

- 현재 DB는 Alembic `ab27c93e4501` 스키마이며, 덤프 `skadi_20261119_161433`을 복원한 상태다. 알람 10행(같은 ID), setpoint 264행, P1~P6의 11월 1분 시계열(2026-11-01 ~ 11-30 KST)이 있다.
- `incident`는 분석기의 **판정 결과**이고 `error_history`는 **확정된 고장 이력**이다. 두 개념을 섞지 않는다.

## 데이터 정리 내역 (2026-11-19)

세 CSV가 서로, 그리고 DB와 맞도록 아래처럼 고쳤다. 고치기 전 원본은 세션 임시 폴더에 백업했다.

| 대상 | 변경 | 이유 |
| --- | --- | --- |
| 알람 | 차압 알람 2행(`AL-P3-DP-LO-202611090808`, `AL-P1-DP-LO-202611191200`) 삭제, `note` 컬럼 삭제 | 차압 센서·setpoint가 DB에 없다(setpoint 파일에 없는 경계) |
| 알람 | `equipment_id` `P-n` → `Pn`, `equipment_group_id` `CDU` → `CDU-01` | DB 표기와 통일 |
| 사건 | `equipment_group_id` `CDU` → `CDU-01` | DB 표기와 통일 |
| 사건 P3 | 선행 센서 `10-PT-1307 − 10-PT-1306`(차압) → `10-PT-1307`(토출압) | 실제 센서 ID로 저장하기 위해서다. 토출압 일평균이 11/07 462 → 11/18 413 kPa로 떨어지므로 선행 센서로 타당하다. 후보 근거 문장의 "차압 -33 %"는 분석 결과 문장이므로 그대로 둔다. |
| 사건 P3 | `first_alarm_time` 11-09 08:08 → 11-19 08:00, `peak_level` 위험 → 경고 | 차압 알람 삭제 후 남은 연결 알람과 맞추기 위해서다 |
| 사건 | `alarm_count`를 실제 연결 수로 변경(P1 4, P2 2, P3 2, P4 2), `alarm_ids`를 알람 CSV의 `incident_id`와 일치시킴 | 원본 값이 어느 기준과도 맞지 않았다 |

정리 후 검증 결과(오류 0건):

- 모든 알람의 설비(`CDU-01` 소속), 센서, setpoint가 DB에 있고, setpoint의 센서·등급(경고=2)이 알람과 일치한다.
- 알람 CSV의 ID 10개가 DB `alarm.source_alarm_id` 10개와 정확히 같다.
- 사건별로 `alarm_ids` = 알람 CSV의 연결 목록, `alarm_count` = 연결 수, `first_alarm_time` = 연결 알람 최소 시작 시각, `peak_level` = 연결 알람 `peak_level` 최댓값이다.
- 모든 알람의 시작·조치 완료·센서 복귀 시각이 사건 구간 안에 있다.
- 알람 점수 = 사건 `top_cof`, 알람 `incident_score` = 사건 점수, 진단 후보의 `cof`·`pof`·`score` = 사건 값, 후보 rank는 연속이고 사건마다 진단 1건이다.

## DB에 반영할 알람 값 변경

알람 ID와 등급·유형·센서·setpoint는 같고, 아래 값만 DB와 다르다. 적재 시 CSV 값으로 갱신한다.

| 항목 | 현재 DB | CSV | 행 수 |
| --- | --- | --- | --- |
| 예측 알람 시작 시각 | 정시 + 1분(03:01, 04:01, 08:01, 09:01, 10:01, 11:01) | 정시(03:00 … 11:00) | 6 |
| `alarm_end_time` | P1 21:45 / P2 11-20 12:10 / P3 11-20 03:10 / P4 11-20 14:10 | P1 VIB 19:59, PS 20:59, PD 15:59 / P2 11-20 07:29 / P3 11-19 19:29 / P4 11-20 10:29 | 10 |
| `sensor_end_time` | P1 PS 19:21 / P2 11-20 15:30 / P3 11-20 06:30 / P4 11-20 17:30 | P1 PS 19:20 / P2 07:29 / P3 19:29 / P4 10:29 | 8 |
| `cof_score` | P1 1.60, P2 1.20 | P1 1.67, P2 1.0 | 6 |

갱신 후 알람 우선순위는 **P1 1.67 > P2 1.0 > P3 1.0 > P4 0.83**이다. P2와 P3는 CoF와 등급이 같아서, 시작 시각이 빠른 P2(04:00)가 P3(08:00)보다 앞선다. 설비 순서는 기존 검증값(P1 > P2 > P3 > P4)과 같고 점수만 바뀐다. [알람 BE 계획](../alarm/be.md)의 완료 기준 점수(1.60/1.20/1.00/0.83)를 새 값으로 고친다.

## 시계열 대조 (현재 `skadi`)

| 사건 | CSV 근거 | DB 시계열 |
| --- | --- | --- |
| P1 캐비테이션 | 흡입압 -28 %, 진동 증가 | 11/19 `10-VT-1105` 최대 4.19(경고 4.0 초과), `10-PT-1106` 최소 55.5 kPa |
| P2 베어링 마모 | 진동 +3.1 mm/s, 끝에서 가속 | 11/19 `10-VT-1205` 최대 4.66 |
| P3 임펠러 마모 | 차압 -33 %, 10일 넘게 천천히 | `10-PT-1307` 일평균 11/07 462 → 11/18 413 kPa, 11/19 08~18시 377 → 350 kPa, 19시대에 130 kPa로 급락(알람 종료 19:29와 일치) |
| P4 커플링 마모 | 진동 +3.1, 흔들림 증가 | 11/19 `10-VT-1405` 최대 5.03 |

시계열은 다시 적재하지 않는다.

## 남은 확인 사항

- **알람 등급과 최고 도달 등급:** 알람 10행의 `alarm_level`은 모두 경고(판정 setpoint 등급)이고, `peak_level`은 7행이 위험이다. 두 값을 별도 컬럼으로 저장한다.
- **`alarm_end_time`의 의미:** 기존 알람 계획은 `alarm_end_time`을 조치 완료, `sensor_end_time`을 센서 복귀로 정의했다. CSV에서는 P1 PS를 빼면 두 값이 같다. 정의는 그대로 두고, 활성 여부를 이 값으로 추정하지 않는다(`is_active=NULL` 유지).
- **종료 시각이 현재보다 뒤:** 오늘은 2026-11-19다. 사건 종료(P1 22:00, P3 19:30, P2 11-20 07:30, P4 11-20 10:30)가 현재보다 뒤일 수 있다. "진행 중" 여부는 조회 시각(`as_of`)과 비교해 계산하고 DB 컬럼으로 고정하지 않는다.
- **차압 알람:** 차압 setpoint가 정의되면 파생 센서(`토출압 − 흡입압`)와 setpoint를 등록한 뒤 다시 추가한다. 이번 범위에서는 하지 않는다.

## 스키마 변경 (Alembic 신규 리비전)

1. `incident`
   - `incident_id` text PK, `plant_id`·`equipment_group_id`·`equipment_id` FK
   - `incident_start_time`, `detect_time`, `first_alarm_time`(nullable), `incident_end_time`(nullable): timestamptz
   - `peak_level` 0~4 정수(주의 1·경고 2·위험 3·비상 4)
   - `lead_sensor_id` FK → `sensor`
   - `diagnosis_error_type_id`·`top_risk_error_type_id` FK → `error_type`
   - `top_cof`, `top_pof`, `incident_score` float(유한), `alarm_grade`, `grade_reason` text, `response_time_h` float, `actionable` boolean, `alarm_count`·`trend_count` int
   - `source_file` text, `loaded_at` timestamptz
   - 제약: `detect_time >= incident_start_time`, 종료 시각이 있으면 시작 이후, 점수 유한
   - 인덱스: `(equipment_id, incident_start_time DESC)`
2. `incident_candidate`
   - PK `(incident_id, rank)`, `error_type_id` FK
   - `rule_score_s`, `s_top3_sum`, `p`, `speed`, `impact`, `w`, `cof`, `p_trend`, `pf_hours`, `p_pf`, `pof`, `score`, `is_diagnosis`, `is_top_risk`, `evidence` text
   - 사건당 `is_diagnosis = true` 1건, `is_top_risk = true` 1건(각각 partial unique index)
3. `alarm` 컬럼 추가: `incident_id` FK(nullable), `peak_level` int(nullable, 0~4). 알람 1개는 사건 1개에만 속한다.
4. `error_type` 시드: 후보에 나온 6종(캐비테이션, 임펠러 불균형, 베어링 마모, 축 정렬 불량, 임펠러 마모, 커플링 마모). `error_type_name`에 unique 제약을 추가한다.
5. (선택) `incident.error_history_id` FK(nullable): 확정 고장과 연결할 자리만 만들어 둔다.

알람 CSV의 `incident_score`, `sensor_name`은 사건·센서 테이블에 있는 값이므로 `alarm`에 저장하지 않고 적재 시 일치 여부만 검증한다.

## 적재 스크립트 `BE/scripts/import_incident_fixture.py`

- 인자: `--data ../plan/incidents/data`. 기본 실행은 검증과 변경 예정 내역(diff) 출력만 하고, `--apply`를 붙여야 커밋한다. `import_cdu_alarm_fixture`와 같은 패턴이다.
- 순서(한 트랜잭션): `error_type` 시드 → `incident` → `incident_candidate` → `alarm` 갱신(`source_alarm_id` 기준; 시각, `cof_score`, `peak_level`, `incident_id`)
- 검증: 위 "정리 후 검증 결과"의 항목을 그대로 코드로 확인한다. 하나라도 어긋나면 전체를 롤백한다. 알람 CSV에 DB에 없는 ID가 있거나 DB 알람이 CSV에 없으면 중단한다.
- `alarm_intake`에 저장된 응답 스냅샷이 갱신 대상 알람을 참조하면 경고를 출력한다(스냅샷은 수정하지 않는다).
- 같은 파일로 다시 실행하면 변경이 0건이어야 한다.

## 적용 결과 (2026-11-19)

- 적용 전 덤프: `DB/dump/skadi_20261119_165813_before_incidents.dump`
- 마이그레이션 `c8e1f5a3b7d2`(`ab27c93e4501` 다음)를 적용했다. `incident`, `incident_candidate`를 만들고, `alarm.incident_id`·`peak_level`과 `error_type_name` unique 제약을 추가했다. 모델은 `app/modules/incidents/models.py`에 있다.
- 적재 스크립트 결과: 24건 변경(error_type 6, incident 4, 후보 4건분 10행, 알람 10행 갱신). 다시 실행하면 0건이다.
- 설비별 대표 알람 순서는 P1 1.67 > P2 1.0(04:00) > P3 1.0(08:00) > P4 0.83이다(기존 정렬 규칙을 SQL로 재현한 결과).
- BE 테스트 21개가 통과했다. `migrate`·`be` 이미지를 다시 빌드해 재시작했으며, 컨테이너의 `alembic upgrade head`가 성공했다.

실행 명령(`BE/`에서):

```sh
uv run alembic upgrade head
uv run python -m scripts.import_incident_fixture --data ../plan/incidents/data          # 검증 + 변경 내역(롤백)
uv run python -m scripts.import_incident_fixture --data ../plan/incidents/data --apply  # 커밋
```

## 검증 기준

- `incident` 4행, `incident_candidate` 10행, 진단·최고 위험 각 4건
- `alarm` 10행 모두 `incident_id`·`peak_level`이 채워지고, 시각·CoF가 CSV와 일치하며, `is_active=NULL`이 유지된다. P5·P6는 사건·알람 0건이다.
- setpoint 264행과 시계열은 변하지 않는다.
- 우선순위 API가 P1 1.67 > P2 1.0 > P3 1.0 > P4 0.83을 반환한다.
- 적재 전후로 `DUMP.md` 절차에 따라 덤프를 남긴다.
