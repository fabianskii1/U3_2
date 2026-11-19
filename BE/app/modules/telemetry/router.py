from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import now, valid_range
from app.database import get_session
from app.modules.equipment.models import sensor
from app.modules.alarms.models import setpoint
from app.modules.telemetry.models import sensor_signal

router = APIRouter(tags=["시계열"])
MAX_POINTS = 10_000

TREND_SQL = {
    "1m": """
        SELECT measured_at AS time, value
        FROM sensor_data_1m
        WHERE signal_id = :signal_id AND measured_at >= :from_time AND measured_at < :to_time
        ORDER BY measured_at
        LIMIT :limit
    """,
    "1h": """
        SELECT time_bucket(INTERVAL '1 hour', measured_at) AS time, avg(value) AS value
        FROM sensor_data_1m
        WHERE signal_id = :signal_id AND measured_at >= :from_time AND measured_at < :to_time
        GROUP BY 1 ORDER BY 1
        LIMIT :limit
    """,
    "1d": """
        SELECT date_trunc('day', measured_at AT TIME ZONE 'Asia/Seoul')
               AT TIME ZONE 'Asia/Seoul' AS time, avg(value) AS value
        FROM sensor_data_1m
        WHERE signal_id = :signal_id AND measured_at >= :from_time AND measured_at < :to_time
        GROUP BY 1 ORDER BY 1
        LIMIT :limit
    """,
}


@router.get("/api/trend")
async def trend(
    from_time: datetime = Query(alias="from"),
    to_time: datetime = Query(alias="to"),
    interval: str = Query(pattern="^(1s|1m|1h|1d)$"),
    sensor_id: str | None = None,
    signal_id: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    if sensor_id is None and signal_id is None:
        raise HTTPException(400, "sensor_id 또는 signal_id가 필요합니다.")
    if interval == "1s":
        raise HTTPException(400, "1초 원본 데이터가 없습니다. 1m, 1h 또는 1d를 선택하세요.")

    if signal_id is not None:
        signal = (
            (
                await db.execute(
                    select(
                        sensor_signal.c.signal_id, sensor_signal.c.sensor_id, sensor_signal.c.unit
                    ).where(sensor_signal.c.signal_id == signal_id)
                )
            )
            .mappings()
            .first()
        )
        if signal is None:
            raise HTTPException(404, "신호를 찾을 수 없습니다.")
        if sensor_id is not None and sensor_id != signal["sensor_id"]:
            raise HTTPException(400, "signal_id가 sensor_id에 속하지 않습니다.")
    else:
        instrument = (
            (
                await db.execute(
                    select(sensor.c.sensor_id, sensor.c.unit).where(sensor.c.sensor_id == sensor_id)
                )
            )
            .mappings()
            .first()
        )
        if instrument is None:
            raise HTTPException(404, "센서를 찾을 수 없습니다.")
        signals = (
            (
                await db.execute(
                    select(
                        sensor_signal.c.signal_id, sensor_signal.c.sensor_id, sensor_signal.c.unit
                    )
                    .where(sensor_signal.c.sensor_id == sensor_id)
                    .order_by(sensor_signal.c.signal_id)
                )
            )
            .mappings()
            .all()
        )
        if len(signals) > 1:
            raise HTTPException(
                400,
                "이 계측기에는 여러 신호가 있습니다. signal_id를 지정하세요: "
                + ", ".join(row["signal_id"] for row in signals),
            )
        if not signals:
            return {
                "sensor_id": sensor_id,
                "signal_id": None,
                "interval": interval,
                "unit": instrument["unit"],
                "points": [],
                "as_of": now(),
                "threshold_value": None,
                "setpoints": [],
            }
        signal = signals[0]

    rows = (
        (
            await db.execute(
                text(TREND_SQL[interval]),
                {
                    "signal_id": signal["signal_id"],
                    "from_time": from_time,
                    "to_time": to_time,
                    "limit": MAX_POINTS + 1,
                },
            )
        )
        .mappings()
        .all()
    )
    if len(rows) > MAX_POINTS:
        raise HTTPException(
            400, f"조회 지점은 최대 {MAX_POINTS:,}개입니다. 기간을 줄이거나 간격을 늘리세요."
        )
    rules = (
        (
            await db.execute(
                select(
                    setpoint.c.setpoint_id,
                    setpoint.c.alarm_level,
                    setpoint.c.direction,
                    setpoint.c.operator,
                    setpoint.c.calculation_type,
                    setpoint.c.parameter,
                    setpoint.c.effective_from,
                    setpoint.c.effective_to,
                ).where(
                    setpoint.c.signal_id == signal["signal_id"],
                    setpoint.c.unit == signal["unit"],
                    setpoint.c.effective_from < to_time,
                    (setpoint.c.effective_to.is_(None) | (setpoint.c.effective_to > from_time)),
                )
            )
        )
        .mappings()
        .all()
    )
    return {
        "sensor_id": signal["sensor_id"],
        "signal_id": signal["signal_id"],
        "interval": interval,
        "unit": signal["unit"],
        "points": [
            {"time": row["time"].isoformat(), "value": row["value"], "quality": None}
            for row in rows
        ],
        "as_of": now(),
        "threshold_value": None,
        "setpoints": [
            {
                "setpoint_id": rule["setpoint_id"],
                "alarm_level": rule["alarm_level"],
                "direction": rule["direction"],
                "operator": rule["operator"],
                "value": rule["parameter"] if rule["calculation_type"] == "FIXED" else None,
                "effective_from": rule["effective_from"].isoformat(),
                "effective_to": rule["effective_to"].isoformat() if rule["effective_to"] else None,
            }
            for rule in rules
        ],
    }
