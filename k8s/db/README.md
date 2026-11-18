# DB Kubernetes 배포

단일 PostgreSQL StatefulSet, 내부 Service, 기존 10Gi PVC를 묶은 배포 설정이다.
DB 이미지 업로드, Secret 등록, Git push, Argo CD 배포 및 덤프 복원은 별도로 진행한다.
파일 작성과 실제 클러스터 자원 생성은 별개이며, 여기의 명령은 사용자가 실행할 때만 반영된다.

## 1. 파일과 실제 생성 위치

| 대상 | 로컬 파일 | 실제 생성 위치 |
| --- | --- | --- |
| StatefulSet `db` | `k8s/db/statefulset.yaml` | EKS `u3-2`, Pod 이름 `db-0` |
| Service `db` | `k8s/db/service.yaml` | EKS `u3-2`, 내부 주소 `db:5432` |
| PVC `db-data` | `k8s/db/pvc.yaml` | EKS `skala-us`의 Namespace `u3-2` |
| Secret `db-credentials` | 로컬 입력용 `k8s/db/db-credentials.env` | EKS `skala-us`의 Namespace `u3-2` |

DB와 저장장치는 BE 이미지 교체와 별도로 관리하도록 `k8s/db`로 분리했다.
같은 PVC를 BE와 DB의 Argo CD Application에 중복 등록하지 않는다.
DB Application은 Source Path `k8s/db`를 사용하고 StatefulSet·Service·PVC를 함께 관리한다.
현재 `k8s/backend`에는 이 PVC를 포함하지 않았다.

## 2. 10Gi PVC

- 이름: `db-data`, Namespace: `u3-2`
- StorageClass: 가이드에서 제공한 `ebs-sc` (EBS gp3)
- 요청 용량: `10Gi`, Access mode: `ReadWriteOnce`
- 원시 파일·위키 원문 보관이 아니라 PostgreSQL의 실제 데이터 디스크로 사용한다.
- StatefulSet은 `persistentVolumeClaim.claimName: db-data`로 기존 PVC를 연결한다.
  `volumeClaimTemplates`로 별도의 디스크를 중복 생성하지 않는다.
- Argo CD의 자동 prune과 Application 삭제 시 PVC가 지워지지 않도록
  `Prune=false,Delete=false`를 지정했다. 직접적인 PVC 삭제를 막거나 백업을 만드는 설정은 아니다.

먼저 로컬에서 최종 YAML을 확인할 수 있다. 클러스터에 배포하지 않는다.

```bash
kubectl kustomize k8s/db
```

GitOps 배포에서는 Git에 반영된 이 경로를 DB Application이 동기화하도록 한다.
StorageClass가 `WaitForFirstConsumer`이면 DB Pod가 생성되기 전 PVC가 Pending일 수 있다.
실제 바인딩 상태는 아래 명령으로 확인한다. 캠퍼스 네트워크에서 실행한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 get pvc db-data
```

## 3. db-credentials 입력

로컬 `db-credentials.env`가 있으면 그대로 편집한다. 없으면 저장소 루트에서
`cp -n k8s/db/db-credentials.env.example k8s/db/db-credentials.env`로 만든다.
기존 로컬 Compose용 `DB/.env`는 변경하지 않는다.

파일의 세 값을 정하고 `POSTGRES_PASSWORD`에 빈 값이 아닌 비밀번호를 입력한다.

```dotenv
POSTGRES_DB=skadi
POSTGRES_USER=skadi
POSTGRES_PASSWORD=
```

`db-credentials.env`는 `.gitignore`로 제외하고 Kustomize resources에도 넣지 않는다.
공개 가능한 `.env.example`에는 비밀번호를 넣지 않는다.
GitHub Actions Secret이 아니라 실행 중인 DB와 BE가 읽을 Kubernetes Secret을 만드는 입력 파일이다.

아래 명령은 비밀번호 입력을 마친 뒤, 캠퍼스 네트워크에서 저장소 루트 기준으로 실행한다.
로컬 파일을 읽어 EKS의 `u3-2` Namespace에 Secret 객체를 생성한다. DB나 PVC는 생성하지 않는다.
앞의 `DYLD_LIBRARY_PATH`는 이 Mac에서 확인된 AWS CLI 실행 오류를 피하는 명령별 설정이다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 create secret generic db-credentials \
  --from-env-file=k8s/db/db-credentials.env
```

이미 존재한다는 오류가 나면 기존 DB의 계정과 연결 상태를 확인한 뒤 처리한다.
기존 Secret을 무조건 삭제하거나 새 값으로 덮어쓰지 않는다.
Secret 등록 여부만 확인할 때는 값이나 YAML을 출력하지 않고 아래 명령을 사용한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 get secret db-credentials
```

현재 BE Blue/Green과 DB StatefulSet이 이 Secret의 세 키를 참조한다.
초기화된 DB의 비밀번호는
Secret 파일을 수정하는 것만으로 바뀌지 않는다.

## 4. DB 실행 설정

```text
BE Blue ─┐
         ├→ db:5432 → db-0 → db-data PVC → EBS 10Gi
BE Green ┘              ↑
                  db-credentials Secret
