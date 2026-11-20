"""Read incidents, their fault candidates and linked alarms."""

import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import serialize
from app.modules.alarms.models import alarm
from app.modules.equipment.models import equipment, sensor
from app.modules.histories.models import error_type
from app.modules.incidents.models import incident, incident_candidate
from app.modules.telemetry.models import sensor_data_1m, sensor_signal

IncidentStatus = Literal["upcoming", "ongoing", "closed"]
KST = ZoneInfo("Asia/Seoul")
LEVEL_LABELS = ("정상", "주의", "경고", "위험", "비상")
TREND_BEFORE = timedelta(hours=24)
TREND_AFTER = timedelta(hours=6)

diagnosis_type = error_type.alias("diagnosis_type")
top_risk_type = error_type.alias("top_risk_type")
lead_sensor = sensor.alias("lead_sensor")


def status_expression(as_of: datetime):
    return case(
        (incident.c.incident_start_time > as_of, literal("upcoming")),
        (
            or_(incident.c.incident_end_time.is_(None), incident.c.incident_end_time > as_of),
            literal("ongoing"),
        ),
        else_=literal("closed"),
    )


def _summary_query(as_of: datetime):
    linked = (
        select(func.count()).where(alarm.c.incident_id == incident.c.incident_id).scalar_subquery()
    )
    return (
        select(
            *incident.c,
            status_expression(as_of).label("status"),
            equipment.c.equipment_name,
            diagnosis_type.c.error_type_name.label("diagnosis"),
            top_risk_type.c.error_type_name.label("top_risk_fault"),
            lead_sensor.c.measurement_name.label("lead_sensor_name"),
            linked.label("linked_alarm_count"),
        )
        .join(equipment, equipment.c.equipment_id == incident.c.equipment_id)
        .join(diagnosis_type, diagnosis_type.c.error_type_id == incident.c.diagnosis_error_type_id)
        .join(top_risk_type, top_risk_type.c.error_type_id == incident.c.top_risk_error_type_id)
        .outerjoin(lead_sensor, lead_sensor.c.sensor_id == incident.c.lead_sensor_id)
    )


