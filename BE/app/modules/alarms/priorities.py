from datetime import UTC, datetime

from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import serialize
from app.modules.alarms.models import alarm, alarm_intake
from app.modules.equipment.models import equipment, sensor


async def get_alarm_priorities(
    db: AsyncSession,
    *,
    equipment_id: str | None = None,
    equipment_group_id: str | None = None,
    plant_id: str | None = None,
    equipment_type: str | None = None,
    limit: int = 3,
) -> dict[str, object]:
    """Read counts and ordered alarms from one snapshot of explicitly assessed Setpoints."""
    as_of = datetime.now(UTC)
    scope = (
        select(
            *alarm.c,
            equipment.c.equipment_name,
            sensor.c.measurement_name.label("sensor_name"),
        )
        .join(equipment, alarm.c.equipment_id == equipment.c.equipment_id)
        .join(
            sensor,
            and_(
                alarm.c.sensor_id == sensor.c.sensor_id,
                equipment.c.equipment_id == sensor.c.equipment_id,
            ),
        )
        .where(func.lower(alarm.c.alarm_type) == "setpoint", alarm.c.alarm_start_time <= as_of)
    )
    for column, value in (
        (equipment.c.equipment_id, equipment_id),
        (equipment.c.equipment_group_id, equipment_group_id),
        (equipment.c.plant_id, plant_id),
        (equipment.c.equipment_type, equipment_type),
    ):
        if value is not None:
            scope = scope.where(column == value)

    scoped = scope.cte("scoped_alarms")
    fields = scoped.c
    active = fields.is_active.is_(True)
    scored = fields.cof_score.is_not(None)
    counts = select(
        func.count().label("record_count"),
        func.count().filter(active).label("active_count"),
        func.count().filter(active, ~scored).label("unscored_count"),
        func.count().filter(fields.is_active.is_(None)).label("unknown_count"),
    ).cte("alarm_counts")
    order = (
        fields.cof_score.desc(),
        fields.alarm_level.desc(),
        fields.alarm_start_time.asc(),
        fields.alarm_id.asc(),
    )
    top = (
        select(
            *fields,
            func.row_number().over(order_by=order).label("rank"),
            select(alarm_intake.c.source_event_id)
            .where(alarm_intake.c.selected_alarm_id == fields.alarm_id)
            .exists()
            .label("has_initial_report"),
        )
        .where(active, scored)
        .order_by(*order)
        .limit(limit)
        .cte("top_alarms")
    )
    priorities_query = (
        select(*counts.c, *top.c).select_from(counts.outerjoin(top, true())).order_by(top.c.rank)
    )
    results = (await db.execute(priorities_query)).mappings().all()
    summary = results[0]
    items = [
        {
            **serialize({column.key: row[column.key] for column in top.c}),
            "reason": row["user_message"],
        }
        for row in results
        if row["alarm_id"] is not None
    ]
    if items:
        status = "ok"
    elif summary["active_count"]:
        status = "unscored"
    elif summary["unknown_count"] or not summary["record_count"]:
        status = "unavailable"
    else:
        status = "empty"

    return {
        "status": status,
        "as_of": as_of.isoformat(),
        "active_count": summary["active_count"],
        "unscored_count": summary["unscored_count"],
        "unknown_count": summary["unknown_count"],
        "items": items,
    }
