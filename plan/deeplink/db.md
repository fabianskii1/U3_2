# DB 구현: Trend View 및 채팅 결과 영속화

## 선행 조사

- 실제 PostgreSQL 스키마, ORM, 마이그레이션 도구, `plant`·`equipment_group`·`equipment`·`sensor` 및 별칭 테이블의 키와 관계를 확인한다. 예시 ID를 실제 DB ID로 가정하지 않는다.
- 기존 `session`·`session_detail`·`chat_request_log` 구조와 결과 저장 방식, 삭제·보존 정책을 확인한 뒤 신규 테이블 또는 동등한 기존 구조 확장을 결정한다. 수정 대상 파일, 관계와 마이그레이션 방식을 기록한다.

## 기존 `session`·`session_detail`과 원본 질문 연결

- `session`은 채팅 세션이고 `session_detail`은 메시지다. `session_detail.type='user'`에 질문, `type='llm'`에 AI 응답을 저장한다. 별도 `chat_message` 테이블을 만들지 않는다.
- 기존 `chat_request_log.session_detail_id`는 완료된 AI 응답을 가리키며 원본 질문 ID는 기록하지 않는다. `session_detail.reply_to_session_detail_id` nullable 자기 참조 FK를 추가한다. DB 제약으로 같은 세션의 메시지만 참조하고, 응답(`type='llm'`)에서만 값을 채우도록 한다. 참조 대상이 사용자 메시지인지 검증하고 값을 기록하는 BE 작업은 별도다.

## `chat_result` (신규)

| 필드 | 역할 |
| --- | --- |
| `result_id` | UUID 기본 키 |
| `session_detail_id` | 결과를 생성한 `type='llm'` 메시지 FK |
| `result_type` | 현재는 `trend`만 허용; 다른 결과 유형은 별도 마이그레이션으로 확장 |
| `trend_view_id` | `trend_view.view_id`의 명시적 FK |
| `created_at` | 생성 시각 (`TIMESTAMPTZ`) |

- 한 AI 응답에 결과 여러 개를 연결할 수 있도록 1:N으로 설계한다.
- 유형별 범용 `resource_id`는 FK를 보장할 수 없어 두지 않는다. 현재는 `trend_view_id`로 참조 무결성을 보장한다. 보고서/설비 결과를 추가할 때 타입별 FK와 CHECK 제약을 확장한다.
- (`session_detail_id`, `trend_view_id`) 중복을 제한하고 `trend_view_id` 조회 인덱스를 둔다. 동일 View 연결 중복은 막지만 재시도로 새 View가 여러 개 생성되는 문제는 BE의 idempotency 처리도 필요하다.
- `chat_request_log`에 nullable `request_id` UUID와 (`session_id`, `request_id`) UNIQUE 제약을 추가한다. 기존 로그는 유지하고, 같은 채팅 요청의 재전송은 저장된 응답을 재생한다.

## `trend_view`

| 필드 | 역할 |
| --- | --- |
| `view_id` | 추측하기 어려운 비순차 UUID 기본 키 |
| `session_id` | View 소유 채팅 세션 FK; 현행 토큰 쿠키 접근 정책에 사용 |
| `plant_id` | 설비 그룹에서 확정한 플랜트 FK; 기존 View에도 역채움 |
| `equipment_group_id` | 조회 대상 설비 그룹의 실제 키 |
| `equipment_id` | 특정 설비의 실제 키; 그룹 전체 조회는 `NULL` 가능 |
| `config` | 버전이 있는 조회 설정 `JSONB` |
| `created_at` | 생성 시각 (`TIMESTAMPTZ`) |
| `expires_at` | 선택적 만료 시각 (`TIMESTAMPTZ`, nullable) |

