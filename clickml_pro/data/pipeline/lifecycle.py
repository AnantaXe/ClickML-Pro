"""
Pipeline lifecycle management.

Lifecycle states:
    draft → validate → deploy → running → retire

Every pipeline has a well-defined lifecycle with transitions, guards,
and audit logging.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PipelineState(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    RUNNING = "running"
    PAUSED = "paused"
    RETIRED = "retired"
    FAILED = "failed"


class DatasetState(str, Enum):
    CREATED = "created"
    EVOLVING = "evolving"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class JobRunState(str, Enum):
    TRIGGERED = "triggered"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    REPLAYING = "replaying"


# Valid transitions
PIPELINE_TRANSITIONS: dict[PipelineState, list[PipelineState]] = {
    PipelineState.DRAFT: [PipelineState.VALIDATED, PipelineState.RETIRED],
    PipelineState.VALIDATED: [PipelineState.DEPLOYED, PipelineState.DRAFT],
    PipelineState.DEPLOYED: [PipelineState.RUNNING, PipelineState.PAUSED, PipelineState.RETIRED],
    PipelineState.RUNNING: [PipelineState.PAUSED, PipelineState.FAILED, PipelineState.RETIRED],
    PipelineState.PAUSED: [PipelineState.RUNNING, PipelineState.RETIRED],
    PipelineState.FAILED: [PipelineState.DRAFT, PipelineState.RETIRED],
    PipelineState.RETIRED: [],
}

DATASET_TRANSITIONS: dict[DatasetState, list[DatasetState]] = {
    DatasetState.CREATED: [DatasetState.EVOLVING, DatasetState.STABLE],
    DatasetState.EVOLVING: [DatasetState.STABLE, DatasetState.DEPRECATED],
    DatasetState.STABLE: [DatasetState.EVOLVING, DatasetState.DEPRECATED],
    DatasetState.DEPRECATED: [DatasetState.RETIRED],
    DatasetState.RETIRED: [],
}


class LifecycleEvent(BaseModel):
    """Audit record of a lifecycle transition."""

    entity_type: str         # pipeline, dataset, job_run
    entity_id: str
    from_state: str
    to_state: str
    actor: str = ""
    reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LifecycleManager:
    """
    Manages lifecycle transitions for pipelines, datasets, and job runs.

    Enforces valid transitions and logs every state change.
    """

    def __init__(self) -> None:
        self._states: dict[str, str] = {}  # entity_id → current state
        self._audit_log: list[LifecycleEvent] = []

    def get_state(self, entity_id: str) -> str | None:
        return self._states.get(entity_id)

    def transition(
        self,
        entity_type: str,
        entity_id: str,
        to_state: str,
        actor: str = "",
        reason: str = "",
    ) -> LifecycleEvent:
        """Attempt a state transition. Raises ValueError if invalid."""
        from_state = self._states.get(entity_id, "unknown")

        # Determine valid transitions
        if entity_type == "pipeline":
            valid = PIPELINE_TRANSITIONS.get(PipelineState(from_state), [])
            if PipelineState(to_state) not in valid:
                raise ValueError(
                    f"Invalid pipeline transition: {from_state} → {to_state}. "
                    f"Valid: {[s.value for s in valid]}"
                )
        elif entity_type == "dataset":
            valid_ds = DATASET_TRANSITIONS.get(DatasetState(from_state), [])
            if DatasetState(to_state) not in valid_ds:
                raise ValueError(
                    f"Invalid dataset transition: {from_state} → {to_state}. "
                    f"Valid: {[s.value for s in valid_ds]}"
                )

        # Record transition
        event = LifecycleEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason=reason,
        )
        self._states[entity_id] = to_state
        self._audit_log.append(event)
        logger.info(
            "Lifecycle: %s '%s' %s → %s (by %s)",
            entity_type, entity_id, from_state, to_state, actor or "system",
        )
        return event

    def initialize(self, entity_id: str, initial_state: str) -> None:
        """Set the initial state for a new entity."""
        self._states[entity_id] = initial_state

    def get_audit_log(self, entity_id: str | None = None, limit: int = 100) -> list[LifecycleEvent]:
        if entity_id:
            return [e for e in self._audit_log if e.entity_id == entity_id][-limit:]
        return self._audit_log[-limit:]
