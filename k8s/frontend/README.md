# FE 배포 설정

아래 고정 태그는 통합 전 확인된 이미지다. 새 기능 코드를 배포할 때는 [상위 배포 안내](../README.md)에 따라
main CI가 게시한 새 태그로 변경한다.

성공한 CI 이미지 `harbor.skala-us.com/u3-2/frontend:33e74a2bfb9294d4467bd4802cf2ade741a7dba0`를
Deployment 1개와 내부 Service `frontend:80`으로 배포한다. 새 이미지 빌드나 CI 변경은 필요하지 않다.
개별 YAML 대신 Kustomize 디렉터리를 사용한다.

```bash
kubectl kustomize k8s/frontend
kubectl --context u3-2 -n u3-2 apply --dry-run=server -k k8s/frontend
```

## Argo CD 연결

Git 반영 후 아래 설정으로 Application을 만들고 수동 Sync한다. 이 파일 작성만으로 실제 배포되지는 않는다.

| 항목 | 값 |
| --- | --- |
| Application / Project | `u3-2-frontend` / `u3-2` |
| Repository | `https://github.com/fabianskii1/U3_2.git` |
| Revision / Path | `main` / `k8s/frontend` |
| Destination | 기존 `skala-us` 클러스터, namespace `u3-2` |
| Sync policy | Manual |

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

버전 교체는 성공한 CI 태그를 `kustomization.yaml`에 반영하고 렌더링·검증한 뒤 Git에 올려
수동 Sync한다. 이전 이미지로 돌아갈 때도 이 태그 변경을 되돌리고 Sync한다.
