"""Internal HTTP entry point for plain chat."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.chat import (
    ChatMessage,
    ChatModel,
    MessageText,
    ModelUnavailableError,
    OpenAIChatModel,
)


class ChatRequest(BaseModel):
    message: MessageText
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    agent: Literal["chat"] = "chat"
    message: str


def create_app(model: ChatModel | None = None) -> FastAPI:
    app = FastAPI(title="SKADI AI", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents/chat/invoke")
    def invoke(request: ChatRequest) -> ChatResponse:
        try:
            chat_model = model or OpenAIChatModel.from_env()
            messages = [*request.history, ChatMessage(role="user", content=request.message)]
            return ChatResponse(message=chat_model.reply(messages))
        except ModelUnavailableError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    return app


app = create_app()
