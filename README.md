# SKADI workspace

```text
U3_2/
├── compose.yaml   # DB, 마이그레이션, BE, AI, FE Docker Compose 진입점
├── DB/            # PostgreSQL + TimescaleDB + pgvector 이미지·설정
├── FE/            # React 프론트엔드
├── BE/            # FastAPI 백엔드
└── AI/            # 설비 ID 조회 AI 서비스와 OKF 지식 번들
```

현재 Compose에는 DB, 마이그레이션, BE, AI, FE 서비스가 있다. FE는 `http://127.0.0.1:5173`에서 BE API에 연결되고, 채팅은 BE를 통해 AI 설비 ID 조회 에이전트를 호출한다. 실행 방법은 [BE/README.md](./BE/README.md), [DB/README.md](./DB/README.md), [FE/README.md](./FE/README.md), [AI/README.md](./AI/README.md)를 참고한다.
