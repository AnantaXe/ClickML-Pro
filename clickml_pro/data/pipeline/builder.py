"""
Pipeline builder — construct data pipelines from YAML configs.

A pipeline is a DAG of data transformations: source → transforms → sink.
This module compiles pipeline configs into executable jobs and manages
their lifecycle.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from clickml_pro.data.engine import get_engine
from clickml_pro.data.observability.metrics import MetricsCollector, MetricsStore
from clickml_pro.data.lineage.graph import LineageGraph, LineageNode

logger = logging.getLogger(__name__)


class PipelineStep(BaseModel):
    """A single step in a data pipeline."""

    name: str = ""
    type: str = ""           # source, transform, sink
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineDefinition(BaseModel):
    """Full pipeline definition compiled from YAML."""

    name: str = ""
    engine: str = "pandas"
    source: dict[str, Any] = Field(default_factory=dict)
    transformations: list[dict[str, Any]] = Field(default_factory=list)
    sink: dict[str, Any] = Field(default_factory=dict)
    schedule: str | None = None
    owner: str = ""
    tags: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Result of executing a pipeline."""

    pipeline: str = ""
    status: str = "completed"
    rows_read: int = 0
    rows_written: int = 0
    runtime_seconds: float = 0.0
    output_path: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class PipelineBuilder:
    """Build and execute data pipelines."""

    def __init__(self) -> None:
        self.metrics_collector = MetricsCollector()
        self.metrics_store = MetricsStore()
        self.lineage_graph = LineageGraph()

    def execute(self, config: dict[str, Any]) -> dict[str, Any]:
        """Execute a pipeline from a config dict."""
        pipeline = self._parse_config(config)
        result = self._run(pipeline)
        return {
            "metrics": result.model_dump(),
            "artifacts": [result.output_path] if result.output_path else [],
        }

    def _parse_config(self, config: dict[str, Any]) -> PipelineDefinition:
        """Parse a raw config dict into a PipelineDefinition."""
        dp = config.get("data_pipeline", config)
        return PipelineDefinition(
            name=config.get("name", "unnamed-pipeline"),
            engine=dp.get("engine", "pandas"),
            source=dp.get("source", {}),
            transformations=dp.get("transformations", []),
            sink=dp.get("sink", {}),
            schedule=dp.get("schedule"),
            owner=config.get("metadata", {}).get("owner", ""),
        )

    def _run(self, pipeline: PipelineDefinition) -> PipelineResult:
        """Execute a parsed pipeline definition."""
        start = time.time()
        engine = get_engine(pipeline.engine)

        logger.info("Pipeline '%s' starting (engine=%s)", pipeline.name, pipeline.engine)

        # Read
        data = engine.read(pipeline.source)
        rows_read = len(data) if hasattr(data, "__len__") else 0

        # Collect pre-transform metrics
        try:
            pre_metrics = self.metrics_collector.collect(f"{pipeline.name}:input", data)
            self.metrics_store.record(pre_metrics)
        except Exception as exc:
            logger.warning("Could not collect input metrics: %s", exc)

        # Transform
        data = engine.transform(data, pipeline.transformations)

        # Write
        output_path = ""
        if pipeline.sink:
            output_path = engine.write(data, pipeline.sink)

        rows_written = len(data) if hasattr(data, "__len__") else 0
        runtime = time.time() - start

        # Collect post-transform metrics
        try:
            post_metrics = self.metrics_collector.collect(f"{pipeline.name}:output", data)
            self.metrics_store.record(post_metrics)
        except Exception as exc:
            logger.warning("Could not collect output metrics: %s", exc)

        # Record lineage
        try:
            self.lineage_graph.add_node(LineageNode(
                id=pipeline.name,
                node_type="pipeline",
                name=pipeline.name,
            ))
            if pipeline.source.get("path"):
                self.lineage_graph.add_node(LineageNode(
                    id=pipeline.source["path"],
                    node_type="dataset",
                    name=pipeline.source["path"],
                ))
                self.lineage_graph.add_derivation(pipeline.source["path"], pipeline.name)
            if output_path:
                self.lineage_graph.add_node(LineageNode(
                    id=output_path,
                    node_type="dataset",
                    name=output_path,
                ))
                self.lineage_graph.add_production(pipeline.name, output_path)
        except Exception as exc:
            logger.warning("Could not record lineage: %s", exc)

        logger.info(
            "Pipeline '%s' completed: %d→%d rows in %.1fs",
            pipeline.name, rows_read, rows_written, runtime,
        )

        return PipelineResult(
            pipeline=pipeline.name,
            rows_read=rows_read,
            rows_written=rows_written,
            runtime_seconds=round(runtime, 2),
            output_path=output_path,
        )
