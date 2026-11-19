# FE 배포 설정

이번 배포는 AI와 새 BE의 Rolling 반영·검증 이후에 진행한다. 전체 순서는 [상위 배포 안내](../README.md)를 따른다.

성공한 CI 이미지 `harbor.skala-us.com/u3-2/frontend:056c253625e73639604ab088ca475cfa675f61d7`를
Deployment 1개와 내부 Service `frontend:80`으로 초기 배포했다. 후속 성공한 CI는 새 SHA 태그를 `gitops/dev`에 발행한다.
최초 자동화 연결과 실패/복귀 절차는 [자동 배포 안내](../../docs/gitops.md)를 따른다.
개별 YAML 대신 Kustomize 디렉터리를 사용한다.

```bash
kubectl kustomize k8s/frontend
kubectl --context u3-2 -n u3-2 apply --dry-run=server -k k8s/frontend
```

## Argo CD 연결

성공한 main CI가 `gitops/dev`를 생성한 후 아래 설정으로 Application을 연결한다.

| 항목 | 값 |
| --- | --- |
| Application / Project | `u3-2-frontend` / `u3-2` |
| Repository | `https://github.com/fabianskii1/U3_2.git` |
| Revision / Path | `gitops/dev` / `k8s/frontend` |
| Destination | 기존 `skala-us` 클러스터, namespace `u3-2` |
| Sync policy | Automated |

기존 기본 ServiceAccount의 `harbor-cred`와 TLS Secret `team-tls`를 사용한다.
새 클러스터·Ingress Controller·인증서·Secret을 만들지 않는다.

## HTTPS 경로

클래스 `nginx`, 호스트 `u3-2.skala-us.com`의 `/` Prefix를 FE에 연결한다.
기존 BE Ingress의 더 구체적인 `/api` Prefix와 `/health` Exact 경로는 그대로 BE가 처리한다.
URI rewrite와 regex는 사용하지 않는다.

FE 이미지의 Nginx가 정적 파일과 SPA 경로를 처리한다. 이미지의 내부 API 프록시도
`BACKEND_UPSTREAM=backend:8000`을 사용하지만, 외부 `/api` 요청은 기존 BE Ingress로 직접 전달된다.
Sync 후 `/`, 실제 JS/CSS 자산, SPA 하위 경로와 기존 `/health`, `/api/hierarchy`를 함께 확인한다.
채팅은 배포된 BE·AI의 API 버전과 모델 연결까지 별도로 검증한다.

## 실행과 자원

- Linux amd64, Pod 1개다. RollingUpdate는 `maxSurge: 1`, `maxUnavailable: 0`이며
  새 Pod가 Ready 상태를 5초 유지한 후 기존 Pod를 교체한다.
- Pod당 request `50m / 64Mi`, limit `100m / 128Mi`다. 교체 중 최대 2개일 때
  request `100m / 128Mi`, limit `200m / 256Mi`를 계획한다. 종료 중인 Pod의 자원 반환은 지연될 수 있다.
  팀 쿼터는 4 CPU / 8Gi이며 다른 워크로드와 합산해야 한다. 초기 할당은 처리량 보장이 아니다.
- 기존 공식 Nginx 이미지의 root master, 기본 capability와 쓰기 가능한 파일시스템을 유지한다.
  entrypoint의 envsubst, PID·임시 파일과 worker 권한 전환에 필요하므로 UID 10001이나
  `drop: [ALL]`, 읽기 전용 루트 파일시스템을 적용하지 않는다.
  `RuntimeDefault` seccomp와 `allowPrivilegeEscalation: false`를 사용하며 ServiceAccount 토큰은 마운트하지 않는다.
- 시작·준비·실행 상태는 HTTP `/`로 검사한다. FE 정적 파일 제공만 확인하며 BE·DB·AI 상태는 확인하지 않는다.
  종료 전 5초 대기 후 이미지의 `SIGQUIT`으로 Nginx를 종료하며 전체 종료 유예는 30초다.

버전 교체는 성공한 CI가 `gitops/dev`의 설정과 태그를 발행하고 Argo가 Auto Sync한다.
이전 이미지로 돌아갈 때는 자동 배포 안내의 중지·태그 복귀·재개 절차를 따른다.
