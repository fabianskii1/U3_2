"""SA-04 incident explanation from the backend's analyzer results."""

from collections.abc import Mapping
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from skadi_agents.inspection_evidence import markdown_text

KST = ZoneInfo("Asia/Seoul")
LEVELS = ("정상", "주의", "경고", "위험", "비상")
STATUS = {"upcoming": "시작 전", "ongoing": "진행 중", "closed": "종료"}


def kst(value: str | None) -> str:
    if not value:
        return "미기록"
    return datetime.fromisoformat(value).astimezone(KST).strftime("%m-%d %H:%M")


def level(value: int | None) -> str:
    return LEVELS[value] if value is not None else "미기록"


def incident_href(incident_id: str) -> str:
    return f"/incidents/{incident_id}"


def _trend_href(detail: Mapping) -> str | None:
    signals = detail.get("trend_window", {}).get("signals") or []
    if not signals:
        return None
    params = {
        "equip_id": detail["equipment_id"],
        "sensor_id": signals[0]["sensor_id"],
        "from": detail["trend_window"]["from"],
        "to": detail["trend_window"]["to"],
    }
    return f"/trend?{urlencode(params)}"


def format_incident(detail: Mapping) -> tuple[str, list[dict[str, str]]]:
    """Explain one incident using only backend fields; causes stay estimates."""
    name = markdown_text(detail["equipment_name"])
    status = STATUS[detail["status"]]
    end_label = "예상 종료" if detail["status"] != "closed" else "종료"
    lead = (
        f"{markdown_text(detail['lead_sensor_name'])}({markdown_text(detail['lead_sensor_id'])})"
        if detail.get("lead_sensor_id")
        else "미기록"
    )
    lines = [
        f"**{name} 이상 사건 · {status}** · 진단 **{markdown_text(detail['diagnosis'])}**(추정)",
        "\n".join(
            [
                (
                    f"- 경과 · {kst(detail['incident_start_time'])} 시작 → "
                    f"{kst(detail['detect_time'])} 감지 → {kst(detail['first_alarm_time'])} 첫 알람"
                    f" → {kst(detail['incident_end_time'])} {end_label}"
                ),
                f"- 선행 센서 · {lead}",
                (
                    f"- 최고 등급 {level(detail['peak_level'])} · 사건 점수 {detail['incident_score']:g}"
                    f" · 사건 CoF {detail['top_cof']:g} · PoF {detail['top_pof']:.1%}"
                ),
                (
                    f"- 대응 · {markdown_text(detail['alarm_grade'])}"
                    f" ({markdown_text(detail['grade_reason'])})"
                    f" · 조치 필요 {'예' if detail['actionable'] else '아니오'}"
                ),
            ]
        ),
    ]
    alarms = detail.get("alarms") or []
    if alarms:
        alarm_lines = []
        for item in alarms:
            peak = level(item.get("peak_level"))
            judged = level(item["alarm_level"])
            reach = f" · 최고 도달 {peak}" if peak != judged else ""
            alarm_lines.append(
                f"- {markdown_text(item['sensor_name'])} · {markdown_text(item['event_type'] or '알람')}"
                f" · {kst(item['alarm_start_time'])} · 판정 {judged}{reach}"
            )
        lines.append(f"**관련 알람 {len(alarms)}건**\n\n" + "\n".join(alarm_lines))
    else:
        lines.append("관련 알람 없음")
    candidates = detail.get("candidates") or []
    candidate_lines = [
        f"{item['rank']}. {markdown_text(item['fault'])} · 점수 {item['score']:g}"
        f"{' · 진단(추정)' if item['is_diagnosis'] else ''}"
        f" — {markdown_text(item['evidence'])}"
        for item in candidates
    ]
    if len(candidates) == 1:
        candidate_lines.append("비교할 다른 원인 후보가 없습니다.")
    lines.append(
        "**원인 후보** · 분석기 추정이며 확정 원인이 아닙니다.\n\n" + "\n".join(candidate_lines)
    )
    if detail.get("data_coverage") == "none":
        lines.append("사건 구간의 센서 데이터가 없어 그래프로 확인할 수 없습니다.")
    for warning in detail.get("warnings") or []:
        lines.append(f"주의 · {markdown_text(warning)}")
    links = [
        {
            "title": f"{detail['equipment_name']} 사건 상세",
            "href": incident_href(detail["incident_id"]),
        }
    ]
    if trend := _trend_href(detail):
        links.append({"title": "사건 구간 트렌드", "href": trend})
    return "\n\n".join(lines), links


def format_incident_list(scope: str, listing: Mapping) -> tuple[str, list[dict[str, str]]]:
    items = listing["items"]
    heading = f"**{markdown_text(scope)} 이상 사건** · {kst(listing['as_of'])} KST 기준"
    if not items:
        return f"{heading}\n\n해당하는 이상 사건이 없습니다.", [
            {"title": "사건 목록 보기", "href": "/incidents"}
        ]
    lines = [heading, f"{len(items)}건{' 이상' if listing.get('next_cursor') else ''}"]
    for index, item in enumerate(items, start=1):
        lines.append(
            f"{index}. **{markdown_text(item['equipment_name'])}** · {STATUS[item['status']]}"
            f" · {markdown_text(item['diagnosis'])}(추정) · {kst(item['incident_start_time'])} 시작"
            f" · 최고 {level(item['peak_level'])} · 대응 {markdown_text(item['alarm_grade'])}"
        )
    links = [
        {
            "title": f"{item['equipment_name']} 사건 상세",
            "href": incident_href(item["incident_id"]),
        }
        for item in items[:3]
    ]
    links.append({"title": "사건 목록 보기", "href": "/incidents"})
    return "\n\n".join(lines), links
