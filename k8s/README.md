# 배포 설정과 통합 소스의 버전

`backend`, `db`, `frontend`, `ai` 디렉터리는 각각 별도 Argo CD Application의 Source Path다.
프로젝트·대상 namespace는 `u3-2`, Git revision은 `main`, 동기화는 수동이다.
팀 도메인은 `u3-2.skala-us.com`, Ingress class는 `nginx`, TLS Secret은 `team-tls`를 사용한다.

## 이번 릴리스의 배포 대상

main CI에서 빌드·검증·업로드한 `056c253625e73639604ab088ca475cfa675f61d7`을 반영한다.
아래는 Git에 준비한 목표 설정이다. 실제 배포 상태는 Argo CD Sync와 검증 후 확인한다.

| 대상 | 고정 태그 | 연결 |
| --- | --- | --- |
| BE Blue | `056c253625e73639604ab088ca475cfa675f61d7` | 새 버전 preview |
| BE Green | `67117a2d12d688e030080e4c20e965bcad85eb36` | active |
| DB | `pg17-ts2.32.0-v1` | 기존 PVC |
| FE | `056c253625e73639604ab088ca475cfa675f61d7` | 새 화면 버전 |
| AI Blue·Green | `056c253625e73639604ab088ca475cfa675f61d7` | 설비 조회, 최초 운영은 Blue |

새 BE와 AI는 같은 통합 릴리스로 맞춘다. 운영 BE Green은 후보 Blue 검증과 별도 전환까지 유지한다.
키 등록과 실제 LLM 호출은 사용자 요청으로 보류한 상태다. AI의 키 없는 `/health`는 모델 연결 검증이 아니다.

새 BE의 알람 수신 기능은 `backend-secrets`의 `ALARM_INGEST_TOKEN`을 읽도록 선택적 참조를 연결했다.
이 Secret을 만들거나 토큰을 등록하는 작업은 수행하지 않는다. 토큰이 없으면 새 알람 수신 API는
503으로 비활성화되며 다른 조회 API의 기동을 막지 않는다. 토큰 등록은 별도 운영 설정이다.

새 BE는 `FORCE_SECURE_CHAT_COOKIE=true`로 HTTPS용 세션 쿠키를 명시한다. 두 slot에 이 값을 설정했다.
로컬 Compose는 기존처럼 요청 scheme에 따라 판단하며, 광범위한 forwarded-header 신뢰는 추가하지 않는다.
이 설정도 새 BE 이미지가 필요하므로, 이전 고정 이미지에 환경 변수만 추가해 수정이 완료됐다고 판단하지 않는다.

## 새 통합 버전 배포 순서

DB는 2026-11-19에 일회성 Job으로 `9a6d82f0c713`까지 반영했고 기존 운영 API 6개가 계속 정상임을 확인했다.
변경 전 백업과 실행 기록은 [마이그레이션 안내](migrations/README.md)에 있다. 같은 Job을 다시 생성하지 않는다.

1. 통합 PR에서 네 컴포넌트 검사를 통과시키고 main에 반영한다.
2. main CI에서 필요한 새 이미지를 빌드·검증·업로드한다. 해당 실행의 전체 SHA 태그를 확인한다.
3. 새 BE의 추가 DB 마이그레이션은 이번 릴리스에서 완료했다. 후속 릴리스도 백업과 이전/새 코드 호환성을 확인하고 별도 작업으로 적용한다.
   이미지 기동이나 Argo Sync가 DB 스키마를 자동으로 갱신하지 않는다.
4. BE·AI는 실제 비운영 slot의 태그만 바꾸고, FE는 새 태그를 지정한다. DB 이미지나 PVC는 이 변경과 분리한다.
5. 수동 Sync 후 이미지·readiness·API/화면을 검증하고 별도 Git 변경으로 운영 slot을 전환한다.

AI를 처음 배포할 때는 새 설비 조회 이미지로 두 slot을 맞춘다. 키가 필요한 모델 호출은 별도 키 등록 후 검증한다.
FE의 `/`와 BE의 `/api`, `/health`는 같은 호스트에서 각 Service로 전달한다. AI는 내부 Service만 사용한다.
URI rewrite나 regex를 추가하지 않는다.

## 자원

현재 팀 쿼터는 4 CPU / 8Gi다. 복구된 BE 두 Pod·DB·FE 한 Pod·AI 두 Pod의 limits 합계는
2.6 CPU / 3200Mi이며, FE 교체용 Pod 한 개를 더하면 2.7 CPU / 3328Mi다.
마이그레이션 Job이나 추가 복제본을 만들 때는 해당 자원도 합산한다.

세부 절차: [BE](backend/README.md), [DB](db/README.md), [FE](frontend/README.md), [AI](ai/README.md).
