# BE 구현: Trend View API와 결과 연결

## 선행 조사

- 실제 FastAPI 라우터, 인증/인가, ORM, `session`·`session_detail` 저장 흐름, 센서 조회 API 및 테스트 규칙을 확인한다. 아래 경로는 제안이며 기존 REST 관례에 맞춰 조정한다.
- [DB 스키마](db.md)의 실제 키/소유권 필드와 [AI Tool](ai.md)의 실행 컨텍스트를 확인하고 수정 파일, 데이터 흐름, 유효성 검사 및 권한 정책을 기록한다.

## `POST /api/trend-views`

- 요청: 설비 그룹 ID, 선택적 설비 ID, `sensorId/start/end` 목록, `showAnomalies`, 결과를 연결할 `session_detail`의 LLM 응답 ID 또는 검증 가능한 채팅 실행 컨텍스트.
- 인증, 채팅 접근 권한, 설비/센서의 존재와 소속 관계를 검증한다. 센서 수, 기간, JSON 크기와 예상 조회량을 제한한다. 각 시간은 타임존이 있고 `start < end`여야 한다.
- `trend_view` 저장과 `chat_result` 연결은 가능한 한 한 DB 트랜잭션에서 처리한다. 저장 실패 시 깨진 링크나 고아 결과를 반환하지 않는다.
- 실제 채팅 AI 처리에서는 클라이언트가 보낸 `session_detail_id`를 무조건 신뢰하지 않고 서버에서 확인된 실행 컨텍스트를 우선한다. 현재 `chat_request_log.session_detail_id`는 AI 응답 ID이고 질문 ID는 저장하지 않으므로 [DB 설계](db.md)의 명시적 질문·응답 연결을 적용한다. 채팅 요청의 `request_id`는 입력받지만 현재 저장하지 않으므로, 재시도 방지에 쓰려면 영속화하거나 별도 idempotency 키를 둔다.
- DB가 발급한 비순차 UUID로 URL을 만들고 조회 조건이나 민감한 메타데이터는 URL에 넣지 않는다. 모델이 URL 인코딩 문자열을 직접 만들지 않는다.

응답 예시:

```json
{
  "viewId": "e6d7f434-5d9a-4e6d-b4c4-0f72fbb74092",
  "url": "/trend?viewId=e6d7f434-5d9a-4e6d-b4c4-0f72fbb74092"
}
```

## `GET /api/trend-views/{view_id}`

- 인증과 기존 로그인/채팅방/테넌트·설비 접근 정책을 적용한다. UUID를 아는 것만으로 접근을 허용하지 않는다.
- 존재하지 않거나 권한이 없는 View, 만료된 View를 적절한 HTTP 상태로 처리하고 권한 여부 노출은 기존 정책을 따른다.
- 저장된 `config.series` 전체를 원형대로 반환한다. 읽기 동작은 불변 스냅샷을 수정하지 않는다.

## `GET /api/chat/messages/{session_detail_id}/results`

- `session_detail` 메시지와 소속 `session`의 접근 권한을 확인하고, 한 AI 응답에 연결된 여러 결과를 반환한다. 경로는 현재 `/api/chat` 라우터 관례에 맞춘 제안이다.
- 신규 질문·응답 연결로 원본 사용자 질문까지 추적 가능해야 한다.

## 일반 트렌드 조회와 무결성

- `/trend?plant_id=...&unit_id=...&equip_id=...`에서 센서 ID가 없을 때 설비의 전체 센서를 조회할 수 있도록 기존 설비/센서 API 계약을 확인하고 필요한 부분만 확장한다.
- `viewId`는 저장 설정 조회 경로이며 일반 URL의 `plant_id`·`unit_id`·`equip_id`·`sensor_id`와 구분한다. 그룹 전체 View(`equipment_id` 없음)와 특정 설비의 전체 센서 일반 URL도 구분한다.
- View의 사용처는 `trend_view` 타입 필드가 아니라 채팅 결과 또는 보고서와의 연결 관계로 판별한다. 보고서가 View를 참조하는 기능을 추가할 때는 [DB 설계](db.md)의 조회 조건 참조와 실제 데이터 스냅샷 구분을 따른다.
- 삭제·비활성화된 센서/설비의 응답 정책을 정한다. N+1 쿼리와 불필요한 전체 시계열 조회를 피한다.

## 완료 기준

- 생성/조회/메시지별 결과 API의 요청·응답 및 권한을 검증한다.
- 다른 사용자의 View, 잘못된/없는/만료된 ID, 잘못된 설비·센서 관계, 과도한 기간·요청량을 안전하게 처리한다.
- 트랜잭션 실패와 재시도 후 중복 결과 또는 깨진 링크가 없다.
- API 스키마/단위/통합 테스트 결과와 남은 위험을 기록한다.
