"""AG-03 Executor. Agent code operates through the application's bound read tools."""

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from skadi_agents.action_planner import plan
from skadi_agents.equipment_status import Entity, matching_sensors, sensor_signal
from skadi_agents.incident import format_incident, format_incident_list
from skadi_agents.inspection_evidence import (
    InspectionEvidence,
    format_inspection_evidence,
    markdown_text,
)
from skadi_agents.maintenance_report import build_maintenance_draft
from skadi_agents.reflector import SIGNAL_LABELS, Reflection, normalize, reflect, view_choice

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class Toolset:
    """Backend-provided ports for registered equipment, alarms and evidence."""

    resolve_entity: Callable[..., Awaitable[tuple[str, list[Entity]]]]
    lookup_alias: Callable[..., Awaitable[dict]]
    resolve_plant: Callable[[str], Awaitable[tuple[str, list[Entity]]]]
    list_plant_units: Callable[[str], Awaitable[list[dict]]]
    load_equipment: Callable[[object], Awaitable[Entity | None]]
    equipment_of_type: Callable[[str], Awaitable[list[Entity]]]
    get_equipment_sensors: Callable[[str], Awaitable[list[dict]]]
    get_alarm_priorities: Callable[..., Awaitable[dict]]
    get_alarm: Callable[[str, object], Awaitable[dict | None]]
    get_inspection_evidence: Callable[[str], Awaitable[InspectionEvidence]]
    get_initial_alarm_report: Callable[[str, object], Awaitable[dict | None]]
    list_incidents: Callable[..., Awaitable[dict]] | None = None
    get_incident: Callable[[str], Awaitable[dict | None]] | None = None


@dataclass
class Reply:
    message: str
    links: list[dict[str, str]] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    navigation_href: str | None = None
    trend_intent: dict | None = None


def _link(title: str, href: str) -> dict[str, str]:
    return {"title": title, "href": href}


def _dates(days: int | None) -> dict[str, str]:
    if days is None:
        return {}
    today = datetime.now(KST).date()
    return {"from": (today - timedelta(days=days - 1)).isoformat(), "to": today.isoformat()}


def _trend_window(
    days: int, hours: int | None = None, *, end: datetime | None = None
) -> dict[str, str]:
    end = (end or datetime.now(KST)).replace(tzinfo=None, microsecond=0)
    start = end - (timedelta(hours=hours) if hours else timedelta(days=days))
    return {"from": start.isoformat(), "to": end.isoformat(), "interval": "1h"}


def _trend_intent(
    entity: Entity,
    sensor_ids: list[str],
    durations: list[timedelta],
    show_anomalies: bool = False,
    *,
    end: datetime | None = None,
) -> dict:
    end = (end or datetime.now(KST)).replace(microsecond=0)
    return {
        "equipmentGroupId": entity.unit_id,
        "equipmentId": entity.id,
        "series": [
            {"sensorId": sensor_id, "start": (end - duration).isoformat(), "end": end.isoformat()}
            for sensor_id, duration in zip(sensor_ids, durations, strict=True)
        ],
        "showAnomalies": show_anomalies,
    }


def _multi_trend_specs(message: str) -> tuple[str, list[tuple[str, timedelta]], bool] | None:
    """Extract explicit sensor durations; ambiguous targets are resolved by DB tools later."""
    labels = re.compile(r"진동|전압|전류|온도|압력|회전수")
    segments = re.split(r"[,，]|그리고", message)
    first = labels.search(segments[0]) if segments else None
    if not first:
        return None
    target = segments[0][: first.start()].strip().removesuffix("의").strip()
    specs: list[tuple[str, timedelta]] = []
    for segment in segments:
        names = labels.findall(segment)
        period = re.search(r"(?:최근\s*)?(\d{1,2})\s*(시간|일)", segment)
        if not names or not period:
            continue
        count = int(period[1])
        if not 1 <= count <= 90:
            return None
        duration = timedelta(hours=count) if period[2] == "시간" else timedelta(days=count)
        specs.extend((name, duration) for name in names)
    if len(specs) < 2 or not target:
        return None
    return target, specs, "이상" in message


