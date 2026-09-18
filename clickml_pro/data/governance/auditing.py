"""
Dataset usage auditing — tracks who accessed what data, when, and why.

Compliance requirements demand a full audit trail of data access, schema
changes, and pipeline modifications.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEvent(BaseModel):
    """A single audit event."""

    event_id: str = ""
    event_type: str = ""       # data_access, schema_change, pipeline_deploy, model_train
    actor: str = ""            # user ID or service name
    resource: str = ""         # dataset, pipeline, or model identifier
    action: str = ""           # read, write, create, delete, modify
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ip_address: str = ""
    success: bool = True


class AuditLog:
    """
    Append-only audit log for data governance.

    All events are immutable and persisted to enable compliance reviews.
    """

    def __init__(self, storage_path: str | Path = "./audit_logs") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._events: list[AuditEvent] = []
        self._counter = 0

    def record(self, event: AuditEvent) -> AuditEvent:
        """Record an audit event (immutable — cannot be modified after recording)."""
        self._counter += 1
        event.event_id = f"audit-{self._counter:06d}"
        self._events.append(event)

        # Persist to daily log file
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.storage_path / f"{date_str}.jsonl"
        with log_file.open("a") as fh:
            fh.write(event.model_dump_json() + "\n")

        logger.debug(
            "Audit: %s %s %s on %s", event.actor, event.action, event.event_type, event.resource
        )
        return event

    def query(
        self,
        actor: str | None = None,
        resource: str | None = None,
        event_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query the audit log with filters."""
        results = self._events

        if actor:
            results = [e for e in results if e.actor == actor]
        if resource:
            results = [e for e in results if e.resource == resource]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]

        return results[-limit:]

    def get_resource_history(self, resource: str) -> list[AuditEvent]:
        """Get the full audit history for a specific resource."""
        return [e for e in self._events if e.resource == resource]

    def get_actor_history(self, actor: str) -> list[AuditEvent]:
        """Get the full audit history for a specific actor."""
        return [e for e in self._events if e.actor == actor]

    def export(self, path: str | Path | None = None) -> str:
        """Export the full audit log as JSON."""
        output = path or self.storage_path / "full_audit_export.json"
        output = Path(output)
        data = [e.model_dump() for e in self._events]
        output.write_text(json.dumps(data, indent=2))
        return str(output)
