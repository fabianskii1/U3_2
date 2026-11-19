"""LangGraph agent for resolving one equipment name to its canonical ID."""

import re
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.equipment_lookup.model import EquipmentModel, ModelChoice, OpenAIEquipmentModel
from app.knowledge.equipment_catalog import EquipmentCatalog, Match, normalize_name

AGENT_NAME = "find-equipment-id-agent"
Status = Literal["found", "not_found", "ambiguous"]
EQUIPMENT_KIND = re.compile(r"(?:펌프|압축기|송풍기|터빈|모터)$")
GENERIC_WORDS = re.compile(r"(?:설비|장비|정보|현황|상태|요청|조회|목록|종류|관련|확인|보기|보여줘|알려줘)*")


class Candidate(TypedDict):
    equipment_id: str
    equipment_name: str
    source: str


class AgentResult(TypedDict):
    agent: str
    status: Status
    equipment_id: str | None
    equipment_name: str | None
    matched_name: str | None
    match_type: str | None
    candidates: list[Candidate]
    source: str | None


class AgentState(TypedDict, total=False):
    input_name: str
    normalized_name: str
    matches: tuple[Match, ...]
    model_choice: ModelChoice
    result: AgentResult


def _can_use_model(query: str, catalog: EquipmentCatalog) -> bool:
    if not catalog.equipment:
        return False
    if kind := EQUIPMENT_KIND.search(query):
        return GENERIC_WORDS.fullmatch(query[: kind.start()]) is None
    return catalog.has_similar_name(query)


def build_agent(catalog: EquipmentCatalog, model: EquipmentModel | None = None):
    def normalize(state: AgentState) -> AgentState:
        return {"normalized_name": normalize_name(state["input_name"])}

    def lookup(state: AgentState) -> AgentState:
        return {"matches": catalog.find(state["normalized_name"])}

    def model_lookup(state: AgentState) -> AgentState:
        if state["matches"] or not _can_use_model(state["normalized_name"], catalog):
            return {}
        choice = (model or OpenAIEquipmentModel.from_env()).choose(
            state["input_name"], catalog.equipment
        )
        return {"model_choice": choice}

    def resolve(state: AgentState) -> AgentState:
        matches = state["matches"]
        if len(matches) == 1:
            match = matches[0]
            item = match.equipment
            result: AgentResult = {
                "agent": AGENT_NAME,
                "status": "found",
                "equipment_id": item.equipment_id,
                "equipment_name": item.equipment_name,
                "matched_name": match.matched_name,
                "match_type": match.match_type,
                "candidates": [],
                "source": item.source,
            }
        elif not matches and "model_choice" in state:
            result = _model_result(state["model_choice"], catalog, state["input_name"])
        else:
            result = {
                "agent": AGENT_NAME,
                "status": "ambiguous" if matches else "not_found",
                "equipment_id": None,
                "equipment_name": None,
                "matched_name": None,
                "match_type": None,
                "candidates": [
                    {
                        "equipment_id": match.equipment.equipment_id,
                        "equipment_name": match.equipment.equipment_name,
                        "source": match.equipment.source,
                    }
                    for match in matches
                ],
                "source": None,
            }
        return {"result": result}

    graph = StateGraph(AgentState)
    graph.add_node("normalize", normalize)
    graph.add_node("lookup", lookup)
    graph.add_node("model_lookup", model_lookup)
    graph.add_node("resolve", resolve)
    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "lookup")
    graph.add_edge("lookup", "model_lookup")
    graph.add_edge("model_lookup", "resolve")
    graph.add_edge("resolve", END)
    return graph.compile()


def _model_result(choice: ModelChoice, catalog: EquipmentCatalog, input_name: str) -> AgentResult:
    by_id = {item.equipment_id: item for item in catalog.equipment}
    if choice.status == "found" and choice.equipment_id in by_id and choice.matched_name:
        item = by_id[choice.equipment_id]
        allowed_names = (item.equipment_name, *item.aliases)
        if any(normalize_name(choice.matched_name) == normalize_name(n) for n in allowed_names):
            return {
                "agent": AGENT_NAME,
                "status": "found",
                "equipment_id": item.equipment_id,
                "equipment_name": item.equipment_name,
                "matched_name": choice.matched_name,
                "match_type": "model",
                "candidates": [],
                "source": item.source,
            }
    if choice.status == "ambiguous":
        ids = list(dict.fromkeys(code for code in choice.candidate_ids if code in by_id))
        if len(ids) >= 2:
            return {
                "agent": AGENT_NAME,
                "status": "ambiguous",
                "equipment_id": None,
                "equipment_name": None,
                "matched_name": None,
                "match_type": "model",
                "candidates": [
                    {"equipment_id": code, "equipment_name": by_id[code].equipment_name,
                     "source": by_id[code].source}
                    for code in ids
                ],
                "source": None,
            }
    ids = list(dict.fromkeys(code for code in choice.candidate_ids if code in by_id))[:3]
    if not ids:
        ids = [item.equipment_id for item in catalog.rank(input_name)]
    return {
        "agent": AGENT_NAME,
        "status": "not_found",
        "equipment_id": None,
        "equipment_name": None,
        "matched_name": None,
        "match_type": "model",
        "candidates": [
            {
                "equipment_id": code,
                "equipment_name": by_id[code].equipment_name,
                "source": by_id[code].source,
            }
            for code in ids
        ],
        "source": None,
    }


def find_equipment_id(
    name: str, catalog: EquipmentCatalog, model: EquipmentModel | None = None
) -> AgentResult:
    graph = build_agent(catalog, model)
    return graph.invoke({"input_name": name})["result"]
