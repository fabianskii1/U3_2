# AI 서버 첫 배포와 개발용 Rolling

이번 최초 배포는 main CI가 검증·업로드한 설비 조회 이미지 `056c253`을 사용한다.
DB와 BE·FE 반영 순서는 [상위 배포 안내](../README.md)를 따른다.

Deployment 두 개와 내부 Service 두 개로 구성한다. Argo Rollouts나 추가 CRD는 사용하지 않는다.
개발 중에는 Blue만 Pod 1개로 실행한다. Green은 향후 Blue-Green용으로 정의만 유지하며 Pod는 0개다.
두 slot의 이미지 태그는 CI에서 빌드·검증·업로드한 아래 버전이다.

```text
harbor.skala-us.com/u3-2/ai:056c253625e73639604ab088ca475cfa675f61d7

BE → ai:8001         → ai-blue  (초기 운영)
     ai-preview:8001 → ai-green (개발 중 Pod 0개)
```

AI는 ClusterIP Service로만 접근한다. 별도 AI Ingress는 만들지 않는다.
팀 호스트의 `/api`, `/health`, `/` 경로는 BE·FE 배포에서 관리한다.
BE의 내부 호출 주소는 `http://ai:8001`이다. 활성 BE Green도 같은 릴리스의 이미지로 검증한다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `deployment-blue.yaml` | 활성 Blue 1개, RollingUpdate, 환경 변수·자원·보안·상태 검사 |
| `deployment-green.yaml` | 비활성 Green 0개, 향후 Blue-Green용 |
| `service.yaml` | 운영 `ai`와 검증 `ai-preview`의 slot 선택 |
| `kustomization.yaml` | namespace `u3-2`, 이미지 별칭과 태그 관리 |

- 운영 slot은 Service `ai`의 `spec.selector.slot`으로 판단한다. 초기값은 `blue`, preview는 `green`이다.
- `ai-blue-image`, `ai-green-image` 별칭은 같은 Harbor 저장소에서 서로 다른 버전을 선택할 수 있다.
- 활성 Blue는 `RollingUpdate`, `maxSurge: 1`, `maxUnavailable: 0`, `minReadySeconds: 5`다.
  개발 중에는 활성 이미지 갱신 후 Sync 한 번으로 교체하며 Service selector는 바꾸지 않는다.
- Pod당 request `100m / 128Mi`, limit `500m / 512Mi`다. 교체 중 새 Pod 1개의 자원이 추가된다.
- 비활성 Green은 `Recreate`이며 0개다. `ai-preview`에 엔드포인트가 없는 것이 현재 설정에 맞다.
- `linux/amd64`, UID/GID `10001`, 권한 상승 금지, capability 제거, `RuntimeDefault` seccomp, API 토큰 마운트 해제를 사용한다.
- startup/readiness/liveness는 `/health`다. 정상 상태는 실제 모델 호출 성공이나 BE 연동을 보장하지 않는다.
- 모델은 `gpt-4.1`, API 키는 `ai-secrets` Secret의 `OPENAI_API_KEY`에서 읽는다.
- 기본 ServiceAccount와 기존 이미지 pull 자격 증명을 사용한다. namespace·quota·RBAC·영구 볼륨을 새로 만들지 않는다.

## 첫 배포

`.github/workflows/build-ai.yaml`은 AI lint·테스트와 이미지 기동·키 미설정 응답을 검증한 뒤 Harbor에 SHA 태그로 업로드한다.
배포 태그는 CI가 자동 수정하지 않는다. 최초 두 이미지 태그는 위의 확인된 버전으로 고정했다.
키 등록은 사용자 요청으로 보류한 상태다. 모델 호출이 필요할 때 `ai-secrets`의 **`OPENAI_API_KEY`만** 별도 등록한다.
로컬 환경 파일 전체를 Secret으로 가져오거나 키를 Git에 기록하지 않는다. 키 없이도 `/health`는 정상이다.
새 설비 조회 소스는 확정된 별칭/조회 후보 없음에 키 없이 응답할 수 있으며, 모델이 필요한 요청은 키 없이 `503 / MODEL_CONFIG_MISSING`이다.

저장소 루트에서 렌더링과 서버 검증을 수행하고 배포 파일을 `main`에 반영한다.

```bash
kubectl kustomize k8s/ai
kubectl --context u3-2 -n u3-2 apply --dry-run=server -k k8s/ai
```

Argo CD → Applications → NEW APP에서 다음 값으로 생성한 뒤 수동 SYNC한다.

| 항목 | 값 |
| --- | --- |
| Application Name | `u3-2-ai` |
| Project | `u3-2` |
| Sync Policy | `Manual` |
| Repository URL | `https://github.com/fabianskii1/U3_2.git` |
| Revision | `main` |
| Path | `k8s/ai` |
| Cluster URL | `https://kubernetes.default.svc` |
| Namespace | `u3-2` |

