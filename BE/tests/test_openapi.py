from app.main import app


def test_openapi_groups_every_endpoint_by_domain():
    schema = app.openapi()
    expected = {
        "/api/hierarchy": "계층",
        "/api/equipment/{equipment_id}": "설비",
        "/api/trend": "시계열",
        "/api/alarms/history": "알람",
        "/api/error-types": "고장·정비 이력",
        "/api/error-histories": "고장·정비 이력",
        "/api/maintenance-histories": "고장·정비 이력",
        "/api/reports": "보고서",
        "/api/reports/{report_id}": "보고서",
        "/api/equipment/{equipment_id}/manuals": "매뉴얼",
        "/api/chat/sessions": "채팅",
        "/api/chat/sessions/{session_id}/messages": "채팅",
        "/api/chat/stream": "채팅",
        "/health": "운영 상태",
    }
    assert set(schema["paths"]) == set(expected)
    for path, tag in expected.items():
        method = "post" if path in {"/api/chat/sessions", "/api/chat/stream"} else "get"
        assert schema["paths"][path][method]["tags"] == [tag]
    assert [tag["name"] for tag in schema["tags"]] == list(dict.fromkeys(expected.values()))
