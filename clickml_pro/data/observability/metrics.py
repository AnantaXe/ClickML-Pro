"""
Data observability metrics — row counts, freshness, null ratios, etc.

Observability as a first-class feature: pipelines fail silently, so we
continuously compute and store health metrics for every dataset.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DatasetMetrics(BaseModel):
    """Point-in-time health metrics for a dataset."""

    dataset: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    row_count: int = 0
    column_count: int = 0
    null_ratios: dict[str, float] = Field(default_factory=dict)     # column → null ratio (0–1)
    unique_ratios: dict[str, float] = Field(default_factory=dict)   # column → unique ratio
    freshness_seconds: float = 0.0    # seconds since last update
    size_bytes: int = 0
    schema_version: int = 0


class MetricsCollector:
    """Collect observability metrics from data frames."""

    def collect(self, dataset_name: str, data: Any) -> DatasetMetrics:
        """Compute metrics for a pandas or polars DataFrame."""
        try:
            import pandas as pd

            if isinstance(data, pd.DataFrame):
                return self._collect_pandas(dataset_name, data)
        except ImportError:
            pass

        try:
            import polars as pl

            if isinstance(data, pl.DataFrame):
                return self._collect_polars(dataset_name, data)
        except ImportError:
            pass

        raise TypeError(f"Unsupported data type: {type(data)}")

    def _collect_pandas(self, name: str, df: Any) -> DatasetMetrics:
        import pandas as pd

        row_count = len(df)
        col_count = len(df.columns)

        null_ratios = {}
        unique_ratios = {}

        for col in df.columns:
            null_ratios[col] = round(df[col].isna().mean(), 4)
            unique_ratios[col] = round(df[col].nunique() / max(row_count, 1), 4)

        return DatasetMetrics(
            dataset=name,
            row_count=row_count,
            column_count=col_count,
            null_ratios=null_ratios,
            unique_ratios=unique_ratios,
            size_bytes=df.memory_usage(deep=True).sum(),
        )

    def _collect_polars(self, name: str, df: Any) -> DatasetMetrics:
        row_count = df.height
        col_count = df.width

        null_ratios = {}
        unique_ratios = {}

        for col in df.columns:
            series = df[col]
            null_ratios[col] = round(series.null_count() / max(row_count, 1), 4)
            unique_ratios[col] = round(series.n_unique() / max(row_count, 1), 4)

        return DatasetMetrics(
            dataset=name,
            row_count=row_count,
            column_count=col_count,
            null_ratios=null_ratios,
            unique_ratios=unique_ratios,
        )


class MetricsStore:
    """Store and query historical dataset metrics."""

    def __init__(self) -> None:
        self._history: dict[str, list[DatasetMetrics]] = {}

    def record(self, metrics: DatasetMetrics) -> None:
        if metrics.dataset not in self._history:
            self._history[metrics.dataset] = []
        self._history[metrics.dataset].append(metrics)
        logger.info(
            "Metrics recorded: %s — rows=%d nulls=%s",
            metrics.dataset,
            metrics.row_count,
            {k: v for k, v in metrics.null_ratios.items() if v > 0},
        )

    def get_latest(self, dataset: str) -> DatasetMetrics | None:
        history = self._history.get(dataset, [])
        return history[-1] if history else None

    def get_history(self, dataset: str, limit: int = 100) -> list[DatasetMetrics]:
        return self._history.get(dataset, [])[-limit:]

    def get_all_latest(self) -> dict[str, DatasetMetrics]:
        return {ds: entries[-1] for ds, entries in self._history.items() if entries}
