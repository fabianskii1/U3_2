import json
from types import SimpleNamespace

from test_find_equipment_id import EQUIPMENT

from app.agents.equipment_lookup import model as equipment_model
from app.agents.equipment_lookup.model import ModelChoice, OpenAIEquipmentModel
from app.knowledge.equipment_catalog import EquipmentCatalog


def test_model_reads_local_key_and_sends_only_candidate_names(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("api_key=test-key\nOPENAI_MODEL=gpt-4.1\n", encoding="utf-8")
    monkeypatch.setattr(equipment_model, "ENV_FILE", env_file)
    monkeypatch.setenv("OPENAI_API_KEY", "different-environment-key")
    monkeypatch.setenv("OPENAI_MODEL", "different-environment-model")
    calls = []

    class FakeResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=ModelChoice(
                    status="found",
                    equipment_id="P2",
                    matched_name="납사 이송 펌프",
                    candidate_ids=[],
                )
            )

    class FakeClient:
        responses = FakeResponses()

    def fake_openai(**kwargs):
        assert kwargs["api_key"] == "test-key"
        return FakeClient()

    monkeypatch.setattr(equipment_model, "OpenAI", fake_openai)
    resolver = OpenAIEquipmentModel.from_env()
    choice = resolver.choose(
        "납사 이송 뻠프", EquipmentCatalog.from_candidates(EQUIPMENT).equipment
    )

    assert choice.equipment_id == "P2"
    assert calls[0]["model"] == "gpt-4.1"
    assert calls[0]["store"] is False
    payload = json.loads(calls[0]["input"])
    assert payload["input_name"] == "납사 이송 뻠프"
    assert len(payload["candidates"]) == 6
    assert set(payload["candidates"][0]) == {"equipment_id", "name", "aliases"}
