"""
PEFT handler — LoRA, adapters, and other parameter-efficient methods.

Uses the HuggingFace PEFT library.  Only a small subset of parameters are
trained while the base model remains frozen.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PEFTHandler:
    """Parameter-efficient fine-tuning with LoRA / adapters."""

    def run(self, config: dict[str, Any]) -> dict[str, Any]:
        logger.info("Starting PEFT (LoRA) fine-tuning …")

        base_model = config.get("base_model", "")
        dataset_name = config.get("dataset", "")
        training = config.get("training", {})
        lora_cfg = training.get("lora", {})

        epochs = training.get("epochs", 3)
        batch_size = training.get("batch_size", 4)
        lr = training.get("learning_rate", 2e-4)
        max_seq = training.get("max_seq_length", 2048)

        lora_r = lora_cfg.get("r", 16)
        lora_alpha = lora_cfg.get("alpha", 32)
        lora_dropout = lora_cfg.get("dropout", 0.05)
        target_modules = lora_cfg.get("target_modules", ["q_proj", "v_proj"])

        try:
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                TrainingArguments,
                Trainer,
                DataCollatorForLanguageModeling,
            )
            from peft import get_peft_model, LoraConfig, TaskType
            from datasets import load_dataset
            from clickml_pro.config.settings import get_settings

            settings = get_settings()

            if not base_model:
                raise ValueError("base_model is required for PEFT")

            tokenizer = AutoTokenizer.from_pretrained(base_model)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                torch_dtype="auto",
                device_map="auto" if settings.default_device == "auto" else None,
            )

            # Apply LoRA
            peft_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=lora_r,
                lora_alpha=lora_alpha,
                lora_dropout=lora_dropout,
                target_modules=target_modules,
            )
            model = get_peft_model(model, peft_config)

            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            total = sum(p.numel() for p in model.parameters())
            logger.info(
                "PEFT enabled: %d / %d trainable (%.2f%%)",
                trainable, total, 100 * trainable / total,
            )

            # Dataset
            if not dataset_name:
                raise ValueError("dataset is required")

            ds = load_dataset(dataset_name, split="train")

            def tokenize_fn(examples: dict) -> dict:
                texts = examples.get("text", examples.get("instruction", [""]))
                return tokenizer(texts, truncation=True, max_length=max_seq, padding="max_length")

            tokenized = ds.map(tokenize_fn, batched=True, remove_columns=ds.column_names)
            collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

            output_dir = str(settings.checkpoint_path / "peft-lora")
            args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=lr,
                warmup_steps=training.get("warmup_steps", 100),
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
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)

            return {
                "metrics": {
                    "train_loss": result.training_loss,
                    "trainable_parameters": trainable,
                    "total_parameters": total,
                    "trainable_pct": round(100 * trainable / total, 2),
                    "lora_r": lora_r,
                    "lora_alpha": lora_alpha,
                },
                "artifacts": [output_dir],
            }

        except ImportError:
            logger.warning(
                "PEFT/training dependencies not installed. "
                "Install with: pip install clickml-pro[training]"
            )
            return {
                "metrics": {
                    "status": "dry_run",
                    "mode": "peft/lora",
                    "base_model": base_model,
                    "lora_r": lora_r,
                    "lora_alpha": lora_alpha,
                    "target_modules": target_modules,
                },
                "artifacts": [],
            }
