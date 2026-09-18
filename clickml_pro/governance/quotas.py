"""
GPU quota enforcement per organisation / team.

Prevents any single team from monopolising shared GPU resources by
tracking and enforcing per-org GPU-hour quotas.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QuotaEntry(BaseModel):
    """Snapshot of a single organisation's GPU hours."""

    org_id: str
    gpu_hours_limit: float = 100.0
    gpu_hours_used: float = 0.0
    active_jobs: int = 0
    max_concurrent_jobs: int = 4
    reset_epoch: float = 0.0  # Next reset timestamp


class QuotaManager:
    """Manage GPU quotas for organisations."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            from clickml_pro.config.settings import get_settings
            storage_dir = Path(get_settings().data_dir) / "governance" / "quotas"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._quotas: dict[str, QuotaEntry] = {}
        self._load()

    # ── public API ──────────────────────────────────────────────────────

    def set_quota(
        self,
        org_id: str,
        gpu_hours_limit: float = 100.0,
        max_concurrent_jobs: int = 4,
        reset_interval_hours: float = 720,  # ~30 days
    ) -> QuotaEntry:
        """Create or update quota for an organisation."""
        existing = self._quotas.get(org_id)
        entry = QuotaEntry(
            org_id=org_id,
            gpu_hours_limit=gpu_hours_limit,
            gpu_hours_used=existing.gpu_hours_used if existing else 0.0,
            active_jobs=existing.active_jobs if existing else 0,
            max_concurrent_jobs=max_concurrent_jobs,
            reset_epoch=time.time() + reset_interval_hours * 3600,
        )
        self._quotas[org_id] = entry
        self._save()
        logger.info("Quota set for org=%s  limit=%.1f h", org_id, gpu_hours_limit)
        return entry

    def check_quota(self, org_id: str, requested_hours: float = 0.0) -> dict[str, Any]:
        """Check whether an org can launch a job.

        Returns dict with keys: allowed, reason, remaining_hours.
        """
        entry = self._quotas.get(org_id)
        if entry is None:
            return {
                "allowed": False,
                "reason": f"No quota defined for org '{org_id}'",
                "remaining_hours": 0.0,
            }

        self._maybe_reset(entry)

        remaining = entry.gpu_hours_limit - entry.gpu_hours_used
        if requested_hours > remaining:
            return {
                "allowed": False,
                "reason": (
                    f"Requested {requested_hours:.1f} h exceeds remaining "
                    f"{remaining:.1f} h for org '{org_id}'"
                ),
                "remaining_hours": remaining,
            }

        if entry.active_jobs >= entry.max_concurrent_jobs:
            return {
                "allowed": False,
                "reason": (
                    f"Org '{org_id}' already has {entry.active_jobs} active jobs "
                    f"(max {entry.max_concurrent_jobs})"
                ),
                "remaining_hours": remaining,
            }

        return {"allowed": True, "reason": "OK", "remaining_hours": remaining}

    def record_usage(self, org_id: str, gpu_hours: float) -> None:
        """Record GPU hours consumed by a completed (or running) job."""
        entry = self._quotas.get(org_id)
        if entry is None:
            logger.warning("record_usage called for unknown org '%s'", org_id)
            return
        entry.gpu_hours_used += gpu_hours
        self._save()

    def job_started(self, org_id: str) -> None:
        entry = self._quotas.get(org_id)
        if entry:
            entry.active_jobs += 1
            self._save()

    def job_finished(self, org_id: str) -> None:
        entry = self._quotas.get(org_id)
        if entry:
            entry.active_jobs = max(0, entry.active_jobs - 1)
            self._save()

    def get_quota(self, org_id: str) -> QuotaEntry | None:
        entry = self._quotas.get(org_id)
        if entry:
            self._maybe_reset(entry)
        return entry

    def list_quotas(self) -> list[QuotaEntry]:
        for e in self._quotas.values():
            self._maybe_reset(e)
        return list(self._quotas.values())

    # ── internals ───────────────────────────────────────────────────────

    def _maybe_reset(self, entry: QuotaEntry) -> None:
        """Auto-reset usage when the billing cycle rolls over."""
        if time.time() >= entry.reset_epoch and entry.reset_epoch > 0:
            logger.info("Resetting quota for org=%s (cycle ended)", entry.org_id)
            entry.gpu_hours_used = 0.0
            entry.active_jobs = 0
            entry.reset_epoch = time.time() + 720 * 3600  # next 30 days
            self._save()

    def _save(self) -> None:
        path = self.storage_dir / "quotas.json"
        data = {k: v.model_dump() for k, v in self._quotas.items()}
        path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        path = self.storage_dir / "quotas.json"
        if path.exists():
            raw = json.loads(path.read_text())
            self._quotas = {k: QuotaEntry(**v) for k, v in raw.items()}
