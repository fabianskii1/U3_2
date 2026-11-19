"""Latest stored readings for equipment sensors."""

from datetime import UTC, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

LATEST_READINGS = text(
    """
    SELECT signal.sensor_id, reading.value, reading.measured_at
    FROM sensor_signal AS signal
    LEFT JOIN LATERAL (
        SELECT value, measured_at
        FROM sensor_data_1m
        WHERE signal_id = signal.signal_id AND measured_at <= :as_of
        ORDER BY measured_at DESC
        LIMIT 1
    ) AS reading ON TRUE
    WHERE signal.sensor_id IN :sensor_ids
    ORDER BY signal.sensor_id, reading.measured_at DESC NULLS LAST, signal.signal_id
    """
).bindparams(bindparam("sensor_ids", expanding=True))


async def latest_sensor_readings(
    db: AsyncSession, sensor_ids: list[str]
) -> dict[str, dict[str, str | float | None]]:
    if not sensor_ids:
        return {}

    rows = (
        (
            await db.execute(
                LATEST_READINGS,
                {"sensor_ids": sensor_ids, "as_of": datetime.now(UTC)},
            )
        )
        .mappings()
        .all()
    )
    readings: dict[str, dict[str, str | float | None]] = {}
    for row in rows:
        readings.setdefault(
            row["sensor_id"],
            {
                "current_value": row["value"],
                "measured_at": row["measured_at"].isoformat() if row["measured_at"] else None,
            },
        )
    return readings