async def _multi_trend_reply(
    tools: Toolset, message: str, screen: dict[str, object]
) -> Reply | None:
    parsed = _multi_trend_specs(message)
    if parsed is None:
        return None
    target, specs, show_anomalies = parsed
    if len(specs) > 24:
        return Reply("한 번에 조회할 수 있는 센서는 최대 24개입니다. 대상을 줄여 주세요.")
    status, candidates = await tools.resolve_entity(target, screen=screen, equipment_only=True)
    if status != "found" or len(candidates) != 1:
        return _ask(Reflection("trend", target=target), status, candidates, {})
    entity = candidates[0]
    sensors = await tools.get_equipment_sensors(entity.id)
    selected: list[str] = []
    durations: list[timedelta] = []
    for label, duration in specs:
        signal = {
            "진동": "vibration",
            "전압": "voltage",
            "전류": "current",
            "온도": "temperature",
            "압력": "pressure",
            "회전수": "speed",
        }[label]
        matches = [row for row in sensors if sensor_signal(row["measurement_name"]) == signal]
        if signal == "vibration":
            matches = matching_sensors(matches, "진동 속도 RMS", signal) or matches
        if len(matches) != 1:
            return Reply(f"{label} 센서를 하나로 확정할 수 없습니다. 센서 태그를 지정해 주세요.")
        selected.append(matches[0]["sensor_id"])
        durations.append(duration)
    intent = _trend_intent(entity, selected, durations, show_anomalies)
    return Reply(
        f"**{markdown_text(entity.name)}**의 센서별 트렌드를 엽니다.",
        context={"equipment_id": entity.id},
        trend_intent=intent,
    )


def _sensor_views(
    entity: Entity,
    matches: list[dict],
    days: int,
    hours: int | None = None,
    show_anomalies: bool = False,
    *,
    historical_end: datetime | None = None,
    alarm_context: dict | None = None,
) -> Reply:
    window = _trend_window(days, hours, end=historical_end)
    if show_anomalies:
        window["show_anomalies"] = "1"
    period_label = f"{hours}시간" if hours else f"{days}일"
    period_label = (
        f"{historical_end:%Y-%m-%d %H:%M} KST 기준 {period_label}"
        if historical_end
        else f"최근 {period_label}"
    )
    links = []
    for sensor in matches:
        sid = sensor["sensor_id"]
        label = f"{sensor['measurement_name']} ({sid}) " if len(matches) > 1 else ""
        filters = {"sensor_id": sid}
        if (
            alarm_context
            and sid == alarm_context.get("sensor_id")
            and alarm_context.get("alarm_id")
        ):
            filters["alarm_id"] = alarm_context["alarm_id"]
        links.extend(
            [
                _link(f"{label}설비 현황 열기", entity.link("/equip", **filters)),
                _link(
                    f"{label}{period_label} 트렌드 열기",
                    entity.link("/trend", **filters, **window),
                ),
            ]
        )

    context = {**(alarm_context or {}), "equipment_id": entity.id}
    if len(matches) > 1:
        return Reply(
            f"**{markdown_text(entity.name)}**에 해당 센서가 여러 개 있습니다. 태그와 화면을 선택해 주세요.",
            links,
            context,
        )
    sensor = matches[0]
    context["sensor_view"] = {
        "equipment_id": entity.id,
        "sensor_id": sensor["sensor_id"],
        "days": days,
        "hours": hours,
    }
    subject = markdown_text(f"{entity.name} · {sensor['measurement_name']}")
    return Reply(
        f"**{subject}** 데이터를 볼까요?\n\n"
        f"최신 측정값은 **설비 현황**, 시간에 따른 변화는 **{period_label} 트렌드**에서 볼 수 있습니다. "
        "아래 링크를 누르거나 ‘설비 현황’, ‘트렌드’라고 답해 주세요.",
        links,
        context,
    )


def _ask(request: Reflection, status: str, candidates: list[Entity], previous: dict) -> Reply:
    candidates = candidates[:3]
    if not candidates:
        label = f"‘{markdown_text(request.target)}’에 해당하는" if request.target else "확인할"
        return Reply(
            f"{label} 설비나 공정을 찾지 못했습니다. 정확한 이름이나 코드를 알려주세요.",
            context=previous,
        )
    lead = (
        "어느 설비 또는 공정을 확인할까요? 번호나 코드를 입력해 주세요."
        if status == "ambiguous"
        else "정확히 일치하는 설비를 찾지 못했습니다. 해당하는 후보의 번호나 코드를 입력해 주세요."
    )
    if request.intent == "plant_units":
        lead = "어느 플랜트의 공정을 확인할까요? 번호나 코드를 입력해 주세요."
    lines = [
        f"{i}. {markdown_text(item.id)} ({markdown_text(item.name)})"
        for i, item in enumerate(candidates, start=1)
    ]
    links = (
        [
            _link(f"{i}순위 {item.id} 설비 보기", item.link("/equip"))
            for i, item in enumerate(candidates, start=1)
        ]
        if request.intent == "equipment_lookup"
        else []
    )
    return Reply(
        lead + "\n\n" + "\n".join(lines),
        links,
        {
            **previous,
            "pending": {
                "request": asdict(request),
                "candidates": [asdict(item) for item in candidates],
            },
        },
    )