- 기존 설비/그룹 구조를 재사용한다. 그룹 전체 조회를 `equipment_id = 'all'` 같은 가짜 DB 키로 저장하지 않는다. `NULL`이나 별도 scope 필드로 의미를 명확히 한다.
- 현재 인증은 세션 토큰 쿠키 기반이므로 `session_id`를 필수 FK로 저장한다. 향후 사용자/테넌트 인증이 추가되면 접근 범위를 재검토한다.
- 센서 ID는 실제 DB 조회 결과를 사용한다. `config.version`을 포함하고 상대 기간은 실행 시 확정한 절대 시각으로 저장한다. `최근 7일` 같은 원문은 추가 메타데이터로 보존할 수 있다.
- 생성 후 조회 설정은 불변 스냅샷이다. 조회 API나 화면 편집으로 원본을 수정하지 않는다.

### `config` 형식 예시

아래 ID와 시각은 형식 예시다.

```json
{
  "version": 1,
  "series": [
    { "sensorId": "VIB-01", "start": "2026-11-11T00:00:00+09:00", "end": "2026-11-18T00:00:00+09:00" },
    { "sensorId": "VOLT-01", "start": "2026-11-17T00:00:00+09:00", "end": "2026-11-18T00:00:00+09:00" },
    { "sensorId": "CURR-01", "start": "2026-11-17T00:00:00+09:00", "end": "2026-11-18T00:00:00+09:00" }
  ],
  "showAnomalies": false
}
```

- `start`/`end`는 타임존을 포함한 ISO 8601 문자열이며 `start < end`여야 한다. 서버 내부 UTC 정규화는 가능하다.
- 각 `series` 항목은 독립 조회 대상이다. 같은 센서의 복수 기간도 별도 항목으로 유지한다. 첫 센서만 저장하거나 센서별 기간을 공통 기간으로 합치지 않는다.
- `showAnomalies`는 이상 구간 표시 요청이며 탐지 결과 자체가 아니다.
- 센서 수, 기간 길이, JSON 크기와 조회량에 합리적인 제한을 둔다. FK, 참조 무결성 및 센서/설비 삭제 시 표시·보존 정책을 기존 스키마에 맞춘다.

## 딥링크와 보고서의 사용 관계

- `trend_view`에는 `deep_link`/`report` 같은 용도 타입을 두지 않는다. 한 조회 설정이 채팅 링크로 열리고 여러 보고서에서도 참조될 수 있으므로, 타입 하나로 사용처를 표현하면 실제 관계를 잃는다. `config.version`은 설정 형식 버전이며 용도 구분과 다르다.
- 채팅 결과가 만든 링크는 `chat_result(session_detail_id=<LLM 응답 ID>, result_type='trend', trend_view_id=view_id)`로 연결한다. 딥링크는 이 View를 여는 URL 표현이다. 기존 `session_detail.report_id`는 보고서 하나에 대한 선택적 FK이며 다중·다종 결과 연결을 대체하지 않는다.
- 보고서가 **같은 조회 조건**을 재사용할 때만 보고서와 View 사이에 명시적 FK를 둔다. 현재 `report_chart_attachments`는 `report_id`·`sensor_id`·조회 기간을 저장하므로, 기존 차트 첨부 의미에 맞으면 nullable `trend_view_id` FK를 추가하고 각 첨부 항목의 기간과 View의 관계를 정의한다. 보고서 하나에 여러 View를 독립적으로 연결해야 한다면 `report_trend_view(report_id, view_id, created_at)` 같은 연결 테이블을 사용한다.
- 보고서가 **조회된 실제 시계열 값이나 AI 분석 결과**를 과거 상태 그대로 보존해야 한다면 `trend_view`만 참조해서는 부족하다. 기존 `report_chart_attachments`를 확장하거나 별도 보고서 데이터/분석 스냅샷을 설계해 값·분석 시각·버전을 보존한다. 이 구현은 이번 딥링크 필수 범위와 분리한다.

## 완료 기준

- 마이그레이션 적용 후 기존 데이터가 유지된다.
- 단일 및 다중 센서, 서로 다른 기간, 그룹 전체 조회 설정이 저장된다.
- AI 응답의 여러 결과와 원본 사용자 질문을 추적할 수 있다.
- 참조 무결성, 인덱스, 재시도 시 중복 방지와 삭제·보존 정책을 검증한다.
- 보고서에서 조회 조건만 참조하는 경우와 데이터/분석 결과를 보존하는 경우를 구분해 선택한 관계를 기록한다.
