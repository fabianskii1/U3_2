# BE Blue-Green 배포 설정

현재 고정 태그와 새 통합 코드의 배포 순서는 [상위 배포 안내](../README.md)를 먼저 확인한다.

AI와 같은 수동 Blue-Green 구성이다. Deployment 두 개와 운영·검증 Service를 사용한다.
Argo CD가 Git의 설정을 반영하며 Argo Rollouts나 추가 CRD는 설치하지 않는다.
자동 검증·승격·오류 시 자동 복귀 기능은 포함하지 않는다.

## 현재 준비 단계

BE 소스 코드는 변경하지 않았다. 이 묶음은 Blue/Green Deployment·Service·외부 Ingress를 포함한다.
DB와 Secret은 `k8s/db` 절차로 별도 준비하고 업무 API 검증 전 덤프 복원·스키마 상태를 확인한다.
Git push, Argo CD Application 생성 및 실제 배포도 이 파일 작성만으로 수행되지 않는다.
먼저 DB와 Secret을 준비해야 두 BE Pod가 정상 실행되고 Ready 상태가 될 수 있다.
이미지 별칭은 Kustomize가 실제 Harbor 주소로 바꾸므로 개별 Deployment 파일을 직접 적용하지 않는다.

```bash
kubectl kustomize k8s/backend
```

준비가 끝난 뒤 Argo CD Application의 Source Path는 `k8s/backend`를 사용한다.

## 파일과 초기 연결

| 파일 | 역할 |
| --- | --- |
| `deployment-blue.yaml` | Blue 실행 영역, Pod 1개 |
| `deployment-green.yaml` | Green 실행 영역, Pod 1개 |
| `service.yaml` | 운영 `backend`와 검증 `backend-preview`의 대상 선택 |
| `ingress.yaml` | 팀 HTTPS 도메인의 `/api`와 `/health`를 운영 Service에 연결 |
| `kustomization.yaml` | 배포 파일 묶기와 각 영역의 이미지 버전 관리 |

```text
운영 경로: backend:8000         → backend-green
검증 경로: backend-preview:8000 → backend-blue

backend-blue  ─┐
              ├→ db:5432 → 같은 PostgreSQL
backend-green ─┘
```

현재 두 영역에는 각각 확인된 이전 BE 이미지 태그가 고정돼 있다.
Blue/Green은 영역 이름이며 운영 여부는 Service `backend`의 `spec.selector.slot`으로 정한다.
Deployment의 selector에도 `slot`을 넣어 서로의 Pod를 관리하지 않도록 했다.
각 Deployment의 `Recreate`는 해당 영역의 Pod 교체 방식이다. Blue-Green 전환은 Service가 담당한다.
운영 영역에 새 이미지를 직접 반영하면 해당 영역의 교체 동안 중단될 수 있다.

## 팀 HTTPS 도메인 연결

Ingress는 기존 `u3-2-backend` Application의 Source Path `k8s/backend`에 포함한다.
별도 Application이나 LoadBalancer, Ingress Controller, DNS, 인증서를 새로 만들지 않는다.
가이드에서 제공한 Nginx 클래스 `nginx`, 도메인 `u3-2.skala-us.com`, TLS Secret `team-tls`를 사용한다.
팀 도메인은 가이드 기준 캠퍼스 네트워크에서 접속한다. 이 파일이 별도의 접속 허용 IP를 설정하지는 않는다.

| 요청 | 전달 대상 |
| --- | --- |
| `https://u3-2.skala-us.com/api/...` | 운영 `backend:8000`의 같은 `/api/...` 경로 |
| `https://u3-2.skala-us.com/health` | 운영 `backend:8000`의 `/health` |

BE는 `/api/hierarchy` 등 `/api`가 포함된 경로를 이미 정의하고 있으므로 URI rewrite를 하지 않는다.
채팅의 SSE 응답을 위해 proxy buffering을 끈다. `backend-preview`는 외부에 연결하지 않는다.
`/`, `/docs`, `/openapi.json`은 이 Ingress에 포함하지 않는다. `/`의 FE 연결은 별도 구성한다.
같은 호스트의 다른 Ingress에 rewrite·regex를 추가하면 Nginx의 호스트 전체 경로 매칭에 영향을 줄 수 있으므로
AI·FE Ingress 추가 시 기존 API·상태 확인 경로도 다시 검증한다.

저장소 루트에서 설정을 확인한 뒤 Git에 반영한다. 아래 명령은 사용자가 실행할 때 반영된다.

```bash
kubectl kustomize k8s/backend
git add k8s/backend/ingress.yaml k8s/backend/kustomization.yaml k8s/backend/README.md
git diff --cached --stat
git commit -m "deploy: route backend API through team HTTPS ingress"
git push origin main
```

Argo CD의 기존 `u3-2-backend` App에서 Refresh 후 Sync → Synchronize한다.
Ingress를 추가하는 작업이라 BE Deployment의 Pod template이나 운영 slot은 변경하지 않는다.
현재 CI는 관련 경로의 main push와 PR에서 검증하며, main 실행만 이미지를 업로드한다. 경로 설정만 복구할 때는
Kustomize에서 지정한 기존 이미지 태그를 그대로 사용한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 get ingress backend

