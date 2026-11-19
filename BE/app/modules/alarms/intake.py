"""Record a monitoring event and snapshot the plant's first-ranked alarm report."""

import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as insert_postgres
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import serialize
from app.config import get_settings
from app.database import get_session
from app.modules.alarms.models import alarm, alarm_intake, setpoint
from app.modules.alarms.priorities import get_alarm_priorities
from app.modules.alarms.schemas import AlarmEventType, AlarmIntakeResult
from app.modules.chat.assets import Entity
from app.modules.chat.evidence import build_maintenance_draft, get_inspection_evidence
from app.modules.equipment.models import equipment, sensor
from app.modules.telemetry.models import sensor_signal
from app.modules.telemetry.router import trend

router = APIRouter()
monitor_bearer = HTTPBearer(auto_error=False)
KST = ZoneInfo("Asia/Seoul")
Code = Annotated[str, Field(min_length=1, max_length=30)]
Measurement = Annotated[float, Field(strict=True, allow_inf_nan=False)]
SourceEventId = Annotated[str, Field(min_length=1, max_length=128)]


class AlarmEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_event_id: SourceEventId
    equipment_id: Code
    sensor_id: Code
    alarm_start_time: AwareDatetime
    alarm_type: Literal["Setpoint"] = "Setpoint"
    is_active: StrictBool
    alarm_level: int = Field(strict=True, ge=0, le=4)
    unit: Code
    user_message: str = Field(min_length=1, max_length=2000)
    cof_score: Measurement | None = None
    closes_source_event_id: SourceEventId | None = None
    setpoint_id: SourceEventId | None = None
    event_type: AlarmEventType | None = None
    alarm_end_time: AwareDatetime | None = None
    sensor_start_time: AwareDatetime | None = None
    sensor_end_time: AwareDatetime | None = None

    @field_validator("alarm_start_time", "alarm_end_time", "sensor_start_time", "sensor_end_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.year < 2 or value > datetime.now(UTC):
            raise ValueError("유효한 알람 발생 시각을 입력해 주세요.")
        normalized = value.astimezone(UTC)
        if normalized.year < 2:
            raise ValueError("유효한 알람 발생 시각을 입력해 주세요.")
        return normalized

    @model_validator(mode="after")
    def validate_event(self) -> "AlarmEvent":
        if self.closes_source_event_id and (
            self.is_active or self.closes_source_event_id == self.source_event_id
        ):
            raise ValueError("해제할 알람의 기존 이벤트 ID와 is_active=false가 필요합니다.")
        if (self.setpoint_id is None) != (self.event_type is None):
            raise ValueError("setpoint_id와 event_type은 함께 지정해야 합니다.")
        if self.alarm_end_time and self.alarm_end_time < self.alarm_start_time:
            raise ValueError("조치 완료 시각은 알람 시작 시각 이후여야 합니다.")
        if self.sensor_start_time and self.sensor_start_time < self.alarm_start_time:
            raise ValueError("센서 초과 시작 시각은 알람 시작 시각 이후여야 합니다.")
        if self.sensor_end_time and (
            not self.sensor_start_time or self.sensor_end_time < self.sensor_start_time
        ):
            raise ValueError("센서 복귀 시각에는 그 이전의 센서 초과 시작 시각이 필요합니다.")
        return self


def _authenticate_monitor(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(monitor_bearer)],
) -> None:
    secret = get_settings().alarm_ingest_token
    expected = secret.get_secret_value() if secret else ""
    if not expected:
        raise HTTPException(503, "알람 수신이 설정되지 않았습니다.")
    if credentials is None or not hmac.compare_digest(
        credentials.credentials.encode(), expected.encode()
    ):
        raise HTTPException(401, "알람 수신 인증이 필요합니다.")


async def _sensor_scope(db: AsyncSession, event: AlarmEvent) -> str:
    asset = (
        await db.execute(
            select(equipment.c.plant_id, sensor.c.unit)
            .join(sensor, sensor.c.equipment_id == equipment.c.equipment_id)
            .where(
                equipment.c.equipment_id == event.equipment_id,
                sensor.c.sensor_id == event.sensor_id,
            )
        )
    ).one_or_none()
    if asset is None:
        raise HTTPException(400, "설비에 속한 센서 태그를 지정해 주세요.")
    if event.setpoint_id is None:
        if event.unit != asset.unit:
            raise HTTPException(400, "알람 단위가 센서에 등록된 단위와 일치해야 합니다.")
        return asset.plant_id

    rule_query = (
        select(setpoint.c.alarm_level, setpoint.c.unit, sensor_signal.c.unit.label("signal_unit"))
        .join(sensor_signal, setpoint.c.signal_id == sensor_signal.c.signal_id)
        .where(
            setpoint.c.setpoint_id == event.setpoint_id,
            setpoint.c.equipment_id == event.equipment_id,
            setpoint.c.sensor_id == event.sensor_id,
            sensor_signal.c.sensor_id == event.sensor_id,
        )
    )
    if event.closes_source_event_id is None:
        rule_query = rule_query.where(
            setpoint.c.effective_from <= event.alarm_start_time,
            or_(
                setpoint.c.effective_to.is_(None), setpoint.c.effective_to > event.alarm_start_time
            ),
        )
    rule = (await db.execute(rule_query)).one_or_none()
    if rule is None:
        raise HTTPException(400, "발생 시점에 해당 설비와 센서에 유효한 setpoint가 필요합니다.")
    if (
        event.alarm_level != rule.alarm_level
        or event.unit != rule.unit
        or event.unit not in (asset.unit, rule.signal_unit)
    ):
        raise HTTPException(400, "알람 등급과 단위가 setpoint에 등록된 값과 일치해야 합니다.")
    return asset.plant_id


