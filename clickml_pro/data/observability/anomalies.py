"""
Runtime anomaly detection for data pipelines.

Detects anomalies in pipeline execution metrics: runtime duration,
resource usage, data volumes, and error rates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AnomalyAlert(BaseModel):
    """An anomaly detected during pipeline execution."""

    alert_id: str = ""
    pipeline: str = ""
    metric: str = ""
    expected_value: float = 0.0
    actual_value: float = 0.0
    deviation_pct: float = 0.0
    severity: str = "warning"  # info, warning, critical
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message: str = ""


class AnomalyDetector:
    """
    Simple statistical anomaly detector based on historical baselines.

    Uses mean + N * stddev for threshold-based detection.
    """

    def __init__(self, sensitivity: float = 2.0) -> None:
        """
        Args:
            sensitivity: Number of standard deviations for anomaly threshold.
        """
        self.sensitivity = sensitivity
        self._baselines: dict[str, list[float]] = {}

    def record(self, metric_key: str, value: float) -> AnomalyAlert | None:
        """Record a metric value and check for anomalies."""
        if metric_key not in self._baselines:
            self._baselines[metric_key] = []

        history = self._baselines[metric_key]
        alert = None

        if len(history) >= 5:  # Need at least 5 data points
            import statistics

            mean = statistics.mean(history)
            stddev = statistics.stdev(history) if len(history) > 1 else 0.0

            if stddev > 0:
                z_score = abs(value - mean) / stddev
                if z_score > self.sensitivity:
                    deviation_pct = round(100 * (value - mean) / mean, 1) if mean != 0 else 0
                    alert = AnomalyAlert(
                        metric=metric_key,
                        expected_value=round(mean, 2),
                        actual_value=round(value, 2),
                        deviation_pct=deviation_pct,
                        severity="critical" if z_score > 3.0 else "warning",
                        message=(
                            f"Anomaly in '{metric_key}': "
                            f"value={value:.2f}, expected≈{mean:.2f} "
                            f"(±{stddev:.2f}), z={z_score:.1f}"
                        ),
                    )
                    logger.warning(alert.message)

        history.append(value)
        # Keep only last 100 points
        if len(history) > 100:
            self._baselines[metric_key] = history[-100:]

        return alert

    def check_pipeline_run(
        self,
        pipeline: str,
        runtime_seconds: float,
        row_count: int,
        error_count: int = 0,
    ) -> list[AnomalyAlert]:
        """Check multiple metrics for a pipeline run."""
        alerts: list[AnomalyAlert] = []

        for metric, value in [
            (f"{pipeline}.runtime_seconds", runtime_seconds),
            (f"{pipeline}.row_count", float(row_count)),
            (f"{pipeline}.error_count", float(error_count)),
        ]:
            alert = self.record(metric, value)
            if alert:
                alert.pipeline = pipeline
                alerts.append(alert)

        return alerts
