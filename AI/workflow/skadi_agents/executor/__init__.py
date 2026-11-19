"""AG-03 Executor. Agent code operates through the application's bound read tools."""

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from skadi_agents.action_planner import plan
from skadi_agents.equipment_status import Entity, matching_sensors, sensor_signal
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


def _trend_window(days: int, hours: int | None = None) -> dict[str, str]:
    end = datetime.now(KST).replace(tzinfo=None, microsecond=0)
    start = end - (timedelta(hours=hours) if hours else timedelta(days=days))
    return {"from": start.isoformat(), "to": end.isoformat(), "interval": "1h"}


def _trend_intent(
    entity: Entity,
    sensor_ids: list[str],
    durations: list[timedelta],
    show_anomalies: bool = False,
) -> dict:
    end = datetime.now(KST).replace(microsecond=0)
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
) -> Reply:
    window = _trend_window(days, hours)
    if show_anomalies:
        window["show_anomalies"] = "1"
    period_label = f"{hours}시간" if hours else f"{days}일"
    links = []
    for sensor in matches:
        sid = sensor["sensor_id"]
        label = f"{sensor['measurement_name']} ({sid}) " if len(matches) > 1 else ""
        links.extend(
            [
                _link(f"{label}설비 현황 열기", entity.link("/equip", sensor_id=sid)),
                _link(
                    f"{label}최근 {period_label} 트렌드 열기",
                    entity.link("/trend", sensor_id=sid, **window),
                ),
            ]
        )

    context = {"equipment_id": entity.id}
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
        f"최신 측정값은 **설비 현황**, 시간에 따른 변화는 **최근 {period_label} 트렌드**에서 볼 수 있습니다. "
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


async def _priority_reply(
    tools: Toolset, entity: Entity | None, request: Reflection, previous: dict
) -> Reply:
    snapshot = await tools.get_alarm_priorities(
        **(entity.alarm_scope() if entity else {}), limit=1 if request.first_only else 3
    )
    scope = entity.name if entity else "전체 설비"
    as_of = (
        datetime.fromisoformat(snapshot["as_of"]).astimezone(KST).strftime("%m월 %d일 %H:%M KST")
    )
    heading = f"**{markdown_text(scope)} 활성 Setpoint 알람** · {as_of} 기준"
    history = entity.link("/alarms") if entity else "/alarms"
    items = snapshot["items"]
    if not items:
        explanation = {
            "empty": "현재 조회 범위에 활성 Setpoint 알람이 없습니다.",
            "unavailable": "활성 상태가 확인된 알람 데이터를 아직 조회할 수 없습니다.",
            "unscored": "현재 활성 알람의 CoF 점수가 아직 평가되지 않았습니다.",
        }.get(snapshot["status"], "현재 알람 우선순위를 확인할 수 없습니다.")
        lines = [heading, explanation]
        if snapshot["unscored_count"]:
            lines.append(f"CoF 미평가 {snapshot['unscored_count']}건")
        return Reply("\n\n".join(lines), [_link("알람 이력 보기", history)], previous)

    lines = [
        heading,
        f"먼저 **{markdown_text(items[0]['equipment_name'])} · {markdown_text(items[0]['sensor_name'])}**을 확인하세요.",
    ]
    links = []
    for item in items:
        alarm_entity = Entity("equipment", item["equipment_id"], item["equipment_name"])
        occurred = (
            datetime.fromisoformat(item["alarm_start_time"])
            .astimezone(KST)
            .strftime("%m월 %d일 %H:%M KST")
        )
        reason = f" · {markdown_text(item['reason'])}" if item.get("reason") else ""
        lines.append(
            f"{item['rank']}. **{markdown_text(item['equipment_name'])} · {markdown_text(item['sensor_name'])}**"
            f" · CoF **{item['cof_score']:g}** · {occurred} 발생"
            f"{reason}"
        )
        links.append(
            _link(
                f"{item['rank']}순위 {item['equipment_name']} 확인",
                alarm_entity.link("/equip", sensor_id=item["sensor_id"], alarm_id=item["alarm_id"]),
            )
        )
    if snapshot["unscored_count"]:
        lines.append(f"CoF 미평가 {snapshot['unscored_count']}건")
    if snapshot["unknown_count"]:
        lines.append(f"활성 상태 미확인 이력 {snapshot['unknown_count']}건")
    links.append(_link("알람 이력 보기", history))
    return Reply(
        "\n\n".join(lines),
        links,
        {key: items[0][key] for key in ("alarm_id", "equipment_id", "sensor_id")},
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
    if request.intent == "sensor_options":
        return _sensor_views(entity, matches, days, request.hours, request.show_anomalies)
    path = "/trend" if request.intent == "trend" else "/equip"
    window = _trend_window(days, request.hours) if path == "/trend" else {}
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
                [timedelta(hours=request.hours) if request.hours else timedelta(days=days)],
                request.show_anomalies,
            )
            if path == "/trend" and len(matches) == 1
            else None
        ),
    )


async def run_chat_workflow(
    tools: Toolset,
    message: str,
    screen: dict[str, object],
    previous: dict,
) -> Reply:
    if multi_reply := await _multi_trend_reply(tools, message, screen):
        return multi_reply
    request = reflect(message)
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
            days=request.days or sensor_view["days"],
            hours=request.hours or sensor_view.get("hours"),
        )
    screen_equipment_id = screen.get("equipment_id")
    if isinstance(screen_equipment_id, str) and screen.get("alarm_id"):
        screen_alarm = await tools.get_alarm(screen_equipment_id, screen["alarm_id"])
        if screen_alarm and (
            not screen.get("sensor_id") or screen["sensor_id"] == screen_alarm["sensor_id"]
        ):
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
    entity = None
    needs_scope = request.target or request.relative
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
        equipment_only = intent in {"inspection_evidence", "maintenance_draft"}
        status, candidates = await _resolve_target(tools, request, screen, previous, equipment_only)
        if selected:
            candidates = [
                item for item in candidates if item.kind == selected.kind and item.id == selected.id
            ]
            status = "found" if len(candidates) == 1 else "not_found"
        if status != "found" or len(candidates) != 1:
            return _ask(request, status, candidates, previous)
        entity = candidates[0]

    if "get_alarm_priorities" in action.tools:
        return await _priority_reply(tools, entity, request, previous)
    if intent == "alarm_history":
        filters = _dates(request.days)
        if request.relative and "알람" in request.relative and previous.get("sensor_id"):
            filters["sensor_id"] = previous["sensor_id"]
        href = entity.link("/alarms", **filters) if entity else "/alarms"
        if not entity and filters:
            href = f"/alarms?from={filters['from']}&to={filters['to']}"
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
            text, links = build_maintenance_draft(entity.name, evidence, alarm=alarm)
        else:
            text, links = format_inspection_evidence(entity.name, evidence)
        return Reply(text, links, context)
    return await _show_equipment(tools, entity, request, previous, screen)
