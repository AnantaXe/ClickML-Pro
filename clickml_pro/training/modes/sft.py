"""
Supervised Fine-Tuning (SFT) handler.

Uses the TRL library's SFTTrainer to fine-tune a model on instruction-
following data.  This is the standard "instruction tuning" pipeline used
to turn base LLMs into chat/assistant models.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SFTHandler:
    """Instruction tuning via supervised fine-tuning (SFT)."""

    def run(self, config: dict[str, Any]) -> dict[str, Any]:
        logger.info("Starting SFT (instruction tuning) …")

        base_model = config.get("base_model", "")
        dataset_name = config.get("dataset", "")
        training = config.get("training", {})
        lora_cfg = training.get("lora", None)

        epochs = training.get("epochs", 3)
        batch_size = training.get("batch_size", 4)
        lr = training.get("learning_rate", 2e-4)
        max_seq = training.get("max_seq_length", 2048)

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from datasets import load_dataset
            from trl import SFTTrainer, SFTConfig
            from clickml_pro.config.settings import get_settings

            settings = get_settings()

            if not base_model:
                raise ValueError("base_model is required for SFT")

            tokenizer = AutoTokenizer.from_pretrained(base_model)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype="auto",
                device_map="auto" if settings.default_device == "auto" else None,
            )

            # Optionally apply LoRA for efficient SFT
            peft_config = None
            if lora_cfg:
                from peft import LoraConfig, TaskType

                peft_config = LoraConfig(
                    task_type=TaskType.CAUSAL_LM,
                    r=lora_cfg.get("r", 16),
                    lora_alpha=lora_cfg.get("alpha", 32),
                    lora_dropout=lora_cfg.get("dropout", 0.05),
                    target_modules=lora_cfg.get("target_modules", ["q_proj", "v_proj"]),
                )

            # Dataset
            if not dataset_name:
                raise ValueError("dataset is required for SFT")

            ds = load_dataset(dataset_name, split="train")

            # SFT expects a "text" column or a formatting function
            def formatting_func(example: dict) -> list[str]:
                """Format instruction-following examples into a single string."""
                instruction = example.get("instruction", "")
                inp = example.get("input", "")
                output = example.get("output", example.get("response", ""))

                if inp:
                    text = (
                        f"### Instruction:\n{instruction}\n\n"
                        f"### Input:\n{inp}\n\n"
                        f"### Response:\n{output}"
                    )
                else:
                    text = (
                        f"### Instruction:\n{instruction}\n\n"
                        f"### Response:\n{output}"
                    )
                return [text]

            output_dir = str(settings.checkpoint_path / "sft")

            sft_config = SFTConfig(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=lr,
                warmup_steps=training.get("warmup_steps", 100),
                weight_decay=training.get("weight_decay", 0.01),
                bf16=training.get("bf16", True),
                gradient_checkpointing=training.get("gradient_checkpointing", True),
                max_seq_length=max_seq,
                logging_steps=10,
                save_strategy="epoch",
                report_to="wandb" if settings.wandb_project else "none",
            )

            trainer = SFTTrainer(
                model=model,
                args=sft_config,
                train_dataset=ds,
                formatting_func=formatting_func,
                tokenizer=tokenizer,
                peft_config=peft_config,
            )

            result = trainer.train()
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)

            return {
                "metrics": {
                    "train_loss": result.training_loss,
                    "train_runtime": result.metrics.get("train_runtime", 0),
                    "mode": "sft",
                    "peft_enabled": peft_config is not None,
                },
                "artifacts": [output_dir],
            }

        except ImportError:
            logger.warning(
                "SFT/TRL dependencies not installed. "
                "Install with: pip install clickml-pro[training]"
            )
            return {
                "metrics": {
                    "status": "dry_run",
                    "mode": "sft",
                    "base_model": base_model,
                    "epochs": epochs,
                    "peft": lora_cfg is not None,
                },
                "artifacts": [],
            }
