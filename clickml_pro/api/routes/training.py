"""Training API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class TrainRequest(BaseModel):
    base_model: str = "meta-llama/Llama-3.1-8B"
    mode: str = "finetune"  # pretrain | finetune | lora | sft | rlhf | diffusion
    dataset: str = ""
    training: dict[str, Any] = Field(default_factory=lambda: {"epochs": 3, "batch_size": 4, "lr": 2e-5})
    output_dir: str = "./output"
    lora: dict[str, Any] | None = None
    distributed: dict[str, Any] | None = None


@router.post("/run")
async def run_training(req: TrainRequest) -> dict:
    """Launch a training job."""
    from clickml_pro.training.manager import TrainingManager

    config = req.model_dump(exclude_none=True)
    try:
        manager = TrainingManager()
        job = manager.submit(config)
        result = manager.execute(job)
        return {"status": "ok", "job_id": job.job_id, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/modes")
async def list_modes() -> dict:
    """List available training modes."""
    return {
        "modes": [
            {"id": "pretrain", "description": "Train a model from scratch"},
            {"id": "finetune", "description": "Full fine-tune of a pre-trained model"},
            {"id": "lora", "description": "LoRA / PEFT parameter-efficient fine-tuning"},
            {"id": "sft", "description": "Supervised fine-tuning (chat / instruction)"},
            {"id": "rlhf", "description": "RLHF alignment (preview)"},
            {"id": "diffusion", "description": "Diffusion model fine-tuning"},
        ]
    }
