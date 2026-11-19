# 컴포넌트별 이미지 CI

BE·FE·AI·DB는 각각 별도 workflow로 검사한다. main에 대한 PR에서도 검사하며,
이미지의 Harbor 업로드는 main에서만 수행한다. 변경 경로로 실행 대상을 구분한다.

```text
관련 파일의 PR / main push / Run workflow
  → 기존 테스트
  → linux/amd64 이미지 빌드·로컬 로드
  → 실제 컨테이너 기동 검사
  → main 실행에서 성공한 이미지만 Harbor에 업로드
```

## 구성

| 대상 | Workflow | 자동 실행 경로 | 업로드 이미지 |
| --- | --- | --- | --- |
| BE | `.github/workflows/build.yaml` | `BE/**`, `AI/workflow/**`, 해당 workflow | `harbor.skala-us.com/u3-2/backend:<SHA>` |
| FE | `.github/workflows/build-fe.yaml` | `fe/**`, 해당 workflow | `harbor.skala-us.com/u3-2/frontend:<SHA>` |
| AI | `.github/workflows/build-ai.yaml` | `AI/**`, 해당 workflow | `harbor.skala-us.com/u3-2/ai:<SHA>` |
| DB | `.github/workflows/build-db.yaml` | `DB/docker/**`, 해당 workflow | `harbor.skala-us.com/u3-2/db:<SHA>` |

자동 검사는 main push와 main을 대상으로 하는 PR에 동작한다. PR에서는 검사·빌드·기동 확인까지만
수행하고 Harbor 로그인과 push는 건너뛴다. 수동 실행은 GitHub Actions의 Run workflow로 수행한다.
main 외 브랜치의 수동 검사도 업로드하지 않는다. main에서의 수동 실행은 검증 후 이미지를 업로드한다.

## 검사 범위

- BE: 고립된 테스트 DB에 확장·마이그레이션을 준비하고 전체 기존 pytest를 실행한다.
  새 스키마의 모든 마이그레이션을 적용하고 빌드한 운영 이미지에서 DB 연결과 조회 API를 확인한다.
  공유 `AI/workflow` 패키지를 Docker의 `agent_workflow` named build context로 포함한다.
  운영 DB나 덤프를 사용하지 않는다.
- FE: 기존 Vitest와 TypeScript/Vite 빌드를 확인하고, 운영 Nginx 이미지에서
  정적 파일·SPA 경로·테스트용 API 프록시를 확인한다.
- AI: frozen 의존성으로 기존 pytest·Ruff를 실행하고, 운영 이미지의 `/health`와
  키가 없을 때의 안전한 실패 응답을 확인한다. 실제 LLM 호출이나 API 사용료는 발생하지 않는다.
- DB: 임시 DB의 비밀번호 인증, TimescaleDB hypertable 읽기·쓰기,
  pgvector 거리 연산을 확인한다. 기존 데이터 디스크의 업그레이드 검사는 포함하지 않는다.

각 컴포넌트의 검사·빌드·기동 확인 중 하나가 실패하면 이후 Harbor 업로드는 실행하지 않는다.
CI용 컨테이너·네트워크·데이터는 검사 후 정리한다.

## Secret과 데이터

GitHub Actions에는 기존 `HARBOR_USERNAME`, `HARBOR_PASSWORD`를 사용한다.
`ARGOCD_CI_TOKEN`은 이 CI에서 사용하지 않는다.
Kubernetes의 DB 비밀번호, OpenAI API 키, AWS 키를 CI에 추가하지 않는다.
실제 `.env`, 덤프, 원시 센서 데이터, 위키 자료는 테스트 fixture나 이미지에 넣지 않는다.

## 운영 배포와의 관계

CI가 새 이미지를 올려도 현재 EKS Pod의 버전은 바뀌지 않는다.
현재 workflow는 매니페스트 수정, Argo CD Sync, Blue-Green 승격을 수행하지 않는다.

1. GitHub Actions 성공과 Harbor의 새 SHA 태그를 확인한다.
2. 현재 개발 모드에서는 활성 BE Green·AI Blue의 이미지 태그를 변경한다. FE는 `k8s/frontend/kustomization.yaml`의 이미지 태그를 변경한다.
3. Git에 반영하고 해당 Argo CD Application을 Sync한다.
4. Rolling 완료와 API·화면을 검증한다. 개발 모드에서는 Service selector를 전환하지 않는다.
5. DB는 백업과 PostgreSQL·확장 호환성을 먼저 확인하고 별도로 배포한다.

통합 소스의 AI는 설비 조회 API를 제공한다. `k8s/`에 고정된 이전 이미지가 이 새 코드를 포함하는 것은 아니다.
현재 이미지 목록과 배포 전 마이그레이션·새 태그 반영 순서는 [배포 안내](../k8s/README.md)를 따른다.
키 없는 CI 통과는 실제 모델 호출이나 응답 품질 검증을 뜻하지 않는다.

향후 운영 Blue-Green에서는 비활성 slot에 후보를 배포·검증하고 별도 Git 변경으로 Service를 전환한다.
현재 개발 설정과 전환 절차는 배포 안내를 따른다.

## FE 실행 주소

FE 이미지는 `BACKEND_UPSTREAM`으로 API 프록시 대상을 지정한다.
기본값 `backend:8000`은 EKS Service 이름에 맞추고, Compose는 `be:8000`으로 덮어쓴다.
브라우저는 상대 경로 `/api`를 사용한다. EKS Ingress의 `/api` 경로는 BE Service로 직접 연결한다.

첫 배포의 Application 설정과 검증 절차는 [FE 배포 안내](../k8s/frontend/README.md),
[AI 배포 안내](../k8s/ai/README.md)를 참고한다. AI는 내부 Service를 사용하며, 모델 키 등록과
실제 모델 호출 검증은 이미지 CI의 키 없는 기동 검사와 별도로 수행한다.

## 참고

- [Docker: 검사 후 이미지 업로드](https://docs.docker.com/build/ci/github-actions/test-before-push/)
- [GitHub Actions: workflow 문법과 경로 필터](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
