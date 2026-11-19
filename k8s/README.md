# 개발용 Rolling 배포와 운영 전환

`backend`, `db`, `frontend`, `ai` 디렉터리는 각각 별도 Argo CD Application의 Source Path다.
프로젝트·대상 namespace는 `u3-2`다. 자동화 연결 후 BE·FE·AI는 Git revision `gitops/dev`와 Auto Sync를 사용한다.
DB는 `main`과 Manual을 유지한다. 초기 main 연결에서 전환하는 절차는 [자동 배포 안내](../docs/gitops.md)를 따른다.
팀 도메인은 `u3-2.skala-us.com`, Ingress class는 `nginx`, TLS Secret은 `team-tls`를 사용한다.

## 이번 릴리스의 배포 대상

main CI에서 빌드·검증·업로드한 `056c253625e73639604ab088ca475cfa675f61d7`을 반영한다.
아래는 Git에 준비한 목표 설정이다. 실제 배포 상태는 Argo CD Sync와 검증 후 확인한다.

| 대상 | 고정 태그 | 개발 중 실행 |
| --- | --- | --- |
| BE Green | `056c253625e73639604ab088ca475cfa675f61d7` | 활성 1개, RollingUpdate |
| BE Blue | 같은 릴리스 | 0개, 향후 Blue-Green용 정의 유지 |
| AI Blue | `056c253625e73639604ab088ca475cfa675f61d7` | 활성 1개, RollingUpdate |
| AI Green | 같은 릴리스 | 0개, 향후 Blue-Green용 정의 유지 |
| FE | `056c253625e73639604ab088ca475cfa675f61d7` | 1개, RollingUpdate |
| DB | `pg17-ts2.32.0-v1` | 기존 StatefulSet 1개·PVC 유지 |

새 BE와 AI는 같은 통합 릴리스로 맞춘다. Service `backend`는 Green, `ai`는 Blue를 계속 선택한다.
개발 중에는 성공한 main CI가 활성 이미지 태그를 `gitops/dev`에 갱신하고 Argo Auto Sync가 새 Pod를 교체한다.
별도 Service 전환은 하지 않는다. 비활성 slot의 preview Service는 유지하지만 Pod가 0개라 엔드포인트가 없다.
키 등록과 실제 LLM 호출은 CI와 별도로 진행한다. AI의 키 없는 `/health`는 모델 연결 검증이 아니다.

새 BE의 알람 수신 기능은 `backend-secrets`의 `ALARM_INGEST_TOKEN`을 읽도록 선택적 참조를 연결했다.
이 Secret을 만들거나 토큰을 등록하는 작업은 수행하지 않는다. 토큰이 없으면 새 알람 수신 API는
503으로 비활성화되며 다른 조회 API의 기동을 막지 않는다. 토큰 등록은 별도 운영 설정이다.

새 BE는 `FORCE_SECURE_CHAT_COOKIE=true`로 HTTPS용 세션 쿠키를 명시한다. 두 slot에 이 값을 설정했다.
로컬 Compose는 기존처럼 요청 scheme에 따라 판단하며, 광범위한 forwarded-header 신뢰는 추가하지 않는다.
이 설정도 새 BE 이미지가 필요하므로, 이전 고정 이미지에 환경 변수만 추가해 수정이 완료됐다고 판단하지 않는다.

## 056c253 최초 통합 버전의 배포 기록

DB는 2026-11-19에 일회성 Job으로 `9a6d82f0c713`까지 반영했고 기존 운영 API 6개가 계속 정상임을 확인했다.
변경 전 백업과 실행 기록은 [마이그레이션 안내](migrations/README.md)에 있다. 같은 Job을 다시 생성하지 않는다.

1. 소스 변경은 PR 검사 후 main에 반영하고, main CI가 검증·업로드한 전체 SHA 태그를 확인한다.
2. 최초에는 `backend-green-image`, `ai-blue-image`, FE의 태그를 수동 갱신했다. 비활성 slot은 0개로 유지한다.
3. 새 BE의 추가 DB 마이그레이션은 이번 릴리스에서 완료했다. 후속 릴리스도 백업과 이전/새 코드 호환성을 확인하고 별도 작업으로 적용한다.
   이미지 기동이나 Argo Sync가 DB 스키마를 자동으로 갱신하지 않는다.
4. 최초에는 배포 설정 PR을 main에 반영하고 AI → BE → FE 순서로 수동 Sync했다. 후속 자동 배포는 위 안내의 `gitops/dev` 연결을 사용한다.
5. BE·AI·FE 모두 `maxSurge: 1`, `maxUnavailable: 0`, `minReadySeconds: 5`다. 이미지·readiness·API/화면을 확인한다.
   되돌릴 때는 활성 이미지 태그를 이전 버전으로 되돌려 Git에 반영하고 Sync한다. DB 변경은 별도 복구 대상이다.

AI를 처음 배포할 때는 Blue만 실행한다. 키가 필요한 모델 호출은 별도 키 등록 후 검증한다.
FE의 `/`와 BE의 `/api`, `/health`는 같은 호스트에서 각 Service로 전달한다. AI는 내부 Service만 사용한다.
URI rewrite나 regex를 추가하지 않는다.

## 자원

현재 팀 쿼터는 4 CPU / 8Gi다. 개발 모드의 limits 합계는 1.6 CPU / 2176Mi다.
BE·AI·FE의 교체용 Pod가 동시에 한 개씩 추가되면 2.7 CPU / 3328Mi다.
종료 중인 Pod의 자원 반환이 늦을 수 있으므로 현재 사용량도 확인한다. Job이나 추가 복제본 자원도 합산한다.

## 운영 전 Blue-Green 검증

현재 자동 발행은 활성 Green/Blue의 개발용 Rolling을 전제로 한다. 운영 Blue-Green으로 바꾸기 전에는
이 자동 발행을 중지하고 후보 검증·승격 방식에 맞게 갱신해야 한다.

1. 현재 활성 slot과 이미지를 먼저 확인한다. 비활성 slot에 후보 이미지를 지정하고 replicas를 1로 올린다.
2. 운영에서 수동 Blue-Green을 사용할 경우 각 slot의 전략을 `Recreate`로 맞춘다. 활성 Pod의 template은 유지한다.
3. 후보를 preview Service로 검증한다. 실제 트래픽·모델·오류·응답 시간과 복귀 동작을 확인한다.
4. 별도 Git 변경으로 active/preview Service selector를 교환하고 Sync한다. 이전 slot은 관찰·복귀 기간 동안 유지한다.

기존 정의를 다시 켜는 것만으로 운영 검증이 완료되지는 않는다. Blue-Green은 애플리케이션 전환이며 DB 복구를 대신하지 않는다.

세부 절차: [BE](backend/README.md), [DB](db/README.md), [FE](frontend/README.md), [AI](ai/README.md).
