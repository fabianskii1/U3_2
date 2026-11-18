# AI

Python 3.12 + FastAPI 기반 일반 채팅 서비스다. OpenAI Responses API로 텍스트 답변을 생성한다.
설비 ID 조회, 위키 검색, 도구 호출은 수행하지 않으며 로컬 지식 문서 없이 시작할 수 있다.

## 실행

```bash
cd AI
uv sync --python 3.12
cp .env.example .env
# .env의 OPENAI_API_KEY를 설정한다.
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

기본 모델은 `gpt-4.1`이고 `OPENAI_MODEL`로 변경할 수 있다.
기존 `api_key` 이름도 지원한다. `AI/.env` 값이 실행 환경 변수보다 우선한다.
키 설정은 요청 시 확인하므로 키가 없어도 `/health`는 응답한다.

## 채팅 API

```bash
curl -s -X POST http://127.0.0.1:8001/agents/chat/invoke \
  -H 'Content-Type: application/json' \
  -d '{"message":"안녕! 간단히 자기소개해 줘"}'
```

응답 형식:

```json
{
  "agent": "chat",
  "message": "안녕하세요! 질문에 답하고 생각을 정리하는 일을 도와드릴게요."
}
```

이전 대화를 이어가려면 호출자가 `history`에 과거 메시지를 전달한다.
현재 `message`는 `history`에 중복해서 넣지 않는다.

```json
{
  "message": "그걸 한 문장으로 요약해 줘",
  "history": [
    {"role": "user", "content": "원심펌프 원리를 설명해 줘"},
    {"role": "assistant", "content": "회전하는 임펠러가 유체에 에너지를 전달합니다."}
  ]
}
```

메시지는 앞뒤 공백을 제거한 뒤 1~5,000자이며 `history`는 최대 20개다.
이력의 역할은 `user`와 `assistant`만 허용한다. 대화 기록을 AI 서버에 저장하지 않으며
OpenAI에도 `store=False`로 요청한다. 응답은 완성된 텍스트 한 번으로 반환한다.
키 인증, 요청 한도, 모델 설정, 연결 오류는 `detail.code`로 구분하고 키나 원문 오류는 노출하지 않는다.

## BE 연결 상태

이번 변경은 AI 서비스에만 적용했다. 기존 BE의
`/agents/find-equipment-id/invoke` 호출과 설비 조회 응답 형식은 변경하지 않았다.
이전 설비 조회 API는 제거했으므로 현재 웹 채팅은 이 AI API와 호환되지 않는다.
일반 채팅 연결 시 BE에서 새 경로와 `message`/`history` 요청, `message` 응답을 사용해야 한다.

## 검증

```bash
uv sync --frozen --group dev
uv run --frozen --no-sync ruff check app tests
uv run --frozen --no-sync pytest -q
```

테스트는 외부 HTTP 응답을 대체하여 실제 모델 호출과 과금 없이 API 계약,
대화 이력 전달, 입력 검증 및 오류 처리를 확인한다.

## 이미지 CI

`.github/workflows/build-ai.yaml`은 `main`의 `AI/**` 변경 또는 수동 실행 시
위 검증을 수행하고 `linux/amd64` 이미지를 빌드한다. 실제 이미지의 기본 명령으로
서버를 시작해 `/health`와 키가 없는 채팅 요청의 `503 MODEL_CONFIG_MISSING`을 확인한 뒤
`harbor.skala-us.com/u3-2/ai:<커밋 SHA>`로 푸시한다. Harbor 인증에는 저장소의
`HARBOR_USERNAME`, `HARBOR_PASSWORD` 시크릿을 사용한다. 수동 실행도 `main`에서만 동작한다.
CI와 Dockerfile은 같은 uv `0.12.13`으로 `uv.lock`의 고정된 의존성을 설치한다.

같은 이미지 검증을 로컬에서 실행할 수 있다.

```bash
docker build --platform linux/amd64 -f AI/deploy/Dockerfile -t skadi-ai-ci:local AI
bash AI/deploy/ci-smoke.sh skadi-ai-ci:local
```

위 명령은 저장소 루트에서 실행한다. 검사 컨테이너는 네트워크와 모델 키 없이 실행하고
종료 시 삭제한다. 호스트 `.env`는 전달하지 않으며 이미지에 `.env`가 포함돼도 검증에 실패한다.
이미지 게시가 배포를 바꾸지는 않는다. BE의 기존 설비 조회 API 연동 불일치는 그대로 남는다.
