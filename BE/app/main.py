import logging
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.modules.alarms.router import router as alarms_router
from app.modules.chat.router import router as chat_router
from app.modules.equipment.router import router as equipment_router
from app.modules.hierarchy.router import router as hierarchy_router
from app.modules.histories.router import router as histories_router
from app.modules.manuals.router import router as manuals_router
from app.modules.reports.router import router as reports_router
from app.modules.telemetry.router import router as telemetry_router

logger = logging.getLogger(__name__)
app = FastAPI(
    title="SKADI BE",
    version="0.1.0",
    openapi_tags=[
        {"name": "계층", "description": "Plant·Unit·설비 계층 조회"},
        {"name": "설비", "description": "설비 상세와 센서 조회"},
        {"name": "시계열", "description": "센서 트렌드 조회"},
        {"name": "알람", "description": "저장된 알람 이력 조회"},
        {"name": "고장·정비 이력", "description": "고장 유형과 고장·정비 이력 조회"},
        {"name": "보고서", "description": "보고서 목록과 상세 조회"},
        {"name": "매뉴얼", "description": "설비 매뉴얼 목록 조회"},
        {"name": "채팅", "description": "설비 ID 조회 채팅"},
        {"name": "운영 상태", "description": "DB 연결 상태 확인"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
for domain_router in (
    hierarchy_router,
    equipment_router,
    telemetry_router,
    alarms_router,
    histories_router,
    reports_router,
    manuals_router,
    chat_router,
):
    app.include_router(domain_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error(request: Request, status: int, code: str, message: str, details: Any = None):
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "request_id": request.state.request_id,
            "details": details,
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    code = {400: "BAD_REQUEST", 404: "NOT_FOUND"}.get(exc.status_code, "HTTP_ERROR")
    return error(request, exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    details = [{"loc": e["loc"], "message": e["msg"]} for e in exc.errors()]
    return error(request, 422, "VALIDATION_ERROR", "요청 필드를 확인해 주세요.", details)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error")
    return error(request, 500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")


@app.get("/health", tags=["운영 상태"])
async def health(db: AsyncSession = Depends(get_session)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
