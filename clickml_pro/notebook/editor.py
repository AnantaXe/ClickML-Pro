"""
Programmatic Jupyter notebook editor.

Allows ClickML-Pro to build, modify, and inspect .ipynb notebooks in
code — useful for auto-generating experiment notebooks, appending
results, or templating training pipelines as notebooks.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Notebook document structure ──────────────────────────────────────────

NBFORMAT_VERSION = 4
NBFORMAT_MINOR = 5


def _new_cell(cell_type: str, source: str, **kwargs: Any) -> dict[str, Any]:
    """Create a single notebook cell dict."""
    cell: dict[str, Any] = {
        "cell_type": cell_type,
        "metadata": kwargs.get("metadata", {}),
        "source": source.splitlines(keepends=True),
    }
    if cell_type == "code":
        cell["execution_count"] = kwargs.get("execution_count", None)
        cell["outputs"] = kwargs.get("outputs", [])
    return cell


class NotebookEditor:
    """Build and edit Jupyter notebooks programmatically.

    Example
    -------
    >>> nb = NotebookEditor()
    >>> nb.add_markdown("# My Experiment")
    >>> nb.add_code("import clickml_pro")
    >>> nb.save("experiment.ipynb")
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.cells: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
        }
        if path is not None:
            self.load(path)

    # ── Cell manipulation ───────────────────────────────────────────────

    def add_code(self, source: str, **kwargs: Any) -> "NotebookEditor":
        """Append a code cell."""
        self.cells.append(_new_cell("code", source, **kwargs))
        return self

    def add_markdown(self, source: str) -> "NotebookEditor":
        """Append a markdown cell."""
        self.cells.append(_new_cell("markdown", source))
        return self

    def add_raw(self, source: str) -> "NotebookEditor":
        """Append a raw cell."""
        self.cells.append(_new_cell("raw", source))
        return self

    def insert_cell(self, index: int, cell_type: str, source: str, **kwargs: Any) -> "NotebookEditor":
        """Insert a cell at a specific position."""
        self.cells.insert(index, _new_cell(cell_type, source, **kwargs))
        return self

    def remove_cell(self, index: int) -> "NotebookEditor":
        """Remove cell at index."""
        if 0 <= index < len(self.cells):
            self.cells.pop(index)
        return self

    def replace_cell(self, index: int, cell_type: str, source: str, **kwargs: Any) -> "NotebookEditor":
        """Replace the cell at *index* with a new one."""
        if 0 <= index < len(self.cells):
            self.cells[index] = _new_cell(cell_type, source, **kwargs)
        return self

    def clear(self) -> "NotebookEditor":
        """Remove all cells."""
        self.cells.clear()
        return self

    # ── I/O ─────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return the notebook as an nbformat-4 dict."""
        return {
            "nbformat": NBFORMAT_VERSION,
            "nbformat_minor": NBFORMAT_MINOR,
            "metadata": self.metadata,
            "cells": self.cells,
        }

    def to_json(self, indent: int = 1) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path) -> Path:
        """Write notebook to disk as .ipynb."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        logger.info("Notebook saved → %s  (%d cells)", path, len(self.cells))
        return path

    def load(self, path: str | Path) -> "NotebookEditor":
        """Load an existing .ipynb file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.cells = data.get("cells", [])
        self.metadata = data.get("metadata", self.metadata)
        logger.info("Notebook loaded ← %s  (%d cells)", path, len(self.cells))
        return self

    # ── Convenience builders ────────────────────────────────────────────

    @classmethod
    def from_training_config(cls, config: dict[str, Any]) -> "NotebookEditor":
        """Auto-generate a notebook that reproduces a training run."""
        nb = cls()
        nb.add_markdown("# ClickML-Pro Training Notebook\n\nAuto-generated.")
        nb.add_code("# Install dependencies\n!pip install clickml-pro[training] -q")
        nb.add_code(
            "import clickml_pro\n"
            "from clickml_pro.training.manager import TrainingManager\n"
            "import yaml\n"
        )
        nb.add_code(
            f"config = {json.dumps(config, indent=2)}"
        )
        nb.add_code(
            "manager = TrainingManager()\n"
            "result = manager.run(config)\n"
            "print(result)"
        )
        nb.add_markdown("## Results\n\n_Run the cells above to populate results._")
        return nb

    @classmethod
    def from_pipeline_config(cls, config: dict[str, Any]) -> "NotebookEditor":
        """Auto-generate a notebook for a data pipeline."""
        nb = cls()
        nb.add_markdown("# ClickML-Pro Data Pipeline Notebook")
        nb.add_code("!pip install clickml-pro[data] -q")
        nb.add_code(
            "from clickml_pro.data.pipeline.builder import PipelineBuilder\n"
            "import json\n"
        )
        nb.add_code(f"config = {json.dumps(config, indent=2)}")
        nb.add_code(
            "builder = PipelineBuilder()\n"
            "result = builder.execute(config)\n"
            "print(json.dumps(result, indent=2, default=str))"
        )
        return nb

    # ── Introspection ───────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.cells)

    def __repr__(self) -> str:
        return f"NotebookEditor(cells={len(self.cells)})"
