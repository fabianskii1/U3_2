"""Navigate actual console controls, retaining the currently visible scope."""

import re
from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode

from skadi_agents.reflector import normalize


def _params(screen):
    query = screen.get("query", "")
    return {
        k: v
        for k, v in parse_qs(query.lstrip("?") if isinstance(query, str) else "").items()
        if k
        in {
            "plant_id",
            "unit_id",
            "equip_id",
            "sensor_id",
            "from",
            "to",
            "severity",
            "event_type",
            "q",
            "status",
            "min_level",
            "actionable",
            "replay",
            "mode",
            "fault",
            "incident_id",
            "section",
            "as_of",
            "equipment_type",
        }
    }


async def run_console(tools, message, screen, previous):
    from skadi_agents.executor import Reply
    from skadi_agents.workspace import ALL, PUMP, SENSOR, _target, canonical_pumps

    text = canonical_pumps(message.strip())
    page = screen.get("page", "")
    params = _params(screen)
    section = params.get("section", [screen.get("section")])[0]
    if (
        re.search(r"보고서|초안", text)
        and not page.startswith("/incidents/")
        and section not in {"diagnosis", "3d"}
    ):
        return None
    pending = previous.get("console_pending")
    numeric = re.fullmatch(r"\s*(\d+)\s*(?:번|번째)?(?:으로|로|요)?\s*", text)
    if pending and numeric:
        index = int(numeric[1]) - 1
        if 0 <= index < len(pending["choices"]):
            return await run_console(
                tools,
                pending["choices"][index]["message"],
                pending["screen"],
                {k: v for k, v in previous.items() if k != "console_pending"},
            )
        return Reply(
            "표시된 선택지의 번호를 골라 주세요.", choices=pending["choices"], context=previous
        )
    if re.search(
        r"매뉴얼|별칭|저장해|보고서.*수정|알람.*(?:뭐부터|우선순위|1순위)|(?:\d+\s*순위|우선순위).*알람|그\s*알람",
        text,
    ):
        return None
    if not page.startswith("/incidents") and re.search(
        r"있어|뭐야|왜|무슨\s*일|조치해야|사건.*보고서\s*써", text
    ):
        return None

    detail_match = re.fullmatch(r"/incidents/([^/]+)", page)
    incident_id = detail_match[1] if detail_match else None
    short_detail = bool(
        re.fullmatch(r"(?:상세|세부|자세히)(?:\s*(?:보기|보여줘|열어줘))?[?!]*", text)
    )
    contextual_detail = short_detail and (
        page.startswith("/incidents") or (page == "/equip" and section in {"diagnosis", "3d"})
    )
    create_report = bool(re.search(r"(?:최종\s*)?보고서\s*(?:작성|생성|만들)", text))
    replay = bool(re.search(r"재생|리플레이|기록|예시\s*시각", text))
    if section == "replay" and re.search(r"현재|실시간|이전|다음|\d+\s*(?:시간|시점)", text):
        replay = True
    model = bool(re.search(r"3\s*[dD]|쓰리디|입체|고장\s*부품|부품\s*강조", text))
    model = model or bool(
        re.search(
            r"(?:장비|부품)(?:만|\s*(?:전체|모델))?(?:를|을)?"
            r"(?:\s*(?:보여줘|보여|보기|열어줘|보고\s*싶어))?[?!。]*$",
            text,
        )
    )
    if page == "/equip" and re.search(r"^(?:강조|부품만|고장만)(?:\s*보여줘)?[?!]*$", text):
        model = True
    if section == "3d" and re.fullmatch(
        r"(?:전체(?:\s*보기)?|강조|고장만|부품만)(?:\s*보여줘)?[?!]*", text
    ):
        model = True
    all_scope = bool(ALL.search(text)) and not model
    feed = bool(re.search(r"지금\s*봐야|알림", text)) and "알람" not in text
    risk = re.search(r"위험\s*(\d+)\s*(?:위)?", text)
    diagnosis = (
        bool(re.search(r"진단|고장\s*유형", text) or risk)
        and not detail_match
        and page != "/incidents"
    )
    detail_section = None
    if incident_id and not PUMP.search(text) and not re.search(r"페이지|목록|센터|이력", text):
        for pattern, value in [
            (r"경과|타임라인|진행\s*과정", "timeline"),
            (r"원인|후보", "causes"),
            (r"관련\s*알람|알람", "alarms"),
            (r"트렌드|추이|그래프|구간", "trend"),
            (r"보고서|초안", "draft"),
        ]:
            if re.search(pattern, text):
                detail_section = value
                break
    incident_area = None
    if not incident_id and (section in {"diagnosis", "3d"} or "사건" in text):
        for pattern, value in [
            (r"경과|타임라인", "timeline"),
            (r"원인|후보", "causes"),
            (r"관련\s*알람", "alarms"),
            (r"구간.*(?:트렌드|추이)|사건.*(?:트렌드|추이)", "trend"),
            (r"보고서|초안", "draft"),
        ]:
            if re.search(pattern, text):
                incident_area = value
                break
    incident_request = (
        bool(re.search(r"사건|이상\s*목록", text)) or bool(incident_area) or contextual_detail
    )
    alarm_request = bool(re.search(r"알람", text)) and not incident_request and not detail_section
    # An explicit destination exits the current list/detail; a short filter stays there.
    explicit_other = (
        bool(
            re.search(
                r"대시보드|설비\s*현황|현황|트렌드|추이|그래프|3\s*[dD]|재생|기록|알림|진단", text
            )
        )
        or model
    )
    if page == "/alarms" and not explicit_other and not incident_request:
        alarm_request = True
    incident_list = (
        incident_request
        and not incident_area
        and not contextual_detail
        and not re.search(r"상세|구체|자세히", text)
    )
    if (
        page == "/incidents"
        and (
            not explicit_other
            or ("진단" in text and not re.search(r"현황|트렌드|3\s*[dD]|재생", text))
        )
        and not alarm_request
        and not re.search(r"상세|구체|자세히", text)
    ):
        incident_list = True
    # Registered fault names can be selected without repeating 'diagnosis'.
    fault_followup = (
        page == "/equip"
        and section in {"diagnosis", "3d"}
        and not any(
            [replay, feed, model, diagnosis, incident_request, alarm_request, explicit_other]
        )
        and not SENSOR.search(text)
    )
    diagnosis = diagnosis or fault_followup
    if not any(
        [
            replay,
            model,
            feed,
            diagnosis,
            incident_request,
            alarm_request,
            detail_section,
            incident_list,
        ]
    ):
        return None

    def reply(body, href=None, choices=None, state=None):
        context = {
            k: v
            for k, v in previous.items()
            if k not in {"console_pending", "workspace_pending", "pending", "sensor_view"}
        }
        if state:
            context.update(state)
        if choices:
            context["console_pending"] = {"choices": choices, "screen": screen}
        return Reply(
            body,
            [{"title": body, "href": href}] if href else [],
            context,
            navigation_href=href,
            choices=choices or [],
        )

    def go(path, changes, title, choices=None, state=None):
        current = dict(params) if path == page else {}
        # Equipment controls retain replay/selection when moving within equipment.
        if path == "/equip":
            current.update(
                {k: v for k, v in params.items() if k in {"replay", "mode", "fault", "incident_id"}}
            )
        for k, value in changes.items():
            if value is None:
                current.pop(k, None)
            else:
                current[k] = value if isinstance(value, list) else [str(value)]
        href = path + ("?" + urlencode(current, doseq=True) if current else "")
        return reply(title, href, choices, state)

    # Detail sections refer only to the incident in the actual route.
    if (create_report or contextual_detail) and incident_id:
        detail = (
            await tools.get_incident(incident_id) if getattr(tools, "get_incident", None) else None
        )
        if not detail:
            return reply("현재 사건을 찾지 못했습니다. 사건 목록에서 다시 선택해 주세요.")
        if not create_report:
            return go(
                page,
                {},
                "이상 사건 상세 열기",
                state={"incident_id": incident_id, "equipment_id": detail["equipment_id"]},
            )
        return go(
            "/reports/new",
            {
                "incident_id": incident_id,
                "equip_id": detail["equipment_id"],
                "as_of": params.get("as_of", [None])[0],
            },
            "사건 내용으로 최종 보고서 작성",
            state={"incident_id": incident_id, "equipment_id": detail["equipment_id"]},
        )
    if detail_section:
        detail = (
            await tools.get_incident(incident_id) if getattr(tools, "get_incident", None) else None
        )
        if not detail:
            return reply("현재 사건을 찾지 못했습니다. 사건 목록에서 다시 선택해 주세요.")
        return go(
            page,
            {"section": detail_section, "draft": "open" if detail_section == "draft" else None},
            {
                "timeline": "사건 경과",
                "causes": "원인 후보",
                "alarms": "관련 알람",
                "trend": "사건 구간 트렌드",
                "draft": "보고서 초안",
            }[detail_section]
            + " 열기",
            state={"incident_id": incident_id, "equipment_id": detail["equipment_id"]},
        )

    codes = list(
        dict.fromkeys(
            m[0].upper() for m in re.finditer(r"(?<![A-Za-z0-9])P\d+(?![A-Za-z0-9])", text)
        )
    )
    entity = None
    if len(codes) > 1:
        return reply(
            "이 기능은 펌프 한 대씩 확인할 수 있습니다. 펌프를 하나 골라 주세요.",
            choices=[
                {"label": code, "message": f"{code} " + ("3D" if model else "진단")}
                for code in codes
            ],
        )
    target = codes[0] if codes else None
    if not target:
        unit = re.search(r"(?:CDU\s*)?\d+\s*호기|CDU-\d+", text, re.IGNORECASE)
        if unit:
            target = unit[0]
    if target:
        status, found = await tools.resolve_entity(target, screen=screen)
        if status != "found" or len(found) != 1:
            return reply("해당 설비나 공정을 찾지 못했습니다. 이름이나 번호를 확인해 주세요.")
        entity = found[0]
    elif not all_scope and screen.get("equipment_id"):
        entity = await tools.load_equipment(screen["equipment_id"])
    # Partial registered pump names before a destination also work.
    if not target and not codes and not fault_followup:
        destination = re.search(
            r"3\s*[dD]|쓰리디|입체|장비|부품|진단|재생|알람|이상\s*사건|사건", text
        )
        prefix = _target(text[: destination.start()].strip()) if destination else None
        if (
            prefix
            and not re.search(
                r"위험|고장|부품|현재|예시|전체|지금|원인|관련|경과|보고서|초안|이전|다음|기록",
                prefix,
            )
            and not SENSOR.search(prefix)
        ):
            status, found = await tools.resolve_entity(prefix, screen=screen)
            if status == "found" and len(found) == 1:
                entity = found[0]
            elif model or diagnosis or replay:
                return reply("어느 설비인지 확인할 수 없습니다. 펌프 이름이나 번호를 알려주세요.")

    scope = {}
    if entity:
        scope = (
            {"equip_id": entity.id}
            if entity.kind == "equipment"
            else {"unit_id": entity.id}
            if entity.kind == "unit"
            else {"plant_id": entity.id}
        )
    elif not all_scope:
        scope = {
            "plant_id": screen.get("plant_id"),
            "unit_id": screen.get("equipment_group_id"),
            "equip_id": screen.get("equipment_id"),
        }
    state = {"equipment_id": scope.get("equip_id")}
    if state["equipment_id"] is None:
        state["workspace"] = {"page": "/equip", "equipment_id": None}

    if replay or feed:
        if entity and entity.unit_id:
            scope["unit_id"] = entity.unit_id
        if not scope.get("unit_id"):
            candidates = await tools.equipment_of_type("펌프")
            groups = {
                e.unit_id: e
                for e in candidates
                if not scope.get("plant_id") or e.plant_id == scope["plant_id"]
            }
            if len(groups) == 1:
                first = next(iter(groups.values()))
                scope.update(plant_id=first.plant_id, unit_id=first.unit_id)
            else:
                return reply(
                    "확인할 공정을 먼저 선택해 주세요.",
                    choices=[
                        {"label": key, "message": key + (" 재생" if replay else " 알림")}
                        for key in groups
                    ],
                )
        changes = {**scope, "section": "replay" if replay else "feed"}
        if replay:
            current = screen.get("replay_hour", 441)
            maximum = screen.get("replay_max", 720)
            if not isinstance(current, int):
                current = 441
            if not isinstance(maximum, int) or maximum < 1:
                maximum = 720
            if re.search(r"현재|실시간", text):
                changes["replay"] = "live"
            elif re.search(r"예시", text):
                changes["replay"] = "example"
            elif re.search(r"이전|다음", text):
                changes["replay"] = str(
                    max(1, min(maximum, current + (-1 if "이전" in text else 1)))
                )
            elif hour := re.search(r"(\d+)\s*(?:시간|시점)", text):
                if not 1 <= int(hour[1]) <= maximum:
                    return reply(f"기록 시각은 1~{maximum}시간 안에서 선택해 주세요.")
                changes["replay"] = hour[1]
            else:
                changes["replay"] = params.get("replay", ["example"])[0]
        return go(
            "/equip",
            changes,
            "설비 상태 기록 재생 열기" if replay else "지금 봐야 할 알림 열기",
            state=state,
        )

    if alarm_request or incident_list:
        changes = dict(scope)
        if all_scope:
            changes.update(
                equip_id=None,
                sensor_id=None,
                q=None,
                severity=None,
                status=None,
                min_level=None,
                actionable=None,
            )
        for pattern, key, value in [
            (r"진행\s*중", "status", "ongoing"),
            (r"종료|끝난", "status", "closed"),
            (r"예정|시작\s*전", "status", "upcoming"),
            (r"조치\s*필요", "actionable", "true"),
        ]:
            if re.search(pattern, text):
                changes[key] = value
        for name, level in [("비상", 4), ("위험", 3), ("경고", 2), ("주의", 1), ("정상", 0)]:
            if name in text:
                changes["severity" if alarm_request else "min_level"] = str(level)
        if alarm_request:
            if "펌프" in text and not codes:
                changes["equipment_type"] = "펌프"
            for name in ["예측", "임계치 초과"]:
                if name in text:
                    changes["event_type"] = name
        remaining = text
        if target:
            remaining = remaining.replace(target, " ")
        remaining = re.sub(
            r"알람|이력|이상\s*사건|사건|목록|페이지|센터|검색|필터|선행\s*센서|진단|추정|관련|진행\s*중|종료|끝난|예정|시작\s*전|조치\s*필요|전체|전부|모두|비상|위험|경고|주의|정상|예측|임계치\s*초과",
            " ",
            remaining,
        )
        search = (
            _target(remaining)
            if not SENSOR.search(remaining)
            else " ".join(m[0] for m in SENSOR.finditer(remaining))
        )
        if search:
            changes["q"] = search
        if alarm_request:
            if re.search(r"최근\s*\d+\s*일|오늘|어제", text):
                from skadi_agents.workspace import window

                try:
                    start, end = window(text)
                except (ValueError, OverflowError) as exc:
                    return reply(str(exc))
                changes.update({"from": start[:10], "to": end[:10]})
            return go("/alarms", changes, "알람 이력 열기", state=state)
        if not getattr(tools, "list_incidents", None):
            return go("/incidents", changes, "이상 사건 목록 열기", state=state)
        merged = {k: v[0] for k, v in params.items()} if page == "/incidents" else {}
        merged.update(changes)
        listing = await tools.list_incidents(
            plant_id=merged.get("plant_id"),
            equipment_group_id=merged.get("unit_id"),
            equipment_id=merged.get("equip_id"),
            status=merged.get("status"),
            min_level=int(merged["min_level"]) if merged.get("min_level") else None,
            actionable=(merged["actionable"] == "true") if merged.get("actionable") else None,
            search=merged.get("q"),
            limit=50,
        )
        items = listing["items"]
        choices = [
            {
                "label": f"{i}. {item['equipment_id']} · {item['diagnosis']} · {item['incident_id']}",
                "message": f"사건 {item['incident_id']} 상세",
            }
            for i, item in enumerate(items, 1)
        ]
        if len(items) == 1:
            return go(
                "/incidents/" + quote(items[0]["incident_id"], safe=""),
                {},
                "이상 사건 상세 열기",
                state={**state, "incident_id": items[0]["incident_id"]},
            )
        return go(
            "/incidents",
            changes,
            f"이상 사건 목록 {len(items)}건 열기",
            choices=choices,
            state=state,
        )

    explicit_incident = re.search(r"사건\s+([A-Za-z0-9][A-Za-z0-9_.:-]+)\s*상세", text)
    if explicit_incident:
        incident_id = explicit_incident[1]
    elif diagnosis or model or incident_request:
        if not entity or entity.kind != "equipment":
            candidates = [
                e
                for e in await tools.equipment_of_type("펌프")
                if not scope.get("unit_id") or e.unit_id == scope["unit_id"]
            ]
            suffix = "3D" if model else "사건 상세" if incident_request else text
            if len(candidates) == 1:
                return await run_console(tools, candidates[0].id + " " + suffix, screen, previous)
            return reply(
                "어느 펌프를 확인할까요?",
                choices=[
                    {"label": f"{e.id} · {e.name}", "message": e.id + " " + suffix}
                    for e in candidates
                ],
            )
        as_of = None
        if isinstance(screen.get("as_of"), str):
            try:
                as_of = datetime.fromisoformat(screen["as_of"])
                if as_of.tzinfo is None:
                    as_of = None
            except ValueError:
                pass
        listing = (
            await tools.list_incidents(equipment_id=entity.id, as_of=as_of, limit=20)
            if getattr(tools, "list_incidents", None)
            else {"items": []}
        )
        incident = next((item for item in listing["items"] if item["status"] == "ongoing"), None)
        incident_id = incident["incident_id"] if incident else None
        detail = (
            await tools.get_incident(incident_id, as_of=as_of)
            if incident_id and getattr(tools, "get_incident", None)
            else None
        )
        candidates = detail.get("candidates", []) if detail else []
        fault = None
        if risk:
            fault = next(
                (item["fault"] for item in candidates if item["rank"] == int(risk[1])), None
            )
            if not fault:
                return reply("이 시각 해당 위험 순위의 진단 후보가 없습니다.")
        elif fault_followup:
            key = normalize(re.sub(r"보여줘|선택|해줘|으로|로$", "", text))
            matches = [
                item["fault"] for item in candidates if key and key in normalize(item["fault"])
            ]
            if len(matches) == 1:
                fault = matches[0]
            elif matches:
                return reply(
                    "여러 고장 유형에 해당합니다. 골라 주세요.",
                    choices=[
                        {"label": value, "message": f"{entity.id} 위험 {item['rank']}"}
                        for value in matches
                        for item in candidates
                        if item["fault"] == value
                    ],
                )
            else:
                return reply(
                    "일치하는 진단 후보가 없습니다. 위험 순위나 표시된 고장명으로 선택해 주세요."
                )
        changes = {
            **scope,
            "section": "3d" if model or (fault_followup and section == "3d") else "diagnosis",
        }
        if fault:
            changes.update(fault=fault, incident_id=incident_id)
        if model:
            changes["mode"] = (
                "only"
                if re.search(r"부품만|고장만", text)
                else "ghost"
                if re.search(r"강조", text)
                else "all"
            )
            choices = [
                {"label": label, "message": f"{entity.id} 3D {label}"}
                for label in ["전체 보기", "고장 부품 강조", "고장 부품만"]
            ]
            return go("/equip", changes, f"{entity.id} 3D 부품 열기", choices=choices, state=state)
        if not incident_request:
            choices = [
                {
                    "label": f"위험 {item['rank']}위 · {item['fault']}",
                    "message": f"{entity.id} 위험 {item['rank']}",
                }
                for item in candidates
            ]
            return go("/equip", changes, f"{entity.id} 진단 열기", choices=choices, state=state)
    if incident_id and getattr(tools, "get_incident", None):
        detail = await tools.get_incident(incident_id)
        if not detail:
            return reply("선택한 이상 사건을 찾을 수 없습니다.")
        if create_report:
            return go(
                "/reports/new",
                {
                    "incident_id": incident_id,
                    "equip_id": detail["equipment_id"],
                    "as_of": screen.get("as_of"),
                },
                "사건 내용으로 최종 보고서 작성",
                state={"equipment_id": detail["equipment_id"], "incident_id": incident_id},
            )
        return go(
            "/incidents/" + quote(incident_id, safe=""),
            {
                "section": incident_area,
                "draft": "open" if incident_area == "draft" else None,
                "as_of": screen.get("as_of") if page == "/equip" else None,
            },
            "이상 사건 상세 열기",
            state={"equipment_id": detail["equipment_id"], "incident_id": incident_id},
        )
    return reply(
        "이 시각 진행 중인 이상 사건이 없습니다. 이상 사건 목록에서 과거 사건도 확인할 수 있습니다."
    )
