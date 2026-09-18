"""
Airflow-integrated ETL pipeline API routes.

Provides a graphical DAG builder / viewer with block-level configuration
for Extract, Transform, and Load tasks. Each task (block) stores its own
config and can be edited independently through the UI.
"""

from __future__ import annotations

import re
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# ── In-memory DAG store ─────────────────────────────────────────────────
_dags: dict[str, dict] = {}
_dag_runs: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Task / block defaults ──────────────────────────────────────────────
TASK_TEMPLATES: dict[str, dict[str, Any]] = {
    "extract": {
        "type": "extract",
        "label": "Extract",
        "description": "Read data from a source system",
        "config": {
            "source_type": "database",
            "connection_string": "",
            "query": "",
            "file_path": "",
            "file_format": "csv",
            "batch_size": 10000,
            "incremental": False,
            "watermark_column": "",
        },
    },
    "transform": {
        "type": "transform",
        "label": "Transform",
        "description": "Apply transformations to the extracted data",
        "config": {
            "engine": "pandas",
            "operations": [],
            "drop_nulls": False,
            "deduplicate": False,
            "rename_columns": {},
            "filter_expression": "",
            "custom_script": "",
        },
    },
    "load": {
        "type": "load",
        "label": "Load",
        "description": "Write transformed data to a destination",
        "config": {
            "destination_type": "database",
            "connection_string": "",
            "table_name": "",
            "file_path": "",
            "file_format": "parquet",
            "write_mode": "append",
            "partition_by": [],
        },
    },
    "validate": {
        "type": "validate",
        "label": "Validate",
        "description": "Run data quality checks",
        "config": {
            "checks": [],
            "fail_on_error": True,
            "sample_size": None,
        },
    },
    "notify": {
        "type": "notify",
        "label": "Notify",
        "description": "Send notifications on task completion",
        "config": {
            "channel": "email",
            "recipients": [],
            "on_success": True,
            "on_failure": True,
            "message_template": "",
        },
    },
    "branch": {
        "type": "branch",
        "label": "Branch",
        "description": "Conditional branching based on data or status",
        "config": {
            "condition": "",
            "true_branch": "",
            "false_branch": "",
        },
    },
}


def _make_task(task_type: str, label: str | None = None, config: dict | None = None, position: dict | None = None) -> dict:
    template = TASK_TEMPLATES.get(task_type, TASK_TEMPLATES["transform"])
    return {
        "id": uuid.uuid4().hex[:8],
        "type": task_type,
        "label": label or template["label"],
        "description": template["description"],
        "config": {**template["config"], **(config or {})},
        "position": position or {"x": 0, "y": 0},
        "status": "idle",
    }


# ── Models ──────────────────────────────────────────────────────────────
class CreateDAGRequest(BaseModel):
    name: str = "my-etl-pipeline"
    description: str = ""
    schedule: str = ""  # cron expression or empty
    tags: list[str] = Field(default_factory=list)


class TaskConfig(BaseModel):
    task_type: str = "extract"
    label: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})


class AddTaskRequest(BaseModel):
    task: TaskConfig


class UpdateTaskConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None
    position: dict[str, float] | None = None


class AddEdgeRequest(BaseModel):
    source_id: str
    target_id: str


# ── DAG CRUD ────────────────────────────────────────────────────────────
@router.get("/dags")
async def list_dags() -> dict:
    return {
        "dags": [
            {
                "id": d["id"],
                "name": d["name"],
                "description": d["description"],
                "schedule": d["schedule"],
                "tags": d["tags"],
                "task_count": len(d["tasks"]),
                "created_at": d["created_at"],
                "updated_at": d["updated_at"],
            }
            for d in _dags.values()
        ]
    }


