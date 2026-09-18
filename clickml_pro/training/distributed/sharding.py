"""
Model sharding utilities for large model training.

Supports:
- Tensor parallelism (splitting layers across GPUs)
- Pipeline parallelism (splitting sequential layers)
- FSDP sharding (parameter + gradient + optimizer sharding)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ShardingStrategy(str, Enum):
    NO_SHARD = "no_shard"
    SHARD_GRAD_OP = "shard_grad_op"     # ZeRO-2 equivalent
    FULL_SHARD = "full_shard"           # ZeRO-3 equivalent
    HYBRID_SHARD = "hybrid_shard"       # Shard within node, replicate across


@dataclass
class ShardingConfig:
    strategy: ShardingStrategy = ShardingStrategy.NO_SHARD
    num_gpus: int = 1
    cpu_offload: bool = False
    offload_params: bool = False        # Offload parameters to CPU (ZeRO-3)
    offload_optimizer: bool = False     # Offload optimizer states to CPU
    min_num_params: int = 1_000_000     # Min params per shard


class ModelSharder:
    """Utilities for sharding models across multiple devices."""

    def __init__(self, config: ShardingConfig | None = None) -> None:
        self.config = config or ShardingConfig()

    def estimate_memory(self, model: Any) -> dict[str, float]:
        """Estimate memory requirements for different sharding strategies."""
        try:
            import torch

            total_params = sum(p.numel() for p in model.parameters())
            param_bytes = sum(p.numel() * p.element_size() for p in model.parameters())

            # Approximate memory estimates (in GB)
            param_gb = param_bytes / (1024**3)
            grad_gb = param_gb  # Same size as params
            optimizer_gb = param_gb * 2  # Adam: 2x param size (momentum + variance)
            activation_gb = param_gb * 0.5  # Rough estimate

            total_gb = param_gb + grad_gb + optimizer_gb + activation_gb

            estimates = {
                "total_parameters": total_params,
                "param_memory_gb": round(param_gb, 2),
                "no_shard_gb": round(total_gb, 2),
                "fsdp_per_gpu_gb": round(total_gb / max(self.config.num_gpus, 1), 2),
                "zero3_per_gpu_gb": round(
                    (param_gb + grad_gb + optimizer_gb) / max(self.config.num_gpus, 1)
                    + activation_gb,
                    2,
                ),
                "recommended_gpus": max(1, int(total_gb / 20) + 1),  # ~20GB per GPU headroom
            }
            return estimates

        except ImportError:
            return {"error": "torch not installed"}

    def get_device_map(self, model_name: str) -> dict[str, Any] | str:
        """Generate a device map for model loading."""
        if self.config.num_gpus <= 1:
            return "auto"

        if self.config.strategy == ShardingStrategy.NO_SHARD:
            return "auto"

        # For multi-GPU, use balanced device map
        return "balanced"

    def get_deepspeed_config(self) -> dict[str, Any]:
        """Generate a DeepSpeed config dict for the current sharding strategy."""
        config: dict[str, Any] = {
            "train_batch_size": "auto",
            "train_micro_batch_size_per_gpu": "auto",
            "gradient_accumulation_steps": "auto",
            "gradient_clipping": 1.0,
            "bf16": {"enabled": True},
        }

        if self.config.strategy == ShardingStrategy.SHARD_GRAD_OP:
            config["zero_optimization"] = {
                "stage": 2,
                "offload_optimizer": {"device": "cpu"} if self.config.offload_optimizer else {"device": "none"},
                "allgather_partitions": True,
                "allgather_bucket_size": 2e8,
                "overlap_comm": True,
                "reduce_scatter": True,
            }
        elif self.config.strategy == ShardingStrategy.FULL_SHARD:
            config["zero_optimization"] = {
                "stage": 3,
                "offload_optimizer": {"device": "cpu"} if self.config.offload_optimizer else {"device": "none"},
                "offload_param": {"device": "cpu"} if self.config.offload_params else {"device": "none"},
                "overlap_comm": True,
                "contiguous_gradients": True,
                "sub_group_size": 1e9,
                "stage3_prefetch_bucket_size": "auto",
                "stage3_param_persistence_threshold": "auto",
                "stage3_max_live_parameters": 1e9,
                "stage3_max_reuse_distance": 1e9,
            }

        return config
