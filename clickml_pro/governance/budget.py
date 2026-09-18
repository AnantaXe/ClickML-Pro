"""
Hard budget limits per team / project.

Tracks cumulative spending across jobs and blocks new launches once the
limit is reached.  Supports per-project and per-org budgets.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BudgetRecord(BaseModel):
    """Single budget entry."""

    entity_id: str  # org_id or project_id
    entity_type: str = "org"  # "org" | "project" | "user"
    limit_usd: float = 500.0
    spent_usd: float = 0.0
    currency: str = "USD"
    period_start: float = 0.0  # epoch
    period_end: float = 0.0  # epoch — 0 means no expiry
    charges: list[dict[str, Any]] = Field(default_factory=list)


class BudgetManager:
    """Enforce hard spending limits."""

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        if storage_dir is None:
            from clickml_pro.config.settings import get_settings
            storage_dir = Path(get_settings().data_dir) / "governance" / "budgets"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._budgets: dict[str, BudgetRecord] = {}
        self._load()

    # ── public API ──────────────────────────────────────────────────────

    def set_budget(
        self,
        entity_id: str,
        limit_usd: float,
        entity_type: str = "org",
        period_days: float = 30,
    ) -> BudgetRecord:
        """Create or update a budget."""
        now = time.time()
        existing = self._budgets.get(entity_id)

        record = BudgetRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            limit_usd=limit_usd,
            spent_usd=existing.spent_usd if existing else 0.0,
            period_start=now,
            period_end=now + period_days * 86400,
            charges=existing.charges if existing else [],
        )
        self._budgets[entity_id] = record
        self._save()
        logger.info("Budget set: %s → $%.2f (%s)", entity_id, limit_usd, entity_type)
        return record

    def check_budget(self, entity_id: str, estimated_cost: float = 0.0) -> dict[str, Any]:
        """Check if spending is within budget.

        Returns dict with keys: allowed, reason, remaining_usd, utilisation_pct.
        """
        record = self._budgets.get(entity_id)
        if record is None:
            return {
                "allowed": True,
                "reason": "No budget constraint defined — allowing by default",
                "remaining_usd": float("inf"),
                "utilisation_pct": 0.0,
            }

        self._maybe_reset(record)

        remaining = record.limit_usd - record.spent_usd
        utilisation = (record.spent_usd / record.limit_usd * 100) if record.limit_usd > 0 else 0.0

        if estimated_cost > remaining:
            return {
                "allowed": False,
                "reason": (
                    f"Estimated cost ${estimated_cost:.2f} exceeds remaining "
                    f"budget ${remaining:.2f} for {entity_id}"
                ),
                "remaining_usd": remaining,
                "utilisation_pct": utilisation,
            }

        return {
            "allowed": True,
            "reason": "OK",
            "remaining_usd": remaining,
            "utilisation_pct": utilisation,
        }

    def record_charge(
        self, entity_id: str, amount_usd: float, description: str = "", job_id: str = ""
    ) -> None:
        """Record a charge against the budget."""
        record = self._budgets.get(entity_id)
        if record is None:
            logger.warning("No budget for entity '%s' — charge not recorded", entity_id)
            return

        record.spent_usd += amount_usd
        record.charges.append(
            {
                "amount_usd": amount_usd,
                "description": description,
                "job_id": job_id,
                "timestamp": time.time(),
            }
        )
        self._save()
        logger.info(
            "Charge $%.2f recorded for %s (total spent: $%.2f / $%.2f)",
            amount_usd, entity_id, record.spent_usd, record.limit_usd,
        )

    def get_budget(self, entity_id: str) -> BudgetRecord | None:
        rec = self._budgets.get(entity_id)
        if rec:
            self._maybe_reset(rec)
        return rec

    def list_budgets(self) -> list[BudgetRecord]:
        for b in self._budgets.values():
            self._maybe_reset(b)
        return list(self._budgets.values())

    def get_summary(self, entity_id: str) -> dict[str, Any]:
        """Human-readable spending summary."""
        record = self._budgets.get(entity_id)
        if record is None:
            return {"error": f"No budget found for '{entity_id}'"}

        self._maybe_reset(record)
        remaining = record.limit_usd - record.spent_usd
        utilisation = (record.spent_usd / record.limit_usd * 100) if record.limit_usd else 0.0

        return {
            "entity_id": entity_id,
            "entity_type": record.entity_type,
            "limit_usd": record.limit_usd,
            "spent_usd": round(record.spent_usd, 2),
            "remaining_usd": round(remaining, 2),
            "utilisation_pct": round(utilisation, 1),
            "num_charges": len(record.charges),
        }

    # ── internals ───────────────────────────────────────────────────────

    def _maybe_reset(self, record: BudgetRecord) -> None:
        if record.period_end > 0 and time.time() >= record.period_end:
            logger.info("Budget period ended for %s — resetting", record.entity_id)
            record.spent_usd = 0.0
            record.charges = []
            record.period_start = time.time()
            record.period_end = record.period_start + 30 * 86400
            self._save()

    def _save(self) -> None:
        path = self.storage_dir / "budgets.json"
        data = {k: v.model_dump() for k, v in self._budgets.items()}
        path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        path = self.storage_dir / "budgets.json"
        if path.exists():
            raw = json.loads(path.read_text())
            self._budgets = {k: BudgetRecord(**v) for k, v in raw.items()}
