"""Plain conversation using the OpenAI Responses API."""

import logging
import os
from pathlib import Path
from typing import Annotated, Literal, Protocol

from dotenv import dotenv_values
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, StringConstraints

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
logger = logging.getLogger(__name__)
MessageText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: MessageText


class ChatModel(Protocol):
    def reply(self, messages: list[ChatMessage]) -> str: ...


class ModelUnavailableError(RuntimeError):
    def __init__(
        self, message: str, code: str = "MODEL_UNAVAILABLE", http_status: int = 503
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _model_error(exc: OpenAIError) -> ModelUnavailableError:
    logger.warning(
        "OpenAI chat failed: error_type=%s upstream_status=%s",
        type(exc).__name__,
        getattr(exc, "status_code", None),
    )
    if isinstance(exc, AuthenticationError):
        return ModelUnavailableError(
            "OpenAI API 키 인증에 실패했습니다. AI/.env의 키를 확인해 주세요.",
            "OPENAI_AUTHENTICATION_FAILED",
            502,
        )
    if isinstance(exc, PermissionDeniedError):
        return ModelUnavailableError(
            "API 키에 선택한 모델의 사용 권한이 없습니다.", "OPENAI_PERMISSION_DENIED", 502
        )
    if isinstance(exc, NotFoundError):
        return ModelUnavailableError(
            "설정한 OpenAI 모델을 찾을 수 없습니다.", "OPENAI_MODEL_NOT_FOUND", 502
        )
    if isinstance(exc, RateLimitError):
        return ModelUnavailableError(
            "OpenAI 요청 한도 또는 사용 가능 잔액을 확인해 주세요.", "OPENAI_RATE_LIMIT", 503
        )
    if isinstance(exc, BadRequestError):
        return ModelUnavailableError("OpenAI 요청 형식이 거절됐습니다.", "OPENAI_BAD_REQUEST", 502)
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return ModelUnavailableError(
            "OpenAI 서버에 연결하지 못했습니다.", "OPENAI_CONNECTION_FAILED", 503
        )
    return ModelUnavailableError("OpenAI 호출에 실패했습니다.", "OPENAI_UPSTREAM_ERROR", 503)


class OpenAIChatModel:
    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_env(cls) -> "OpenAIChatModel":
        file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
        api_key = (
            file_values.get("OPENAI_API_KEY")
            or file_values.get("api_key")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("api_key")
        )
        if not api_key:
            raise ModelUnavailableError(
                "OPENAI_API_KEY 또는 api_key가 설정되지 않았습니다.", "MODEL_CONFIG_MISSING"
            )
        model = file_values.get("OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1"
        return cls(api_key=api_key, model=model)

    def reply(self, messages: list[ChatMessage]) -> str:
        try:
            with OpenAI(api_key=self.api_key, timeout=15.0, max_retries=0) as client:
                response = client.responses.create(
                    model=self.model,
                    instructions=(
                        "당신은 SKADI의 대화 도우미입니다. 사용자의 언어에 맞춰 친절하고 "
                        "간결하게 답하세요. 제공되지 않은 설비 데이터를 조회하거나 "
                        "현장 작업을 실행했다고 말하지 마세요."
                    ),
                    input=[message.model_dump() for message in messages],
                    max_output_tokens=800,
                    store=False,
                )
        except OpenAIError as exc:
            raise _model_error(exc) from exc
        answer = response.output_text.strip()
        if not answer:
            raise ModelUnavailableError("AI 응답이 비어 있습니다.", "MODEL_EMPTY_RESPONSE", 502)
        return answer
