from app.modules.chat.evidence import (
    InspectionEvidence,
    build_maintenance_draft,
    format_inspection_evidence,
)


def test_evidence_keeps_source_ids_and_only_links_supported_destinations():
    evidence = InspectionEvidence(
        equipment_id="P2",
        manuals=[
            {
                "equipment_manual_id": "1",
                "equipment_manual_title": "펌프 매뉴얼 [설치]",
                "equipment_manual_link": "https://manual.example/pump(section)",
            },
            {
                "equipment_manual_id": "2",
                "equipment_manual_title": "구버전 매뉴얼",
                "equipment_manual_link": "javascript:alert(1)",
            },
        ],
        reports=[{"report_id": "8", "title": "이전 정비", "version": 3}],
        maintenance=[],
    )

    message, links = format_inspection_evidence("나프타 제품 이송 펌프", evidence)

    assert r"[펌프 매뉴얼 \[설치\]](<https://manual.example/pump(section)>)" in message
    assert "구버전 매뉴얼" in message
    assert "javascript:" not in message
    assert "버전 3" in message
    assert links == [{"title": "보고서 8 열기", "href": "/reports/8"}]


def test_maintenance_draft_includes_only_same_equipment_alarm_observations():
    evidence = InspectionEvidence("P2", [], [], [])
    alarm = {
        "alarm_id": "3",
        "equipment_id": "P2",
        "sensor_id": "10-VT-1205",
        "alarm_start_time": "2026-11-18T00:00:00+00:00",
        "unit": "mm/s",
        "cof_score": 0,
    }

    matching, _ = build_maintenance_draft("나프타 제품 이송 펌프", evidence, alarm=alarm)
    foreign, _ = build_maintenance_draft(
        "나프타 제품 이송 펌프", evidence, alarm={**alarm, "equipment_id": "P3"}
    )

    assert "센서 10-VT-1205 · CoF 0" in matching
    assert "원인 · 확인 대기" in matching
    assert "연결된 알람 관측값 없음" in foreign
    assert "CoF 0" not in foreign
