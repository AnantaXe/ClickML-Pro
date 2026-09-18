"""Governance API routes — cost estimation, budgets, quotas, policies."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ── Cost ────────────────────────────────────────────────────────────────

class CostEstimateRequest(BaseModel):
    type: str = "training"
    base_model: str = ""
    mode: str = "finetune"
    training: dict[str, Any] = Field(default_factory=lambda: {"epochs": 3, "batch_size": 4})


@router.post("/cost/estimate")
async def estimate_cost(req: CostEstimateRequest) -> dict:
    from clickml_pro.governance.cost import CostEstimator

    estimator = CostEstimator()
    estimate = estimator.estimate(req.model_dump())
    return estimate.model_dump()


# ── Budgets ─────────────────────────────────────────────────────────────

class SetBudgetRequest(BaseModel):
    entity_id: str
    limit_usd: float = 500.0
    entity_type: str = "org"
    period_days: float = 30.0


@router.post("/budget/set")
async def set_budget(req: SetBudgetRequest) -> dict:
    from clickml_pro.governance.budget import BudgetManager

    mgr = BudgetManager()
    record = mgr.set_budget(
        entity_id=req.entity_id,
        limit_usd=req.limit_usd,
        entity_type=req.entity_type,
        period_days=req.period_days,
    )
    return record.model_dump()


@router.get("/budget/{entity_id}")
async def get_budget(entity_id: str) -> dict:
    from clickml_pro.governance.budget import BudgetManager

    mgr = BudgetManager()
    summary = mgr.get_summary(entity_id)
    return summary


# ── Quotas ──────────────────────────────────────────────────────────────

class SetQuotaRequest(BaseModel):
    org_id: str
    gpu_hours_limit: float = 100.0
    max_concurrent_jobs: int = 4


@router.post("/quota/set")
async def set_quota(req: SetQuotaRequest) -> dict:
    from clickml_pro.governance.quotas import QuotaManager

    mgr = QuotaManager()
    entry = mgr.set_quota(
        org_id=req.org_id,
        gpu_hours_limit=req.gpu_hours_limit,
        max_concurrent_jobs=req.max_concurrent_jobs,
    )
    return entry.model_dump()


@router.get("/quota/{org_id}")
async def check_quota(org_id: str, hours: float = 0.0) -> dict:
    from clickml_pro.governance.quotas import QuotaManager

    mgr = QuotaManager()
    return mgr.check_quota(org_id, hours)


# ── Policies ────────────────────────────────────────────────────────────

@router.get("/policies")
async def list_policies() -> dict:
    from clickml_pro.governance.policies import PolicyEngine

    engine = PolicyEngine()
    policies = engine.list_policies()
    return {"policies": [p.model_dump() for p in policies]}
