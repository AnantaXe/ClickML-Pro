"""
Gradient synchronisation helpers for distributed training.

Supports:
- Data-parallel gradient all-reduce (DDP)
- Pipeline-parallel gradient sync
- DeepSpeed ZeRO Stage 1/2/3 integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SyncStrategy(str, Enum):
    DDP = "ddp"                       # torch.nn.parallel.DistributedDataParallel
    FSDP = "fsdp"                     # Fully Sharded Data Parallel
    DEEPSPEED_ZERO1 = "zero1"         # DeepSpeed ZeRO Stage 1
    DEEPSPEED_ZERO2 = "zero2"         # DeepSpeed ZeRO Stage 2
    DEEPSPEED_ZERO3 = "zero3"         # DeepSpeed ZeRO Stage 3


@dataclass
class GradientSyncConfig:
    """Configuration for gradient synchronisation."""

    strategy: SyncStrategy = SyncStrategy.DDP
    world_size: int = 1
    local_rank: int = 0
    backend: str = "nccl"             # nccl, gloo, mpi
    gradient_accumulation_steps: int = 1
    communication_dtype: str = "fp32"  # fp32, fp16, bf16
    bucket_cap_mb: int = 25
    find_unused_parameters: bool = False


class GradientSyncManager:
    """Manages gradient synchronisation across training workers."""

    def __init__(self, config: GradientSyncConfig | None = None) -> None:
        self.config = config or GradientSyncConfig()
        self._initialized = False

    def initialize(self) -> None:
        """Set up the distributed process group."""
        if self.config.world_size <= 1:
            logger.info("Single-device mode — no gradient sync needed.")
            return

        try:
            import torch.distributed as dist

            if not dist.is_initialized():
                dist.init_process_group(
                    backend=self.config.backend,
                    world_size=self.config.world_size,
                    rank=self.config.local_rank,
                )
                self._initialized = True
                logger.info(
                    "Distributed init: strategy=%s  world_size=%d  rank=%d",
                    self.config.strategy,
                    self.config.world_size,
                    self.config.local_rank,
                )
        except ImportError:
            logger.warning("torch.distributed not available")

    def wrap_model(self, model: Any) -> Any:
        """Wrap a model with the appropriate distributed wrapper."""
        if self.config.world_size <= 1:
            return model

        try:
            import torch
            import torch.nn as nn

            if self.config.strategy == SyncStrategy.DDP:
                from torch.nn.parallel import DistributedDataParallel as DDP

                model = DDP(
                    model,
                    device_ids=[self.config.local_rank],
                    find_unused_parameters=self.config.find_unused_parameters,
                    bucket_cap_mb=self.config.bucket_cap_mb,
                )
                logger.info("Model wrapped with DDP")

            elif self.config.strategy == SyncStrategy.FSDP:
                from torch.distributed.fsdp import (
                    FullyShardedDataParallel as FSDP,
                    MixedPrecision,
                )

                mp_policy = MixedPrecision(
                    param_dtype=torch.bfloat16,
                    reduce_dtype=torch.bfloat16,
                    buffer_dtype=torch.bfloat16,
                )
                model = FSDP(model, mixed_precision=mp_policy)
                logger.info("Model wrapped with FSDP")

            elif self.config.strategy.value.startswith("zero"):
                logger.info(
                    "DeepSpeed %s — use DeepSpeed config in TrainingArguments",
                    self.config.strategy.value.upper(),
                )

            return model

        except ImportError:
            logger.warning("Could not apply distributed wrapper")
            return model

    def cleanup(self) -> None:
        """Clean up the distributed process group."""
        if self._initialized:
            try:
                import torch.distributed as dist
                dist.destroy_process_group()
                self._initialized = False
            except Exception:
                pass
