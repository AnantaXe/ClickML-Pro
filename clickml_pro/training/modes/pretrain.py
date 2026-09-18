"""
From-scratch pre-training handler.

Supports training a language model from a random initialisation on a large
corpus.  Uses HuggingFace Transformers + Accelerate for distributed training.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PretrainingHandler:
    """Train a model from scratch on raw text corpora."""

    def run(self, config: dict[str, Any]) -> dict[str, Any]:
        logger.info("Starting from-scratch pretraining …")

        base_model = config.get("base_model", "")
        training = config.get("training", {})
        epochs = training.get("epochs", 1)
        batch_size = training.get("batch_size", 8)
        lr = training.get("learning_rate", 1e-4)
        max_seq = training.get("max_seq_length", 2048)

        try:
            from transformers import (
                AutoConfig,
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from datasets import load_dataset
            from clickml_pro.config.settings import get_settings

            settings = get_settings()

            # Load or create model config
            if base_model:
                model_config = AutoConfig.from_pretrained(base_model)
                tokenizer = AutoTokenizer.from_pretrained(base_model)
            else:
                raise ValueError("base_model is required for pretraining (as architecture ref)")

            # Init model from config (random weights)
            model = AutoModelForCausalLM.from_config(model_config)
            param_count = sum(p.numel() for p in model.parameters())
            logger.info("Model initialised with %d parameters", param_count)

            # Load dataset
            dataset_name = config.get("dataset", "")
            if not dataset_name:
                raise ValueError("dataset is required for pretraining")

            ds = load_dataset(dataset_name, split="train")

            # Tokenize
            def tokenize_fn(examples: dict) -> dict:
                return tokenizer(
                    examples["text"],
                    truncation=True,
                    max_length=max_seq,
                    padding="max_length",
                )

            tokenized = ds.map(tokenize_fn, batched=True, remove_columns=ds.column_names)

            collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

            output_dir = str(settings.checkpoint_path / "pretrain")
            args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=lr,
                warmup_steps=training.get("warmup_steps", 500),
                weight_decay=training.get("weight_decay", 0.01),
                bf16=training.get("bf16", True),
                gradient_checkpointing=training.get("gradient_checkpointing", True),
                logging_steps=10,
                save_strategy="epoch",
                report_to="wandb" if settings.wandb_project else "none",
            )

            trainer = Trainer(
                model=model,
                args=args,
                train_dataset=tokenized,
                data_collator=collator,
            )

            result = trainer.train()
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)

            return {
                "metrics": {
                    "train_loss": result.training_loss,
                    "train_runtime": result.metrics.get("train_runtime", 0),
                    "parameters": param_count,
                },
                "artifacts": [output_dir],
            }

        except ImportError:
            logger.warning(
                "Training dependencies not installed. "
                "Install with: pip install clickml-pro[training]"
            )
            return {
                "metrics": {
                    "status": "dry_run",
                    "mode": "pretrain",
                    "base_model": base_model,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "learning_rate": lr,
                },
                "artifacts": [],
            }
