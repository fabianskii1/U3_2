# BE 개발용 Rolling 배포

현재 고정 태그와 새 통합 코드의 배포 순서는 [상위 배포 안내](../README.md)를 먼저 확인한다.

개발 중에는 운영 Service가 선택하는 Green Deployment만 Pod 1개로 실행하고 RollingUpdate로 교체한다.
Blue Deployment는 0개로 유지한다. 기존 두 Deployment와 Service 정의는 향후 수동 Blue-Green 전환에 사용한다.
Argo CD에서 Git 설정을 수동 Sync하며, Argo Rollouts나 추가 CRD는 사용하지 않는다.

## 현재 준비 단계

이 묶음은 Blue/Green Deployment·Service·외부 Ingress를 포함한다.
DB와 `db-credentials`는 이미 배포돼 있으며, 이번 릴리스의 DB 마이그레이션도 완료했다.
실행 기록은 [마이그레이션 안내](../migrations/README.md)를 따른다. 완료한 Job을 다시 실행하지 않는다.
설정 PR 병합 후 기존 Argo CD Application을 Sync해야 실제 BE 버전이 바뀐다.
이미지 별칭은 Kustomize가 실제 Harbor 주소로 바꾸므로 개별 Deployment 파일을 직접 적용하지 않는다.

```bash
kubectl kustomize k8s/backend
```

준비가 끝난 뒤 Argo CD Application의 Source Path는 `k8s/backend`를 사용한다.

## 파일과 초기 연결

| 파일 | 역할 |
| --- | --- |
| `deployment-blue.yaml` | 비활성 Blue, Pod 0개 |
| `deployment-green.yaml` | 활성 Green, Pod 1개, RollingUpdate |
| `service.yaml` | 운영 `backend`와 검증 `backend-preview`의 대상 선택 |
| `ingress.yaml` | 팀 HTTPS 도메인의 `/api`와 `/health`를 운영 Service에 연결 |
| `kustomization.yaml` | 배포 파일 묶기와 각 영역의 이미지 버전 관리 |

```text
운영 경로: backend:8000         → backend-green
검증 경로: backend-preview:8000 → backend-blue (개발 중 Pod 0개)

backend-blue  ─┐
              ├→ db:5432 → 같은 PostgreSQL
backend-green ─┘
```

이번 릴리스는 main CI가 검증·업로드한 `056c253625e73639604ab088ca475cfa675f61d7` 태그를 사용한다.
Blue/Green은 영역 이름이며 운영 여부는 Service `backend`의 `spec.selector.slot`으로 정한다.
Deployment의 selector에도 `slot`을 넣어 서로의 Pod를 관리하지 않도록 했다.
활성 Green은 `maxSurge: 1`, `maxUnavailable: 0`, `minReadySeconds: 5`다.
교체 중에는 새 Pod가 준비될 때까지 기존 Pod를 유지한다. 교체 전후 코드가 같은 DB와 API 계약에 호환돼야 한다.
이 설정만으로 처리 중인 채팅·SSE 요청의 무중단을 보장하지는 않는다.
비활성 Blue의 `Recreate`는 Pod 0개인 현재 운영 경로에 영향을 주지 않는다.

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

저장소 루트에서 렌더링한 뒤 설정 PR을 검토·병합한다.

```bash
kubectl kustomize k8s/backend
kubectl --context u3-2 -n u3-2 apply --dry-run=server -k k8s/backend
```

Argo CD의 기존 `u3-2-backend` App에서 Refresh 후 Sync → Synchronize한다.
이번 변경은 기존 Ingress·Service selector를 유지하고 활성 Green의 이미지를 갱신한다.
현재 CI는 관련 경로의 main push와 PR에서 검증하며, main 실행만 이미지를 업로드한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 get ingress backend

curl --fail-with-body https://u3-2.skala-us.com/health
curl --fail-with-body https://u3-2.skala-us.com/api/hierarchy
```

두 요청이 정상 동작하면 이 경로에는 PC의 port-forward가 필요하지 않다.
`/health`는 DB 연결만 확인하므로 업무 데이터 조회는 `/api/hierarchy`로 별도 확인한다.
채팅의 BE·AI 버전 호환과 실제 모델 연결은 이 Ingress 확인과 별도로 검증한다.

## 개발 중 버전 교체

1. Git과 실제 Service에서 현재 운영 slot을 확인한다.
2. 새 BE 이미지를 빌드해 Harbor에 올린다. 현재 CI는 업로드까지만 수행한다.
3. `kustomization.yaml`의 `backend-green-image` 태그를 새 전체 SHA로 변경한다. Blue는 0개, Service는 Green을 유지한다.
4. 설정 PR 병합 후 기존 `u3-2-backend` Application에서 Refresh → Sync → Synchronize한다.
5. 아래 상태와 실제 API를 확인한다. Argo Healthy와 `/health`만으로 업무·AI 연동 검증을 대신하지 않는다.

   ```bash
   kubectl --context u3-2 -n u3-2 rollout status deployment/backend-green --timeout=180s
   kubectl --context u3-2 -n u3-2 get deployment backend-green backend-blue
   curl --fail-with-body https://u3-2.skala-us.com/health
   curl --fail-with-body https://u3-2.skala-us.com/api/hierarchy
   ```

문제가 있으면 Green의 이미지 태그를 이전 버전으로 되돌리는 PR을 반영하고 다시 Sync한다.
`kubectl rollout undo`만 사용하면 Git과 상태가 달라진다. 이미지 복귀는 DB 스키마·쓰기 결과를 취소하지 않는다.

## 향후 수동 Blue-Green

운영 검증 시 Blue에 후보 이미지를 지정하고 replicas를 1로 올린다. 각 slot의 전략을 `Recreate`로 맞추되
현재 활성 Green의 Pod template은 유지한다. `backend-preview`로 후보 기능·호환성을 검사한 뒤
별도 Git 변경으로 Service selector만 바꾼다.

현재 Green에서 후보 Blue로 전환할 때의 값은 다음과 같다.

| Service | 전환 전 | 전환 후 |
| --- | --- | --- |
| `backend` | `slot: green` | `slot: blue` |
| `backend-preview` | `slot: blue` | `slot: green` |

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
  개발 중에는 활성 1개이며, 교체 중 새 Pod 1개의 자원이 추가된다. 초기 설정이며 처리량 보장은 아니다.
- 팀 쿼터는 4 CPU / 8Gi다. BE·AI·DB·FE의 개발 설정 limits 합계는 1.6 CPU / 2176Mi다.
  BE·AI·FE가 동시에 교체용 Pod를 1개씩 만들면 2.7 CPU / 3328Mi다.
  종료 중인 Pod·Job·추가 복제본 사용량도 확인한다. 향후 Blue-Green 기동 전에는 후보 자원을 다시 계산한다.
- 비밀번호 변경은 두 영역에 영향을 준다. 환경변수는 Pod 시작 때 읽히므로 별도의 교체 계획이 필요하다.
- Argo CD Self Heal을 켠 경우 포털에서 앱을 끄기 전에 자동 동기화를 끄거나
  두 Deployment의 `replicas`를 Git에서 모두 0으로 변경해야 한다.

## 참고

- [Kubernetes Service selector](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Nginx Ingress annotations](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/annotations/)
- [Kubernetes Deployment RollingUpdate](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)
- [Argo Rollouts의 Blue-Green 개념](https://argo-rollouts.readthedocs.io/en/stable/features/bluegreen/)