@router.post("/dags")
async def create_dag(req: CreateDAGRequest) -> dict:
    dag_id = uuid.uuid4().hex[:12]
    dag = {
        "id": dag_id,
        "name": req.name,
        "description": req.description,
        "schedule": req.schedule,
        "tags": req.tags,
        "tasks": [],
        "edges": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    _dags[dag_id] = dag
    return {"dag": dag}


@router.get("/dags/{dag_id}")
async def get_dag(dag_id: str) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    return {"dag": dag}


@router.delete("/dags/{dag_id}")
async def delete_dag(dag_id: str) -> dict:
    if dag_id not in _dags:
        raise HTTPException(404, f"DAG {dag_id} not found")
    del _dags[dag_id]
    return {"status": "deleted"}


# ── Task CRUD within a DAG ─────────────────────────────────────────────
@router.post("/dags/{dag_id}/tasks")
async def add_task(dag_id: str, req: AddTaskRequest) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    task = _make_task(
        req.task.task_type,
        req.task.label,
        req.task.config,
        req.task.position,
    )
    dag["tasks"].append(task)
    dag["updated_at"] = _now()
    return {"task": task}


@router.put("/dags/{dag_id}/tasks/{task_id}")
async def update_task(dag_id: str, task_id: str, req: UpdateTaskConfigRequest) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    task = next((t for t in dag["tasks"] if t["id"] == task_id), None)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    if req.config:
        task["config"].update(req.config)
    if req.label is not None:
        task["label"] = req.label
    if req.position is not None:
        task["position"] = req.position
    dag["updated_at"] = _now()
    return {"task": task}


@router.delete("/dags/{dag_id}/tasks/{task_id}")
async def remove_task(dag_id: str, task_id: str) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    dag["tasks"] = [t for t in dag["tasks"] if t["id"] != task_id]
    dag["edges"] = [e for e in dag["edges"] if e["source"] != task_id and e["target"] != task_id]
    dag["updated_at"] = _now()
    return {"status": "deleted"}


# ── Edges between tasks ────────────────────────────────────────────────
@router.post("/dags/{dag_id}/edges")
async def add_edge(dag_id: str, req: AddEdgeRequest) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    task_ids = {t["id"] for t in dag["tasks"]}
    if req.source_id not in task_ids:
        raise HTTPException(400, f"Source task {req.source_id} not found")
    if req.target_id not in task_ids:
        raise HTTPException(400, f"Target task {req.target_id} not found")
    if req.source_id == req.target_id:
        raise HTTPException(400, "Cannot connect a task to itself")
    # Prevent duplicate edges
    existing = any(e["source"] == req.source_id and e["target"] == req.target_id for e in dag["edges"])
    if existing:
        return {"status": "already_exists"}
    edge = {"id": uuid.uuid4().hex[:8], "source": req.source_id, "target": req.target_id}
    dag["edges"].append(edge)
    dag["updated_at"] = _now()
    return {"edge": edge}


@router.delete("/dags/{dag_id}/edges/{edge_id}")
async def remove_edge(dag_id: str, edge_id: str) -> dict:
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")
    dag["edges"] = [e for e in dag["edges"] if e["id"] != edge_id]
    dag["updated_at"] = _now()
    return {"status": "deleted"}


# ── DAG run (simulate) ─────────────────────────────────────────────────
@router.post("/dags/{dag_id}/run")
async def run_dag(dag_id: str) -> dict:
    """Simulate running a DAG — executes tasks in topological order."""
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")

    run_id = uuid.uuid4().hex[:12]
    task_results = []

    # Build adjacency and in-degree for topo sort
    tasks_by_id = {t["id"]: t for t in dag["tasks"]}
    in_degree = {t["id"]: 0 for t in dag["tasks"]}
    children: dict[str, list[str]] = {t["id"]: [] for t in dag["tasks"]}
    for e in dag["edges"]:
        if e["target"] in in_degree:
            in_degree[e["target"]] += 1
        if e["source"] in children:
            children[e["source"]].append(e["target"])

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    executed = set()

    while queue:
        tid = queue.pop(0)
        if tid in executed:
            continue
        executed.add(tid)
        task = tasks_by_id.get(tid)
        if not task:
            continue

        start_time = time.time()
        task["status"] = "running"
        # Simulate execution (0.1s per task)
        time.sleep(0.05)
        task["status"] = "success"
        elapsed = time.time() - start_time

        task_results.append({
            "task_id": tid,
            "label": task["label"],
            "type": task["type"],
            "status": "success",
            "duration_ms": round(elapsed * 1000, 1),
        })

        for child_id in children.get(tid, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] <= 0:
                queue.append(child_id)

    run = {
        "run_id": run_id,
        "dag_id": dag_id,
        "status": "completed",
        "tasks": task_results,
        "started_at": _now(),
        "completed_at": _now(),
    }
    _dag_runs[run_id] = run
    return {"run": run}


# ── DAG run history ────────────────────────────────────────────────────
@router.get("/dags/{dag_id}/runs")
async def dag_run_history(dag_id: str) -> dict:
    runs = [r for r in _dag_runs.values() if r["dag_id"] == dag_id]
    return {"runs": runs}


# ── DAG export (generate Airflow Python file) ─────────────────────────
def _generate_airflow_dag(dag: dict) -> str:
    """Generate a valid Apache Airflow DAG Python file from the internal DAG."""
    name = dag["name"]
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower().strip("_")
    description = dag.get("description", "")
    schedule = dag.get("schedule", "") or None
    tags = dag.get("tags", [])

    lines: list[str] = [
        '"""',
        f"Auto-generated Airflow DAG: {name}",
        f"Generated by ClickML-Pro at {_now()}",
        '"""',
        "",
        "from airflow import DAG",
        "from airflow.operators.python import PythonOperator",
        "from datetime import datetime, timedelta",
        "",
        "",
        "default_args = {",
        "    'owner': 'clickml-pro',",
        "    'depends_on_past': False,",
        "    'start_date': datetime(2024, 1, 1),",
        "    'retries': 1,",
        "    'retry_delay': timedelta(minutes=5),",
        "    'email_on_failure': False,",
        "}",
        "",
    ]

    # Task handler functions
    for task in dag["tasks"]:
        tid = task["id"]
        ttype = task["type"]
        label = task["label"]
        config = task.get("config", {})
        fn_name = f"run_{ttype}_{tid}"

        lines.append("")
        lines.append(f"def {fn_name}(**kwargs):")
        lines.append(f'    """Handler for {label} ({ttype})."""')
        lines.append(f"    config = {config!r}")

        if ttype == "extract":
            lines.append("    source_type = config.get('source_type', 'database')")
            lines.append("    print(f'Extracting data from {source_type}')")
            lines.append("    # TODO: implement extraction logic")
            lines.append("    return config")
        elif ttype == "transform":
            lines.append("    engine = config.get('engine', 'pandas')")
            lines.append("    print(f'Transforming data with {engine}')")
            lines.append("    # TODO: implement transformation logic")
            lines.append("    return config")
        elif ttype == "load":
            lines.append("    dest = config.get('destination_type', 'database')")
            lines.append("    print(f'Loading data to {dest}')")
            lines.append("    # TODO: implement load logic")
            lines.append("    return config")
        elif ttype == "validate":
            lines.append("    checks = config.get('checks', [])")
            lines.append("    print(f'Running {len(checks)} validation checks')")
            lines.append("    # TODO: implement validation logic")
            lines.append("    return {'valid': True}")
        elif ttype == "notify":
            lines.append("    channel = config.get('channel', 'email')")
            lines.append("    print(f'Sending notification via {channel}')")
            lines.append("    # TODO: implement notification logic")
            lines.append("    return config")
        elif ttype == "branch":
            lines.append("    condition = config.get('condition', '')")
            lines.append("    print(f'Evaluating branch condition: {condition}')")
            lines.append("    # TODO: implement branching logic")
            lines.append("    return config")
        else:
            lines.append(f"    print(f'Executing task: {label}')")
            lines.append("    return config")

    # DAG definition
    schedule_str = f"'{schedule}'" if schedule else "None"
    tags_str = repr(tags) if tags else "['etl']"

    lines.append("")
    lines.append("")
    lines.append("with DAG(")
    lines.append(f"    '{safe_name}',")
    lines.append("    default_args=default_args,")
    lines.append(f"    description={description!r},")
    lines.append(f"    schedule={schedule_str},")
    lines.append("    catchup=False,")
    lines.append(f"    tags={tags_str},")
    lines.append(") as dag:")
    lines.append("")

    # Task operator declarations
    task_var_map: dict[str, str] = {}
    for task in dag["tasks"]:
        tid = task["id"]
        ttype = task["type"]
        label = task["label"]
        var_name = f"task_{ttype}_{tid}"
        task_var_map[tid] = var_name
        fn_name = f"run_{ttype}_{tid}"

        lines.append(f"    {var_name} = PythonOperator(")
        lines.append(f"        task_id='{ttype}_{tid}',")
        lines.append(f"        python_callable={fn_name},")
        lines.append(f"    )")
        lines.append("")

    # Edge dependencies
    if dag["edges"]:
        lines.append("    # Dependencies")
        for edge in dag["edges"]:
            src_var = task_var_map.get(edge["source"])
            tgt_var = task_var_map.get(edge["target"])
            if src_var and tgt_var:
                lines.append(f"    {src_var} >> {tgt_var}")
        lines.append("")

    return "\n".join(lines)


class DeployRequest(BaseModel):
    dags_dir: str | None = None


@router.get("/dags/{dag_id}/export")
async def export_dag(dag_id: str) -> dict:
    """Generate and return an Airflow DAG Python file for download."""
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")

    content = _generate_airflow_dag(dag)
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dag["name"]).lower().strip("_")
    filename = f"{safe_name}.py"

    return {
        "filename": filename,
        "content": content,
        "dag_id": dag_id,
        "dag_name": dag["name"],
    }


