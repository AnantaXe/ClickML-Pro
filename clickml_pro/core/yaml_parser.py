"""
YAML job configuration parser.

Every user action in the UI (click → configure → run) produces a YAML job
config.  This module loads, validates, and normalises those configs.

Example YAML::

    type: training
    mode: lora
    base_model: meta-llama/Llama-3-8B
    dataset: my-org/instructions-v2
    training:
      epochs: 3
      batch_size: 4
      learning_rate: 2e-4
      lora:
        r: 16
        alpha: 32
        target_modules: [q_proj, v_proj]
    output:
      registry: true
      quantize: int8
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ── Schema Models ───────────────────────────────────────────────────────────


class LoraConfig(BaseModel):
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = Field(default_factory=lambda: ["q_proj", "v_proj"])


class TrainingParams(BaseModel):
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 1
    learning_rate: float = 2e-4
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_seq_length: int = 2048
    fp16: bool = False
    bf16: bool = True
    gradient_checkpointing: bool = True
    lora: LoraConfig | None = None
    deepspeed_config: str | None = None


class QuantizationParams(BaseModel):
    method: str = "int8"  # int8, int4, awq, gptq, gguf
    calibration_samples: int = 128
    group_size: int = 128


class OutputConfig(BaseModel):
    registry: bool = True
    quantize: str | None = None
    push_to_hub: bool = False
    hub_repo: str | None = None


class DataPipelineParams(BaseModel):
    engine: str = "pandas"  # pandas, polars, duckdb, spark
    source: dict[str, Any] = Field(default_factory=dict)
    transformations: list[dict[str, Any]] = Field(default_factory=list)
    sink: dict[str, Any] = Field(default_factory=dict)
    schedule: str | None = None  # cron expression


class JobConfig(BaseModel):
    """Top-level job configuration produced from YAML."""

    type: str = "training"  # training, quantization, data_pipeline, benchmark, deployment
    mode: str = ""  # pretrain, finetune, lora, sft, rlhf, diffusion
    name: str = ""
    base_model: str = ""
    dataset: str = ""
    training: TrainingParams = Field(default_factory=TrainingParams)
    quantization: QuantizationParams = Field(default_factory=QuantizationParams)
    data_pipeline: DataPipelineParams = Field(default_factory=DataPipelineParams)
    output: OutputConfig = Field(default_factory=OutputConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Loader ──────────────────────────────────────────────────────────────────


def load_job_config(path: str | Path) -> dict[str, Any]:
    """Load and validate a YAML job config file, returning a plain dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    # Validate through pydantic then return as dict for flexible downstream use
    validated = JobConfig(**raw)
    return validated.model_dump()


def dump_job_config(config: dict[str, Any], path: str | Path) -> Path:
    """Write a job config dict to a YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.safe_dump(config, fh, default_flow_style=False, sort_keys=False)
    return path
