"""Conversational navigation and data queries for the three monitoring screens."""

import re
from dataclasses import asdict
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from skadi_agents.equipment_status import Entity, matching_sensors, sensor_signal
from skadi_agents.inspection_evidence import markdown_text
from skadi_agents.reflector import normalize, reflect, view_choice
from skadi_agents.workspace.comparison import comparison_href
from skadi_agents.workspace.selection import (
    matching_equipment_choices,
    matching_sensor_choices,
    selection_reply,
)

KST = ZoneInfo("Asia/Seoul")
PUMP = re.compile(
    r"펌프\s*0*(\d+)\s*(?:번|호)?|0*(\d+)\s*(?:번|호)\s*펌프|(?<![A-Za-z0-9])[Pp]\s*0*(\d+)(?![A-Za-z0-9])"
)
SENSOR = re.compile(
    r"\d{2}-[A-Za-z]{2}-\d{4}|(?:모터\s*)?(?:선간\s*)?전압|(?:모터\s*)?전류|"
    r"(?:베어링\s*|유체\s*|모터\s*)?온도|흡입(?:\s*압력?)?(?:\s*(?:측|쪽))?|토출(?:\s*압력?)?(?:\s*(?:측|쪽))?|압력|"
    r"(?:베어링\s*|모터\s*|축\s*)?진동(?:\s*속도(?:\s*RMS)?)?|회전수|선간|베어링(?:\s*(?:측|쪽))?|유체|회전|속도",
    re.IGNORECASE,
)
MOVE = re.compile(r"보여|보여줘|열어|이동|가\s*줘|가자|돌아|보고\s*싶|확인하고\s*싶")
VALUE = re.compile(r"얼마|몇\s*(?:볼트|암페어|도)|현재\s*값|최신\s*값|측정값|값.*알려")
DATE = re.compile(r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일|\d{4}-\d{2}-\d{2}")
DURATION = re.compile(r"(?:최근\s*)?(\d+)\s*(일|시간)(?!\s*간격)")
INTERVAL = re.compile(r"(1분|1시간|하루|1일|1초)\s*(?:단위|간격)")
ALL = re.compile(r"전체|전부|모두|모든|다\s*같이")


def canonical_pumps(message: str) -> str:
    return PUMP.sub(lambda m: f"P{int(next(g for g in m.groups() if g))}", message)


def _date(match: re.Match, now: datetime) -> datetime:
    if match[1] is None and match[2] is None:
        return datetime.fromisoformat(match[0]).replace(tzinfo=KST)
    return datetime(int(match[1] or now.year), int(match[2]), int(match[3]), tzinfo=KST)


def window(text: str, inherited: dict | None = None) -> tuple[str, str]:
    now = datetime.now(KST).replace(microsecond=0)
    dates = list(DATE.finditer(text))
    if dates:
        if len(dates) != 2:
            raise ValueError("시작일과 종료일을 함께 알려주세요. 예: 11월 10일부터 15일까지")
        start, end = (_date(item, now) for item in dates)
        end += timedelta(days=1)  # A named end date includes that whole KST day.
    elif "어제" in text or "오늘" in text:
        end = now if "오늘" in text else now.replace(hour=0, minute=0, second=0)
        start = (
            now.replace(hour=0, minute=0, second=0) if "오늘" in text else end - timedelta(days=1)
        )
    elif duration := DURATION.search(INTERVAL.sub("", text)):
        amount = int(duration[1])
        end = now
        start = end - (timedelta(days=amount) if duration[2] == "일" else timedelta(hours=amount))
    elif inherited:
        start = datetime.fromisoformat(inherited["start"])
        end = datetime.fromisoformat(inherited["end"])
    else:
        start, end = now - timedelta(days=7), now
    if start >= end or end - start > timedelta(days=90):
        raise ValueError("조회 기간은 0일 초과, 90일 이내로 지정해 주세요.")
    if end > now + timedelta(minutes=5):
        raise ValueError("미래 시각까지 조회할 수 없습니다. 종료일을 확인해 주세요.")
    return start.isoformat(), end.isoformat()


def _expand_dates(text: str) -> str:
    # '11월 10일부터 15일까지' has an omitted second month.
    return re.sub(
        r"(\d{1,2})월\s*(\d{1,2})일\s*부터\s*(\d{1,2})일",
        lambda m: f"{m[1]}월 {m[2]}일부터 {m[1]}월 {m[3]}일",
        text,
    )


def _interval(text: str, inherited: str | None) -> str | None:
    match = INTERVAL.search(text)
    if not match:
        return inherited
    if match[1] == "1초":
        raise ValueError("1초 데이터는 없습니다. 1분·1시간·1일 간격을 사용할 수 있습니다.")
    return {"1분": "1m", "1시간": "1h", "하루": "1d", "1일": "1d"}[match[1]]


def _target(text: str) -> str | None:
    # Keep only an explicitly named asset; never send navigation words to lookup.
    value = INTERVAL.sub(" ", text)
    value = DATE.sub(" ", value)
    value = DURATION.sub(" ", value)
    value = SENSOR.sub(" ", value).strip(" \t\n?!.,。！？")
    value = re.sub(
        r"설비\s*현황|현재\s*현황|센서값?|측정값|현재\s*값|최신\s*값|"
        r"트렌드(?:\s*분석)?|추이|그래프|차트|현황|상태|데이터|정보|화면|"
        r"내부\s*(?:펌프|설비)\s*목록|설비\s*목록|"
        r"보여\s*주세요|보여\s*줘|알려\s*주세요|알려\s*줘|열어\s*줘|"
        r"이동해\s*줘|가\s*줘|보고\s*싶어|확인하고\s*싶어|얼마야|얼마|"
        r"이번에는|이번엔|이번에|최근|어제|오늘|현재|지금|최신|"
        r"전체|전부|모든|같이|함께|추가해\s*줘|추가|비교해\s*줘|비교|자세히",
        " ",
        value,
    )
    value = re.sub(r"^(?:이|그|해당)\s*(?:설비|펌프)", " ", value).strip()
    # Sensor/scope words leave particles behind (e.g. '흡입압의 전체를 다').
    # Discard only standalone grammatical words, keeping unknown asset names.
    value = re.sub(
        r"(?<!\S)(?:(?:펌프|설비|센서|모두)(?:의|을|를|은|는|도)?|"
        r"의|을|를|은|는|도|다|것|좀|그중에서|그중|이중에서|이중)(?!\S)",
        " ",
        value,
    )
    value = re.sub(
        r"(?:에\s*대한|으로|로|의|도|은|는|을|를|만|부터|까지|\?)\s*$", "", value
    ).strip()
    if value in {"", "이", "그", "설비", "펌프", "센서", "값", "단위", "간격", "으로", "로"}:
        return None
    value = re.sub(r"\s*설비$", "", value).strip()
    if value in {"랑", "과", "와", "및", "그리고", "이", "그"}:
        return None
    return value or None


def _sensor_matches(rows: list[dict], label: str) -> list[dict]:
    signal = sensor_signal(label)
    matches = matching_sensors(rows, label, signal)
    if not matches and "압력" in label:
        matches = matching_sensors(rows, label.replace("압력", "압"), signal)
    if not matches and normalize(label) in {
        "전류",
        "모터전류",
        "전압",
        "모터전압",
        "온도",
        "압력",
        "진동",
        "회전수",
    }:
        matches = [row for row in rows if sensor_signal(row["measurement_name"]) == signal]
    return matches


async def run_workspace(tools, message: str, screen: dict, previous: dict):
    from skadi_agents.executor import Reply

    text = _expand_dates(canonical_pumps(message.strip()))
    # Alarm, incident and document workflows keep their established interpretation.
    if re.search(r"별칭|매뉴얼|보고서|초안|사건|원인|알람\s*이력", text):
        return None
    if reflect(text).intent == "incident":
        return None
    if previous.get("alarm_as_of") and not PUMP.search(text) and not VALUE.search(text):
        return None
    old = previous.get("workspace", {})
    active = screen.get("trend_series") if screen.get("page") == "/trend" else None
    inherited_series = active if isinstance(active, list) else old.get("series", [])
    pending = previous.get("workspace_pending")
    choice = re.fullmatch(r"\s*(\d+)\s*(?:번|번째)?(?:으로|로|요)?\s*", text)
    chosen_sensor = None
    chosen_entity = None
    all_entities = []
    all_comparison = False
    if pending and pending.get("all_equipment_ids"):
        all_entities = [await tools.load_equipment(code) for code in pending["all_equipment_ids"]]
        all_entities = [entity for entity in all_entities if entity]
        all_comparison = bool(all_entities)
    if (
        pending
        and pending.get("allow_all")
        and (
            (choice and int(choice[1]) == len(pending["candidates"]) + 1)
            or (ALL.search(text) and not PUMP.search(text) and not _target(text))
        )
    ):
        followup_text = text
        all_entities = [Entity(**candidate) for candidate in pending["candidates"]]
        all_comparison = True
        choice = None
        screen, text, old = pending["screen"], pending["text"], pending["old"]
        inherited_series = pending["series"]
        if SENSOR.search(followup_text) or re.search(r"현황|상태", followup_text):
            # A scope reply can also refine the sensor or explicitly change the view.
            text = SENSOR.sub(" ", text) + " " + followup_text
    if pending and pending["kind"] == "entity" and not choice and not all_comparison:
        matches, spelling_suggestion = await matching_equipment_choices(
            tools, text, pending["candidates"]
        )
        if spelling_suggestion:
            suggested = {**pending, "candidates": [pending["candidates"][i] for i in matches]}
            return selection_reply(
                suggested, previous, "입력하신 표현과 비슷한 펌프입니다. 맞는 펌프를 선택해 주세요."
            )
        if len(matches) == 1:
            choice = re.fullmatch(r"(\d+)", str(matches[0] + 1))
        elif len(matches) > 1:
            narrowed = {**pending, "candidates": [pending["candidates"][i] for i in matches]}
            return selection_reply(
                narrowed, previous, "여러 펌프에 해당합니다. 아래 후보 중에서 선택해 주세요."
            )
    if pending and choice:
        candidates = pending["candidates"]
        index = int(choice[1]) - 1
        if not 0 <= index < len(candidates):
            return selection_reply(
                pending,
                previous,
                f"1번부터 {len(candidates) + int(bool(pending.get('allow_all')))}번 중에서 선택해 주세요.",
            )
        if pending["kind"] == "sensor":
            chosen_sensor = candidates[index]["sensor_id"]
        else:
            chosen_entity = Entity(**candidates[index])
        screen = pending["screen"]
        text = pending["text"]
        old = pending["old"]
        inherited_series = pending["series"]
    elif pending and pending["kind"] == "sensor":
        sensor_reply = (
            " ".join(m[0] for m in SENSOR.finditer(text))
            if not PUMP.search(text) and not _target(text)
            else text
        )
        matches = matching_sensor_choices(sensor_reply or text, pending["candidates"])
        if len(matches) == 1:
            followup_text = text
            chosen_sensor = matches[0]["sensor_id"]
            screen, text, old = pending["screen"], pending["text"], pending["old"]
            inherited_series = pending["series"]
            if ALL.search(followup_text) and not PUMP.search(followup_text):
                # '흡입압 전체' replaces the original single-pump scope.
                text = PUMP.sub(" ", SENSOR.sub(" ", text)) + " " + followup_text
                chosen_sensor = None
                pending = None
                all_entities, all_comparison = [], False
            else:
                text += " " + followup_text
        elif len(matches) > 1:
            narrowed = {**pending, "candidates": matches}
            return selection_reply(
                narrowed, previous, "해당하는 센서가 여러 개입니다. 아래에서 선택해 주세요."
            )
        elif (
            not PUMP.search(text)
            and not MOVE.search(text)
            and not re.search(r"대시보드|현황|트렌드|추이|알람|보고서|사건|취소", text)
        ):
            return selection_reply(
                pending,
                previous,
                "선택할 센서를 찾지 못했습니다. 짧은 센서명이나 번호로 골라 주세요.",
            )

    if (
        pending
        and not choice
        and chosen_entity is None
        and chosen_sensor is None
        and not all_comparison
    ):
        pending = None

    def response(body, links=None, *, href=None, state=None, trend=None):
        context = {
            k: v
            for k, v in previous.items()
            if k not in {"workspace_pending", "pending", "sensor_view"}
        }
        if state is not None:
            context["workspace"] = state
            if state.get("equipment_id"):
                context["equipment_id"] = state["equipment_id"]
            elif state.get("page") in {"/dashboard", "/trend"}:
                context.pop("equipment_id", None)
                context.pop("sensor_id", None)
        return Reply(body, links or [], context, navigation_href=href, trend_intent=trend)

    def ask(kind, candidates, body, allow_all=False):
        saved = {
            "kind": kind,
            "candidates": candidates,
            "text": f"{chosen_entity.id} {text}"
            if chosen_entity and not PUMP.search(text)
            else text,
            "screen": screen,
            "old": old,
            "series": inherited_series,
            "allow_all": allow_all,
            "all_equipment_ids": [entity.id for entity in all_entities] if all_comparison else [],
        }
        return selection_reply(saved, previous, body)

    dashboard = bool(
        re.search(
            r"대시보드|전체\s*(?:상황|운영)|설비\s*(?:몇\s*대|수)|정상\s*설비|알람(?:이|은|을)?\s*(?:상황|건수|몇\s*개|가장\s*많)",
            text,
        )
    )
    if dashboard and getattr(tools, "get_dashboard", None):
        scope = (
            {}
            if "전체" in text
            else {
                key: screen[key]
                for key in ("plant_id", "equipment_group_id", "equipment_id")
                if screen.get(key)
            }
        )
        target = re.split(r"대시보드|전체\s*상황|설비\s*(?:몇|수)|정상\s*설비|알람", text)[
            0
        ].strip()
        target = re.sub(r"(?:의|에서|으로|로)$", "", target).strip()
        if (
            target
            and not chosen_entity
            and target not in {"전체", "현재", "지금", "운영", "전체 운영"}
        ):
            status, entities = await tools.resolve_entity(target, screen=screen)
            if status != "found" or len(entities) != 1:
                if entities:
                    return ask("entity", [asdict(e) for e in entities], "어느 범위를 확인할까요?")
                return response(
                    "해당 플랜트·공정·설비를 찾지 못했습니다. 이름이나 코드를 확인해 주세요."
                )
            scope = entities[0].alarm_scope()
        if chosen_entity:
            scope = chosen_entity.alarm_scope()
        data = await tools.get_dashboard(**scope)
        p = data["priority"]
        lines = [
            f"모니터링 설비 **{data['equipment_count']}대** · 정상 설비 **{data['normal_count']}대**"
        ]
        if p["status"] in {"unavailable", "no_data"}:
            lines.append("활성 알람 상태를 확인할 데이터가 없습니다.")
        else:
            lines.append(
                f"활성 알람 **{p['active_count']}건** · 영향 설비 **{p['affected_equipment_count']}대**"
            )
        if p["unknown_count"]:
            lines.append(
                f"활성 여부 미확인 이력 {p['unknown_count']}건은 활성 알람 수에서 제외했습니다."
            )
        if p["unscored_count"]:
            lines.append(f"CoF 미평가 활성 알람 {p['unscored_count']}건은 순위에서 제외했습니다.")
        links = []
        for item in p["items"][:3]:
            lines.append(
                f"- 대응 {item['rank']}순위: {markdown_text(item['equipment_name'])} · CoF {item['cof_score']}"
            )
            links.append(
                {
                    "title": f"{item['equipment_id']} 현황",
                    "href": f"/equip?equip_id={item['equipment_id']}",
                }
            )
        if re.search(r"가장\s*많", text):
            totals = {}
            for row in data["alarm_summary"]:
                totals[row["equipment_id"]] = totals.get(row["equipment_id"], 0) + row["count"]
            if totals:
                highest = max(totals.values())
                lines.append(
                    "알람 건수 최다: "
                    + ", ".join(
                        f"{key} {value}건" for key, value in totals.items() if value == highest
                    )
                )
        query = urlencode(
            {
                {"equipment_id": "equip_id", "equipment_group_id": "unit_id"}.get(k, k): v
                for k, v in scope.items()
            }
        )
        href = "/dashboard" + (f"?{query}" if query else "")
        links.insert(0, {"title": "대시보드 열기", "href": href})
        return response(
            "\n\n".join(lines),
            links,
            href=href if MOVE.search(text) else None,
            state={"page": "/dashboard", **scope},
        )

    if "알람" in text or "우선" in text:
        if re.search(r"우선.*(?:설비|확인).*보여", text) and getattr(tools, "get_dashboard", None):
            scope = {k: screen[k] for k in ("plant_id", "equipment_group_id") if screen.get(k)}
            data = await tools.get_dashboard(**scope)
            items = data["priority"]["items"]
            if not items:
                return response("우선순위를 확정할 활성·평가 알람이 없습니다.")
            asset = await tools.load_equipment(items[0]["equipment_id"])
            href = asset.link("/equip")
            return response(
                f"대응 1순위 **{markdown_text(asset.name)}** 현황을 엽니다.",
                [{"title": "설비 현황", "href": href}],
                href=href,
                state={"page": "/equip", "equipment_id": asset.id},
            )
        return None

    labels = [m[0] for m in SENSOR.finditer(text)]
    if "비교" in text and not labels and not old:
        return None
    explicit_trend = bool(re.search(r"트렌드|추이|그래프|차트|비교", text))
    explicit_equip = bool(
        re.search(r"현황|상태|센서값|현재\s*현황|설비\s*전부|설비\s*전체|설비\s*목록", text)
    )
    values = bool(VALUE.search(text))
    dates_or_duration = bool(
        DATE.search(text)
        or DURATION.search(INTERVAL.sub("", text))
        or re.search(r"어제|오늘", text)
    )
    followup = bool(
        re.search(
            r"이번에는|이번엔|추가|최근|단위|간격|이\s*설비|그\s*설비|이\s*펌프|다른\s*펌프", text
        )
    )
    core = (
        explicit_trend
        or explicit_equip
        or values
        or bool(PUMP.search(text))
        or bool(labels)
        or bool(old and (followup or dates_or_duration))
    )
    if not core:
        return None
    legacy_request = reflect(text)
    # Preserve explicit alarm-relative historical requests handled by the legacy executor.
    if previous.get("alarm_as_of") and re.search(r"그\s*설비|해당\s*설비", text):
        return None
    page = (
        "/trend"
        if explicit_trend
        or (
            not explicit_equip
            and not values
            and (
                labels
                or dates_or_duration
                or old.get("page") == "/trend"
                or screen.get("page") == "/trend"
            )
        )
        else "/equip"
    )
    targets = list(
        dict.fromkeys(
            m[0].upper() for m in re.finditer(r"(?<![A-Za-z0-9])P\d+(?![A-Za-z0-9])", text)
        )
    )
    target = None if targets else _target(text)
    if target:
        # Strip request/date/sensor words before resolving a registered name.
        target = re.split(r"最近|최근|어제|오늘|\d{4}-\d{2}-\d{2}|\d{1,2}월", target)[0].strip()
        target = re.sub(r"(?:이번에는|이번엔|다른)\s*", "", target)
        target = re.sub(
            r"(?:전체|전부|센서값?|현재\s*값|최신\s*값|얼마야|얼마|보고\s*싶어|가\s*줘|보여줘|열어줘|도|은|는|의|으로|로)$",
            "",
            target,
        ).strip()
        if target in {"", "최근", "현재", "최신", "이", "그"}:
            target = None
    if all_comparison:
        targets = [entity.id for entity in all_entities]
        target = None
    if chosen_entity:
        targets = [chosen_entity.id]
        target = None
    explicit_reference = bool(
        re.search(
            r"(?:이|그|해당|선택한|선택된)\s*(?:설비|펌프)|현재\s*선택|이어서|도\s*(?:추가|보여|열어)|추가",
            text,
        )
    )
    needs_equipment = (
        not chosen_entity
        and not targets
        and not target
        and not explicit_reference
        and not (view_choice(text) and (previous.get("sensor_view") or old.get("series")))
        and (bool(labels) or explicit_trend)
    )
    if needs_equipment:
        candidates = await tools.equipment_of_type("펌프")
        candidates = [
            e
            for e in candidates
            if (not screen.get("plant_id") or e.plant_id == screen["plant_id"])
            and (not screen.get("equipment_group_id") or e.unit_id == screen["equipment_group_id"])
        ]
        eligible = []
        for entity in candidates:
            sensors = await tools.get_equipment_sensors(entity.id)
            if all(_sensor_matches(sensors, label) for label in labels):
                eligible.append(entity)
        if not eligible:
            return response(
                "현재 범위에 요청한 센서가 등록된 펌프가 없습니다. 플랜트나 공정을 변경해 주세요."
            )
        subject = "·".join(labels) or "센서"
        if ALL.search(text):
            all_entities, all_comparison = eligible, True
            targets, target = [entity.id for entity in eligible], None
        else:
            return ask(
                "entity",
                [asdict(e) for e in eligible],
                f"어느 펌프의 {markdown_text(subject)} 데이터를 확인할까요? 펌프를 선택해 주세요.",
                allow_all=page == "/trend"
                and len(eligible) > 1
                and len({e.unit_id for e in eligible}) == 1,
            )
    if (
        not pending
        and not all_comparison
        and not (view_choice(text) and old.get("series") and not previous.get("sensor_view"))
        and not explicit_reference
        and (not labels or explicit_equip or explicit_trend)
        and not (explicit_equip and not labels and not target and not previous.get("sensor_view"))
        and len(labels) <= 1
        and not values
        and not dates_or_duration
        and not INTERVAL.search(text)
        and legacy_request.intent in {"equipment_status", "sensor_options", "trend"}
        and not re.search(r"추가|비교|이번|전체|전부|모든|도\s*(?:보여|열어)|온도|압력", text)
    ):
        return None
    if "다른 펌프" in text:
        entities = await tools.equipment_of_type("펌프")
        entities = [
            e
            for e in entities
            if not screen.get("equipment_group_id") or e.unit_id == screen["equipment_group_id"]
        ]
        return (
            ask("entity", [asdict(e) for e in entities], "어느 펌프를 확인할까요?")
            if entities
            else response("선택할 펌프가 없습니다.")
        )
    if "전체" in text and explicit_equip and not targets and not target:
        screen = {**screen, "equipment_id": None, "equipment_group_id": None, "plant_id": None}
        old = {}
        previous = {k: v for k, v in previous.items() if k != "equipment_id"}
    if not targets and not target and explicit_reference and screen.get("equipment_id"):
        targets = [screen["equipment_id"]]
    if not targets and not target and inherited_series and page == "/trend":
        if getattr(tools, "equipment_for_sensors", None):
            owners = await tools.equipment_for_sensors([s["sensorId"] for s in inherited_series])
            targets = [e.id for e in owners]
        elif old.get("equipment_ids"):
            targets = old["equipment_ids"]
    if not targets and not target:
        current = screen.get("equipment_id") or (
            old.get("equipment_id") if old else previous.get("equipment_id")
        )
        if (
            screen.get("equipment_group_id")
            and not screen.get("equipment_id")
            and not re.search(r"그\s*설비|이\s*설비", text)
        ):
            current = None
            target = screen["equipment_group_id"]
        if current:
            targets = [current]
        elif target:
            pass
        elif explicit_equip:
            scope = screen.get("equipment_group_id") or screen.get("plant_id")
            if scope:
                target = scope
            else:
                return response(
                    "전체 설비 현황을 엽니다.",
                    [{"title": "설비 현황", "href": "/equip"}],
                    href="/equip",
                    state={"page": "/equip"},
                )
        else:
            return response(
                "어느 설비를 확인할까요? 예를 들어 ‘펌프1번 전류 트렌드 보여줘’라고 입력해 주세요."
            )
    entities = []
    for phrase in targets or [target]:
        status, candidates = await tools.resolve_entity(phrase, screen=screen)
        if status != "found" or len(candidates) != 1:
            if candidates:
                return ask(
                    "entity", [asdict(e) for e in candidates], "어느 설비 또는 공정을 확인할까요?"
                )
            return response(f"‘{markdown_text(phrase)}’에 해당하는 설비나 공정을 찾지 못했습니다.")
        entities.append(candidates[0])
    if any(e.kind != "equipment" for e in entities):
        entity = entities[0]
        if page == "/trend" or values or labels:
            return response(
                "센서를 확인할 펌프를 선택해 주세요.",
                [{"title": "내부 설비 목록", "href": entity.link("/equip")}],
            )
        href = entity.link("/equip")
        return response(
            f"**{markdown_text(entity.name)}** 설비 현황을 엽니다.",
            [{"title": "설비 현황", "href": href}],
            href=href,
            state={"page": "/equip"},
        )

    if all_comparison and not labels and not chosen_sensor and not inherited_series:
        labels = ["진동"]
    if (
        (
            old.get("comparison")
            or (
                screen.get("page") == "/trend"
                and not screen.get("equipment_id")
                and screen.get("sensor_ids") == []
                and active
            )
        )
        and not PUMP.search(text)
        and not labels
        and (dates_or_duration or INTERVAL.search(text))
    ):
        all_comparison, all_entities = True, entities
    # Inherit sensor names rather than sensor IDs when switching equipment.
    if not labels and not explicit_equip:
        if screen.get("equipment_id") and screen.get("sensor_id") and not inherited_series:
            rows = await tools.get_equipment_sensors(screen["equipment_id"])
            labels = [s["measurement_name"] for s in rows if s["sensor_id"] == screen["sensor_id"]]
        elif inherited_series:
            for item in inherited_series:
                if item.get("label"):
                    labels.append(item["label"])
                elif item.get("sensorId"):
                    owners = []
                    if getattr(tools, "equipment_for_sensors", None):
                        owners = await tools.equipment_for_sensors([item["sensorId"]])
                    elif owner := await tools.load_equipment(
                        screen.get("equipment_id") or old.get("equipment_id")
                    ):
                        owners = [owner]
                    for owner in owners:
                        rows = await tools.get_equipment_sensors(owner.id)
                        labels.extend(
                            s["measurement_name"]
                            for s in rows
                            if s["sensor_id"] == item["sensorId"]
                        )
        labels = list(dict.fromkeys(labels))
    selected = []
    for entity in entities:
        rows = await tools.get_equipment_sensors(entity.id)
        if chosen_sensor:
            source_sensor = next(
                (
                    row
                    for row in (pending or {}).get("candidates", [])
                    if row["sensor_id"] == chosen_sensor
                ),
                None,
            )
            queries = [
                source_sensor["measurement_name"]
                if all_comparison and source_sensor
                else chosen_sensor
            ]
        else:
            queries = labels
        matches = []
        for label in queries:
            signal = sensor_signal(label)
            found = _sensor_matches(rows, label)
            if signal == "vibration" and len(found) > 1 and label == "진동":
                found = matching_sensors(found, "진동 속도 RMS", signal) or found
            if not found:
                return response(
                    f"{markdown_text(entity.name)}에 ‘{markdown_text(label)}’ 센서가 없습니다. 등록 센서: "
                    + ", ".join(markdown_text(s["measurement_name"]) for s in rows)
                )
            if len(found) > 1:
                return ask(
                    "sensor",
                    found,
                    f"{markdown_text(label)} 센서가 여러 개 있습니다. 어느 센서를 볼까요?",
                )
            matches.extend(found)
        matches = matches or rows
        selected.extend((entity, s) for s in matches)
    selected = list({s["sensor_id"]: (e, s) for e, s in selected}.values())
    if not selected:
        return response("이 설비에 등록된 센서가 없습니다.")
    first = entities[0]
    context = {"page": page, "equipment_id": first.id if len(entities) == 1 else None}
    if values:
        if not getattr(tools, "get_equipment_readings", None):
            return None
        lines = []
        for entity in entities:
            data = await tools.get_equipment_readings(entity.id)
            for e, s in selected:
                if e.id != entity.id:
                    continue
                reading = next(
                    (r for r in data["sensors"] if r["sensor_id"] == s["sensor_id"]), None
                )
                value = reading.get("current_value") if reading else None
                when = reading.get("measured_at") if reading else None
                detail = (
                    "저장된 측정값 없음"
                    if value is None
                    else f"{value:g} {s.get('unit', '')} · {datetime.fromisoformat(when).astimezone(KST):%Y-%m-%d %H:%M:%S} KST"
                )
                lines.append(
                    f"- {markdown_text(entity.name)} · {markdown_text(s['measurement_name'])}: {detail}"
                )
        context["series"] = [
            {"sensorId": s["sensor_id"], "label": s["measurement_name"]} for _, s in selected
        ]
        return response(
            "**최신 저장 측정값**\n\n" + "\n".join(lines),
            [{"title": "설비 현황", "href": first.link("/equip")}],
            state=context,
        )
    if page == "/equip":
        if all_comparison and len({e.unit_id for e in entities}) != 1:
            return response("전체 센서 현황을 확인할 공정을 먼저 선택해 주세요.")
        params = (
            {"plant_id": first.plant_id, "unit_id": first.unit_id}
            if all_comparison
            else {"equip_id": first.id}
        )
        href = "/equip?" + urlencode(params)
        if labels or chosen_sensor:
            href += "".join("&sensor_id=" + s["sensor_id"] for _, s in selected)
        context["series"] = [
            {"sensorId": s["sensor_id"], "label": s["measurement_name"]} for _, s in selected
        ]
        return response(
            (
                f"**전체 펌프 {len(entities)}대** 설비 현황을 엽니다."
                if all_comparison
                else f"**{markdown_text(first.name)}** 설비 현황을 엽니다."
            ),
            [{"title": "설비 현황", "href": href}],
            href=href,
            state=context,
        )
    if len({e.unit_id for e in entities}) != 1:
        return response("같은 공정에 속한 설비끼리 비교해 주세요.")
    try:
        interval = _interval(text, screen.get("sensor_interval") or old.get("interval"))
        series = []
        has_period = dates_or_duration
        for entity, sensor in selected:
            inherited = next(
                (
                    s
                    for s in inherited_series
                    if s.get("sensorId") == sensor["sensor_id"]
                    or s.get("label") == sensor["measurement_name"]
                ),
                None,
            )
            if inherited and "start" not in inherited:
                inherited = None
            if inherited is None and inherited_series and "start" in inherited_series[0]:
                inherited = inherited_series[0]
            period_text = text
            if len(list(DURATION.finditer(text))) > 1:
                # Each comma/그리고 clause may define a separate sensor duration.
                for part in re.split(r"[,，]|그리고", text):
                    if any(
                        sensor_signal(m[0]) == sensor_signal(sensor["measurement_name"])
                        for m in SENSOR.finditer(part)
                    ) and DURATION.search(part):
                        period_text = part
                        break
            if all_comparison and series and len(list(DURATION.finditer(text))) <= 1:
                start, end = series[0]["start"], series[0]["end"]
            else:
                start, end = window(period_text, None if has_period else inherited)
            series.append(
                {
                    "sensorId": sensor["sensor_id"],
                    "start": start,
                    "end": end,
                    "label": sensor["measurement_name"],
                }
            )
        if "추가" in text or ("비교" in text and len(entities) == 1):
            by_id = {s["sensorId"]: s for s in inherited_series if "start" in s}
            by_id.update({s["sensorId"]: s for s in series})
            series = list(by_id.values())
        if len(series) > 24:
            raise ValueError("한 번에 최대 24개 센서를 조회할 수 있습니다. 센서를 줄여 주세요.")
        for item in series:
            if interval:
                step = {"1m": 60, "1h": 3600, "1d": 86400}[interval]
                if (
                    datetime.fromisoformat(item["end"]) - datetime.fromisoformat(item["start"])
                ).total_seconds() / step > 10000:
                    raise ValueError(
                        "조회 지점이 10,000개를 넘습니다. 기간을 줄이거나 간격을 늘려 주세요."
                    )
    except (ValueError, OverflowError) as exc:
        return response(str(exc))
    # Mixed-equipment series are validated against the group, never a single equipment.
    mixed = any(
        s["sensorId"] not in {r["sensor_id"] for e, r in selected if e.id == first.id}
        for s in series
    )
    intent = {
        "equipmentGroupId": first.unit_id,
        "equipmentId": None if mixed or len(entities) > 1 else first.id,
        "series": [{k: v for k, v in s.items() if k != "label"} for s in series],
        "showAnomalies": "이상 구간" in text,
        "interval": interval,
    }
    context.update(
        series=series,
        comparison=all_comparison,
        interval=interval,
        equipment_id=intent["equipmentId"],
        equipment_ids=list(
            dict.fromkeys(
                [
                    *(old.get("equipment_ids", []) if "추가" in text or "비교" in text else []),
                    *(e.id for e in entities),
                ]
            )
        ),
    )
    periods = list(
        dict.fromkeys(
            f"{datetime.fromisoformat(s['start']).astimezone(KST):%Y-%m-%d %H:%M} ~ {datetime.fromisoformat(s['end']).astimezone(KST):%Y-%m-%d %H:%M} KST"
            for s in series
        )
    )
    if all_comparison:
        href = comparison_href(entities, selected, series, interval)
        if href:
            return response(
                f"**전체 펌프 {len(entities)}대 비교 트렌드**를 엽니다. 펌프마다 한 선으로 표시합니다.\n\n"
                + "\n".join(periods),
                [{"title": "전체 펌프 비교 트렌드 열기", "href": href}],
                href=href,
                state=context,
            )
    return response(
        "**"
        + ", ".join(markdown_text(e.name) for e in entities)
        + f"** 트렌드를 엽니다. 센서 {len(series)}개\n\n"
        + "\n".join(periods),
        state=context,
        trend=intent,
    )
