"""ClickML Pro CLI — the main entry point for the ``clickml`` command."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="clickml-pro")
def main() -> None:
    """ClickML Pro — Enterprise MLOps & Data Engineering platform."""


# ── Server ──────────────────────────────────────────────────────────────────


@main.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
@click.option("--workers", default=1, type=int, help="Number of workers")
def serve(host: str, port: int, reload: bool, workers: int) -> None:
    """Start the ClickML Pro API server."""
    import uvicorn

    console.print(f"[bold green]🚀 ClickML Pro[/] starting on {host}:{port}")
    uvicorn.run(
        "clickml_pro.api.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )


# ── UI Dashboard ────────────────────────────────────────────────────────────


@main.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--dev", is_flag=True, help="Start Vite dev server (instead of serving built assets)")
def ui(host: str, port: int, dev: bool) -> None:
    """Launch the ClickML Pro dashboard.

    By default, serves the production build via the FastAPI server.
    Use --dev to start the Vite dev server with hot-reload (requires npm).
    """
    import subprocess
    import sys
    from pathlib import Path

    dashboard_dir = Path(__file__).resolve().parent / "ui" / "dashboard"

    if dev:
        console.print(f"[bold cyan]⚡ ClickML Pro Dashboard[/] (dev mode) — Vite on http://localhost:5173")
        console.print("[dim]API server must be running separately: clickml serve[/]")
        node_modules = dashboard_dir / "node_modules"
        if not node_modules.exists():
            console.print("[yellow]Installing npm dependencies…[/]")
            subprocess.run(["npm", "install"], cwd=str(dashboard_dir), check=True)
        subprocess.run(["npm", "run", "dev"], cwd=str(dashboard_dir))
    else:
        dist_dir = dashboard_dir / "dist"
        if not dist_dir.is_dir():
            console.print("[yellow]Dashboard not built yet. Building…[/]")
            node_modules = dashboard_dir / "node_modules"
            if not node_modules.exists():
                subprocess.run(["npm", "install"], cwd=str(dashboard_dir), check=True)
            subprocess.run(["npm", "run", "build"], cwd=str(dashboard_dir), check=True)

        console.print(f"[bold cyan]⚡ ClickML Pro Dashboard[/] on http://{host}:{port}")
        import uvicorn
        uvicorn.run("clickml_pro.api.app:app", host=host, port=port)


# ── Training ────────────────────────────────────────────────────────────────


@main.group()
def train() -> None:
    """Model training commands."""


@train.command("run")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Validate config without executing")
def train_run(config_path: str, dry_run: bool) -> None:
    """Launch a training job from a YAML config file."""
    from clickml_pro.core.yaml_parser import load_job_config
    from clickml_pro.training.manager import TrainingManager

    config = load_job_config(config_path)
    if dry_run:
        console.print("[yellow]Dry run — config is valid.[/]")
        console.print(config)
        return

    manager = TrainingManager()
    job = manager.submit(config)
    console.print(f"[green]Job submitted:[/] {job.job_id}")


@train.command("list")
def train_list() -> None:
    """List recent training jobs."""
    from clickml_pro.training.manager import TrainingManager

    manager = TrainingManager()
    jobs = manager.list_jobs()
    if not jobs:
        console.print("[dim]No jobs found.[/dim]")
        return
    for j in jobs:
        console.print(f"  {j.job_id}  {j.status}  {j.mode}  {j.created_at}")


# ── Registry ────────────────────────────────────────────────────────────────


@main.group()
def registry() -> None:
    """Model registry commands."""


@registry.command("list")
def registry_list() -> None:
    """List registered models."""
    from clickml_pro.registry.model_registry import ModelRegistry

    reg = ModelRegistry()
    for m in reg.list_models():
        console.print(f"  {m.name}  v{m.version}  [{m.format}]  {m.status}")


@registry.command("info")
@click.argument("model_name")
def registry_info(model_name: str) -> None:
    """Show details of a registered model."""
    from clickml_pro.registry.model_registry import ModelRegistry

    reg = ModelRegistry()
    info = reg.get_model(model_name)
    if info is None:
        console.print(f"[red]Model '{model_name}' not found.[/]")
        return
    console.print(info)


# ── Data ────────────────────────────────────────────────────────────────────


@main.group()
def data() -> None:
    """Data engineering commands."""


@data.command("validate")
@click.argument("schema_path", type=click.Path(exists=True))
def data_validate(schema_path: str) -> None:
    """Validate a dataset schema contract."""
    from clickml_pro.data.schema.contracts import validate_contract

    result = validate_contract(schema_path)
    if result.valid:
        console.print("[green]Schema contract is valid.[/]")
    else:
        console.print("[red]Validation errors:[/]")
        for err in result.errors:
            console.print(f"  - {err}")


@data.command("lineage")
@click.argument("dataset_name")
def data_lineage(dataset_name: str) -> None:
    """Show lineage graph for a dataset."""
    from clickml_pro.data.lineage.graph import LineageGraph

    graph = LineageGraph()
    tree = graph.get_upstream(dataset_name)
    console.print(tree)


# ── Quantization ────────────────────────────────────────────────────────────


@main.group()
def quantize() -> None:
    """Model quantization commands."""


@quantize.command("run")
@click.argument("config_path", type=click.Path(exists=True))
def quantize_run(config_path: str) -> None:
    """Run a quantization job from YAML config."""
    from clickml_pro.core.yaml_parser import load_job_config
    from clickml_pro.quantization.pipeline import QuantizationPipeline

    config = load_job_config(config_path)
    pipeline = QuantizationPipeline()
    result = pipeline.run(config)
    console.print(f"[green]Quantization complete:[/] {result.output_path}")


# ── Notebook ────────────────────────────────────────────────────────────────


@main.group()
def notebook() -> None:
    """Notebook editing & export commands."""


@notebook.command("export")
@click.argument("source", type=click.Path(exists=True))
@click.option("--format", "fmt", default="ipynb", type=click.Choice(["ipynb", "py", "html"]))
@click.option("--output", "-o", default=None, help="Output path")
def notebook_export(source: str, fmt: str, output: str | None) -> None:
    """Export a ClickML notebook/config to Jupyter, Python, or HTML."""
    from clickml_pro.notebook.exporter import NotebookExporter

    exporter = NotebookExporter()
    out = exporter.export(source, fmt=fmt, output_path=output)
    console.print(f"[green]Exported →[/] {out}")


# ── Governance ──────────────────────────────────────────────────────────────


@main.group()
def governance() -> None:
    """Cost, governance, and safety commands."""


@governance.command("estimate")
@click.argument("config_path", type=click.Path(exists=True))
def governance_estimate(config_path: str) -> None:
    """Estimate cost for a training job before launch."""
    from clickml_pro.core.yaml_parser import load_job_config
    from clickml_pro.governance.cost import CostEstimator

    config = load_job_config(config_path)
    estimator = CostEstimator()
    est = estimator.estimate(config)
    console.print(f"  Estimated GPU hours : {est.gpu_hours:.1f}")
    console.print(f"  Estimated cost      : ${est.cost_usd:.2f}")
    console.print(f"  Budget remaining    : ${est.budget_remaining:.2f}")


if __name__ == "__main__":
    main()
