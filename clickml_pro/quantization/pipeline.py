"""
Quantization pipeline — orchestrates the full post-training quantization flow.

Pipeline: fine-tuned model → Quantization job → Benchmark job → deployment-ready artifacts
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QuantizationResult(BaseModel):
    """Result of a quantization job."""

    output_path: str = ""
    method: str = ""
    original_size_mb: float = 0.0
    quantized_size_mb: float = 0.0
    compression_ratio: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)


class QuantizationPipeline:
    """
    Full post-training quantization pipeline.

    Usage::

        pipeline = QuantizationPipeline()
        result = pipeline.run(config)  # config from YAML
    """

    def run(self, config: dict[str, Any]) -> QuantizationResult:
        """Execute quantization based on config."""
        quant = config.get("quantization", config)
        method = quant.get("method", "int8")
        model_path = config.get("base_model", quant.get("model_path", ""))

        logger.info("Starting quantization: method=%s model=%s", method, model_path)

        handlers = {
            "int8": self._quantize_int8,
            "int4": self._quantize_int4,
            "awq": self._quantize_awq,
            "gptq": self._quantize_gptq,
            "gguf": self._quantize_gguf,
            "onnx": self._quantize_onnx,
        }

        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"Unknown quantization method: '{method}'. Available: {list(handlers.keys())}")

        return handler(model_path, quant)

    def _quantize_int8(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """8-bit weight-only quantization using bitsandbytes."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch

            quant_config = BitsAndBytesConfig(load_in_8bit=True)

            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=quant_config,
                device_map="auto",
            )
            tokenizer = AutoTokenizer.from_pretrained(model_path)

            output_dir = config.get("output_dir", f"{model_path}-int8")
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)

            return QuantizationResult(
                output_path=output_dir,
                method="int8",
                metrics={"bits": 8, "method": "bitsandbytes"},
            )

        except ImportError:
            logger.warning("bitsandbytes not installed — returning dry run")
            return QuantizationResult(
                method="int8",
                metrics={"status": "dry_run", "model_path": model_path},
            )

    def _quantize_int4(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """4-bit quantization using bitsandbytes NF4."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch

            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )

            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=quant_config,
                device_map="auto",
            )
            tokenizer = AutoTokenizer.from_pretrained(model_path)

            output_dir = config.get("output_dir", f"{model_path}-int4")
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)

            return QuantizationResult(
                output_path=output_dir,
                method="int4",
                metrics={"bits": 4, "quant_type": "nf4", "double_quant": True},
            )

        except ImportError:
            return QuantizationResult(
                method="int4",
                metrics={"status": "dry_run", "model_path": model_path},
            )

    def _quantize_awq(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """Activation-aware weight quantization (AWQ)."""
        try:
            from awq import AutoAWQForCausalLM
            from transformers import AutoTokenizer

            model = AutoAWQForCausalLM.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)

            quant_config = {
                "zero_point": True,
                "q_group_size": config.get("group_size", 128),
                "w_bit": 4,
            }

            model.quantize(tokenizer, quant_config=quant_config)

            output_dir = config.get("output_dir", f"{model_path}-awq")
            model.save_quantized(output_dir)
            tokenizer.save_pretrained(output_dir)

            return QuantizationResult(
                output_path=output_dir,
                method="awq",
                metrics={"bits": 4, "group_size": quant_config["q_group_size"]},
            )

        except ImportError:
            return QuantizationResult(
                method="awq",
                metrics={"status": "dry_run", "model_path": model_path},
            )

    def _quantize_gptq(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """GPTQ quantization."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, GPTQConfig

            gptq_config = GPTQConfig(
                bits=config.get("bits", 4),
                group_size=config.get("group_size", 128),
                dataset="c4",
                desc_act=True,
            )

            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=gptq_config,
                device_map="auto",
            )
            tokenizer = AutoTokenizer.from_pretrained(model_path)

            output_dir = config.get("output_dir", f"{model_path}-gptq")
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)

            return QuantizationResult(
                output_path=output_dir,
                method="gptq",
                metrics={"bits": gptq_config.bits, "group_size": gptq_config.group_size},
            )

        except ImportError:
            return QuantizationResult(
                method="gptq",
                metrics={"status": "dry_run", "model_path": model_path},
            )

    def _quantize_gguf(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """GGUF quantization for llama.cpp / CPU-friendly inference."""
        logger.info("GGUF quantization — requires llama.cpp convert script")

        quant_type = config.get("gguf_type", "q4_k_m")
        output_path = config.get("output_dir", f"{model_path}-{quant_type}.gguf")

        return QuantizationResult(
            output_path=output_path,
            method="gguf",
            metrics={
                "status": "requires_llama_cpp",
                "quant_type": quant_type,
                "note": "Use `llama.cpp/convert.py` and `quantize` binary for GGUF conversion.",
            },
        )

    def _quantize_onnx(self, model_path: str, config: dict[str, Any]) -> QuantizationResult:
        """ONNX export + quantization for cross-platform deployment."""
        try:
            from optimum.onnxruntime import ORTModelForCausalLM, ORTQuantizer
            from optimum.onnxruntime.configuration import AutoQuantizationConfig

            output_dir = config.get("output_dir", f"{model_path}-onnx")

            # Export to ONNX
            model = ORTModelForCausalLM.from_pretrained(model_path, export=True)
            model.save_pretrained(output_dir)

            # Quantize
            quantizer = ORTQuantizer.from_pretrained(output_dir)
            quant_config = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)
            quantizer.quantize(save_dir=output_dir, quantization_config=quant_config)

            return QuantizationResult(
                output_path=output_dir,
                method="onnx",
                metrics={"format": "onnx", "quantization": "dynamic"},
            )

        except ImportError:
            return QuantizationResult(
                method="onnx",
                metrics={"status": "dry_run", "model_path": model_path},
            )
