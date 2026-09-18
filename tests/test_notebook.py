"""Tests for notebook editor and exporter."""

import json
import pytest
from pathlib import Path
from clickml_pro.notebook.editor import NotebookEditor
from clickml_pro.notebook.exporter import NotebookExporter


class TestNotebookEditor:
    def test_add_cells(self):
        nb = NotebookEditor()
        nb.add_markdown("# Title")
        nb.add_code("print('hello')")
        nb.add_raw("raw text")

        assert len(nb) == 3
        assert nb.cells[0]["cell_type"] == "markdown"
        assert nb.cells[1]["cell_type"] == "code"
        assert nb.cells[2]["cell_type"] == "raw"

    def test_save_and_load(self, tmp_path: Path):
        nb = NotebookEditor()
        nb.add_markdown("# Test")
        nb.add_code("x = 1")

        path = nb.save(tmp_path / "test.ipynb")
        assert path.exists()

        nb2 = NotebookEditor(path)
        assert len(nb2) == 2

    def test_to_dict_format(self):
        nb = NotebookEditor()
        nb.add_code("1 + 1")
        data = nb.to_dict()

        assert data["nbformat"] == 4
        assert "cells" in data
        assert "metadata" in data

    def test_from_training_config(self):
        nb = NotebookEditor.from_training_config({
            "base_model": "bert-base",
            "mode": "finetune",
        })
        assert len(nb) > 0
        # Should have markdown and code cells
        types = {c["cell_type"] for c in nb.cells}
        assert "markdown" in types
        assert "code" in types

    def test_remove_cell(self):
        nb = NotebookEditor()
        nb.add_code("a").add_code("b").add_code("c")
        nb.remove_cell(1)
        assert len(nb) == 2

    def test_clear(self):
        nb = NotebookEditor()
        nb.add_code("x").add_code("y")
        nb.clear()
        assert len(nb) == 0


class TestNotebookExporter:
    def test_export_python(self, tmp_path: Path):
        nb = NotebookEditor()
        nb.add_markdown("# Hello")
        nb.add_code("print(42)")
        ipynb = nb.save(tmp_path / "test.ipynb")

        exporter = NotebookExporter()
        py_path = exporter.export(ipynb, fmt="python")

        assert py_path.suffix == ".py"
        content = py_path.read_text()
        assert "print(42)" in content

    def test_export_markdown(self, tmp_path: Path):
        nb = NotebookEditor()
        nb.add_markdown("# Hello")
        nb.add_code("x = 1")
        ipynb = nb.save(tmp_path / "test.ipynb")

        exporter = NotebookExporter()
        md_path = exporter.export(ipynb, fmt="markdown")

        assert md_path.suffix == ".md"
        content = md_path.read_text()
        assert "# Hello" in content
        assert "```python" in content

    def test_export_html(self, tmp_path: Path):
        nb = NotebookEditor()
        nb.add_markdown("# Hello")
        nb.add_code("x = 1")
        ipynb = nb.save(tmp_path / "test.ipynb")

        exporter = NotebookExporter()
        html_path = exporter.export(ipynb, fmt="html")

        assert html_path.suffix == ".html"
        content = html_path.read_text()
        assert "<html>" in content.lower() or "<!doctype" in content.lower()
