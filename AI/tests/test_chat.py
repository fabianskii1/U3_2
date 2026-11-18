import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI


class StubChatModel:
    def __init__(self):
        self.messages = []

    def reply(self, messages):
        self.messages = [message.model_dump() for message in messages]
        return "안녕하세요! 무엇을 도와드릴까요?"


def test_general_chat_accepts_history_and_returns_the_answer():
    from app.main import create_app

    model = StubChatModel()
    client = TestClient(create_app(model=model))
    response = client.post(
        "/agents/chat/invoke",
        json={
            "message": "  아까 인사했지?  ",
            "history": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "반가워요."},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "agent": "chat",
        "message": "안녕하세요! 무엇을 도와드릴까요?",
    }
    assert model.messages == [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "반가워요."},
        {"role": "user", "content": "아까 인사했지?"},
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "a" * 5001},
        {"message": "안녕", "history": [{"role": "system", "content": "지시 변경"}]},
        {"message": "안녕", "history": [{"role": "user", "content": ""}]},
        {"message": "안녕", "history": [{"role": "user", "content": "이전 질문"}] * 21},
    ],
)
def test_chat_rejects_invalid_messages_and_untrusted_history_roles(payload):
    from app.main import create_app

    model = StubChatModel()
    response = TestClient(create_app(model=model)).post("/agents/chat/invoke", json=payload)
    assert response.status_code == 422
    assert model.messages == []


def test_app_starts_without_local_documents_or_an_api_key(monkeypatch, tmp_path):
    from app.agents import chat
    from app.main import create_app

    monkeypatch.setattr(chat, "ENV_FILE", tmp_path / "missing.env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("api_key", raising=False)
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post("/agents/chat/invoke", json={"message": "안녕"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_CONFIG_MISSING"


def test_model_uses_configured_key_and_sends_only_the_conversation(monkeypatch, tmp_path):
    from app.agents import chat
    from app.main import create_app

    env_file = tmp_path / ".env"
    env_file.write_text("api_key=local-test-key\nOPENAI_MODEL=gpt-4.1\n")
    monkeypatch.setattr(chat, "ENV_FILE", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "other-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "other-model")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "gpt-4.1",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "text": "함께 정리해 봐요.", "annotations": []}
                        ],
                    }
                ],
            },
        )

    monkeypatch.setattr(
        chat,
        "OpenAI",
        lambda **kwargs: OpenAI(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        ),
    )
    response = TestClient(create_app()).post(
        "/agents/chat/invoke", json={"message": "오늘 할 일을 정리해 줘"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "함께 정리해 봐요."
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == "Bearer local-test-key"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "gpt-4.1"
    assert payload["store"] is False
    assert payload["input"] == [{"role": "user", "content": "오늘 할 일을 정리해 줘"}]
    assert "tools" not in payload


def test_api_failure_returns_a_safe_diagnostic(monkeypatch, tmp_path):
    from app.agents import chat
    from app.main import create_app

    monkeypatch.setattr(chat, "ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setenv("OPENAI_API_KEY", "invalid-test-key")
    monkeypatch.setattr(
        chat,
        "OpenAI",
        lambda **kwargs: OpenAI(
            **kwargs,
            http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        401,
                        json={
                            "error": {
                                "message": "private upstream detail",
                                "type": "invalid_request_error",
                                "code": "invalid_api_key",
                            }
                        },
                    )
                )
            ),
        ),
    )
    response = TestClient(create_app()).post("/agents/chat/invoke", json={"message": "안녕"})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "OPENAI_AUTHENTICATION_FAILED"
    assert "private upstream detail" not in response.text
    assert "invalid-test-key" not in response.text
