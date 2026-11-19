# AI

Skadi 채팅 워크플로와 설비명 판별 서비스다. 별칭의 기준 데이터는 BE가 조회한 DB의 `plant_alias`, `equipment_group_alias`, `equipment_alias`, `sensor_alias`다. AI는 삭제된 로컬 지식 문서나 LLM wiki를 읽지 않는다.

## 채팅 워크플로

BE의 `/api/chat/stream`은 `AI/workflow`의 Reflector, Action Planner, Executor를 실행하며 DB 읽기 도구를 주입한다. “P1의 별칭 알려줘”, “이 센서 별칭” 같은 질문은 BE의 `lookup_alias` 도구를 호출한다. 도구는 ID·정식 이름·등록 별칭을 정확히 조회하고, 같은 표현이 여러 대상에 해당하면 후보 선택을 요청한다. 화면의 플랜트·공정·설비 범위로 후보를 좁힐 수 있다.

## 설비명 판별 API

정확히 일치하는 DB 이름이나 별칭이 없을 때 BE는 현재 DB에서 읽은 설비 후보를 내부 AI API에 전달한다. AI는 전달된 후보 밖의 설비 ID를 반환하지 않으며, 유사 표현 판별 결과도 BE가 DB 설비 및 범위와 다시 대조한다. 후보가 없으면 `not_found`를 반환한다.

```http
POST /agents/find-equipment-id/invoke
Content-Type: application/json

{
  "equipment_name": "납사 이송 펌프",
  "candidates": [
    {
      "equipment_id": "P2",
      "equipment_name": "나프타 제품 이송 펌프",
      "aliases": ["나프타 펌프"]
    }
  ]
}
```

응답의 `status`는 `found`, `ambiguous`, `not_found` 중 하나다. 유사 표현에 모델을 사용하면 요청 표현과 DB 후보의 ID·등록명·별칭이 OpenAI API로 전송된다. 모델 응답 저장은 `store=False`로 요청한다. 모델 설정에는 `AI/.env`의 `OPENAI_API_KEY` 또는 `api_key`, 선택적으로 `OPENAI_MODEL`을 사용한다.

## 실행과 검증

```bash
cd AI
uv sync --frozen --group dev --python 3.12
uv run --frozen --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8001
uv run --frozen --no-sync ruff check app tests
uv run --frozen --no-sync pytest -q
```

Compose에서는 프로젝트 루트에서 `docker compose --env-file DB/.env up -d --build`를 실행한다. AI API는 내부 서비스이며 FE는 BE의 채팅 API에 연결한다.

## 이미지 검증과 CI

프로젝트 루트에서 운영 이미지와 키 없는 설비 조회를 검증한다. Dockerfile과 CI는 `uv==0.12.13`을 사용한다.

```bash
docker buildx build --platform linux/amd64 --load -f AI/deploy/Dockerfile -t skadi-ai:check AI
bash AI/deploy/ci-smoke.sh skadi-ai:check
```

스모크 테스트는 외부 네트워크와 호스트 환경 파일을 연결하지 않은 임시 컨테이너에서 `/health`, DB 후보의 정확한 별칭 일치, 빈 후보의 `not_found`, 유사 표현을 판별할 때 키가 없으면 반환하는 HTTP 503 `MODEL_CONFIG_MISSING`을 확인한다. 실제 모델 호출이나 API 키는 필요하지 않다.

`build-ai.yaml`은 관련 경로의 main push, main 대상 PR, 수동 실행에서 Ruff·전체 pytest·amd64 이미지 빌드·스모크를 수행한다. Harbor 로그인과 검증한 SHA 태그 이미지 업로드는 PR이 아닌 main 실행에서만 수행한다.