async def _alias_reply(
    tools: Toolset,
    request: Reflection,
    screen: dict[str, object],
    previous: dict,
    chosen: dict | None = None,
) -> Reply:
    target = request.target
    if chosen:
        target = chosen["id"]
        result = await tools.lookup_alias(target, entity_type=chosen["entity_type"])
    else:
        key = normalize(target or "")
        if key in {"이센서", "그센서", "해당센서"}:
            target = previous.get("sensor_id") or screen.get("sensor_id")
        elif key in {"이설비", "그설비", "해당설비"}:
            target = previous.get("equipment_id") or screen.get("equipment_id")
        elif key in {"이공정", "그공정", "해당공정", "이호기", "그호기"}:
            target = screen.get("equipment_group_id")
        elif key in {"이플랜트", "그플랜트", "해당플랜트", "이공장", "그공장"}:
            target = screen.get("plant_id")
        elif not key:
            target = (
                screen.get("sensor_id")
                or screen.get("equipment_id")
                or screen.get("equipment_group_id")
                or screen.get("plant_id")
            )
        if not isinstance(target, str) or not target:
            return Reply("별칭을 확인할 대상의 이름이나 코드를 알려주세요.", context=previous)
        result = await tools.lookup_alias(target)

    candidates = result["candidates"]
    if len(candidates) > 1:
        for scope_key in ("equipment_id", "equipment_group_id", "plant_id"):
            scope = screen.get(scope_key)
            if isinstance(scope, str) and scope:
                scoped = [item for item in candidates if item.get(scope_key) == scope]
                if scoped:
                    candidates = scoped
    if not candidates:
        return Reply(
            f"‘{markdown_text(target)}’에 해당하는 등록 대상을 찾지 못했습니다.",
            context=previous,
        )
    if len(candidates) > 1:
        choices = candidates[:3]
        lines = [
            f"{i}. {markdown_text(item['id'])} ({markdown_text(item['name'])}, "
            f"{item['entity_type']})"
            for i, item in enumerate(choices, 1)
        ]
        return Reply(
            "어느 대상의 별칭을 확인할까요? 번호나 코드를 입력해 주세요.\n\n" + "\n".join(lines),
            context={
                **previous,
                "pending": {"kind": "alias", "request": asdict(request), "candidates": choices},
            },
        )
    item = candidates[0]
    subject = markdown_text(f"{item['name']} ({item['id']})")
    names = [markdown_text(alias["alias_name"]) for alias in item["aliases"]]
    if not names:
        return Reply(f"**{subject}**에 등록된 별칭이 없습니다.", context=previous)
    return Reply(f"**{subject}**의 등록 별칭: {', '.join(names)}", context=previous)


async def _plant_units_reply(
    tools: Toolset, request: Reflection, screen: dict[str, object], previous: dict
) -> Reply:
    target = request.target or screen.get("plant_id")
    if not isinstance(target, str) or not target:
        return Reply(
            "어느 플랜트의 공정을 확인할까요? 예를 들어 ‘울산 CLX는 몇 호기까지 있어?’라고 물어보세요.",
            context=previous,
        )
    status, plants = await tools.resolve_plant(target)
    if status == "ambiguous":
        return _ask(request, status, plants, previous)
    if status != "found":
        return Reply(
            f"‘{markdown_text(target)}’에 해당하는 플랜트를 찾지 못했습니다. 등록된 이름이나 코드를 알려주세요.",
            context=previous,
        )
    (plant,) = plants
    units = await tools.list_plant_units(plant.id)
    lines = [f"현재 Skadi에 등록된 **{markdown_text(plant.name)} 공정은 {len(units)}개**입니다."]
    links = []
    for unit in units:
        name = unit["equipment_group_name"]
        unit_id = unit["equipment_group_id"]
        lines.append(f"- {markdown_text(name)} · 내부 설비 {unit['equipment_count']}대")
        links.append(_link(f"{name} 열기", Entity("unit", unit_id, name).link("/equip")))
    return Reply("\n\n".join(lines), links, previous)


async def _resolve_target(
    tools: Toolset,
    request: Reflection,
    screen: dict[str, object],
    previous: dict,
    equipment_only: bool,
) -> tuple[str, list[Entity]]:
    if request.target:
        return await tools.resolve_entity(
            request.target, screen=screen, equipment_only=equipment_only
        )

    previous_id = previous.get("equipment_id")
    screen_id = screen.get("equipment_id")
    if request.relative and "알람" in request.relative:
        entity = await tools.load_equipment(previous_id) if previous.get("alarm_id") else None
        return ("found", [entity]) if entity else ("not_found", [])
    use_previous = request.relative in {"그설비", "해당설비", "이걸로"}
    unit_id = screen.get("equipment_group_id")
    if (
        not use_previous
        and not equipment_only
        and not screen_id
        and isinstance(unit_id, str)
        and unit_id
    ):
        return await tools.resolve_entity(unit_id, screen=screen)
    entity = await tools.load_equipment(
        (previous_id or screen_id) if use_previous else (screen_id or previous_id)
    )
    if entity:
        return "found", [entity]
    if not equipment_only:
        scope = screen.get("equipment_group_id") or screen.get("plant_id")
        if isinstance(scope, str):
            return await tools.resolve_entity(scope, screen=screen)
    return "not_found", []