```

- 이미지: `harbor.skala-us.com/u3-2/db:pg17-ts2.32.0-v1`, 플랫폼 `linux/amd64`.
  `DB/docker/Dockerfile.db`로 빌드한 이미지를 Harbor에 올린 뒤 배포한다.
  덤프나 비밀번호는 이미지에 포함하지 않는다.
- DB는 `replicas: 1`이다. 고정 PVC 하나를 쓰므로 단순히 2로 올리면 안 된다.
  DB 복제·자동 장애 전환은 구현하지 않았고 DB 교체 중에는 접속이 중단될 수 있다.
- Service `db`는 StatefulSet의 식별자를 위한 Headless Service라 `CLUSTER-IP: None`이 정상이다.
  준비된 DB Pod의 IP로 해석되며 BE는 `DB_HOST=db`, `DB_PORT=5432`로 접속한다.
  외부 Ingress나 LoadBalancer는 만들지 않는다.
- `PGDATA=/var/lib/postgresql/data/pgdata`로 디스크 루트의 `lost+found`와 구분한다.
  Pod 시작 시 덤프를 자동 복원하지 않으며 재시작하면 기존 데이터를 사용한다.
- 고정 이미지의 postgres 계정인 UID/GID 70으로 실행하고 `fsGroup: 70`으로 볼륨 접근 권한을 준다.
  privileged, hostPath, 추가 capability, Kubernetes API 토큰을 사용하지 않는다.
- request는 `250m / 512Mi`, limit은 `500m / 1Gi`다.
  노드 전체 RAM 기준 자동 튜닝을 끄고 `shared_buffers=128MB`, `max_connections=50`으로 시작한다.
  초기 설정이며 실제 데이터량과 쿼리·복원 부하에 맞춰 조정한다.
- 시작·준비·실행 검사는 localhost의 `pg_isready`를 사용한다.
  시작 검사는 5초 간격 60회, 실행 검사는 10초 간격 6회 실패 후 재시작한다.
  Ready는 접속 준비 상태이며 덤프 복원이나 업무 테이블까지 완료됐다는 뜻은 아니다.
- 현재는 초기 DB 계정을 BE도 사용한다. 운영용 권한 분리는 별도 작업이다.

DB와 BE 두 영역의 limit 합계는 `1.5 CPU / 2Gi`다.
현재 AI 두 영역까지 더하면 CPU limit 합계가 `2.5 CPU`라 팀 기본 2 CPU 한도를 넘는다.
FE·AI·작업자를 함께 배포하기 전 자원 배분 또는 팀 쿼터를 조정한다.

## 5. GitOps 배포

Harbor에 이미지가 존재하고 `db-credentials` 등록이 완료됐는지 확인한다.
Secret 값이나 전체 YAML을 출력할 필요는 없다.
최종 설정 확인은 `kubectl kustomize k8s/db`로 한다. 이는 클러스터에 배포하지 않는다.

파일을 검토해 Git에 반영한 다음 Argo CD NEW APP에서 아래 값을 사용한다.

| 항목 | 값 |
| --- | --- |
| Application Name | `u3-2-db` |
| Project | `u3-2` |
| Sync Policy | `Manual` |
| Repository URL | `https://github.com/fabianskii1/U3_2.git` |
| Revision | `main` |
| Path | `k8s/db` |
| Cluster URL | `https://kubernetes.default.svc` |
| Namespace | `u3-2` |

CREATE 후 SYNC → SYNCHRONIZE한다. 기본 ServiceAccount의 `harbor-cred`를 사용한다.
클러스터·Namespace·StorageClass·ResourceQuota·RBAC를 새로 만들지 않는다.
Secret이 없으면 `CreateContainerConfigError`, 이미지가 없으면 `ImagePullBackOff`가 발생할 수 있다.

캠퍼스 네트워크에서 아래 명령으로 DB 기동과 확장 활성화를 확인한다.

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 rollout status statefulset/db --timeout=300s

DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 get pods,svc,pvc -l app=db

DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
kubectl --context u3-2 -n u3-2 exec db-0 -- sh -ec \
  'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT extname, extversion FROM pg_extension ORDER BY extname;"'
```

Pod `db-0`가 `Running`, `READY 1/1`, PVC가 `Bound`인지 확인한다.
이후 덤프 원본의 확장 버전과 복원 대상 상태를 확인하고 TimescaleDB 복원 절차를 별도로 수행한다.
덤프에는 스키마가 포함될 수 있어 Alembic 초기화·시드와 중복 실행하지 않는다.
BE는 복원과 업무 데이터 확인이 끝난 뒤 배포한다.

## 6. 보존과 운영

- PVC를 직접 지우면 EBS도 지워질 수 있다. Argo CD 보존 옵션은 백업을 만드는 설정이 아니다.
- 자동 동기화 Self Heal을 켠 경우 포털로 끄기 전에 자동 동기화를 끄거나
  Git의 DB replicas를 0으로 변경한다. 데이터 디스크는 앱을 꺼도 남는다.
- DB 이미지 버전을 바꿀 때는 확장·PostgreSQL 호환성과 백업·복구 계획을 먼저 확인한다.

## 참고

- [Kubernetes StatefulSet](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [PostgreSQL 이미지 설정](https://hub.docker.com/_/postgres)
- [TimescaleDB 덤프 복원](https://www.tigerdata.com/docs/deploy/self-hosted/backup-and-restore/logical-backup)
- [Kubernetes PVC](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [kubectl로 Secret 생성](https://kubernetes.io/docs/tasks/configmap-secret/managing-secret-using-kubectl/)
- [Argo CD 자원 보존 옵션](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/)
