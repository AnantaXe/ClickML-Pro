"""Notebook API routes — CRUD, execute cells, export notebooks."""

from __future__ import annotations

import uuid
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter()

# ── In-memory notebook store ────────────────────────────────────────────
_notebooks: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_cell(cell_type: str = "code", source: str = "", outputs: list | None = None) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "cell_type": cell_type,
        "source": source,
        "outputs": outputs or [],
        "execution_count": None,
        "metadata": {},
    }


def _new_notebook(name: str = "Untitled") -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "created_at": _now(),
        "updated_at": _now(),
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"},
        },
        "cells": [
            _make_cell("markdown", "# New Notebook\n\nCreated by ClickML Pro"),
            _make_cell("code", ""),
        ],
    }


# ── List notebooks ─────────────────────────────────────────────────────
@router.get("/list")
async def list_notebooks() -> dict:
    return {
        "notebooks": [
            {"id": nb["id"], "name": nb["name"], "created_at": nb["created_at"], "updated_at": nb["updated_at"], "cell_count": len(nb["cells"])}
            for nb in _notebooks.values()
        ]
    }


# ── Create notebook ────────────────────────────────────────────────────
class CreateNotebookRequest(BaseModel):
    name: str = "Untitled"


@router.post("/create")
async def create_notebook(req: CreateNotebookRequest) -> dict:
    nb = _new_notebook(req.name)
    _notebooks[nb["id"]] = nb
    return {"notebook": nb}


# ── Get notebook ───────────────────────────────────────────────────────
@router.get("/get/{notebook_id}")
async def get_notebook(notebook_id: str) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    return {"notebook": nb}


# ── Save notebook ──────────────────────────────────────────────────────
class SaveNotebookRequest(BaseModel):
    name: str | None = None
    cells: list[dict[str, Any]] = Field(default_factory=list)


@router.put("/save/{notebook_id}")
async def save_notebook(notebook_id: str, req: SaveNotebookRequest) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    if req.name is not None:
        nb["name"] = req.name
    nb["cells"] = req.cells
    nb["updated_at"] = _now()
    return {"status": "saved", "notebook": nb}


# ── Delete notebook ────────────────────────────────────────────────────
@router.delete("/delete/{notebook_id}")
async def delete_notebook(notebook_id: str) -> dict:
    if notebook_id not in _notebooks:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    del _notebooks[notebook_id]
    return {"status": "deleted"}


# ── Add cell ───────────────────────────────────────────────────────────
class AddCellRequest(BaseModel):
    cell_type: str = "code"
    source: str = ""
    index: int | None = None


@router.post("/cell/add/{notebook_id}")
async def add_cell(notebook_id: str, req: AddCellRequest) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    cell = _make_cell(req.cell_type, req.source)
    if req.index is not None and 0 <= req.index <= len(nb["cells"]):
        nb["cells"].insert(req.index, cell)
    else:
        nb["cells"].append(cell)
    nb["updated_at"] = _now()
    return {"cell": cell}


# ── Delete cell ────────────────────────────────────────────────────────
@router.delete("/cell/delete/{notebook_id}/{cell_id}")
async def delete_cell(notebook_id: str, cell_id: str) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    nb["cells"] = [c for c in nb["cells"] if c["id"] != cell_id]
    nb["updated_at"] = _now()
    return {"status": "deleted"}


# ── Move cell ──────────────────────────────────────────────────────────
class MoveCellRequest(BaseModel):
    to_index: int


@router.post("/cell/move/{notebook_id}/{cell_id}")
async def move_cell(notebook_id: str, cell_id: str, req: MoveCellRequest) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    idx = next((i for i, c in enumerate(nb["cells"]) if c["id"] == cell_id), None)
    if idx is None:
        raise HTTPException(404, f"Cell {cell_id} not found")
    cell = nb["cells"].pop(idx)
    to = max(0, min(req.to_index, len(nb["cells"])))
    nb["cells"].insert(to, cell)
    nb["updated_at"] = _now()
    return {"status": "moved"}


# ── Execute cell ───────────────────────────────────────────────────────
_exec_counter: dict[str, int] = {}


class ExecuteCellRequest(BaseModel):
    source: str


