"""
Core execution engine — translates validated job configs into runnable tasks.

The engine is responsible for:
1. Validating job configs
2. Resolving dependencies (datasets, base models, etc.)
3. Dispatching to the correct subsystem (training, quantization, data pipeline)
4. Managing job lifecycle (queued → running → completed / failed)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    TRAINING = "training"
    QUANTIZATION = "quantization"
    DATA_PIPELINE = "data_pipeline"
    BENCHMARK = "benchmark"
    DEPLOYMENT = "deployment"


class Job(BaseModel):
    """Represents a single execution job in the system."""

    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_type: JobType
    mode: str = ""  # e.g. "pretrain", "finetune", "lora", "sft"
    status: JobStatus = JobStatus.PENDING
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)


class ExecutionEngine:
    """
    Central orchestrator — receives job configs and dispatches them.

    Usage::

        engine = ExecutionEngine()
        job = engine.submit(config)
        engine.wait(job.job_id)
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def submit(self, config: dict[str, Any]) -> Job:
        """Create and enqueue a new job from a parsed YAML config."""
        job_type = JobType(config.get("type", "training"))
        mode = config.get("mode", "")
        job = Job(job_type=job_type, mode=mode, config=config)
        self._jobs[job.job_id] = job
        job.status = JobStatus.QUEUED
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status in (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            return True
        return False

    def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 50,
    ) -> list[Job]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.job_type == job_type]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    def run_sync(self, job_id: str) -> Job:
        """Execute a job synchronously (for CLI & testing)."""
        job = self._jobs[job_id]
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)

        try:
            result = self._dispatch(job)
            job.metrics = result.get("metrics", {})
            job.artifacts = result.get("artifacts", [])
            job.status = JobStatus.COMPLETED
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
        finally:
            job.completed_at = datetime.now(timezone.utc)

        return job

    # ── Dispatch ────────────────────────────────────────────────────────

    def _dispatch(self, job: Job) -> dict[str, Any]:
        """Route the job to the correct handler."""
        handlers = {
            JobType.TRAINING: self._handle_training,
            JobType.QUANTIZATION: self._handle_quantization,
            JobType.DATA_PIPELINE: self._handle_data_pipeline,
            JobType.BENCHMARK: self._handle_benchmark,
            JobType.DEPLOYMENT: self._handle_deployment,
        }
        handler = handlers.get(job.job_type)
        if handler is None:
            raise ValueError(f"Unknown job type: {job.job_type}")
        return handler(job)

    def _handle_training(self, job: Job) -> dict[str, Any]:
        from clickml_pro.training.manager import TrainingManager

        mgr = TrainingManager()
        return mgr.execute(job)

    def _handle_quantization(self, job: Job) -> dict[str, Any]:
        from clickml_pro.quantization.pipeline import QuantizationPipeline

        pipeline = QuantizationPipeline()
        result = pipeline.run(job.config)
        return {"artifacts": [result.output_path], "metrics": result.metrics}

    def _handle_data_pipeline(self, job: Job) -> dict[str, Any]:
        from clickml_pro.data.pipeline.builder import PipelineBuilder

        builder = PipelineBuilder()
        return builder.execute(job.config)

    def _handle_benchmark(self, job: Job) -> dict[str, Any]:
        # Benchmark jobs: run inference benchmarks on quantized models
        return {"metrics": {"status": "benchmark_placeholder"}}

    def _handle_deployment(self, job: Job) -> dict[str, Any]:
        return {"metrics": {"status": "deployment_placeholder"}}