async def _close_alarm(db: AsyncSession, event: AlarmEvent) -> str | None:
    if event.closes_source_event_id is None:
        return None
    source_alarm_id = (
        select(alarm_intake.c.alarm_id)
        .where(alarm_intake.c.source_event_id == event.closes_source_event_id)
        .scalar_subquery()
    )
    closed_id = (
        await db.execute(
            update(alarm)
            .where(
                alarm.c.alarm_id == source_alarm_id,
                alarm.c.equipment_id == event.equipment_id,
                alarm.c.sensor_id == event.sensor_id,
                alarm.c.setpoint_id.is_not_distinct_from(event.setpoint_id),
                alarm.c.is_active.is_(True),
                alarm.c.alarm_start_time <= event.alarm_start_time,
            )
            .values(is_active=False)
            .returning(alarm.c.alarm_id)
        )
    ).scalar_one_or_none()
    if closed_id is None:
        raise HTTPException(409, "해제할 활성 알람을 확인할 수 없습니다.")
    return str(closed_id)


async def _recent_trend(
    db: AsyncSession, selected: dict, entity: Entity
) -> tuple[dict, dict[str, str] | None]:
    stop = datetime.fromisoformat(selected["alarm_start_time"]).replace(microsecond=0)
    start = stop - timedelta(days=7) if stop.year >= 2 else stop
    summary = {
        "status": "empty",
        "from": start.astimezone(UTC).isoformat(),
        "to": stop.astimezone(UTC).isoformat(),
        "interval": "1h",
        "point_count": 0,
        "unit": None,
        "min": None,
        "max": None,
    }
    if stop.year < 2:
        summary["status"] = "out_of_range"
        return summary, None
    sensor_id = selected["sensor_id"]
    selected_setpoint = selected["setpoint_id"]
    signal_query = select(sensor_signal.c.signal_id).where(sensor_signal.c.sensor_id == sensor_id)
    if selected_setpoint is not None:
        signal_query = signal_query.join(
            setpoint, setpoint.c.signal_id == sensor_signal.c.signal_id
        ).where(setpoint.c.setpoint_id == selected_setpoint)
    signals = (await db.execute(signal_query.limit(2))).scalars().all()
    if len(signals) != 1:
        if signals:
            summary["status"] = "ambiguous"
        return summary, None

    telemetry = await trend(
        from_time=start,
        to_time=stop,
        interval="1h",
        sensor_id=sensor_id,
        signal_id=signals[0],
        db=db,
    )
    values = [
        point["value"]
        for point in telemetry["points"]
        if point["value"] is not None and math.isfinite(point["value"])
    ]
    summary["unit"] = telemetry["unit"]
    if values:
        summary.update(status="ok", point_count=len(values), min=min(values), max=max(values))
    return summary, {
        "title": "알람 발생 전 7일 추이 보기",
        "href": entity.link(
            "/trend",
            sensor_id=sensor_id,
            alarm_id=selected["alarm_id"],
            interval="1h",
            **{
                "from": start.astimezone(KST).replace(tzinfo=None).isoformat(),
                "to": stop.astimezone(KST).replace(tzinfo=None).isoformat(),
            },
        ),
    }


