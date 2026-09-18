"""
Training job abstraction models — shared types for all training modes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class TrainingResult(BaseModel):
    """Returned by every training handler after a run."""

    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    checkpoint_path: str | None = None
    model_path: str | None = None


class TrainingProgress(BaseModel):
    """Real-time progress update emitted during training."""

    epoch: int = 0
    step: int = 0
    total_steps: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0
    elapsed_seconds: float = 0.0
    throughput_samples_per_sec: float = 0.0
    gpu_memory_used_mb: float = 0.0
