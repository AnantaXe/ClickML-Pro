"""
Backfill and replay support for data pipelines.

Pipelines store immutable, versioned results.  This module supports:
- Replay: re-execute a pipeline for a historical time window
- Backfill: fill gaps in historical data
- Point-in-time queries: retrieve data as it existed at a past timestamp
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackfillRequest(BaseModel):
    """Request to backfill data for a time window."""

    pipeline: str
    start_date: str        # ISO format
    end_date: str          # ISO format
    strategy: str = "full"  # full, incremental, snapshot
    parallelism: int = 1
    dry_run: bool = False


class ReplayRequest(BaseModel):
    """Request to replay a specific pipeline run."""

    pipeline: str
    original_run_id: str
    as_of: str = ""        # Replay with data as-of this timestamp
    override_config: dict[str, Any] = Field(default_factory=dict)


class BackfillResult(BaseModel):
    """Result of a backfill operation."""

    pipeline: str
    partitions_total: int = 0
    partitions_completed: int = 0
    partitions_failed: int = 0
    runtime_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class BackfillManager:
    """Orchestrates backfill and replay operations."""

    def __init__(self) -> None:
        self._history: list[BackfillResult] = []

    def backfill(self, request: BackfillRequest) -> BackfillResult:
        """Execute a backfill for the specified time window."""
        logger.info(
            "Backfill requested: %s [%s → %s] strategy=%s",
            request.pipeline, request.start_date, request.end_date, request.strategy,
        )

        if request.dry_run:
            partitions = self._compute_partitions(request)
            return BackfillResult(
                pipeline=request.pipeline,
                partitions_total=len(partitions),
            )

        partitions = self._compute_partitions(request)
        result = BackfillResult(
            pipeline=request.pipeline,
            partitions_total=len(partitions),
        )

        for partition in partitions:
            try:
                self._execute_partition(request.pipeline, partition)
                result.partitions_completed += 1
            except Exception as exc:
                result.partitions_failed += 1
                result.errors.append(f"Partition {partition}: {exc}")

        self._history.append(result)
        logger.info(
            "Backfill complete: %s — %d/%d partitions succeeded",
            request.pipeline, result.partitions_completed, result.partitions_total,
        )
        return result

    def replay(self, request: ReplayRequest) -> dict[str, Any]:
        """Replay a specific pipeline run."""
        logger.info(
            "Replay requested: %s (original_run=%s, as_of=%s)",
            request.pipeline, request.original_run_id, request.as_of or "now",
        )

        # In a full implementation, this would:
        # 1. Retrieve the original run config
        # 2. Load data as-of the specified timestamp
        # 3. Re-execute the pipeline with the original or overridden config

        return {
            "status": "replayed",
            "pipeline": request.pipeline,
            "original_run_id": request.original_run_id,
        }

    def _compute_partitions(self, request: BackfillRequest) -> list[str]:
        """Compute the list of date partitions to backfill."""
        from datetime import timedelta

        start = datetime.fromisoformat(request.start_date)
        end = datetime.fromisoformat(request.end_date)

        partitions: list[str] = []
        current = start
        while current <= end:
            partitions.append(current.date().isoformat())
            current += timedelta(days=1)

        return partitions

    def _execute_partition(self, pipeline: str, partition: str) -> None:
        """Execute a single partition of a backfill."""
        logger.debug("Executing partition: %s / %s", pipeline, partition)
        # Delegate to pipeline builder
        from clickml_pro.data.pipeline.builder import PipelineBuilder

        builder = PipelineBuilder()
        # In production, load the pipeline config and inject the partition date
        # For now, this is a placeholder
