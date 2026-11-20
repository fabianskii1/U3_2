# SKADI workspace

```text
U3_2/
├── compose.yaml   # DB, 마이그레이션, BE, AI, FE Docker Compose 진입점
├── DB/            # PostgreSQL + TimescaleDB + pgvector 이미지·설정
├── FE/            # React 프론트엔드
├── BE/            # FastAPI 백엔드
└── AI/            # 설비 조회 AI 서비스와 채팅 워크플로
```

현재 Compose에는 DB, 마이그레이션, BE, AI, FE 서비스가 있다. FE는 `http://127.0.0.1:5173`에서 BE API에 연결되고, 채팅은 BE를 통해 AI 설비 ID 조회 에이전트를 호출한다.

## Docker Compose 실행

프로젝트 루트(`compose.yaml`이 있는 디렉터리)에서 실행한다. 처음 실행할 때 `DB/.env`를 만들고 `POSTGRES_PASSWORD`를 설정한다. 아래 `up -d --build`는 서비스 이름을 지정하지 않으므로 **DB, 마이그레이션, BE, AI, FE 전체를 빌드하고 실행**한다.

```bash
docker compose --env-file DB/.env up -d --build
docker compose --env-file DB/.env ps -a
```

서비스를 중지할 때는 다음 명령을 실행한다. DB 볼륨은 유지된다.

```bash
docker compose --env-file DB/.env down
```

각 서비스의 상세 설정은 [BE/README.md](./BE/README.md), [DB/README.md](./DB/README.md), [FE/README.md](./FE/README.md), [AI/README.md](./AI/README.md)를 참고한다.

챗봇의 대시보드·설비 현황·트렌드 조회 및 화면 이동 사용법은 [CHATBOT.md](./CHATBOT.md)를 참고한다.
