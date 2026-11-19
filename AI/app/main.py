"""Internal HTTP entry point for the equipment ID agent."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.equipment_lookup.agent import AgentResult, build_agent
from app.agents.equipment_lookup.model import EquipmentModel, ModelUnavailableError
from app.knowledge.equipment_catalog import EquipmentCatalog


class EquipmentCandidate(BaseModel):
    equipment_id: str = Field(min_length=1, max_length=30)
    equipment_name: str = Field(min_length=1, max_length=200)
    aliases: list[str]


class FindEquipmentRequest(BaseModel):
    equipment_name: str = Field(min_length=1, max_length=200)
    candidates: list[EquipmentCandidate]


def create_app(model: EquipmentModel | None = None) -> FastAPI:
    app = FastAPI(title="SKADI AI", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agents/find-equipment-id/invoke")
    def invoke(request: FindEquipmentRequest) -> AgentResult:
        try:
            catalog = EquipmentCatalog.from_candidates(
                [candidate.model_dump() for candidate in request.candidates]
            )
            graph = build_agent(catalog, model)
            return graph.invoke({"input_name": request.equipment_name})["result"]
        except ModelUnavailableError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


app = create_app()
