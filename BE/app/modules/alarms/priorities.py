from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import String, and_, case, cast, func, select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import serialize
from app.modules.alarms.models import alarm, alarm_intake
from app.modules.alarms.schemas import PriorityGroup
from app.modules.equipment.models import equipment, sensor
from app.modules.histories.models import error_type
from app.modules.incidents.models import incident


def _historical_state(as_of: datetime):
    # Receipts preserve the initial state even when the alarm row is later cleared.
    opened = alarm_intake.alias("opening_receipt")
    close_event = alarm.alias("close_event")
    closed = (
        select(
            alarm_intake.c.response["closed_alarm_id"].as_string().label("closed_alarm_id"),
            func.min(close_event.c.alarm_start_time).label("closed_at"),
        )
        .join(close_event, close_event.c.alarm_id == alarm_intake.c.alarm_id)
        .where(alarm_intake.c.response["closed_alarm_id"].as_string().is_not(None))
        .group_by("closed_alarm_id")
        .subquery()
    )
    initially_active = opened.c.response["alarm"]["is_active"].as_boolean()
    state = case((closed.c.closed_at <= as_of, False), else_=initially_active)
    return opened, closed, state


async def get_alarm_priorities(
    db: AsyncSession,
    *,
    equipment_id: str | None = None,
    equipment_ids: Sequence[str] | None = None,
    equipment_group_id: str | None = None,
    plant_id: str | None = None,
    equipment_type: str | None = None,
    limit: int = 3,
    group_by: PriorityGroup = "equipment",
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Read counts and ordered alarms in one SQL snapshot."""
    historical = as_of is not None
    as_of = as_of or datetime.now(UTC)
    fields = list(alarm.c)
    source = alarm
    if historical:
        opened, closed, state = _historical_state(as_of)
        source = alarm.outerjoin(opened, opened.c.alarm_id == alarm.c.alarm_id).outerjoin(
            closed, closed.c.closed_alarm_id == cast(alarm.c.alarm_id, String)
        )
        fields = [col if col.key != "is_active" else state.label("is_active") for col in fields]

    scope = (
        select(*fields, equipment.c.equipment_name, sensor.c.measurement_name.label("sensor_name"))
        .select_from(source)
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
    if equipment_ids is not None:
        scope = scope.where(equipment.c.equipment_id.in_(equipment_ids))

    scoped = scope.cte("scoped_alarms")
    fields = scoped.c
    active = fields.is_active.is_(True)
    scored = fields.cof_score.is_not(None)
    condition = func.distinct(tuple_(fields.sensor_id, fields.setpoint_id))
    counts = select(
        func.count().label("record_count"),
        func.count().filter(active).label("active_count"),
        func.count().filter(active, ~scored).label("unscored_count"),
        func.count().filter(fields.is_active.is_(None)).label("unknown_count"),
        func.count(func.distinct(fields.equipment_id))
        .filter(active)
        .label("affected_equipment_count"),
        func.count(condition).filter(active).label("condition_count"),
    ).cte("alarm_counts")
    equipment_counts = (
        select(
            fields.equipment_id,
            func.count().label("equipment_active_count"),
            func.count().filter(fields.event_type == "예측").label("prediction_count"),
            func.count()
            .filter(fields.event_type == "임계치 초과")
            .label("threshold_exceeded_count"),
            func.count(condition).label("condition_count"),
        )
        .where(active)
        .group_by(fields.equipment_id)
        .cte("equipment_counts")
    )

    def rank_order(columns):
        return (
            columns.cof_score.desc(),
            columns.alarm_level.desc(),
            columns.alarm_start_time.asc(),
            columns.alarm_id.asc(),
        )

    candidates = select(*fields).where(active, scored)
    if group_by == "equipment":
        per_equipment = candidates.add_columns(
            func.row_number()
            .over(partition_by=fields.equipment_id, order_by=rank_order(fields))
            .label("equipment_rank")
        ).subquery()
        candidates = select(*(per_equipment.c[col.key] for col in fields)).where(
            per_equipment.c.equipment_rank == 1
        )

    eligible = candidates.subquery()
    order = rank_order(eligible.c)
    top = (
        select(
            *eligible.c,
            equipment_counts.c.equipment_active_count,
            equipment_counts.c.prediction_count,
            equipment_counts.c.threshold_exceeded_count,
            equipment_counts.c.condition_count,
            func.row_number().over(order_by=order).label("rank"),
            select(alarm_intake.c.source_event_id)
            .where(alarm_intake.c.selected_alarm_id == eligible.c.alarm_id)
            .exists()
            .label("has_initial_report"),
            select(error_type.c.error_type_name)
            .select_from(
                incident.join(
                    error_type, error_type.c.error_type_id == incident.c.diagnosis_error_type_id
                )
            )
            .where(incident.c.incident_id == eligible.c.incident_id)
            .scalar_subquery()
            .label("diagnosis"),
            select(incident.c.incident_score)
            .where(incident.c.incident_id == eligible.c.incident_id)
            .scalar_subquery()
            .label("incident_score"),
        )
        .join(equipment_counts, eligible.c.equipment_id == equipment_counts.c.equipment_id)
        .order_by(*order)
        .limit(limit)
        .cte("top_alarms")
    )
    # Use column objects to distinguish global and per-equipment condition counts.
    query = (
        select(*counts.c, *top.c).select_from(counts.outerjoin(top, true())).order_by(top.c.rank)
    )
    results = (await db.execute(query)).mappings().all()
    summary = results[0]
    items = [
        {**serialize({column.key: row[column] for column in top.c}), "reason": row["user_message"]}
        for row in results
        if row["alarm_id"] is not None
    ]
    if items:
        status = "ok"
    elif summary["active_count"]:
        status = "unscored"
    elif summary["unknown_count"]:
        status = "unavailable"
    elif summary["record_count"]:
        status = "empty"
    else:
        status = "no_data"

    return {
        "status": status,
        "as_of": as_of.isoformat(),
        "group_by": group_by,
        **{column.key: summary[column] for column in counts.c if column.key != "record_count"},
        "items": items,
    }
