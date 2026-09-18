"""
Training job manager — the top-level orchestrator for all training modes.

Responsibilities:
- Accept a job config (dict or Job object)
- Resolve the correct training mode handler
- Manage checkpointing, logging, and metric collection
- Integrate with the event bus for lifecycle notifications
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from clickml_pro.core.engine import Job, JobStatus, JobType
from clickml_pro.core.events import get_event_bus

logger = logging.getLogger(__name__)


class TrainingManager:
    """High-level training orchestrator."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._bus = get_event_bus()

    # ── Public API ──────────────────────────────────────────────────────

    def submit(self, config: dict[str, Any]) -> Job:
        """Create a training job from a validated config dict."""
        job = Job(
            job_type=JobType.TRAINING,
            mode=config.get("mode", "finetune"),
            config=config,
        )
        self._jobs[job.job_id] = job
        job.status = JobStatus.QUEUED
        self._bus.publish("training.queued", {"job_id": job.job_id}, source="TrainingManager")
        logger.info("Training job queued: %s (mode=%s)", job.job_id, job.mode)
        return job

    def execute(self, job: Job) -> dict[str, Any]:
        """Execute a training job synchronously. Returns metrics & artifacts."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        self._bus.publish("training.started", {"job_id": job.job_id}, source="TrainingManager")
        logger.info("Training job started: %s", job.job_id)

        try:
            handler = self._get_handler(job.mode)
            result = handler.run(job.config)
            job.status = JobStatus.COMPLETED
            job.metrics = result.get("metrics", {})
            job.artifacts = result.get("artifacts", [])
            self._bus.publish(
                "training.completed",
                {"job_id": job.job_id, "metrics": job.metrics},
                source="TrainingManager",
            )
            logger.info("Training job completed: %s", job.job_id)
            return result
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            self._bus.publish(
                "training.failed",
                {"job_id": job.job_id, "error": str(exc)},
                source="TrainingManager",
            )
            logger.exception("Training job failed: %s", job.job_id)
            raise
        finally:
            job.completed_at = datetime.now(timezone.utc)

    def list_jobs(self, limit: int = 50) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)[:limit]

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    # ── Handler Resolution ──────────────────────────────────────────────

    def _get_handler(self, mode: str) -> Any:
        """Return the correct training mode handler."""
        from clickml_pro.training.modes.pretrain import PretrainingHandler
        from clickml_pro.training.modes.finetune import FineTuneHandler
        from clickml_pro.training.modes.peft import PEFTHandler
        from clickml_pro.training.modes.sft import SFTHandler
        from clickml_pro.training.modes.rlhf import RLHFHandler
        from clickml_pro.training.modes.diffusion import DiffusionHandler

        handlers = {
            "pretrain": PretrainingHandler,
            "finetune": FineTuneHandler,
            "lora": PEFTHandler,
            "peft": PEFTHandler,
            "adapter": PEFTHandler,
            "sft": SFTHandler,
            "rlhf": RLHFHandler,
            "rlaif": RLHFHandler,
            "diffusion": DiffusionHandler,
        }

        handler_cls = handlers.get(mode)
        if handler_cls is None:
            raise ValueError(
                f"Unknown training mode: '{mode}'. "
                f"Supported: {', '.join(handlers.keys())}"
            )
        return handler_cls()
