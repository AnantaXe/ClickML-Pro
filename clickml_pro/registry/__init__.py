"""
Model Registry sub-package.

Tracks base model lineage, fine-tuning method, dataset versions,
quantization format, compatible runtimes, and inference cost estimates.
One logical model → many physical artifacts.
"""

from clickml_pro.registry.model_registry import ModelRegistry

__all__ = ["ModelRegistry"]
