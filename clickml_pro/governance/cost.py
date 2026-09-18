"""
Per-job cost estimation before launch.

Estimates GPU hours and dollar cost BEFORE a training job runs, allowing
teams to make informed decisions and respect budget limits.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── GPU pricing (approximate, on-demand, per GPU-hour) ──────────────────

GPU_PRICING: dict[str, float] = {
    "a100-80gb": 3.50,
    "a100-40gb": 2.50,
    "h100": 5.00,
    "a10g": 1.20,
    "l4": 0.80,
    "t4": 0.50,
    "v100": 1.00,
    "rtx-4090": 0.60,
    "cpu": 0.10,
}

# ── Model size heuristics (approximate params → GB) ─────────────────────

MODEL_SIZE_ESTIMATES: dict[str, dict[str, float]] = {
    # model_name_pattern: {param_count_billions, memory_gb_fp16}
    "7b": {"params_b": 7, "memory_gb_fp16": 14},
    "8b": {"params_b": 8, "memory_gb_fp16": 16},
    "13b": {"params_b": 13, "memory_gb_fp16": 26},
    "30b": {"params_b": 30, "memory_gb_fp16": 60},
    "70b": {"params_b": 70, "memory_gb_fp16": 140},
}


class CostEstimate(BaseModel):
    """Result of a cost estimation."""

    gpu_type: str = "a100-80gb"
    num_gpus: int = 1
    gpu_hours: float = 0.0
    cost_usd: float = 0.0
    budget_limit: float = 0.0
    budget_remaining: float = 0.0
    within_budget: bool = True
    breakdown: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CostEstimator:
    """Estimate the cost of a training job before execution."""

    def __init__(self, budget_limit: float | None = None, spent: float = 0.0) -> None:
        from clickml_pro.config.settings import get_settings

        settings = get_settings()
        self.budget_limit = budget_limit or settings.budget_limit_usd
        self.spent = spent

    def estimate(self, config: dict[str, Any]) -> CostEstimate:
        """Estimate cost for a job config."""
        job_type = config.get("type", "training")

        if job_type == "training":
            return self._estimate_training(config)
        elif job_type == "quantization":
            return self._estimate_quantization(config)
        elif job_type == "data_pipeline":
            return self._estimate_data_pipeline(config)
        else:
            return CostEstimate(
                warnings=[f"No cost model for job type: {job_type}"]
            )

    def _estimate_training(self, config: dict[str, Any]) -> CostEstimate:
        """Estimate training cost based on model size, data, and epochs."""
        training = config.get("training", {})
        base_model = config.get("base_model", "").lower()
        mode = config.get("mode", "finetune")
        epochs = training.get("epochs", 3)
        batch_size = training.get("batch_size", 4)

        # Estimate model size
        model_info = self._detect_model_size(base_model)
        params_b = model_info["params_b"]
        mem_gb = model_info["memory_gb_fp16"]

        # GPU selection heuristic
        if mem_gb > 60:
            gpu_type, num_gpus = "h100", max(2, int(mem_gb / 70) + 1)
        elif mem_gb > 30:
            gpu_type, num_gpus = "a100-80gb", max(1, int(mem_gb / 70) + 1)
        elif mem_gb > 16:
            gpu_type, num_gpus = "a100-40gb", 1
        else:
            gpu_type, num_gpus = "a10g", 1

        # PEFT is ~60% cheaper (fewer FLOPs)
        peft_discount = 0.4 if mode in ("lora", "peft", "adapter", "sft") else 1.0

        # Rough: ~1 GPU-hour per 1B params per epoch (very approximate)
        gpu_hours = params_b * epochs * peft_discount * num_gpus
        # Batch size scaling
        gpu_hours *= max(1, 4 / batch_size)

        cost_per_hour = GPU_PRICING.get(gpu_type, 2.0)
        cost_usd = gpu_hours * cost_per_hour

        remaining = self.budget_limit - self.spent
        within_budget = cost_usd <= remaining

        warnings = []
        if not within_budget:
            warnings.append(
                f"Estimated cost (${cost_usd:.2f}) exceeds remaining budget (${remaining:.2f})"
            )
        if mem_gb > 160:
            warnings.append("Very large model — consider quantized training (QLoRA)")

        return CostEstimate(
            gpu_type=gpu_type,
            num_gpus=num_gpus,
            gpu_hours=round(gpu_hours, 1),
            cost_usd=round(cost_usd, 2),
            budget_limit=self.budget_limit,
            budget_remaining=round(remaining, 2),
            within_budget=within_budget,
            breakdown={
                "model_params_b": params_b,
                "model_memory_gb_fp16": mem_gb,
                "epochs": epochs,
                "batch_size": batch_size,
                "mode": mode,
                "peft_discount": peft_discount,
                "cost_per_gpu_hour": cost_per_hour,
            },
            warnings=warnings,
        )

    def _estimate_quantization(self, config: dict[str, Any]) -> CostEstimate:
        """Quantization is typically cheap — a few GPU-hours at most."""
        gpu_hours = 2.0  # Rough estimate
        cost_usd = gpu_hours * GPU_PRICING.get("a10g", 1.20)
        remaining = self.budget_limit - self.spent

        return CostEstimate(
            gpu_type="a10g",
            gpu_hours=gpu_hours,
            cost_usd=round(cost_usd, 2),
            budget_limit=self.budget_limit,
            budget_remaining=round(remaining, 2),
            within_budget=cost_usd <= remaining,
        )

    def _estimate_data_pipeline(self, config: dict[str, Any]) -> CostEstimate:
        """Data pipelines are CPU-bound — very cheap."""
        gpu_hours = 0.5
        cost_usd = gpu_hours * GPU_PRICING.get("cpu", 0.10)
        remaining = self.budget_limit - self.spent

        return CostEstimate(
            gpu_type="cpu",
            gpu_hours=gpu_hours,
            cost_usd=round(cost_usd, 2),
            budget_limit=self.budget_limit,
            budget_remaining=round(remaining, 2),
            within_budget=True,
        )

    def _detect_model_size(self, model_name: str) -> dict[str, float]:
        """Heuristically detect model size from the name."""
        for key, info in MODEL_SIZE_ESTIMATES.items():
            if key in model_name:
                return info

        # Default: assume ~7B if unknown
        return {"params_b": 7, "memory_gb_fp16": 14}