@router.post("/cell/execute/{notebook_id}/{cell_id}")
async def execute_cell(notebook_id: str, cell_id: str, req: ExecuteCellRequest) -> dict:
    """Execute a code cell in a subprocess."""
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")

    cell = next((c for c in nb["cells"] if c["id"] == cell_id), None)
    if not cell:
        raise HTTPException(404, f"Cell {cell_id} not found")

    if cell["cell_type"] != "code":
        return {"outputs": [], "execution_count": None}

    count = _exec_counter.get(notebook_id, 0) + 1
    _exec_counter[notebook_id] = count

    source = req.source.strip()
    cell["source"] = source
    outputs: list[dict] = []

    if not source:
        cell["outputs"] = outputs
        cell["execution_count"] = count
        nb["updated_at"] = _now()
        return {"outputs": outputs, "execution_count": count}

    try:
        result = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.cwd()),
        )
        if result.stdout.strip():
            outputs.append({"output_type": "stream", "name": "stdout", "text": result.stdout})
        if result.stderr.strip():
            outputs.append({"output_type": "stream", "name": "stderr", "text": result.stderr})
        if result.returncode != 0 and not any(o.get("name") == "stderr" for o in outputs):
            outputs.append({"output_type": "error", "ename": "ProcessError", "evalue": f"Exit code {result.returncode}", "traceback": []})
    except subprocess.TimeoutExpired:
        outputs.append({"output_type": "error", "ename": "TimeoutError", "evalue": "Cell execution timed out (30s)", "traceback": []})
    except Exception as exc:
        outputs.append({"output_type": "error", "ename": type(exc).__name__, "evalue": str(exc), "traceback": traceback.format_exception(exc)})

    cell["outputs"] = outputs
    cell["execution_count"] = count
    nb["updated_at"] = _now()
    return {"outputs": outputs, "execution_count": count}


# ── Execute all ────────────────────────────────────────────────────────
@router.post("/execute-all/{notebook_id}")
async def execute_all(notebook_id: str) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    results = []
    for cell in nb["cells"]:
        if cell["cell_type"] == "code" and cell["source"].strip():
            req = ExecuteCellRequest(source=cell["source"])
            r = await execute_cell(notebook_id, cell["id"], req)
            results.append({"cell_id": cell["id"], **r})
    return {"results": results}


# ── Generate from template ─────────────────────────────────────────────
class GenerateNotebookRequest(BaseModel):
    template: str = "training"
    config: dict[str, Any] = Field(default_factory=dict)


@router.post("/generate")
async def generate_notebook(req: GenerateNotebookRequest) -> dict:
    from clickml_pro.notebook.editor import NotebookEditor

    if req.template == "training":
        nb_editor = NotebookEditor.from_training_config(req.config)
    elif req.template == "pipeline":
        nb_editor = NotebookEditor.from_pipeline_config(req.config)
    else:
        raise HTTPException(400, f"Unknown template: {req.template}")
    return {"notebook": nb_editor.to_dict()}


# ── Export ──────────────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    format: str = "python"


@router.post("/export")
async def export_notebook_file(req: ExportRequest, file: UploadFile = File(...)) -> FileResponse:
    from clickml_pro.notebook.exporter import NotebookExporter

    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "notebook.ipynb"
        src.write_bytes(await file.read())
        exporter = NotebookExporter()
        output_path = exporter.export(src, fmt=req.format)
        return FileResponse(path=str(output_path), filename=output_path.name, media_type="application/octet-stream")


# ── Download as .ipynb ──────────────────────────────────────────────────
@router.get("/download/{notebook_id}")
async def download_notebook(notebook_id: str) -> dict:
    nb = _notebooks.get(notebook_id)
    if not nb:
        raise HTTPException(404, f"Notebook {notebook_id} not found")
    ipynb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": nb["metadata"],
        "cells": [
            {
                "cell_type": c["cell_type"],
                "source": c["source"].splitlines(keepends=True) if isinstance(c["source"], str) else c["source"],
                "metadata": c.get("metadata", {}),
                **({"execution_count": c.get("execution_count"), "outputs": c.get("outputs", [])} if c["cell_type"] == "code" else {}),
            }
            for c in nb["cells"]
        ],
    }
    return {"ipynb": ipynb}