@router.post("/dags/{dag_id}/deploy")
async def deploy_dag(dag_id: str, req: DeployRequest | None = None) -> dict:
    """Deploy the DAG to an Apache Airflow instance by writing the DAG file."""
    dag = _dags.get(dag_id)
    if not dag:
        raise HTTPException(404, f"DAG {dag_id} not found")

    from clickml_pro.config.settings import get_settings
    settings = get_settings()

    dags_dir = Path(req.dags_dir).expanduser() if req and req.dags_dir else settings.airflow_dags_path

    # Create directory if it doesn't exist
    try:
        dags_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(500, f"Cannot create Airflow DAGs directory '{dags_dir}': {exc}")

    content = _generate_airflow_dag(dag)
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dag["name"]).lower().strip("_")
    filename = f"{safe_name}.py"
    filepath = dags_dir / filename

    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(500, f"Failed to write DAG file: {exc}")

    return {
        "status": "deployed",
        "filename": filename,
        "path": str(filepath),
        "dags_dir": str(dags_dir),
        "dag_id": dag_id,
        "dag_name": dag["name"],
        "deployed_at": _now(),
    }


# ── Task templates (for UI block palette) ──────────────────────────────
@router.get("/task-templates")
async def get_task_templates() -> dict:
    return {
        "templates": [
            {"type": k, "label": v["label"], "description": v["description"], "default_config": v["config"]}
            for k, v in TASK_TEMPLATES.items()
        ]
    }


# ── Create default ETL DAG ─────────────────────────────────────────────
@router.post("/dags/create-etl")
async def create_default_etl(req: CreateDAGRequest) -> dict:
    """Create an ETL DAG with default Extract -> Transform -> Load tasks."""
    dag_id = uuid.uuid4().hex[:12]
    extract = _make_task("extract", position={"x": 100, "y": 200})
    transform = _make_task("transform", position={"x": 400, "y": 200})
    load = _make_task("load", position={"x": 700, "y": 200})

    edges = [
        {"id": uuid.uuid4().hex[:8], "source": extract["id"], "target": transform["id"]},
        {"id": uuid.uuid4().hex[:8], "source": transform["id"], "target": load["id"]},
    ]

    dag = {
        "id": dag_id,
        "name": req.name or "ETL Pipeline",
        "description": req.description or "Extract, Transform, Load pipeline",
        "schedule": req.schedule,
        "tags": req.tags or ["etl"],
        "tasks": [extract, transform, load],
        "edges": edges,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _dags[dag_id] = dag
    return {"dag": dag}