def _encode(start: datetime, incident_id: str) -> str:
    payload = json.dumps({"time": start.isoformat(), "id": incident_id})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        moment = datetime.fromisoformat(payload["time"])
        if moment.tzinfo is None or not isinstance(payload["id"], str):
            raise ValueError
        return moment, payload["id"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPException(400, "잘못된 cursor입니다.") from exc


async def list_incidents(
    db: AsyncSession,
    *,
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_id: str | None = None,
    equipment_ids: list[str] | None = None,
    equipment_type: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    min_level: int | None = None,
    actionable: bool | None = None,
    status: IncidentStatus | None = None,
    as_of: datetime | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
    state = status_expression(as_of)
    stmt = _summary_query(as_of)
    for column, value in (
        (incident.c.plant_id, plant_id),
        (incident.c.equipment_group_id, equipment_group_id),
        (incident.c.equipment_id, equipment_id),
        (equipment.c.equipment_type, equipment_type),
        (incident.c.actionable, actionable),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if equipment_ids is not None:
        stmt = stmt.where(incident.c.equipment_id.in_(equipment_ids))
    if from_time is not None:
        stmt = stmt.where(incident.c.incident_start_time >= from_time)
    if to_time is not None:
        stmt = stmt.where(incident.c.incident_start_time < to_time)
    if min_level is not None:
        stmt = stmt.where(incident.c.peak_level >= min_level)
    # Incidents that have not started at as_of are only shown when asked for.
    stmt = stmt.where(state == status) if status else stmt.where(state != "upcoming")
    if cursor:
        moment, key = _decode(cursor)
        stmt = stmt.where(
            tuple_(incident.c.incident_start_time, incident.c.incident_id) < (moment, key)
        )
    stmt = stmt.order_by(incident.c.incident_start_time.desc(), incident.c.incident_id.desc())
    rows = (await db.execute(stmt.limit(limit + 1))).mappings().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "as_of": as_of.isoformat(),
        "items": [serialize(row) for row in rows],
        "next_cursor": _encode(rows[-1]["incident_start_time"], rows[-1]["incident_id"])
        if has_more
        else None,
    }


async def _signals(db: AsyncSession, sensor_ids: list[str]) -> list[dict[str, Any]]:
    rows = (
        (
            await db.execute(
                select(
                    sensor.c.sensor_id,
                    sensor.c.measurement_name,
                    sensor_signal.c.signal_id,
                    sensor_signal.c.unit,
                )
                .join(sensor_signal, sensor_signal.c.sensor_id == sensor.c.sensor_id)
                .where(sensor.c.sensor_id.in_(sensor_ids))
            )
        )
        .mappings()
        .all()
    )
    order = {sensor_id: index for index, sensor_id in enumerate(sensor_ids)}
    return sorted((dict(row) for row in rows), key=lambda row: order[row["sensor_id"]])


async def _coverage(db: AsyncSession, signal_ids: list[str], start: datetime, end: datetime) -> str:
    if not signal_ids or end <= start:
        return "none"
    count = await db.scalar(
        select(func.count()).where(
            sensor_data_1m.c.signal_id.in_(signal_ids),
            sensor_data_1m.c.measured_at >= start,
            sensor_data_1m.c.measured_at < end,
        )
    )
    expected = len(signal_ids) * int((end - start).total_seconds() // 60)
    if not count:
        return "none"
    return "full" if count >= expected * 0.95 else "partial"


async def _load(db: AsyncSession, incident_id: str, as_of: datetime):
    row = (
        (await db.execute(_summary_query(as_of).where(incident.c.incident_id == incident_id)))
        .mappings()
        .first()
    )
    if row is None:
        return None, [], []
    candidates = (
        (
            await db.execute(
                select(
                    *(c for c in incident_candidate.c if c.key != "incident_id"),
                    error_type.c.error_type_name.label("fault"),
                )
                .join(error_type, error_type.c.error_type_id == incident_candidate.c.error_type_id)
                .where(incident_candidate.c.incident_id == incident_id)
                .order_by(incident_candidate.c.rank)
            )
        )
        .mappings()
        .all()
    )
    alarms = (
        (
            await db.execute(
                select(*alarm.c, sensor.c.measurement_name.label("sensor_name"))
                .join(sensor, sensor.c.sensor_id == alarm.c.sensor_id)
                .where(alarm.c.incident_id == incident_id)
                .order_by(alarm.c.alarm_start_time, alarm.c.alarm_id)
            )
        )
        .mappings()
        .all()
    )
    return row, candidates, alarms


def _trend_window(row, as_of: datetime) -> tuple[datetime, datetime]:
    start = row["incident_start_time"] - TREND_BEFORE
    if row["status"] == "upcoming":
        return start, (row["incident_end_time"] or row["incident_start_time"]) + TREND_AFTER
    last = min(row["incident_end_time"] or as_of, as_of)
    return start, min(last + TREND_AFTER, as_of)


async def get_incident(
    db: AsyncSession, incident_id: str, *, as_of: datetime | None = None
) -> dict[str, Any] | None:
    as_of = (as_of or datetime.now(UTC)).astimezone(UTC)
    row, candidates, alarms = await _load(db, incident_id, as_of)
    if row is None:
        return None
    lead = [row["lead_sensor_id"]] if row["lead_sensor_id"] else []
    sensor_ids = list(dict.fromkeys([*lead, *(item["sensor_id"] for item in alarms)]))
    signals = await _signals(db, sensor_ids)
    start, end = _trend_window(row, as_of)
    coverage = await _coverage(db, [item["signal_id"] for item in signals], start, end)
    return {
        **serialize(row),
        "as_of": as_of.isoformat(),
        "candidates": [serialize(item) for item in candidates],
        "alarms": [serialize(item) for item in alarms],
        "trend_window": {"from": start.isoformat(), "to": end.isoformat(), "signals": signals},
        "data_coverage": coverage,
        "warnings": _warnings(row, alarms),
    }


def _warnings(row, alarms) -> list[str]:
    warnings = []
    if row["alarm_count"] != len(alarms):
        warnings.append(
            f"분석기 alarm_count({row['alarm_count']})와 연결된 알람 수({len(alarms)})가 다릅니다."
        )
    first = alarms[0]["alarm_start_time"] if alarms else None
    if first and row["first_alarm_time"] and row["first_alarm_time"] != first:
        warnings.append("첫 알람 시각이 연결된 알람의 가장 이른 시작 시각과 다릅니다.")
    return warnings


def _kst(value: datetime | None) -> str:
    return value.astimezone(KST).strftime("%m-%d %H:%M") if value else "—"


def _level(value: int | None) -> str:
    return LEVEL_LABELS[value] if value is not None else "미기록"


async def incident_report_draft(db: AsyncSession, incident_id: str) -> dict[str, Any] | None:
    """Prefill a maintenance report draft. Causes stay as items to review."""
    row, candidates, alarms = await _load(db, incident_id, datetime.now(UTC))
    if row is None:
        return None
    symptom = [
        (
            f"사건 {_kst(row['incident_start_time'])} 시작 · {_kst(row['detect_time'])} 감지"
            f" · 선행 센서 {row['lead_sensor_name'] or '미기록'}"
        ),
        *(
            f"- {item['sensor_name']}({item['sensor_id']}) {item['event_type'] or '알람'}"
            f" {_kst(item['alarm_start_time'])}~{_kst(item['alarm_end_time'])}"
            f" · 최고 {_level(item['peak_level'])}"
            for item in alarms
        ),
    ]
    causes = [
        f"{c['rank']}. {c['fault']} (점수 {c['score']:g})"
        f"{' · 진단(추정)' if c['is_diagnosis'] else ''} — {c['evidence']}"
        for c in candidates
    ]
    return {
        "incident_id": incident_id,
        "equipment_id": row["equipment_id"],
        "title": f"{row['equipment_name']} {row['diagnosis']} 의심 점검 보고서",
        "symptom": "\n".join(symptom),
        "cause": "검토 필요 · 분석기 원인 후보(추정)\n" + "\n".join(causes),
        "action": "현장 점검 후 입력",
        "risk": (
            f"대응 등급 {row['alarm_grade']} ({row['grade_reason']}) · "
            f"PoF {row['top_pof']:.1%} · 최고 등급 {_level(row['peak_level'])}"
        ),
        "suspected_error_type_ids": [str(c["error_type_id"]) for c in candidates],
    }


async def incidents_overlapping(
    db: AsyncSession, equipment_id: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    as_of = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                _summary_query(as_of).where(
                    incident.c.equipment_id == equipment_id,
                    incident.c.incident_start_time < end,
                    or_(
                        incident.c.incident_end_time.is_(None),
                        incident.c.incident_end_time > start,
                    ),
                    incident.c.incident_start_time <= as_of,
                )
            )
        )
        .mappings()
        .all()
    )
    return [
        {
            key: serialize(row)[key]
            for key in (
                "incident_id",
                "incident_start_time",
                "incident_end_time",
                "peak_level",
                "diagnosis",
                "status",
            )
        }
        for row in rows
    ]
