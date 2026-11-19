# 통합 버전 056c253의 일회성 DB 마이그레이션

이 디렉터리는 기존 Argo CD Application의 Source Path에 포함하지 않는다.
Job 생성은 운영 DB에 실제 변경을 적용하므로, 변경 내용을 확인한 뒤 별도 실행한다.
BE·DB 컨테이너의 시작 명령이나 반복 Sync에 마이그레이션을 묶지 않는다.

- 이미지: main CI가 검증·업로드한 BE `056c253625e73639604ab088ca475cfa675f61d7`
- 현재 확인한 revision: `d4e6c2a9b105`
- 적용 대상: `9a6d82f0c713`
- 변경: 알람 상태·CoF와 채팅 문맥 컬럼, 알람 수신 테이블, 공정 유형 컬럼, CDU 이름·별칭 정리
- 사전 확인: 추가 대상 컬럼·테이블은 현재 없고, 삭제 조건에 해당하는 기존 펌프 번호 별칭은 0건
- 변경 전 논리 백업: DB 볼륨 내부 `/var/lib/postgresql/data/backups/pre-056c253-20261119.dump` (약 194.8MiB)
- 백업 SHA256: `60a9f967eb63687af5943fc16d2f78d65082c601556011eb9a90221401494297`
- 아카이브 전체 읽기 검증은 통과했다. 이는 별도 DB로의 복원 시험이나 볼륨 장애 대비 백업을 의미하지 않는다.

Job은 실패 시 자동 재시도하지 않는다. 먼저 로그와 DB revision을 확인하고 후속 조치를 결정한다.
`process_type` 마이그레이션은 자동 downgrade를 지원하지 않으므로, DB 복귀는 백업을 이용한 별도 절차가 필요하다.
Service의 이전 이미지로 전환하는 것만으로 DB 변경이 되돌아가지는 않는다.

실행이 승인되면 이 Job을 한 번 생성하고 완료·로그·DB revision을 확인한다.
실행 전후와 작업 중 구버전 운영 BE의 `/health`, `/api/hierarchy`, `/api/equipment/P1`도 확인한다.

```bash
kubectl --context u3-2 -n u3-2 create -f k8s/migrations/backend-056c253.yaml
kubectl --context u3-2 -n u3-2 logs job/backend-migrate-056c253
```

DB 확인 후 AI Blue를 먼저 기동하고 BE Green을 Rolling으로 갱신·검증한다. Service selector는 유지하고
FE는 그 뒤에 검증한다. 개발 중 비활성 BE Blue·AI Green은 0개로 두며 기존 정의는 보존한다.
AI 키 등록은 보류한다. 키 없는 기동·확정 별칭 조회와 모델 호출 검증을 구분한다.

## 2026-11-19 실행 기록

`backend-migrate-056c253` Job은 성공 1회로 완료됐다. DB revision `9a6d82f0c713`, 새 컬럼 4개,
`alarm_intake` 테이블, CDU 이름·공정 유형 반영과 기존 펌프 번호 별칭 0건을 확인했다.
기존 Green을 통한 HTTPS 조회 API 6개는 모두 200이었다. 백업은 DB 볼륨에 유지한다.