def _priority_time(value: str, now: datetime) -> datetime:
    """Resolve explicit ISO or Korean local times without filling in a missing hour."""
    value = re.sub(r"\s*KST$", "", value, flags=re.IGNORECASE).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}.*", value):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=KST)
    match = re.fullmatch(
        r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일"
        r"\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?",
        value,
    )
    if not match:
        raise ValueError("missing date or time")
    year, month, day, hour, minute = match.groups()
    return datetime(
        int(year or now.year), int(month), int(day), int(hour), int(minute or 0), tzinfo=KST
    )


def _alarm_date_label(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


async def _priority_reply(
    tools: Toolset,
    entity: Entity | None,
    request: Reflection,
    previous: dict,
    comparison: list[Entity] | None = None,
) -> Reply:
    query: dict = entity.alarm_scope() if entity else {}
    scope = entity.name if entity else "전체 설비"
    if comparison:
        query["equipment_ids"] = [item.id for item in comparison]
        scope = " · ".join(item.name for item in comparison)
    if request.priority_time is not None:
        now = datetime.now(KST)
        try:
            instant = _priority_time(request.priority_time, now)
        except ValueError:
            return Reply(
                "알람 순위를 확인할 날짜와 시각을 알려주세요. 예를 들어 ‘2026년 11월 19일 14시 기준 알람 순위’라고 물어보세요.",
                context=previous,
            )
        if instant > now:
            return Reply(
                "미래 시각의 알람 순위는 조회할 수 없습니다. 현재 또는 과거 시각을 알려주세요.",
                context=previous,
            )
        query["as_of"] = instant
    limit = 1 if request.first_only else 100 if request.priority_all else 3
    snapshot = await tools.get_alarm_priorities(
        **query, group_by=request.priority_group, limit=limit
    )
    label = "개별 알람 순위" if request.priority_group == "alarm" else "설비별 알람 순위"
    heading = f"**{label} · {markdown_text(scope)}** · {_alarm_date_label(snapshot['as_of'])} 기준"
    history = entity.link("/alarms") if entity else "/alarms"
    items = snapshot["items"]
    lines = [heading]
    links = []
    if not items:
        lines.append(
            {
                "empty": "조회 범위에 활성 Setpoint 알람이 0건입니다.",
                "unavailable": "조회 범위에 이력이 있으나 활성 여부가 확인되지 않았습니다.",
                "no_data": "조회 범위와 기준 시각에 해당하는 Setpoint 알람 이력이 없습니다.",
                "unscored": "활성 알람의 CoF가 평가되지 않아 순위를 제시할 수 없습니다.",
            }.get(snapshot["status"], "알람 우선순위를 확인할 수 없습니다.")
        )
    if snapshot["active_count"]:
        lines.append(
            f"활성 알람 {snapshot['active_count']}건 · 영향 설비 "
            f"{snapshot['affected_equipment_count']}대 · 고유 조건 {snapshot['condition_count']}개"
        )
    severity = ("정상", "주의", "경고", "위험", "비상")
    for item in items:
        alarm_entity = Entity("equipment", item["equipment_id"], item["equipment_name"])
        reason = f" · {markdown_text(item['reason'])}" if item.get("reason") else ""
        event_type = markdown_text(item["event_type"] or "유형 미기록")
        setpoint = (
            f" · Setpoint {markdown_text(item['setpoint_id'])}" if item["setpoint_id"] else ""
        )
        lines.append(
            f"{item['rank']}. **{markdown_text(item['equipment_name'])} · {markdown_text(item['sensor_name'])}**"
            f" · {severity[item['alarm_level']]} · {event_type} · CoF **{item['cof_score']:g}**"
            f" · {_alarm_date_label(item['alarm_start_time'])} 발생{setpoint}{reason}"
        )
        if item.get("diagnosis"):
            lines.append(
                f"   관련 이상 사건 진단(추정) · {markdown_text(item['diagnosis'])}"
                f" · 사건 점수 {item['incident_score']:g} (순위에는 쓰지 않음)"
            )
        if request.priority_group == "equipment":
            lines.append(
                f"   활성 {item['equipment_active_count']}건 · 예측 {item['prediction_count']}건"
                f" · 임계치 초과 {item['threshold_exceeded_count']}건 · 고유 조건 {item['condition_count']}개"
            )
        links.append(
            _link(
                f"{item['rank']}순위 {item['equipment_name']} 확인",
                alarm_entity.link("/equip", sensor_id=item["sensor_id"], alarm_id=item["alarm_id"]),
            )
        )
    if comparison and items:
        ranked_ids = {item["equipment_id"] for item in items}
        excluded = [markdown_text(item.name) for item in comparison if item.id not in ranked_ids]
        if excluded:
            lines.append(f"순위에 포함되지 않은 비교 대상: {', '.join(excluded)}")
    if request.priority_all and len(items) == limit == 100:
        lines.append("조회 상한까지 상위 100개를 표시했습니다.")
    if snapshot["unscored_count"]:
        lines.append(f"CoF 미평가 {snapshot['unscored_count']}건")
    if snapshot["unknown_count"]:
        lines.append(f"활성 상태 미확인 이력 {snapshot['unknown_count']}건")
    for item in items:
        if item.get("incident_id"):
            links.append(
                _link(
                    f"{item['equipment_name']} 이상 사건 보기", f"/incidents/{item['incident_id']}"
                )
            )
    links.append(_link("알람 이력 보기", history))
    context = {
        "alarm_priority_scope": entity.id if entity else None,
        "alarm_priority_group": request.priority_group,
    }
    if comparison:
        context["alarm_comparison_ids"] = [item.id for item in comparison]
    if request.priority_time is not None:
        context["alarm_as_of"] = snapshot["as_of"]
    if items:
        selected = items[0]
        context.update(
            {
                key: selected[key]
                for key in ("alarm_id", "equipment_id", "sensor_id", "has_initial_report")
            }
        )
        if selected.get("incident_id"):
            context["incident_id"] = selected["incident_id"]
    return Reply("\n\n".join(lines), links, context)


async def _initial_alarm_report_reply(
    tools: Toolset, entity: Entity | None, previous: dict
) -> Reply:
    alarm_id = previous.get("alarm_id")
    if (
        not entity
        or entity.kind != "equipment"
        or not alarm_id
        or entity.id != previous.get("equipment_id")
    ):
        return Reply("초기 보고서를 확인할 알람을 선택해 주세요.", context=previous)
    report = await tools.get_initial_alarm_report(entity.id, alarm_id)
    if report is None:
        return Reply("선택한 알람에 저장된 초기 보고서가 없습니다.", context=previous)
    created = _alarm_date_label(report["as_of"])
    return Reply(
        f"**저장된 초기 보고서** · {created} 생성\n\n{report['message']}",
        report["links"],
        previous,
    )


async def _show_equipment(
    tools: Toolset, entity: Entity, request: Reflection, previous: dict, screen: dict[str, object]
) -> Reply:
    sensor_query = request.sensor
    if not sensor_query and request.intent == "trend":
        if request.relative and "알람" in request.relative:
            sensor_query = previous.get("sensor_id")
        if not sensor_query and screen.get("equipment_id") == entity.id:
            value = screen.get("sensor_id")
            sensor_query = value if isinstance(value, str) else None
            signal = screen.get("sensor")
            if not sensor_query and isinstance(signal, str) and signal in SIGNAL_LABELS:
                request = replace(request, signal=signal)
                sensor_query = SIGNAL_LABELS[signal]
        if not sensor_query and previous.get("equipment_id") == entity.id:
            sensor_query = previous.get("sensor_id")

    if entity.kind != "equipment" and (sensor_query or request.intent == "trend"):
        if entity.kind == "unit":
            return Reply(
                f"**{markdown_text(entity.name)}**의 내부 설비 중 센서를 확인할 펌프를 선택해 주세요.",
                [_link("내부 설비 목록 열기", entity.link("/equip"))],
            )
        return Reply("센서 데이터를 확인할 설비의 이름이나 코드를 알려주세요.", context=previous)
    if request.intent == "trend" and not sensor_query:
        sensors = await tools.get_equipment_sensors(entity.id)
        if not sensors:
            return Reply("이 설비에 등록된 센서가 없습니다.", context=previous)
        if len(sensors) > 24:
            return Reply("한 번에 조회할 수 있는 센서는 최대 24개입니다. 센서를 지정해 주세요.")
        days = request.days or 7
        duration = timedelta(hours=request.hours) if request.hours else timedelta(days=days)
        return Reply(
            f"**{markdown_text(entity.name)}**의 전체 센서 트렌드를 엽니다.",
            context={"equipment_id": entity.id},
            trend_intent=_trend_intent(
                entity,
                [row["sensor_id"] for row in sensors],
                [duration] * len(sensors),
                request.show_anomalies,
            ),
        )
    if not sensor_query:
        href = entity.link("/equip")
        return Reply(
            f"**{markdown_text(entity.name)}** 현황을 엽니다.",
            [_link(f"{entity.name} 현황 열기", href)],
            {"equipment_id": entity.id} if entity.kind == "equipment" else {},
            navigation_href=href,
        )

    sensors = await tools.get_equipment_sensors(entity.id)
    generic = request.signal and normalize(sensor_query) == normalize(SIGNAL_LABELS[request.signal])
    vibration_rms = generic and request.signal == "vibration"
    if generic:
        matches = [
            row for row in sensors if sensor_signal(row["measurement_name"]) == request.signal
        ]
        if vibration_rms:
            matches = matching_sensors(matches, "진동 속도 RMS", "vibration") or matches
    else:
        matches = matching_sensors(sensors, sensor_query, request.signal)
    if not matches:
        return Reply(
            f"**{markdown_text(entity.name)}**에서 ‘{markdown_text(sensor_query)}’ 센서를 찾지 못했습니다. 센서명이나 태그를 확인해 주세요.",
            context={"equipment_id": entity.id},
        )
    days = request.days or 7
    historical_end = (
        datetime.fromisoformat(previous["alarm_as_of"]).astimezone(KST)
        if request.relative
        and previous.get("alarm_as_of")
        and previous.get("equipment_id") == entity.id
        else None
    )
    if request.intent == "sensor_options":
        return _sensor_views(
            entity,
            matches,
            days,
            request.hours,
            request.show_anomalies,
            historical_end=historical_end,
            alarm_context=previous if historical_end else None,
        )
    path = "/trend" if request.intent == "trend" else "/equip"
    duration = timedelta(hours=request.hours) if request.hours else timedelta(days=days)
    window = _trend_window(days, request.hours, end=historical_end) if path == "/trend" else {}
    if len(matches) > 1 and (path == "/trend" or not generic or vibration_rms):
        links = [
            _link(
                f"{row['measurement_name']} ({row['sensor_id']})",
                entity.link(
                    path,
                    sensor_id=row["sensor_id"],
                    **window,
                ),
            )
            for row in matches
        ]
        return Reply(
            f"**{markdown_text(entity.name)}**에 해당 센서가 여러 개 있습니다. 볼 태그를 선택해 주세요.",
            links,
        )

    filters = (
        {"sensor_id": matches[0]["sensor_id"]} if len(matches) == 1 else {"sensor": request.signal}
    )
    measurement = matches[0]["measurement_name"] if len(matches) == 1 else sensor_query
    period_label = f"최근 {request.hours}시간" if request.hours else f"최근 {days}일"
    if historical_end:
        period_label = (
            f"{historical_end:%Y-%m-%d %H:%M} KST 기준 {period_label.removeprefix('최근 ')}"
        )
    view = f"{period_label} 추이" if path == "/trend" else "현황"
    subject = f"{entity.name} {measurement} {view}"
    result_context = {"equipment_id": entity.id, **filters}
    if (
        previous.get("equipment_id") == entity.id
        and previous.get("sensor_id") == filters.get("sensor_id")
        and (alarm_id := previous.get("alarm_id"))
    ):
        result_context["alarm_id"] = alarm_id
        filters["alarm_id"] = alarm_id
        if previous.get("alarm_as_of"):
            result_context["alarm_as_of"] = previous["alarm_as_of"]
    href = entity.link(path, **filters, **window)
    action = " 그래프를 엽니다." if path == "/trend" else " 화면을 엽니다."
    return Reply(
        f"**{markdown_text(subject)}**{action}",
        [_link(f"{subject} 열기", href)],
        result_context,
        navigation_href=href,
        trend_intent=(
            _trend_intent(
                entity,
                [matches[0]["sensor_id"]],
                [duration],
                request.show_anomalies,
                end=historical_end,
            )
            if path == "/trend" and len(matches) == 1
            else None
        ),
    )


async def _incident_reply(
    tools: Toolset, request: Reflection, screen: dict[str, object], previous: dict
) -> Reply:
    if tools.list_incidents is None or tools.get_incident is None:
        return Reply("이상 사건 조회를 사용할 수 없습니다.", context=previous)

    async def detail_reply(incident_id: str) -> Reply:
        detail = await tools.get_incident(incident_id)
        if detail is None:
            return Reply("이상 사건을 찾을 수 없습니다.", context=previous)
        text, links = format_incident(detail)
        context = previous if previous.get("equipment_id") == detail["equipment_id"] else {}
        return Reply(
            text,
            links,
            {**context, "equipment_id": detail["equipment_id"], "incident_id": incident_id},
        )

    if request.relative and "알람" in request.relative:
        alarm = (
            await tools.get_alarm(previous["equipment_id"], previous["alarm_id"])
            if previous.get("alarm_id") and previous.get("equipment_id")
            else None
        )
        if alarm is None:
            return Reply("사건을 확인할 알람을 먼저 선택해 주세요.", context=previous)
        if not alarm.get("incident_id"):
            return Reply("선택한 알람에 연결된 이상 사건이 없습니다.", context=previous)
        return await detail_reply(alarm["incident_id"])
    if not request.target and not request.incident_list and previous.get("incident_id"):
        return await detail_reply(previous["incident_id"])

    entity = None
    if request.target or any(
        screen.get(key) for key in ("equipment_id", "equipment_group_id", "plant_id")
    ):
        status, candidates = await _resolve_target(tools, request, screen, previous, False)
        if status != "found" or len(candidates) != 1:
            return _ask(request, status, candidates, previous)
        entity = candidates[0]
    scope = entity.alarm_scope() if entity else {}
    if request.incident_status:
        scope["status"] = request.incident_status
    name = entity.name if entity else "전체 설비"
    if entity and entity.kind == "equipment" and not request.incident_list:
        latest = await tools.list_incidents(**scope, limit=1)
        if not latest["items"]:
            return Reply(
                f"**{markdown_text(name)}**에 기록된 이상 사건이 없습니다.",
                [_link(f"{name} 현황 보기", entity.link("/equip"))],
                {"equipment_id": entity.id},
            )
        return await detail_reply(latest["items"][0]["incident_id"])
    listing = await tools.list_incidents(**scope, limit=10)
    text, links = format_incident_list(name, listing)
    context = {"equipment_id": entity.id} if entity and entity.kind == "equipment" else previous
    if len(listing["items"]) == 1:
        context = {**context, "incident_id": listing["items"][0]["incident_id"]}
    return Reply(text, links, context)


async def run_chat_workflow(
    tools: Toolset,
    message: str,
    screen: dict[str, object],
    previous: dict,
) -> Reply:
    if multi_reply := await _multi_trend_reply(tools, message, screen):
        return multi_reply
    request = reflect(message)
    if "alarm_priority_scope" in previous and normalize(message.rstrip("?!.。")) in {
        "전체순서",
        "전체순서보여줘",
        "전체순서알려줘",
    }:
        request = Reflection(
            "alarm_priority",
            target=previous["alarm_priority_scope"],
            priority_all=True,
            priority_time=previous.get("alarm_as_of"),
            priority_group=previous.get("alarm_priority_group", "equipment"),
            comparison_targets=tuple(previous.get("alarm_comparison_ids", ())),
        )
    if request.intent == "out_of_scope":
        return Reply(
            "Skadi에서는 설비 현황, 센서 추이, 알람을 조회할 수 있어요. 예를 들어 ‘1호기 현황’이라고 물어보세요.",
            context=previous,
        )
    if request.intent == "clarify":
        return Reply(
            "어떤 내용을 확인할까요? 설비 현황, 센서 추이, 알람 중에서 골라 주세요.",
            context=previous,
        )
    pending = previous.get("pending")
    sensor_view = previous.get("sensor_view")
    previous = {
        key: value for key, value in previous.items() if key not in {"pending", "sensor_view"}
    }
    if sensor_view and (chosen_view := view_choice(message)):
        request = Reflection(
            chosen_view,
            target=sensor_view["equipment_id"],
            sensor=sensor_view["sensor_id"],
            relative="그설비" if previous.get("alarm_as_of") else None,
            days=request.days or sensor_view["days"],
            hours=request.hours or sensor_view.get("hours"),
        )
    screen_equipment_id = screen.get("equipment_id")
    if isinstance(screen_equipment_id, str) and screen.get("alarm_id"):
        screen_alarm = await tools.get_alarm(screen_equipment_id, screen["alarm_id"])
        if screen_alarm and (
            not screen.get("sensor_id") or screen["sensor_id"] == screen_alarm["sensor_id"]
        ):
            if screen_alarm["alarm_id"] != previous.get("alarm_id"):
                previous.pop("alarm_as_of", None)
                previous.pop("has_initial_report", None)
            previous.update(
                {key: screen_alarm[key] for key in ("equipment_id", "sensor_id", "alarm_id")}
            )
    selected = None
    alias_chosen = None
    if pending:
        choices = pending["candidates"]
        candidate = next(
            (
                item
                for i, item in enumerate(choices, start=1)
                if request.selection == i or normalize(message) == normalize(item["id"])
            ),
            None,
        )
        if candidate:
            if pending.get("kind") == "alias":
                alias_chosen = candidate
                request = replace(Reflection(**pending["request"]), selection=None)
            else:
                selected = Entity(**candidate)
                request = replace(
                    Reflection(**pending["request"]), target=selected.id, selection=None
                )
        elif request.selection is not None:
            return Reply(
                f"1번부터 {len(choices)}번 중에서 골라 주세요.",
                context={**previous, "pending": pending},
            )
    if request.selection is not None:
        return Reply(
            "선택할 설비 목록이 없습니다. 설비 이름이나 코드를 알려주세요.", context=previous
        )

    action = plan(request)
    if "lookup_alias" in action.tools:
        return await _alias_reply(tools, request, screen, previous, alias_chosen)
    if "list_plant_units" in action.tools:
        return await _plant_units_reply(tools, request, screen, previous)
    intent = action.request.intent
    if intent == "incident":
        return await _incident_reply(tools, request, screen, previous)
    entity = None
    if request.comparison_targets:
        candidates = []
        for target in request.comparison_targets:
            status, matches = await tools.resolve_entity(target, screen=screen, equipment_only=True)
            if status != "found" or len(matches) != 1:
                return Reply(
                    f"비교 대상 ‘{markdown_text(target)}’을 하나로 확인할 수 없습니다. 설비 ID를 알려주세요.",
                    context=previous,
                )
            candidates.append(matches[0])
        if len({item.id for item in candidates}) < 2:
            return Reply("비교할 서로 다른 설비를 지정해 주세요.", context=previous)
        return await _priority_reply(tools, None, request, previous, candidates)
    if intent == "initial_alarm_report" and not (request.target or previous.get("alarm_id")):
        return await _initial_alarm_report_reply(tools, None, previous)
    if intent == "initial_alarm_report" and not request.target:
        request = replace(request, relative="그알람")
    priority_screen_scope = intent == "alarm_priority" and any(
        screen.get(key) for key in ("equipment_id", "equipment_group_id", "plant_id")
    )
    needs_scope = request.target or request.relative or priority_screen_scope
    if action.target_kind == "equipment_type" and selected is None:
        entities = await tools.equipment_of_type(request.target)
        if not entities:
            return _ask(request, "not_found", [], previous)
        if intent in {"alarm_history", "alarm_priority"}:
            entity = Entity("equipment_type", request.target, request.target)
        elif len(entities) == 1:
            entity = entities[0]
        else:
            return _ask(request, "ambiguous", entities, previous)
    elif "resolve_entity" in action.tools and (
        needs_scope or intent not in {"alarm_history", "alarm_priority"}
    ):
        equipment_only = intent in {
            "inspection_evidence",
            "maintenance_draft",
            "initial_alarm_report",
        }
        status, candidates = await _resolve_target(tools, request, screen, previous, equipment_only)
        if selected:
            candidates = [
                item for item in candidates if item.kind == selected.kind and item.id == selected.id
            ]
            status = "found" if len(candidates) == 1 else "not_found"
        if status != "found" or len(candidates) != 1:
            return _ask(request, status, candidates, previous)
        entity = candidates[0]

    if "get_initial_alarm_report" in action.tools:
        return await _initial_alarm_report_reply(tools, entity, previous)
    if "get_alarm_priorities" in action.tools:
        return await _priority_reply(tools, entity, request, previous)
    if intent == "alarm_history":
        filters = _dates(request.days)
        if request.relative and "알람" in request.relative and previous.get("sensor_id"):
            filters["sensor_id"] = previous["sensor_id"]
        if request.alarm_event_type:
            filters["event_type"] = request.alarm_event_type
        href = (
            entity.link("/alarms", **filters)
            if entity
            else f"/alarms?{urlencode(filters)}"
            if filters
            else "/alarms"
        )
        scope = entity.name if entity else "전체 설비"
        context = previous
        if entity and entity.kind == "equipment" and entity.id != previous.get("equipment_id"):
            context = {"equipment_id": entity.id}
        return Reply(
            f"**{markdown_text(scope)} 알람 이력**을 확인할 수 있습니다.",
            [_link(f"{scope} 알람 이력 보기", href)],
            context,
        )
    if entity is None:
        return _ask(request, "not_found", [], previous)
    if intent == "equipment_lookup":
        if entity.kind == "unit":
            return Reply(
                f"**{markdown_text(entity.name)}**의 내부 설비 목록을 확인할 수 있습니다.",
                [_link("내부 설비 목록 열기", entity.link("/equip"))],
            )
        label = "설비" if entity.kind == "equipment" else "플랜트"
        return Reply(
            f"{markdown_text(entity.name)}의 {label} ID는 {markdown_text(entity.id)}입니다.",
            [_link(f"{entity.id} {label} 보기", entity.link("/equip"))],
            {"equipment_id": entity.id} if entity.kind == "equipment" else {},
        )
    if "get_inspection_evidence" in action.tools:
        evidence = await tools.get_inspection_evidence(entity.id)
        context = (
            {**previous, "equipment_id": entity.id}
            if previous.get("equipment_id") == entity.id
            else {"equipment_id": entity.id}
        )
        if "build_maintenance_draft" in action.tools:
            alarm: Mapping[str, object] | None = await tools.get_alarm(
                entity.id, context.get("alarm_id")
            )
            incident = None
            if tools.get_incident and context.get("incident_id"):
                incident = await tools.get_incident(context["incident_id"])
                if incident and incident["equipment_id"] != entity.id:
                    incident = None
            text, links = build_maintenance_draft(
                entity.name, evidence, alarm=alarm, incident=incident
            )
        else:
            text, links = format_inspection_evidence(entity.name, evidence)
        return Reply(text, links, context)
    return await _show_equipment(tools, entity, request, previous, screen)
