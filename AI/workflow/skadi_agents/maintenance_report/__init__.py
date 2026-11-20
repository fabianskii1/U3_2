"""SA-03 draft generation from a verified alarm and inspection evidence."""

from collections.abc import Mapping

from skadi_agents.incident import kst, level
from skadi_agents.inspection_evidence import InspectionEvidence, format_sources, markdown_text


def _incident_sections(incident: Mapping) -> tuple[list[str], str, str]:
    observations = [
        (
            f"이상 사건 {markdown_text(incident['incident_id'])} · {kst(incident['incident_start_time'])} 시작"
            f" · 선행 센서 {markdown_text(incident.get('lead_sensor_name') or '미기록')}"
        )
    ]
    observations += [
        f"{markdown_text(item['sensor_name'])} {markdown_text(item['event_type'] or '알람')}"
        f" {kst(item['alarm_start_time'])}~{kst(item['alarm_end_time'])}"
        f" · 최고 {level(item.get('peak_level'))}"
        for item in incident.get("alarms") or []
    ]
    causes = "; ".join(
        f"{markdown_text(item['fault'])}({item['score']:g})" for item in incident["candidates"]
    )
    risk = (
        f"대응 등급 {markdown_text(incident['alarm_grade'])}"
        f" ({markdown_text(incident['grade_reason'])}) · PoF {incident['top_pof']:.1%}"
    )
    return observations, f"검토 필요 · 분석기 후보(추정) {causes}", risk


def build_maintenance_draft(
    equipment_name: str,
    evidence: InspectionEvidence,
    *,
    alarm: Mapping[str, object] | None = None,
    incident: Mapping | None = None,
) -> tuple[str, list[dict[str, str]]]:
    lines, links = format_sources(evidence)
    subject = f"{markdown_text(equipment_name)} ({markdown_text(evidence.equipment_id)})"
    observation = "연결된 알람 관측값 없음. 현장 관측 내용을 입력해 주세요."
    if alarm and alarm.get("equipment_id") == evidence.equipment_id:
        alarm_id = markdown_text(alarm["alarm_id"])
        alarm_start_time = markdown_text(alarm["alarm_start_time"])
        sensor_id = markdown_text(alarm["sensor_id"])
        observation = f"알람 {alarm_id} · {alarm_start_time} · 센서 {sensor_id}"
        if alarm.get("cof_score") is not None:
            observation += f" · CoF {markdown_text(alarm['cof_score'])}"
    body = [f"- 관측 내용 · {observation}", "- 원인 · 확인 대기"]
    if incident and incident.get("equipment_id") == evidence.equipment_id:
        observations, cause, risk = _incident_sections(incident)
        body = [
            "- 관측 내용\n" + "\n".join(f"  - {item}" for item in observations),
            f"- 원인 · {cause}",
            f"- 잔여 위험 · {risk}",
        ]
        links = [
            {"title": "이상 사건 상세", "href": f"/incidents/{incident['incident_id']}"},
            *links,
        ]
    sections = [
        f"**{subject} 정비 보고서 초안 · 검토용**",
        "\n".join([*body, "- 현장 조치 및 결과 · 담당자 입력 필요"]),
        "**참고 자료**\n\n" + ("\n".join(lines) if lines else "연결된 점검 자료 없음"),
    ]
    return "\n\n".join(sections), links
