"""Model Registry API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


def _get_registry():
    from clickml_pro.registry.model_registry import ModelRegistry
    return ModelRegistry()


class RegisterRequest(BaseModel):
    name: str
    description: str = ""
    framework: str = "pytorch"
    base_model: str = ""
    tags: list[str] = Field(default_factory=list)
    artifact_path: str = ""
    owner: str = ""


@router.post("/register")
async def register_model(req: RegisterRequest) -> dict:
    from clickml_pro.registry.model_registry import (
        RegisteredModel, ModelLineage, ModelArtifact,
    )

    registry = _get_registry()

    lineage = ModelLineage(base_model=req.base_model)
    artifacts = []
    if req.artifact_path:
        artifacts.append(ModelArtifact(path=req.artifact_path))

    model = RegisteredModel(
        name=req.name,
        description=req.description,
        lineage=lineage,
        artifacts=artifacts,
        tags=req.tags,
        owner=req.owner,
        metadata={"framework": req.framework},
    )

    entry = registry.register(model)
    return {"status": "registered", "entry": entry.model_dump()}


@router.get("/list")
async def list_models() -> dict:
    registry = _get_registry()
    models = registry.list_models()
    return {"models": [m.model_dump() for m in models]}


@router.get("/info/{name}")
async def model_info(name: str) -> dict:
    registry = _get_registry()
    model = registry.get_model(name)
    if model is None:
        raise HTTPException(404, f"Model '{name}' not found")
    return {"model": name, "entry": model.model_dump()}


@router.post("/promote/{name}/{version}")
async def promote_model(name: str, version: int, stage: str = "staging") -> dict:
    from clickml_pro.registry.model_registry import ModelStatus

    status_map: dict[str, ModelStatus] = {
        "staging": ModelStatus.STAGING,
        "production": ModelStatus.PRODUCTION,
        "archived": ModelStatus.ARCHIVED,
        "deprecated": ModelStatus.DEPRECATED,
    }
    target = status_map.get(stage.lower())
    if target is None:
        raise HTTPException(400, f"Invalid stage: {stage}. Must be one of: {', '.join(status_map)}")

    registry = _get_registry()
    ok = registry.promote(name, version, target)
    if not ok:
        raise HTTPException(404, "Model/version not found")
    return {"status": "promoted", "name": name, "version": version, "stage": stage}