```bash
kubectl --context u3-2 -n u3-2 rollout status deployment/ai-blue --timeout=180s
kubectl --context u3-2 -n u3-2 get pods,svc -l app=ai
kubectl --context u3-2 -n u3-2 port-forward service/ai 18001:8001 --address 127.0.0.1
```

별도 터미널에서 `curl --fail-with-body http://127.0.0.1:18001/health`를 실행한다.
Green은 0개이므로 preview 포트 포워딩은 사용하지 않는다.
키 등록과 실제 모델 호출은 사용자 요청으로 보류했다. 키 없는 설비 별칭 조회와 BE 연동은 별도로 확인한다.
첫 배포는 초기 기동이다. 무중단 전환은 이후 실제 트래픽 시험으로 검증한다.

## 개발 중 버전 교체

1. AI CI의 검사·Harbor 업로드 성공과 새 전체 SHA 태그를 확인한다.
2. `kustomization.yaml`의 `ai-blue-image` 태그를 갱신한다. Blue는 1개, Green은 0개, Service는 Blue를 유지한다.
3. 설정 PR 병합 후 기존 `u3-2-ai`에서 Refresh → Sync → Synchronize한다.
4. Blue의 rollout, `/health`, 설비 조회 응답과 BE 연동을 확인한다. 모델 연결·품질 검증은 키 등록 후 별도 수행한다.

문제가 있으면 Blue의 이미지 태그를 이전 버전으로 되돌려 Git에 반영하고 Sync한다.
교체 전후 API가 BE와 호환돼야 하며, readiness 성공만으로 처리 중인 요청의 무중단을 보장하지 않는다.
Secret 환경 변수는 Pod 시작 시 읽힌다. 키 교체 후에는 활성 Pod의 계획된 교체와 검증이 필요하다.

## 향후 수동 Blue-Green: 후보 배포

운영 검증 시 각 slot의 전략을 `Recreate`로 맞추되 활성 Pod template은 유지한다.
비활성 slot의 replicas를 1로 올려야 preview 검사·전환·복귀에 사용할 수 있다.

1. Git과 실제 Service `ai`의 selector가 일치하는지 확인한다.

   ```bash
   kubectl --context u3-2 -n u3-2 get service ai -o jsonpath='{.spec.selector.slot}{"\n"}'
   ```

2. AI CI에서 새 이미지가 성공적으로 업로드됐는지 확인한다. 운영이 Blue이면 `kustomization.yaml`의 **`ai-green-image` 태그만** 새 SHA로 수정한다. 운영이 Green이면 Blue만 수정한다.
3. 렌더링·검증 후 Git에 반영하고 Argo CD에서 수동 SYNC한다. 이 변경에는 운영 이미지나 Service selector를 포함하지 않는다.
4. 후보 Deployment의 rollout과 `ai-preview` 내부 상태를 확인한다. 필요한 모델·응답·오류·지연 검증은 별도로 수행하고 결과를 기록한다.

이 구성은 검증 결과를 자동 판정하거나 승인 없는 전환을 막는 컨트롤러를 포함하지 않는다.
`/health` 200이나 Argo Healthy만으로 모델 또는 기능 검증을 대신하지 않는다.

## 향후 수동 Blue-Green: 전환과 복귀

후보 검증 후 별도 Git 변경에서 `service.yaml`의 selector 두 개만 교환한다.
Blue → Green이면 `ai`는 `green`, `ai-preview`는 `blue`를 선택한다.
이미지·환경 변수·replicas는 함께 바꾸지 않는다. 검토 후 Git에 반영하고 Argo CD에서 수동 SYNC한다.

```bash
kubectl --context u3-2 -n u3-2 get service ai -o jsonpath='{.spec.selector.slot}{"\n"}'
kubectl --context u3-2 -n u3-2 get endpointslice -l kubernetes.io/service-name=ai
```

운영 Service의 내부 상태와 실제 호출을 확인한다. Service 전환은 기존 연결을 옮기지 않으므로
처리 중 요청·엔드포인트 전파·관찰 기간을 고려해 이전 Pod와 이미지를 유지한다.
문제가 있으면 **전환 selector만** 되돌리는 Git 변경을 수동 SYNC한다.
이전 slot이 준비돼 있어야 빠르게 복귀할 수 있으며, 외부 API 호출 결과는 트래픽 복귀로 취소되지 않는다.
복귀 기간이 끝나면 이전 slot을 다음 후보 공간으로 재사용한다.

Blue-Green을 사용하는 운영 단계에서는 키 교체도 비운영 slot부터 재생성·검증·전환한다.
`app=ai` 전체 Pod를 한 번에 삭제하지 않는다. 키가 폐기되면 이전 slot도 영향을 받는다.
