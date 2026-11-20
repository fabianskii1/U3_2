"""AG-01 Reflector for interpreting supported chat requests."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Intent = Literal[
    "alias_lookup",
    "equipment_lookup",
    "equipment_status",
    "sensor_options",
    "alarm_history",
    "alarm_priority",
    "initial_alarm_report",
    "incident",
    "trend",
    "inspection_evidence",
    "maintenance_draft",
    "out_of_scope",
    "clarify",
    "plant_units",
]
ViewIntent = Literal["equipment_status", "trend"]

SIGNALS = {
    "진동": "vibration",
    "온도": "temperature",
    "압력": "pressure",
    "전류": "current",
    "전압": "voltage",
    "회전수": "speed",
}
SIGNAL_LABELS = {value: name for name, value in SIGNALS.items()}
EQUIPMENT_TYPES = {"압축기", "펌프", "송풍기", "터빈", "모터"}
REQUEST_END = re.compile(
    r"(?:를|을)?\s*(?:보여\s*줘|보여\s*주세요|알려\s*줘|알려\s*주세요|열어\s*줘|"
    r"열어\s*주세요|찾아\s*줘|찾아\s*주세요|확인해\s*줘|확인해\s*주세요|"
    r"작성해\s*줘|만들어\s*줘|써\s*줘|그려\s*줘|이동해\s*줘)$"
)
TREND_TERMS = r"트렌드(?:\s*분석)?|추이|차트"
STATUS_END = re.compile(
    r"(?:현재\s*값|측정값|(?:설비\s*)?현황|(?:내부\s*)?(?:펌프|설비)\s*목록|"
    rf"상태|데이터|정보|화면|{TREND_TERMS})(?:를|을)?$"
)
SENSOR_PHRASE = re.compile(
    r"(?P<name>(?:베어링\s*|축\s*|모터\s*)?진동(?:\s*속도\s*RMS)?|"
    r"(?:베어링\s*|유체\s*|모터\s*)?온도|흡입압력?|토출압력?|압력|(?:모터\s*)?전류|전압|회전수)"
    r"(?:만|을|를)?$",
    re.IGNORECASE,
)
PRIORITY = re.compile(
    r"우선|순위|순서|비교|cof|뭐부터|어떤.*먼저|뭐\s*(?:봐|보|확인)|먼저", re.IGNORECASE
)
ALARM_REQUEST = re.compile(
    r"\s*(?:활성\s*)?알람(?:의|을|이|은)?(?=\s|$|별|이력|관련|데이터|현황|목록|뭐)"
)
ALARM_REFERENCE = re.compile(r"^(?:이|그|해당)\s*알람(?:의)?(?=\s|$)")
TREND = re.compile(TREND_TERMS)
TREND_TERM = re.compile(rf"(?<!\S)(?:{TREND_TERMS})(?:를|을)?(?=\s|$)")
RELATIVE_TARGETS = {"이설비", "그설비", "이알람", "그알람", "해당설비", "해당알람", "이걸로"}
WEATHER = re.compile(
    r"날씨|일기\s*예보|기상\s*(?:정보|예보|특보)|기온|미세\s*먼지|강수\s*(?:확률|량)|"
    r"(?<!\S)(?:비|눈)(?:가)?\s*(?:와|오[니는나요]|올까)"
)
VAGUE_REQUESTS = {
    "",
    "요청",
    "요청있어",
    "요청이있어",
    "요청사항",
    "질문",
    "질문있어",
    "질문이있어",
    "정보",
    "확인",
    "도움",
    "도와줘",
    "뭐좀",
}
PLANT_UNITS = re.compile(
    r"(?:등록(?:된)?\s*)?(?:몇\s*호기(?:까지)?|"
    r"(?:공정|호기)\s*(?:목록|수(?=\s|$|[가를는]))|"
    r"(?:공정|호기)(?:은|는|이|가)?\s*몇\s*(?:개|기|곳)|"
    r"몇\s*(?:개의?\s*)?공정)"
)
PLANT_PARTICLE = re.compile(r"(?:에는|에서는|에서|에|의|은|는|이|가)$")
PLANT_CONTEXT = {"", "현재", "지금", "여기", "이플랜트", "그플랜트", "이공장", "그공장"}
ALARM_DATE = re.compile(
    r"(?<!\d)(?:\d{4}\s*년\s*)?\d{1,2}\s*월\s*\d{1,2}\s*일"
    r"(?:\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?)?(?:\s*KST)?"
    r"|(?<!\d)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?)?(?:\s*KST)?",
    re.IGNORECASE,
)
INCIDENT = re.compile(
    r"이상\s*사건|사건|원인|무슨\s*일|왜\s*(?:떴|발생|울렸|났|생겼)|"
    r"조치\s*(?:해야|필요)|얼마나\s*급"
)
INCIDENT_LIST = re.compile(r"목록|있어|있나|있니|있는지|진행\s*중|발생한|들(?=\s|$)")
INCIDENT_FILLER = re.compile(
    r"(?<!\S)(?:지금|현재|최근|이번\s*달|이번달|올해|진행\s*중인?|발생한|목록|있어|있나|있니|"
    r"있는지|뭐야|뭐예요|뭔가요|알려\s*줘|이야|이에요|인가요|인지)(?=\s|$)|"
    r"(?:의|이|가|은|는|을|를|에|에서)$"
)
PUMP_COMPARISON = re.compile(r"(?i)^P\d+\s*(?:과|와|,|·|\s+및\s+)\s*P\d+\s*비교$")
ALARM_TYPES = re.compile(r"임계치\s*초과|예측")


@dataclass(frozen=True)
class Reflection:
    intent: Intent
    target: str | None = None
    sensor: str | None = None
    signal: str | None = None
    relative: str | None = None
    days: int | None = None
    first_only: bool = False
    selection: int | None = None
    hours: int | None = None
    show_anomalies: bool = False
    priority_time: str | None = None
    priority_group: Literal["equipment", "alarm"] = "equipment"
    priority_all: bool = False
    comparison_targets: tuple[str, ...] = ()
    alarm_event_type: str | None = None
    incident_list: bool = False
    incident_status: str | None = None


def normalize(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def view_choice(message: str) -> ViewIntent | None:
    text = re.sub(r"[?!.。\s]+$", "", unicodedata.normalize("NFKC", message).strip())
    key = normalize(REQUEST_END.sub("", text))
    if key in {"설비현황", "현황", "현재값", "측정값"}:
        return "equipment_status"
    if key in {"트렌드", "트렌드분석", "추이", "차트", "최근7일추이", "최근7일트렌드"}:
        return "trend"
    return None


def _extract_sensor(text: str) -> tuple[str, str | None, str | None]:
    explicit = re.search(r"(?:^|\s)(\d{2}-[A-Z]{2}-\d{4})$", text, re.IGNORECASE)
    if explicit:
        return text[: explicit.start()].strip(), explicit[1], None
    match = SENSOR_PHRASE.search(text)
    if not match:
        return text, None, None
    name = match["name"]
    signal = next((value for key, value in SIGNALS.items() if key in name), None)
    if signal is None and name.startswith(("흡입압", "토출압")):
        signal = "pressure"
    return text[: match.start()].strip(), name, signal


def reflect(message: str) -> Reflection:
    """Extract only the requested intent and user-supplied phrases."""
    text = re.sub(r"[?!.。\s]+$", "", unicodedata.normalize("NFKC", message).strip())
    compact = normalize(text)
    selection = re.fullmatch(r"(\d{1,3})(?:번|번째)(?:으로|로|요)?", compact)
    if selection or compact in {"첫번째", "첫번째요", "두번째", "두번째요", "세번째", "세번째요"}:
        index = int(selection[1]) if selection else {"첫": 1, "두": 2, "세": 3}[compact[0]]
        return Reflection("equipment_lookup", target=text, selection=index)

    target = REQUEST_END.sub("", text).strip()
    if WEATHER.search(target):
        return Reflection("out_of_scope")
    if normalize(target) in VAGUE_REQUESTS:
        return Reflection("clarify")
    alias_request = re.search(
        r"(?:의\s*)?(?:별칭|다른\s*이름)(?:은|이|을|를)?(?:\s*(?:뭐야|뭔가요|조회))?$",
        target,
    )
    if alias_request:
        subject = target[: alias_request.start()].strip()
        return Reflection("alias_lookup", target=subject or None)
    priority_time = None
    priority_group = "equipment"
    priority_all = False
    comparison_targets = ()
    alarm_event_type = None
    if report := re.search(r"초기\s*보고서", target):
        target = target[: report.start()].strip()
        intent: Intent = "initial_alarm_report"
    elif re.search(r"보고서|초안", target):
        target = re.split(r"\s*(?:정비\s*(?:조치\s*)?)?보고서|\s*초안", target, maxsplit=1)[0]
        target = re.sub(r"^(?:이|그|해당)\s*사건(?:으로|의|을|를|로)?$", "", target.strip())
        intent = "maintenance_draft"
    elif re.search(r"점검\s*근거|매뉴얼|유사\s*사례", target):
        target = re.split(r"\s*(?:의\s+)?(?:점검\s*근거|매뉴얼|유사\s*사례)", target, maxsplit=1)[0]
        intent = "inspection_evidence"
    elif incident := INCIDENT.search(target):
        stem = target[: incident.start()].strip()
        listing = bool(
            INCIDENT_LIST.search(target[incident.start() :]) or INCIDENT_LIST.search(stem)
        )
        previous_stem = None
        while stem != previous_stem:
            previous_stem = stem
            stem = INCIDENT_FILLER.sub(" ", stem).strip()
        compact_stem = normalize(stem)
        relative = compact_stem if compact_stem in RELATIVE_TARGETS else None
        if compact_stem in {"이", "그", "해당", "이사건", "그사건", "해당사건"}:
            relative, stem = "그알람", ""
        return Reflection(
            "incident",
            target=None if relative else stem or None,
            relative=relative,
            incident_list=listing and not relative,
            incident_status="ongoing" if re.search(r"진행\s*중", target) else None,
        )
    elif PUMP_COMPARISON.fullmatch(target):
        return Reflection(
            "alarm_priority",
            comparison_targets=tuple(re.findall(r"P\d+", target, re.IGNORECASE)),
        )
    elif (alarm := ALARM_REQUEST.search(target)) and not (
        ALARM_REFERENCE.match(target) and TREND.search(target)
    ):
        intent = (
            "alarm_priority"
            if PRIORITY.search(text) or re.fullmatch(r"(?:지금|현재)알람(?:을)?", compact)
            else "alarm_history"
        )
        tail = target[alarm.end() :]
        stem = target[: alarm.start()].strip()
        if intent == "alarm_priority":
            date = ALARM_DATE.search(target)
            priority_time = (
                date[0]
                if date
                else ""
                if re.search(r"어제|그제|지난|과거|\d+\s*시", target)
                else None
            )
            priority_group = "alarm" if re.search(r"개별|알람\s*별", target) else "equipment"
            priority_all = bool(re.search(r"전체|모든", target))
            stem = ALARM_DATE.sub(" ", stem)
            stem = re.sub(r"기준(?:으로)?|개별|전체|모든|알람별", " ", stem).strip()
            if "비교" in target:
                targets = re.split(r"(?<=\S)[과와]\s+|\s+(?:및|그리고)\s+|[,·]", stem)
                if len(targets) > 1:
                    comparison_targets = tuple(item.strip() for item in targets)
                    stem = ""
        elif kind := ALARM_TYPES.search(target):
            alarm_event_type = "예측" if kind[0] == "예측" else "임계치 초과"
            stem = ALARM_TYPES.sub(" ", stem)
        target = stem.strip()
        if target in {"이", "그", "해당"}:
            target += " 알람"
        else:
            target = re.sub(r"^(?:지금|현재|오늘)\s*", "", target)
            target = re.sub(r"(?:^|\s)(?:상위\s*)?1\s*순위\s*$", "", target).strip()
    elif unit_query := PLANT_UNITS.search(target):
        plant = target[: unit_query.start()].strip()
        plant = re.sub(r"^(?:현재|지금)\s+|\s+(?:현재|지금)$", "", plant)
        plant = PLANT_PARTICLE.sub("", plant.strip()).strip()
        return Reflection(
            "plant_units", target=None if normalize(plant) in PLANT_CONTEXT else plant
        )
    else:
        if TREND.search(target):
            intent = "trend"
            target = TREND_TERM.sub(" ", target).strip()
        elif STATUS_END.search(target):
            intent = "equipment_status"
        elif _extract_sensor(target)[1]:
            intent = "sensor_options"
        elif target != text:
            intent = "equipment_status"
        else:
            return Reflection("equipment_lookup", target=text)
        while STATUS_END.search(target):
            target = STATUS_END.sub("", target).strip()

    show_anomalies = bool(re.search(r"이상\s*(?:구간|치)", text))
    target = re.sub(r"이상\s*(?:구간|치)(?:을|를)?(?:\s*표시)?", " ", target).strip()
    duration_pattern = r"(?<!\S)(?:최근\s*)?(\d{1,2})\s*(일|시간)(?=\s|$)"
    duration = re.search(duration_pattern, target)
    history_duration = (
        re.search(duration_pattern, tail) if intent == "alarm_history" and not duration else None
    )
    period = duration or history_duration
    amount = int(period[1]) if period and 1 <= int(period[1]) <= 90 else None
    days = amount if period and period[2] == "일" else None
    hours = amount if period and period[2] == "시간" else None
    if duration:
        target = (target[: duration.start()] + target[duration.end() :]).strip()
    target, sensor, signal = _extract_sensor(target)
    if target.endswith("의") and len(target) > 1:
        target = target[:-1].strip()
    relative = normalize(target) if normalize(target) in RELATIVE_TARGETS else None
    return Reflection(
        intent,
        None if relative else target or None,
        sensor,
        signal,
        relative,
        days,
        bool(re.search(r"(?<!\d)1\s*순위", text)),
        hours=hours,
        show_anomalies=show_anomalies,
        priority_time=priority_time,
        priority_group=priority_group,
        priority_all=priority_all,
        comparison_targets=comparison_targets,
        alarm_event_type=alarm_event_type,
    )
