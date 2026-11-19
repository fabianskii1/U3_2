"""SA-02 evidence types and presentation for verified inspection records."""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class InspectionEvidence:
    equipment_id: str
    manuals: list[dict[str, Any]]
    reports: list[dict[str, Any]]
    maintenance: list[dict[str, Any]]


def markdown_text(value: object) -> str:
    text = " ".join(str(value).split())
    return re.sub(r"([\\`*_\[\]{}()<>#!|])", r"\\\1", text)


def _manual_url(url: str) -> str | None:
    if any(char.isspace() or ord(char) < 32 or char in "\\<>" for char in url):
        return None
    try:
        parts = urlsplit(url)
        if parts.scheme in {"http", "https"} and parts.hostname and parts.username is None:
            return url
    except ValueError:
        return None
    return None


def format_sources(evidence: InspectionEvidence) -> tuple[list[str], list[dict[str, str]]]:
    lines = []
    links = []
    for manual in evidence.manuals:
        title = markdown_text(manual["equipment_manual_title"])
        url = _manual_url(manual["equipment_manual_link"])
        label = f"[{title}](<{url}>)" if url else title
        lines.append(f"- 매뉴얼 {manual['equipment_manual_id']} · {label}")
    for prior in evidence.reports:
        title = markdown_text(prior["title"])
        report_id = prior["report_id"]
        lines.append(f"- 저장된 보고서 {report_id} · {title} · 버전 {prior['version']}")
        links.append({"title": f"보고서 {report_id} 열기", "href": f"/reports/{report_id}"})
    for history in evidence.maintenance:
        started_at = history["start_time"]
        ended_at = history["end_time"] or "종료 시각 기록 없음"
        lines.append(f"- 정비 이력 {history['maintenance_history_id']} · {started_at} ~ {ended_at}")
    return lines, links


def format_inspection_evidence(
    equipment_name: str, evidence: InspectionEvidence
) -> tuple[str, list[dict[str, str]]]:
    lines, links = format_sources(evidence)
    subject = f"{markdown_text(equipment_name)} ({markdown_text(evidence.equipment_id)})"
    if not lines:
        return f"{subject}에 연결된 매뉴얼, 저장된 보고서, 정비 이력을 찾지 못했습니다.", []
    return "\n\n".join([f"**{subject}의 등록된 점검 자료**", "\n".join(lines)]), links
