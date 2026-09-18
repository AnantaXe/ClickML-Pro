"""
Training sub-package — supports from-scratch pretraining, full fine-tuning,
PEFT (LoRA/adapters), SFT, RLHF (placeholder), and diffusion fine-tuning.
"""

from clickml_pro.training.manager import TrainingManager

__all__ = ["TrainingManager"]
