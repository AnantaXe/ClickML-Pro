"""Tests for YAML config parsing."""

import pytest
from pathlib import Path

from clickml_pro.core.yaml_parser import load_job_config


SAMPLE_YAML = """\
name: test-run
type: training
base_model: meta-llama/Llama-3.1-8B
mode: finetune
training:
  epochs: 3
  batch_size: 4
  learning_rate: 0.00002
output:
  dir: ./output
  format: safetensors
"""


class TestYamlParser:
    def test_load_valid_config(self, tmp_path: Path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(SAMPLE_YAML)

        config = load_job_config(str(cfg_path))
        assert config["name"] == "test-run"
        assert config["type"] == "training"
        assert config["training"]["epochs"] == 3
        assert config["training"]["learning_rate"] == pytest.approx(2e-5)

    def test_load_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_job_config("/nonexistent/path.yaml")

    def test_defaults(self, tmp_path: Path):
        minimal = "name: minimal\ntype: training\n"
        cfg_path = tmp_path / "min.yaml"
        cfg_path.write_text(minimal)

        config = load_job_config(str(cfg_path))
        assert config["training"]["epochs"] == 3
        assert config["training"]["batch_size"] == 4
