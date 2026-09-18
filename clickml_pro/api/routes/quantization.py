"""Quantization API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class QuantizeRequest(BaseModel):
    model_path: str
    output_dir: str = "./quantized"
    methods: list[str] = Field(default_factory=lambda: ["int8"])
    base_model: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


@router.post("/run")
async def run_quantization(req: QuantizeRequest) -> dict:
    """Run quantization pipeline."""
    from clickml_pro.quantization.pipeline import QuantizationPipeline

    pipeline = QuantizationPipeline()
    try:
        results = pipeline.run(
            model_path=req.model_path,
            output_dir=req.output_dir,
            methods=req.methods,
        )
        return {"status": "ok", "results": results}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/methods")
async def list_methods() -> dict:
    return {
        "methods": [
            {"id": "int8", "description": "8-bit quantization (bitsandbytes)"},
            {"id": "int4", "description": "4-bit NF4 quantization"},
            {"id": "awq", "description": "AWQ activation-aware quantization"},
            {"id": "gptq", "description": "GPTQ post-training quantization"},
            {"id": "gguf", "description": "GGUF for llama.cpp / ollama"},
            {"id": "onnx", "description": "ONNX Runtime optimised export"},
        ]
    }
