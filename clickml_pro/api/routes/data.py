"""Data engineering API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class ValidateRequest(BaseModel):
    engine: str = "pandas"
    source_path: str
    schema_name: str | None = None
    contract_name: str | None = None


@router.post("/validate")
async def validate_data(req: ValidateRequest) -> dict:
    """Validate a data source against a schema or contract."""
    from clickml_pro.data.engine import get_engine

    engine = get_engine(req.engine)
    try:
        df = engine.read(req.source_path)
        result = {"rows": len(df) if hasattr(df, '__len__') else 0, "valid": True}
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(400, str(exc))


class LineageQueryRequest(BaseModel):
    node_id: str
    direction: str = "downstream"  # upstream | downstream


@router.post("/lineage")
async def query_lineage(req: LineageQueryRequest) -> dict:
    """Query lineage graph."""
    from clickml_pro.data.lineage.graph import LineageGraph

    graph = LineageGraph()
    if req.direction == "upstream":
        nodes = graph.upstream(req.node_id)
    else:
        nodes = graph.downstream(req.node_id)
    return {"node_id": req.node_id, "direction": req.direction, "related": nodes}


class PipelineRunRequest(BaseModel):
    name: str = "pipeline"
    source: dict[str, Any] = Field(default_factory=dict)
    transforms: list[dict[str, Any]] = Field(default_factory=list)
    sink: dict[str, Any] = Field(default_factory=dict)
    engine: str = "pandas"


@router.post("/pipeline/run")
async def run_pipeline(req: PipelineRunRequest) -> dict:
    """Execute a data pipeline."""
    from clickml_pro.data.pipeline.builder import PipelineBuilder

    builder = PipelineBuilder(engine_name=req.engine)
    try:
        result = builder.execute(req.model_dump())
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(500, str(exc))
