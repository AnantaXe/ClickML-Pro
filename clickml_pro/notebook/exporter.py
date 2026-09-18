"""
Notebook exporter — convert .ipynb to .py, .html, or .md.

Uses nbconvert when available, otherwise provides lightweight
built-in fallbacks for .py and .md.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class NotebookExporter:
    """Export Jupyter notebooks to various formats."""

    # ── public API ──────────────────────────────────────────────────────

    def export(self, source: str | Path, fmt: str = "python", output: str | Path | None = None) -> Path:
        """Export a .ipynb notebook.

        Parameters
        ----------
        source : path to .ipynb file, or already-parsed dict
        fmt    : "python" | "html" | "markdown" | "script"
        output : destination path (auto-derived if None)
        """
        source = Path(source)
        nb_data = json.loads(source.read_text(encoding="utf-8"))

        fmt = fmt.lower().strip()
        if fmt in ("python", "py", "script"):
            return self._export_python(nb_data, source, output)
        elif fmt in ("html",):
            return self._export_html(nb_data, source, output)
        elif fmt in ("markdown", "md"):
            return self._export_markdown(nb_data, source, output)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

    # ── Python (.py) ────────────────────────────────────────────────────

    def _export_python(
        self, nb: dict[str, Any], source: Path, output: str | Path | None
    ) -> Path:
        output = Path(output) if output else source.with_suffix(".py")
        lines: list[str] = [
            "# -*- coding: utf-8 -*-",
            f'"""Exported from {source.name} by ClickML-Pro."""\n',
        ]

        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))
            if cell["cell_type"] == "code":
                lines.append(f"\n# %%\n{src}\n")
            elif cell["cell_type"] == "markdown":
                commented = "\n".join(f"# {l}" for l in src.splitlines())
                lines.append(f"\n# %% [markdown]\n{commented}\n")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Exported Python script → %s", output)
        return output

    # ── HTML ────────────────────────────────────────────────────────────

    def _export_html(
        self, nb: dict[str, Any], source: Path, output: str | Path | None
    ) -> Path:
        output = Path(output) if output else source.with_suffix(".html")

        # Try nbconvert first
        try:
            import nbconvert  # type: ignore
            from nbformat import reads as nb_reads  # type: ignore

            nb_node = nb_reads(json.dumps(nb), as_version=4)
            html_exporter = nbconvert.HTMLExporter()
            body, _resources = html_exporter.from_notebook_node(nb_node)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(body, encoding="utf-8")
            logger.info("Exported HTML (nbconvert) → %s", output)
            return output
        except ImportError:
            pass

        # Lightweight fallback
        parts = [
            "<html><head><meta charset='utf-8'><title>ClickML Notebook</title>",
            "<style>body{font-family:sans-serif;max-width:900px;margin:auto;padding:2rem}",
            "pre{background:#f5f5f5;padding:1rem;border-radius:4px;overflow-x:auto}",
            ".md{color:#333}.code{color:#1a1a2e}</style></head><body>",
        ]

        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))
            if cell["cell_type"] == "markdown":
                # Minimal markdown → html (just wrap in div)
                parts.append(f'<div class="md">{_basic_md(src)}</div>')
            elif cell["cell_type"] == "code":
                escaped = src.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(f'<pre class="code">{escaped}</pre>')

        parts.append("</body></html>")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(parts), encoding="utf-8")
        logger.info("Exported HTML (builtin) → %s", output)
        return output

    # ── Markdown ────────────────────────────────────────────────────────

    def _export_markdown(
        self, nb: dict[str, Any], source: Path, output: str | Path | None
    ) -> Path:
        output = Path(output) if output else source.with_suffix(".md")

        parts: list[str] = [f"<!-- Exported from {source.name} by ClickML-Pro -->\n"]

        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))
            if cell["cell_type"] == "markdown":
                parts.append(src + "\n")
            elif cell["cell_type"] == "code":
                parts.append(f"```python\n{src}\n```\n")

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(parts), encoding="utf-8")
        logger.info("Exported Markdown → %s", output)
        return output


# ── helpers ─────────────────────────────────────────────────────────────


def _basic_md(text: str) -> str:
    """Super-minimal markdown → HTML (headers and paragraphs only)."""
    import re

    lines = text.split("\n")
    html_lines: list[str] = []
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{m.group(2)}</h{level}>")
        elif line.strip():
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)
