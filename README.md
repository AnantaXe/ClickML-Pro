# ClickML-Pro

**Enterprise MLOps & Data Engineering platform — one `pip install` away.**

ClickML-Pro is a batteries-included Python package that unifies **model training**, **quantization**, **data engineering**, **model governance**, and **experiment management** into a single CLI, Python API, and REST service.

---

## Features

| Module | Highlights |
|--------|-----------|
| **Training** | Pre-training, full fine-tune, LoRA/PEFT, SFT, RLHF (preview), Diffusion (LoRA, DreamBooth) |
| **Distributed** | DDP, FSDP, DeepSpeed ZeRO 1/2/3, automatic model sharding, checkpoint management |
| **Quantization** | INT8, INT4 (NF4), AWQ, GPTQ, GGUF (llama.cpp), ONNX Runtime |
| **Data Engineering** | Multi-engine (Pandas, Polars, DuckDB), schema versioning, data contracts, lineage graph, observability (drift, anomaly detection), backfill & replay |
| **Model Registry** | Versioned model registration, artifact management, lineage tracking, promotion (staging → production), search |
| **Governance** | Per-job cost estimation, GPU quotas per org, hard budget limits, RBAC policy engine |
| **Notebook** | Programmatic notebook editor, auto-generated experiment notebooks, export to `.py` / `.html` / `.md` |
| **API** | FastAPI REST service with endpoints for every module |

---

## Quick Start

### Install via pip

```bash
# Core (lightweight — no GPU deps)
pip install clickml-pro

# With training support (PyTorch, Transformers, PEFT, TRL)
pip install "clickml-pro[training]"

# With data engineering
pip install "clickml-pro[data]"

# With quantization
pip install "clickml-pro[quantization]"

# Everything
pip install "clickml-pro[all]"

# Development
pip install "clickml-pro[dev]"
```

### Install via Docker

```bash
# CPU / API-only
docker compose up clickml

# GPU (training & quantization)
docker build -f Dockerfile.gpu -t clickml-pro:gpu .
docker run --gpus all -p 8000:8000 clickml-pro:gpu
```

---

## CLI

```bash
# Start the API server
clickml serve --port 8000

# Run a training job from YAML config
clickml train run --config training.yaml

# List training modes
clickml train list

# Register a model
clickml registry list

# Validate data
clickml data validate --source data.csv --engine pandas

# Quantize a model
clickml quantize run --model ./model --methods int8,int4

# Export a notebook
clickml notebook export --input experiment.ipynb --format python

# Estimate job cost
clickml governance estimate --config job.yaml
```

---

## YAML Configuration

```yaml
name: llama-finetune
type: training
base_model: meta-llama/Llama-3.1-8B
mode: lora
dataset: my_dataset

training:
  epochs: 3
  batch_size: 4
  lr: 2.0e-5

lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules:
    - q_proj
    - v_proj

output:
  dir: ./output
  format: safetensors
```

---

## Python API

```python
from clickml_pro.training.manager import TrainingManager
from clickml_pro.quantization.pipeline import QuantizationPipeline
from clickml_pro.registry.model_registry import ModelRegistry
from clickml_pro.notebook.editor import NotebookEditor
from clickml_pro.governance.cost import CostEstimator

# Train
manager = TrainingManager()
result = manager.run({
    "base_model": "meta-llama/Llama-3.1-8B",
    "mode": "lora",
    "training": {"epochs": 3},
})

# Quantize
pipeline = QuantizationPipeline()
pipeline.run(model_path="./output", methods=["int8", "gguf"])

# Registry
registry = ModelRegistry()
registry.register(name="my-model", version="1.0", framework="pytorch")

# Notebook
nb = NotebookEditor.from_training_config({"base_model": "bert-base"})
nb.save("experiment.ipynb")

# Cost estimation
estimator = CostEstimator()
estimate = estimator.estimate({
    "type": "training",
    "base_model": "llama-7b",
    "mode": "lora",
    "training": {"epochs": 3},
})
print(f"Estimated cost: ${estimate.cost_usd}")
```

---

## REST API

Start the server:

```bash
clickml serve
# or
uvicorn clickml_pro.api.app:create_app --factory --reload
```

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/training/run` | Launch training job |
| `GET` | `/api/v1/training/modes` | List training modes |
| `POST` | `/api/v1/registry/register` | Register a model |
| `GET` | `/api/v1/registry/list` | List all models |
| `POST` | `/api/v1/quantization/run` | Run quantization |
| `POST` | `/api/v1/data/validate` | Validate data source |
| `POST` | `/api/v1/data/pipeline/run` | Execute data pipeline |
| `POST` | `/api/v1/governance/cost/estimate` | Estimate job cost |
| `POST` | `/api/v1/governance/budget/set` | Set budget limit |
| `POST` | `/api/v1/governance/quota/set` | Set GPU quota |
| `POST` | `/api/v1/notebook/generate` | Generate notebook |

Full interactive docs at `http://localhost:8000/docs`.

---

## Project Structure

```
clickml_pro/
├── __init__.py
├── cli.py                     # Click CLI entry point
├── config/
│   └── settings.py            # Pydantic Settings
├── core/
│   ├── engine.py              # Job execution engine
│   ├── events.py              # Event bus (pub/sub)
│   └── yaml_parser.py         # YAML config loader
├── training/
│   ├── manager.py             # Training orchestrator
│   ├── jobs.py                # Data models
│   ├── modes/                 # pretrain, finetune, peft, sft, rlhf, diffusion
│   └── distributed/           # gradient_sync, sharding, checkpointing
├── data/
│   ├── engine.py              # Multi-engine (Pandas/Polars/DuckDB)
│   ├── schema/                # Schema versioning, contracts, migrations
│   ├── lineage/               # DAG lineage graph
│   ├── observability/         # Metrics, drift detection, anomalies
│   ├── pipeline/              # Builder, lifecycle, backfill/replay
│   └── governance/            # Audit logging
├── registry/
│   └── model_registry.py      # Model versioning & promotion
├── quantization/
│   └── pipeline.py            # INT8, INT4, AWQ, GPTQ, GGUF, ONNX
├── governance/
│   ├── cost.py                # Pre-launch cost estimation
│   ├── quotas.py              # GPU quota enforcement
│   ├── policies.py            # RBAC policy engine
│   └── budget.py              # Hard budget limits
├── notebook/
│   ├── editor.py              # Programmatic .ipynb builder
│   └── exporter.py            # Export to .py / .html / .md
└── api/
    ├── app.py                 # FastAPI application factory
    └── routes/                # REST endpoints per module
```

---

## Development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint & format
make lint
make format

# Type check
mypy clickml_pro/
```

---

## Environment Variables

All settings use the `CLICKML_` prefix. See [.env.example](.env.example) for the full list.

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CLICKML_ENV` | `development` | Environment name |
| `CLICKML_DATA_DIR` | `~/.clickml` | Data storage directory |
| `CLICKML_LOG_LEVEL` | `INFO` | Logging level |
| `CLICKML_BUDGET_LIMIT_USD` | `500` | Default budget limit |
| `CLICKML_REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `CLICKML_DATABASE_URL` | `sqlite:///clickml.db` | Database URL |

---

## License

MIT

---

Built with ❤️ by the ClickML team.
