"""
Full fine-tuning handler.

Loads a pre-trained model and fine-tunes ALL parameters on a downstream
dataset.  Best when you have enough compute and data to justify updating
the entire model.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FineTuneHandler:
    """Full-parameter fine-tuning of a pre-trained model."""

    def run(self, config: dict[str, Any]) -> dict[str, Any]:
        logger.info("Starting full fine-tuning …")

        base_model = config.get("base_model", "")
        dataset_name = config.get("dataset", "")
        training = config.get("training", {})
        epochs = training.get("epochs", 3)
        batch_size = training.get("batch_size", 4)
        lr = training.get("learning_rate", 2e-5)
        max_seq = training.get("max_seq_length", 2048)

        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from datasets import load_dataset
            from clickml_pro.config.settings import get_settings

            settings = get_settings()

            if not base_model:
                raise ValueError("base_model is required for fine-tuning")

            tokenizer = AutoTokenizer.from_pretrained(base_model)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype="auto",
                device_map="auto" if settings.default_device == "auto" else None,
            )

            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            logger.info("Trainable parameters: %d", trainable)

            # Dataset
            if not dataset_name:
                raise ValueError("dataset is required")

            ds = load_dataset(dataset_name, split="train")

            def tokenize_fn(examples: dict) -> dict:
                return tokenizer(
                    examples.get("text", examples.get("instruction", "")),
                    truncation=True,
                    max_length=max_seq,
                    padding="max_length",
                )

            tokenized = ds.map(tokenize_fn, batched=True, remove_columns=ds.column_names)
            collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

            output_dir = str(settings.checkpoint_path / "finetune")
            args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=lr,
                warmup_steps=training.get("warmup_steps", 100),
                weight_decay=training.get("weight_decay", 0.01),
                bf16=training.get("bf16", True),
                fp16=training.get("fp16", False),
                gradient_checkpointing=training.get("gradient_checkpointing", True),
                gradient_accumulation_steps=training.get("gradient_accumulation_steps", 1),
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
                    "trainable_parameters": trainable,
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
                    "mode": "finetune",
                    "base_model": base_model,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "learning_rate": lr,
                },
                "artifacts": [],
            }
