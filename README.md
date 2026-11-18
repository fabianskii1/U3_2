# SKADI workspace

```text
U3_2/
├── compose.yaml   # DB, 마이그레이션, BE, AI, FE Docker Compose 진입점
├── DB/            # PostgreSQL + TimescaleDB + pgvector 이미지·설정
├── fe/            # React 프론트엔드
├── BE/            # FastAPI 백엔드
└── AI/            # 일반 채팅 AI 서비스
```

현재 Compose에는 DB, 마이그레이션, BE, AI, FE 서비스가 있다. FE는 `http://127.0.0.1:5173`에서 BE API에 연결된다. BE의 기존 설비 조회 채팅 호출과 AI의 새 일반 채팅 API는 아직 호환 작업이 필요하다. 실행 방법은 [BE/README.md](./BE/README.md), [DB/README.md](./DB/README.md), [fe/README.md](./fe/README.md), [AI/README.md](./AI/README.md)를 참고한다.

GitHub Actions의 컴포넌트별 검사·이미지 업로드와 수동 배포 버전 반영 방법은 [CI 안내](./docs/ci.md)를 참고한다.
