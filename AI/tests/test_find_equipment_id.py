from fastapi.testclient import TestClient
from httpx import Request, Response
from openai import AuthenticationError

from app.agents.equipment_lookup.agent import find_equipment_id
from app.agents.equipment_lookup.model import ModelChoice, ModelUnavailableError, _model_error
from app.knowledge.equipment_catalog import Equipment, EquipmentCatalog
from app.main import create_app

EQUIPMENT = [
    {"equipment_id": "P1", "equipment_name": "원유 공급 펌프", "aliases": ["원유 펌프"]},
    {
        "equipment_id": "P2",
        "equipment_name": "나프타 제품 이송 펌프",
        "aliases": ["납사 이송 펌프", "P2 펌프"],
    },
    {"equipment_id": "P3", "equipment_name": "등유 측류 이송 펌프", "aliases": []},
    {"equipment_id": "P4", "equipment_name": "경유 측류 이송 펌프", "aliases": []},
    {
        "equipment_id": "P5",
        "equipment_name": "펌프어라운드 순환 펌프",
        "aliases": ["중질유 이송 펌프"],
    },
    {"equipment_id": "P6", "equipment_name": "상압잔사유 이송 펌프", "aliases": []},
]


def catalog():
    return EquipmentCatalog.from_candidates(EQUIPMENT)


class StubModel:
    def __init__(self, choice: ModelChoice):
        self.choice = choice
        self.calls = 0

    def choose(self, name, equipment):
        self.calls += 1
        return self.choice


def test_every_database_name_and_alias_resolves_to_its_equipment_id():
    items = catalog()
    model = StubModel(
        ModelChoice(status="not_found", equipment_id=None, matched_name=None, candidate_ids=[])
    )
    assert len(items.equipment) == 6
    for item in items.equipment:
        for name in (item.equipment_id, item.equipment_name, *item.aliases):
            result = find_equipment_id(name, items, model)
            assert result["status"] == "found"
            assert result["equipment_id"] == item.equipment_id
            assert result["source"] == item.source
    assert model.calls == 0


def test_normalization_and_unknown_name():
    assert find_equipment_id("  Ｐ２  펌프  ", catalog())["equipment_id"] == "P2"
    model = StubModel(
        ModelChoice(status="not_found", equipment_id=None, matched_name=None, candidate_ids=[])
    )
    result = find_equipment_id("존재하지 않는 펌프", catalog(), model=model)
    assert result["status"] == "not_found"
    assert result["equipment_id"] is None
    assert len(result["candidates"]) == 3
    assert model.calls == 1


def test_non_equipment_and_vague_names_skip_model():
    model = StubModel(
        ModelChoice(status="not_found", equipment_id=None, matched_name=None, candidate_ids=[])
    )
    items = catalog()
    for name in (
        "",
        "  ",
        "오늘 날씨 정보",
        "요청",
        "뉴스를 알려줘",
        "펌프 관련 정보",
        "펌프 색은 뭐야",
        "울산 clx",
    ):
        result = find_equipment_id(name, items, model)
        assert result["status"] == "not_found", name
        assert result["candidates"] == [], name
        assert result["match_type"] is None, name
    assert model.calls == 0


def test_not_found_candidates_keep_model_ranking_or_use_catalog_similarity():
    model = StubModel(
        ModelChoice(
            status="not_found",
            equipment_id=None,
            matched_name=None,
            candidate_ids=["P5", "P1", "P99", "P5"],
        )
    )
    result = find_equipment_id("열교환기 공급 펌프", catalog(), model=model)
    assert [item["equipment_id"] for item in result["candidates"]] == ["P5", "P1"]

    model.choice = ModelChoice(
        status="not_found", equipment_id=None, matched_name=None, candidate_ids=[]
    )
    result = find_equipment_id("열교환기 공급 펌프", catalog(), model=model)
    assert result["candidates"][0]["equipment_id"] == "P1"


def test_similar_name_uses_model_but_rejects_unlisted_identity():
    model = StubModel(
        ModelChoice(
            status="found", equipment_id="P2", matched_name="납사 이송 펌프", candidate_ids=[]
        )
    )
    result = find_equipment_id("납사 이송 뻠프", catalog(), model=model)
    assert result["equipment_id"] == "P2"
    assert result["match_type"] == "model"
    assert model.calls == 1

    model.choice = ModelChoice(
        status="found", equipment_id="P99", matched_name="없는 펌프", candidate_ids=[]
    )
    result = find_equipment_id("상상 펌프", catalog(), model=model)
    assert result["status"] == "not_found"
    assert result["equipment_id"] is None


def test_conflicting_alias_returns_candidates_instead_of_guessing():
    catalog = EquipmentCatalog(
        (
            Equipment("P1", "첫 번째", ("공통 펌프",), "database"),
            Equipment("P2", "두 번째", ("공통 펌프",), "database"),
        )
    )
    result = find_equipment_id("공통 펌프", catalog)
    assert result["status"] == "ambiguous"
    assert result["equipment_id"] is None
    assert [item["equipment_id"] for item in result["candidates"]] == ["P1", "P2"]


def test_http_contract():
    client = TestClient(create_app())
    response = client.post(
        "/agents/find-equipment-id/invoke",
        json={"equipment_name": "중질유 이송 펌프", "candidates": EQUIPMENT},
    )
    assert response.status_code == 200
    assert response.json()["equipment_id"] == "P5"
    assert response.json()["match_type"] == "alias"
    assert (
        client.post("/agents/find-equipment-id/invoke", json={"equipment_name": ""}).status_code
        == 422
    )


def test_model_unavailable_is_http_503():
    class FailedModel:
        def choose(self, name, equipment):
            raise ModelUnavailableError("모델 호출 실패")

    client = TestClient(create_app(model=FailedModel()))
    response = client.post(
        "/agents/find-equipment-id/invoke",
        json={"equipment_name": "열교환기 공급 펌프", "candidates": EQUIPMENT},
    )
    assert response.status_code == 503


def test_openai_authentication_failure_has_diagnostic_code():
    request = Request("POST", "https://api.openai.com/v1/responses")
    upstream = Response(401, request=request)

    class FailedModel:
        def choose(self, name, equipment):
            raise _model_error(AuthenticationError("invalid key", response=upstream, body=None))

    client = TestClient(create_app(model=FailedModel()))
    response = client.post(
        "/agents/find-equipment-id/invoke",
        json={"equipment_name": "열교환기 공급 펌프", "candidates": EQUIPMENT},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "OPENAI_AUTHENTICATION_FAILED"
    assert "invalid key" not in response.text
