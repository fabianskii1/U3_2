"""SA-03 draft generation from a verified alarm and inspection evidence."""

from collections.abc import Mapping

from skadi_agents.inspection_evidence import InspectionEvidence, format_sources, markdown_text


def build_maintenance_draft(
    equipment_name: str,
    evidence: InspectionEvidence,
    *,
    alarm: Mapping[str, object] | None = None,
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
    sections = [
        f"**{subject} 정비 보고서 초안 · 검토용**",
        "\n".join(
            [
                f"- 관측 내용 · {observation}",
                "- 원인 · 확인 대기",
                "- 현장 조치 및 결과 · 담당자 입력 필요",
            ]
        ),
        "**참고 자료**\n\n" + ("\n".join(lines) if lines else "연결된 점검 자료 없음"),
    ]
    return "\n\n".join(sections), links
