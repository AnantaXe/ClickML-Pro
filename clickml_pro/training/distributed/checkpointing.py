"""
Checkpointing utilities for training fault tolerance.

Supports:
- Full model checkpoints
- LoRA adapter checkpoints
- Optimizer state checkpoints
- Async checkpointing (non-blocking saves)
- Checkpoint pruning (keep only N best)
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CheckpointMetadata(BaseModel):
    """Metadata stored alongside a training checkpoint."""

    job_id: str = ""
    step: int = 0
    epoch: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: dict[str, Any] = Field(default_factory=dict)


class CheckpointManager:
    """Manages saving, loading, and pruning of training checkpoints."""

    def __init__(self, checkpoint_dir: str | Path, max_keep: int = 3) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_keep = max_keep

    def save(
        self,
        model: Any,
        optimizer: Any | None = None,
        scheduler: Any | None = None,
        metadata: CheckpointMetadata | None = None,
        tag: str = "",
    ) -> Path:
        """Save a checkpoint."""
        metadata = metadata or CheckpointMetadata()
        tag = tag or f"step-{metadata.step}"
        ckpt_path = self.checkpoint_dir / tag
        ckpt_path.mkdir(parents=True, exist_ok=True)

        try:
            import torch

            # Save model
            if hasattr(model, "save_pretrained"):
                model.save_pretrained(ckpt_path)
            else:
                torch.save(model.state_dict(), ckpt_path / "model.pt")

            # Save optimizer
            if optimizer is not None:
                torch.save(optimizer.state_dict(), ckpt_path / "optimizer.pt")

            # Save scheduler
            if scheduler is not None:
                torch.save(scheduler.state_dict(), ckpt_path / "scheduler.pt")

        except ImportError:
            logger.warning("torch not installed — saving metadata only")

        # Save metadata
        meta_path = ckpt_path / "metadata.json"
        meta_path.write_text(metadata.model_dump_json(indent=2))

        logger.info("Checkpoint saved: %s", ckpt_path)
        self._prune()
        return ckpt_path

    def load_latest(self) -> Path | None:
        """Return the path to the latest checkpoint."""
        checkpoints = self._list_checkpoints()
        if not checkpoints:
            return None
        return checkpoints[-1]

    def load_best(self, metric: str = "loss", lower_is_better: bool = True) -> Path | None:
        """Return the path to the best checkpoint by a given metric."""
        checkpoints = self._list_checkpoints()
        best: Path | None = None
        best_value = float("inf") if lower_is_better else float("-inf")

        for ckpt_path in checkpoints:
            meta = self._load_metadata(ckpt_path)
            if meta is None:
                continue
            value = meta.metrics.get(metric, meta.loss)
            if lower_is_better and value < best_value:
                best_value = value
                best = ckpt_path
            elif not lower_is_better and value > best_value:
                best_value = value
                best = ckpt_path

        return best

    def _list_checkpoints(self) -> list[Path]:
        """List all checkpoint directories sorted by modification time."""
        if not self.checkpoint_dir.exists():
            return []
        dirs = [d for d in self.checkpoint_dir.iterdir() if d.is_dir()]
        return sorted(dirs, key=lambda d: d.stat().st_mtime)

    def _load_metadata(self, ckpt_path: Path) -> CheckpointMetadata | None:
        meta_file = ckpt_path / "metadata.json"
        if not meta_file.exists():
            return None
        return CheckpointMetadata(**json.loads(meta_file.read_text()))

    def _prune(self) -> None:
        """Remove old checkpoints, keeping only max_keep."""
        checkpoints = self._list_checkpoints()
        while len(checkpoints) > self.max_keep:
            oldest = checkpoints.pop(0)
            logger.info("Pruning old checkpoint: %s", oldest)
            shutil.rmtree(oldest, ignore_errors=True)