async def _initial_report(db: AsyncSession, selected: dict, as_of: str) -> dict:
    entity = Entity("equipment", selected["equipment_id"], selected["equipment_name"])
    evidence = await get_inspection_evidence(db, entity.id)
    message, source_links = build_maintenance_draft(entity.name, evidence, alarm=selected)
    trend_summary, trend_link = await _recent_trend(db, selected, entity)
    trend_note = {
        "ambiguous": "연결된 신호가 여러 개입니다. 신호를 선택해 주세요.",
        "empty": "집계된 관측값이 없습니다.",
        "out_of_range": "발생 시각 이전 7일 범위를 표시할 수 없습니다.",
        "ok": (
            f"유효 시간 집계 {trend_summary['point_count']}건 · "
            f"최소 {trend_summary['min']} / 최대 {trend_summary['max']} {trend_summary['unit']}"
        ),
    }[trend_summary["status"]]
    links = [
        {
            "title": "알람 설비 현황 열기",
            "href": entity.link(
                "/equip", sensor_id=selected["sensor_id"], alarm_id=selected["alarm_id"]
            ),
        },
        *([trend_link] if trend_link else []),
        *source_links,
    ]
    return {
        "version": 1,
        "alarm_id": selected["alarm_id"],
        "equipment_id": entity.id,
        "sensor_id": selected["sensor_id"],
        "setpoint_id": selected["setpoint_id"],
        "event_type": selected["event_type"],
        "alarm_start_time": selected["alarm_start_time"],
        "cof_score": selected["cof_score"],
        "as_of": as_of,
        "message": (
            "**같은 플랜트의 CoF 평가 완료 활성 Setpoint 알람 중 1순위**\n\n"
            f"{message}\n\n**알람 발생 전 7일 추이** · {trend_note}"
        ),
        "links": links,
        "trend": trend_summary,
    }


@router.post(
    "/api/alarms/intake",
    status_code=201,
    dependencies=[Depends(_authenticate_monitor)],
    responses={
        201: {"model": AlarmIntakeResult, "description": "알람 저장"},
        200: {"model": AlarmIntakeResult, "description": "기존 수신 결과 재전송"},
        409: {"description": "이벤트 충돌"},
    },
)
async def intake_alarm(
    event: AlarmEvent,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    optional_fields = {
        "setpoint_id",
        "event_type",
        "alarm_end_time",
        "sensor_start_time",
        "sensor_end_time",
    }
    missing_fields = {field for field in optional_fields if getattr(event, field) is None}
    digest = hashlib.sha256(event.model_dump_json(exclude=missing_fields).encode()).hexdigest()
    async with db.begin():
        inserted = (
            await db.execute(
                insert_postgres(alarm_intake)
                .values(source_event_id=event.source_event_id, request_digest=digest)
                .on_conflict_do_nothing(index_elements=[alarm_intake.c.source_event_id])
                .returning(alarm_intake.c.source_event_id)
            )
        ).scalar_one_or_none()
        if inserted is None:
            existing = (
                await db.execute(
                    select(alarm_intake.c.request_digest, alarm_intake.c.response).where(
                        alarm_intake.c.source_event_id == event.source_event_id
                    )
                )
            ).one()
            if digest != existing.request_digest:
                raise HTTPException(409, "이 이벤트 ID는 이미 다른 알람 내용으로 수신되었습니다.")
            response.status_code = 200
            return existing.response

        plant_id = await _sensor_scope(db, event)
        # Serialize writes and report selection within a plant, including concurrent clears.
        await db.execute(select(func.pg_advisory_xact_lock(478431, func.hashtext(plant_id))))
        closed_alarm_id = await _close_alarm(db, event)
        alarm_row = (
            (
                await db.execute(
                    insert_postgres(alarm)
                    .values(
                        source_alarm_id=event.source_event_id,
                        **event.model_dump(exclude={"source_event_id", "closes_source_event_id"}),
                    )
                    .on_conflict_do_nothing(index_elements=[alarm.c.source_alarm_id])
                    .returning(*alarm.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if alarm_row is None:
            raise HTTPException(409, "이미 등록된 원본 알람 ID입니다.")
        priority = await get_alarm_priorities(db, plant_id=plant_id, limit=1)
        ranked = priority.pop("items")
        selected = ranked[0] if ranked else None
        initial_report = (
            await _initial_report(db, selected, priority["as_of"]) if selected else None
        )
        selected_id = selected["alarm_id"] if selected else None
        result = {
            "alarm": serialize(alarm_row),
            "closed_alarm_id": closed_alarm_id,
            "priority": {**priority, "plant_id": plant_id, "selected_alarm_id": selected_id},
            "initial_report": initial_report,
        }
        await db.execute(
            update(alarm_intake)
            .where(alarm_intake.c.source_event_id == event.source_event_id)
            .values(
                alarm_id=alarm_row["alarm_id"],
                selected_alarm_id=int(selected_id) if selected_id else None,
                processed_at=datetime.fromisoformat(priority["as_of"]),
                response=result,
            )
        )
    return result


async def get_initial_alarm_report(db: AsyncSession, alarm_id: int) -> dict | None:
    receipt = (
        await db.execute(
            select(alarm_intake.c.response)
            .where(alarm_intake.c.selected_alarm_id == alarm_id)
            .order_by(alarm_intake.c.processed_at.desc(), alarm_intake.c.source_event_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return receipt.get("initial_report") if receipt else None


@router.get("/api/alarms/{alarm_id}/initial-report")
async def read_initial_report(
    alarm_id: Annotated[int, Path(ge=1, le=2**63 - 1)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    report = await get_initial_alarm_report(db, alarm_id)
    if report is None:
        raise HTTPException(404, "이 알람에 생성된 초기 보고서가 없습니다.")
    return report
