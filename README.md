# SKADI workspace

```text
U3_2/
├── compose.yaml   # DB, 마이그레이션, BE, AI, FE Docker Compose 진입점
├── DB/            # PostgreSQL + TimescaleDB + pgvector 이미지·설정
├── fe/            # React 프론트엔드
├── BE/            # FastAPI 백엔드
└── AI/            # 설비 ID 조회 AI 서비스와 공유 에이전트 워크플로우
```

현재 Compose에는 DB, 마이그레이션, BE, AI, FE 서비스가 있다. FE는 `http://127.0.0.1:5173`에서 BE API에 연결되고, 채팅은 BE를 통해 AI 설비 ID 조회 에이전트를 호출한다. 실행 방법은 [BE/README.md](./BE/README.md), [DB/README.md](./DB/README.md), [fe/README.md](./fe/README.md), [AI/README.md](./AI/README.md)를 참고한다.

컴포넌트별 검사와 이미지 업로드는 [CI 안내](./docs/ci.md), 현재 고정된 배포 이미지와 새 버전 반영 순서는 [배포 안내](./k8s/README.md)를 참고한다.