curl --fail-with-body https://u3-2.skala-us.com/health
curl --fail-with-body https://u3-2.skala-us.com/api/hierarchy
```

두 요청이 정상 동작하면 이 경로에는 PC의 port-forward가 필요하지 않다.
`/health`는 DB 연결만 확인하므로 업무 데이터 조회는 `/api/hierarchy`로 별도 확인한다.
채팅의 BE·AI 버전 호환과 실제 모델 연결은 이 Ingress 확인과 별도로 검증한다.

## 버전 교체 순서

1. Git과 실제 Service에서 현재 운영 slot을 확인한다.
2. 새 BE 이미지를 빌드해 Harbor에 올린다. 현재 CI는 업로드까지만 수행한다.
3. `kustomization.yaml`에서 비운영 영역의 이미지 태그만 바꾸어 Git에 반영한다.
   운영 이미지, 운영 환경 설정, Service selector는 이 변경에 포함하지 않는다.
4. Argo CD 동기화 후 비운영 Pod의 준비 상태와 실제 API 동작을 검증한다.
5. 검증이 끝나면 별도 커밋에서 운영·검증 Service의 slot을 서로 바꾸고 동기화한다.
6. 이전 Pod와 이미지를 유지한 채 운영 상태와 처리 중인 요청을 확인한다.
   문제가 있으면 Service 전환 커밋을 되돌려 기존 영역으로 복귀한다.

Blue에서 Green으로 전환할 때 `service.yaml`에서 바꿀 값은 다음과 같다.

| Service | 전환 전 | 전환 후 |
| --- | --- | --- |
| `backend` | `slot: blue` | `slot: green` |
| `backend-preview` | `slot: green` | `slot: blue` |

기존 연결은 Service 변경만으로 새 Pod로 이동하지 않는다. 이전 Pod를 즉시 종료하지 않고
엔드포인트 반영, 처리 중인 요청, 운영 관찰 및 복귀 기간을 고려해 유지한다.
실제 트래픽 시험 전에는 무중단 전환이 검증됐다고 판단하지 않는다.

## DB와 검사 조건

- 공통 Secret `db-credentials`의 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 읽는다.
  Secret 값은 Git에 기록하지 않는다. DB 주소는 내부 Service `db:5432`를 사용한다.
- Blue와 Green은 같은 DB를 사용한다. Green에서 실행한 쓰기도 같은 DB에 반영된다.
  실제 사용자 데이터에 영향을 주지 않는 검증 요청과 테스트 데이터를 정해야 한다.
- DB 스키마 변경은 이전·새 BE 버전 모두와 호환돼야 한다. 마이그레이션은 별도 작업으로 관리하고
  각 영역의 시작 명령에 중복 실행을 넣지 않는다. Service 복귀는 DB 변경이나 쓰기를 되돌리지 않는다.
- `/health`는 DB의 `SELECT 1`까지 확인한다. 업무 테이블, 데이터, AI 연동의 정상 동작을 보장하지 않는다.
  DB 마이그레이션과 대표 API 검증은 별도로 필요하다.
- 고정된 이전 이미지와 현재 소스의 API는 구분해야 한다. 새 BE·AI를 함께 배포할 때는 상위 배포 안내의 새 태그·마이그레이션 절차를 따른다.
- 준비 상태는 HTTP `/health`, 시작·실행 상태는 TCP 8000으로 검사한다.
  DB 장애만으로 BE 재시작이 반복되지 않도록 구분했다. TCP 검사는 HTTP 처리 전체의 정상 여부를 보장하지 않는다.

## 자원과 운영 제약

- BE Pod당 request `100m / 256Mi`, limit `500m / 512Mi`다.
  두 개 합계는 request `200m / 512Mi`, limit `1 CPU / 1Gi`다. 초기 설정이며 처리량 보장은 아니다.
- 현재 AI 두 영역의 CPU limit 합계도 1 CPU다. 팀 쿼터는 4 CPU / 8Gi이며,
  BE·AI·DB·FE의 limits 합계는 기본 2.6 CPU다. 마이그레이션과 추가 복제본 자원도 합산한다.
  비운영 영역을 0개로 두면 사용량은 줄지만 검증·전환·복귀 전에 다시 기동하고 확인해야 한다.
- 비밀번호 변경은 두 영역에 영향을 준다. 환경변수는 Pod 시작 때 읽히므로 별도의 교체 계획이 필요하다.
- Argo CD Self Heal을 켠 경우 포털에서 앱을 끄기 전에 자동 동기화를 끄거나
  두 Deployment의 `replicas`를 Git에서 모두 0으로 변경해야 한다.

## 참고

- [Kubernetes Service selector](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Nginx Ingress annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Kubernetes Deployment Recreate](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#recreate-deployment)
- [Argo Rollouts의 Blue-Green 개념](https://argo-rollouts.readthedocs.io/en/stable/features/bluegreen/)
