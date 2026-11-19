# 개발 환경의 자동 이미지 배포

```text
main에 코드·컴포넌트 배포 YAML 반영
  → 컴포넌트 CI의 테스트·이미지 검사·Harbor push 성공
  → promote 작업이 해당 컴포넌트 설정과 SHA 태그를 gitops/dev에 커밋
  → Argo CD가 gitops/dev를 읽고 Auto Sync
  → 활성 Deployment의 RollingUpdate
```

`main`에는 PR과 승인 1명이 필요한 규칙이 있다. CI는 이 규칙을 변경하거나 우회하지 않는다.
사용자가 선택한 `gitops/dev` 배포 브랜치는 CI가 일반 push로 갱신하며, 소스·배포 설정의 검토는 main PR에서 한다.

## 최초 연결

1. 자동화 PR을 검토·승인·병합한다. 이번 PR은 세 컴포넌트 workflow를 변경하므로 main CI가 각각 실행된다.
2. BE·FE·AI의 main CI에서 `build`와 `promote / publish` 성공을 확인한다. 이때 `gitops/dev`가 자동 생성된다.
3. Argo CD 웹에서 아래 기존 Application의 Source `Target Revision`을 `gitops/dev`로 변경한다. Repository와 Path는 유지한다.

   | Application | Path | Revision | Sync Policy |
   | --- | --- | --- | --- |
   | `u3-2-backend` | `k8s/backend` | `gitops/dev` | Automated |
   | `u3-2-ai` | `k8s/ai` | `gitops/dev` | Automated |
   | `u3-2-frontend` | `k8s/frontend` | `gitops/dev` | Automated |
   | `u3-2-db` | `k8s/db` | `main` 유지 | Manual 유지 |

4. 각 앱의 Refresh 후 Synced/Healthy, 실제 이미지 SHA, API·화면을 확인한다. 기존 Application을 재생성하지 않는다.

처음에는 Argo의 Auto Sync만 켜도 된다. Prune은 Git에서 사라진 리소스를 삭제하는 별도 옵션이다.
Self Heal을 켜면 포털에서 앱을 꺼도 Git의 replicas로 다시 올라올 수 있으므로, 종료 시 자동 동기화도 함께 중지한다.

## CI가 변경하는 범위

| 컴포넌트 | main에서 가져오는 설정 | 갱신하는 이미지 별칭 |
| --- | --- | --- |
| BE | 빌드한 SHA의 `k8s/backend/` | `backend-green-image` |
| AI | 빌드한 SHA의 `k8s/ai/` | `ai-blue-image` |
| FE | 빌드한 SHA의 `k8s/frontend/` | `frontend-image` |

- 현재 개발용 Rolling 구성에 맞춘 자동화다. 비활성 slot을 기동하거나 Service selector를 교환하지 않는다.
- 이미지 검사를 통과하고 Harbor push까지 성공한 main 실행만 배포를 발행한다. PR 실행은 쓰기 권한 없이 검사만 한다.
- 새 패키지·PAT·Argo 토큰·AWS 키 없이 publish job의 `contents: write`와 기본 `GITHUB_TOKEN`을 사용한다. 빌드 job은 `contents: read`를 유지한다.
- 배포 브랜치가 없으면 main에서 시작한다. 이후에는 해당 컴포넌트 디렉터리만 교체하고 다른 컴포넌트의 배포 태그를 보존한다. DB 디렉터리와 Secret은 갱신하지 않는다.
- source SHA 이후 main에 해당 소스·workflow·배포 YAML 변경이 있으면 오래된 빌드를 건너뛴다. 더 최신 이미지가 이미 발행된 경우에도 이전 SHA로 덮어쓰지 않는다.
- 동시에 push가 발생하면 최신 배포 브랜치를 다시 읽고 최대 5회 재시도한다. Force push와 작업 checkout 변경은 사용하지 않는다.
- 컴포넌트별 발행이므로 FE·BE·AI의 원자적 동시 전환을 보장하지 않는다. 상호 호환되지 않는 API 변경은 별도 릴리스 순서를 정한다.

main의 컴포넌트 YAML 변경도 해당 CI를 실행한다. `gitops/dev`에는 직접 기능 코드를 개발하지 않는다.
main의 고정 태그는 초기 기준이며, 자동화 연결 후 현재 적용 태그는 `gitops/dev`와 실제 Pod에서 확인한다.

## 실패·복귀

- 테스트·Harbor push가 실패하면 기존 배포를 유지한다. 배포 push가 실패하면 CI 실패 로그를 확인하고 성공한 source SHA의 workflow를 재실행한다.
- `Skip ... superseded`는 새 소스의 CI를 기다린다는 뜻이다. 이전 run을 반복 실행해도 최신 버전을 덮어쓰지 않는다.
- 긴급 이미지 복귀는 해당 앱의 Auto Sync를 잠시 중지하고, `gitops/dev`에서 활성 태그를 검증된 이전 SHA로 변경해 수동 Sync한다. 복귀 상태가 검증될 때까지 해당 컴포넌트의 자동 발행도 중지한다. 안정화 후 main에 수정 코드를 반영해 다시 자동 발행한다.
- DB 이미지·PVC·데이터 복구와 스키마 마이그레이션은 자동 발행 대상이 아니다. DB 스키마 변경이 필요한 BE는 배포 전에 별도 마이그레이션과 구버전 호환성을 확인한다. 이미지 복귀가 DB 쓰기를 되돌리지는 않는다.

검증 명령: `python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v`.
테스트는 임시 로컬 Git 저장소만 사용하며 실제 GitHub·Harbor·EKS·LLM에는 접근하지 않는다.
