"""
Model Registry — track, version, and manage model artifacts.

A single logical model (e.g. "llama3-sft-v2") may have many physical
artifacts:
    - fp16 (GPU)
    - int8 (CPU)
    - int4 (edge)
    - distilled (mobile)

The registry tracks lineage, training method, dataset versions, quantization
format, compatible runtimes, and inference cost estimates.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelFormat(str, Enum):
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    GPTQ = "gptq"
    AWQ = "awq"
    GGUF = "gguf"
    ONNX = "onnx"
    COREML = "coreml"
    TFLITE = "tflite"


class ModelStatus(str, Enum):
    DRAFT = "draft"
    REGISTERED = "registered"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ModelArtifact(BaseModel):
    """A physical artifact — one specific format/quantization of a model."""

    artifact_id: str = ""
    format: ModelFormat = ModelFormat.FP16
    path: str = ""                 # Local or S3 path
    size_bytes: int = 0
    compatible_runtimes: list[str] = Field(default_factory=list)  # vllm, tgi, ollama, onnxruntime, etc.
    inference_cost_per_1k_tokens: float = 0.0
    latency_ms_p50: float = 0.0
    latency_ms_p99: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelLineage(BaseModel):
    """Tracks the lineage of a model — how it was created."""

    base_model: str = ""
    base_model_version: str = ""
    fine_tuning_method: str = ""     # pretrain, finetune, lora, sft, rlhf, diffusion
    dataset: str = ""
    dataset_version: str = ""
    training_job_id: str = ""
    quantization_method: str = ""
    parent_model: str = ""           # If derived from another registered model


class RegisteredModel(BaseModel):
    """A logical model in the registry."""

    name: str
    version: int = 1
    description: str = ""
    status: ModelStatus = ModelStatus.REGISTERED
    lineage: ModelLineage = Field(default_factory=ModelLineage)
    artifacts: list[ModelArtifact] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    owner: str = ""
    team: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def format(self) -> str:
        """Primary format (first artifact)."""
        return self.artifacts[0].format.value if self.artifacts else "unknown"


class ModelRegistry:
    """
    Local-first model registry with file-based persistence.

    Usage::

        registry = ModelRegistry()
        registry.register(model)
        registry.add_artifact(model_name, artifact)
        models = registry.list_models()
    """

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        from clickml_pro.config.settings import get_settings

        settings = get_settings()
        self.storage_dir = Path(storage_dir or settings.registry_path)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # ── Registration ────────────────────────────────────────────────────

    def register(self, model: RegisteredModel) -> RegisteredModel:
        """Register a new model or a new version of an existing model."""
        model_dir = self.storage_dir / model.name
        model_dir.mkdir(parents=True, exist_ok=True)

        # Auto-increment version
        existing = self._list_versions(model.name)
        if existing:
            model.version = max(existing) + 1

        path = model_dir / f"v{model.version}.json"
        path.write_text(model.model_dump_json(indent=2))
        logger.info("Model registered: %s v%d", model.name, model.version)
        return model

    def add_artifact(self, model_name: str, version: int, artifact: ModelArtifact) -> RegisteredModel | None:
        """Add a physical artifact to an existing model version."""
        model = self.get_model(model_name, version)
        if model is None:
            logger.error("Model not found: %s v%d", model_name, version)
            return None

        artifact.artifact_id = f"{model_name}-v{version}-{artifact.format.value}"
        model.artifacts.append(artifact)
        model.updated_at = datetime.now(timezone.utc).isoformat()

        path = self.storage_dir / model_name / f"v{version}.json"
        path.write_text(model.model_dump_json(indent=2))
        logger.info("Artifact added: %s → %s v%d", artifact.artifact_id, model_name, version)
        return model

    # ── Queries ─────────────────────────────────────────────────────────

    def get_model(self, name: str, version: int | None = None) -> RegisteredModel | None:
        """Get a model by name and optional version (latest if None)."""
        if version is None:
            versions = self._list_versions(name)
            if not versions:
                return None
            version = max(versions)

        path = self.storage_dir / name / f"v{version}.json"
        if not path.exists():
            return None
        return RegisteredModel(**json.loads(path.read_text()))

    def list_models(self, status: ModelStatus | None = None) -> list[RegisteredModel]:
        """List all registered models (latest version of each)."""
        models: list[RegisteredModel] = []
        if not self.storage_dir.exists():
            return models

        for model_dir in self.storage_dir.iterdir():
            if not model_dir.is_dir():
                continue
            model = self.get_model(model_dir.name)
            if model is None:
                continue
            if status and model.status != status:
                continue
            models.append(model)

        return sorted(models, key=lambda m: m.name)

    def search(self, query: str = "", tags: list[str] | None = None) -> list[RegisteredModel]:
        """Search models by name or tags."""
        models = self.list_models()
        results: list[RegisteredModel] = []

        for m in models:
            name_match = query.lower() in m.name.lower() if query else True
            tag_match = all(t in m.tags for t in (tags or []))
            if name_match and tag_match:
                results.append(m)

        return results

    def get_artifact(self, model_name: str, format: ModelFormat) -> ModelArtifact | None:
        """Get a specific format artifact for a model."""
        model = self.get_model(model_name)
        if model is None:
            return None
        for artifact in model.artifacts:
            if artifact.format == format:
                return artifact
        return None

    # ── Lifecycle ───────────────────────────────────────────────────────

    def promote(self, model_name: str, version: int, to_status: ModelStatus) -> bool:
        """Promote a model to a new status (e.g., staging → production)."""
        model = self.get_model(model_name, version)
        if model is None:
            return False

        model.status = to_status
        model.updated_at = datetime.now(timezone.utc).isoformat()

        path = self.storage_dir / model_name / f"v{version}.json"
        path.write_text(model.model_dump_json(indent=2))
        logger.info("Model promoted: %s v%d → %s", model_name, version, to_status)
        return True

    def compare(self, name: str, v1: int, v2: int) -> dict[str, Any]:
        """Compare two versions of the same model."""
        m1 = self.get_model(name, v1)
        m2 = self.get_model(name, v2)

        if m1 is None or m2 is None:
            raise ValueError(f"Model version not found: {name} v{v1} or v{v2}")

        return {
            "model": name,
            "v1": v1,
            "v2": v2,
            "lineage_diff": {
                "base_model": (m1.lineage.base_model, m2.lineage.base_model),
                "fine_tuning_method": (m1.lineage.fine_tuning_method, m2.lineage.fine_tuning_method),
                "dataset": (m1.lineage.dataset, m2.lineage.dataset),
            },
            "artifact_counts": (len(m1.artifacts), len(m2.artifacts)),
            "formats_v1": [a.format.value for a in m1.artifacts],
            "formats_v2": [a.format.value for a in m2.artifacts],
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _list_versions(self, name: str) -> list[int]:
        model_dir = self.storage_dir / name
        if not model_dir.exists():
            return []
        versions = []
        for f in model_dir.glob("v*.json"):
            try:
                versions.append(int(f.stem[1:]))
            except ValueError:
                pass
        return sorted(versions)
