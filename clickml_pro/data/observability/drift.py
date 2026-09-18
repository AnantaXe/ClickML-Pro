"""
Distribution drift detection for data observability.

Detects when the statistical distribution of a column changes significantly
between data snapshots — a leading indicator of data quality issues.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DriftResult(BaseModel):
    """Result of a drift check for a single column."""

    column: str
    metric: str = ""          # ks_statistic, psi, js_divergence
    score: float = 0.0
    threshold: float = 0.1
    drifted: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class DriftDetector:
    """Detect distribution drift between two data snapshots."""

    def __init__(self, threshold: float = 0.1) -> None:
        self.threshold = threshold

    def detect(
        self,
        reference: Any,
        current: Any,
        columns: list[str] | None = None,
    ) -> list[DriftResult]:
        """
        Compare distributions between reference and current DataFrames.

        Uses the Kolmogorov-Smirnov test for numeric columns and
        Population Stability Index for categorical columns.
        """
        try:
            import pandas as pd
            import numpy as np

            ref_df: pd.DataFrame = reference
            cur_df: pd.DataFrame = current

            if columns is None:
                columns = list(set(ref_df.columns) & set(cur_df.columns))

            results: list[DriftResult] = []

            for col in columns:
                if ref_df[col].dtype in ("float64", "int64", "float32", "int32"):
                    result = self._ks_test(ref_df[col], cur_df[col], col)
                else:
                    result = self._psi(ref_df[col], cur_df[col], col)
                results.append(result)

            drifted = [r for r in results if r.drifted]
            if drifted:
                logger.warning(
                    "Drift detected in %d/%d columns: %s",
                    len(drifted), len(results),
                    [r.column for r in drifted],
                )

            return results

        except ImportError:
            logger.warning("pandas/numpy not installed for drift detection")
            return []

    def _ks_test(self, ref_series: Any, cur_series: Any, col: str) -> DriftResult:
        """Kolmogorov-Smirnov test for numeric columns."""
        from scipy import stats

        ref_clean = ref_series.dropna()
        cur_clean = cur_series.dropna()

        if len(ref_clean) == 0 or len(cur_clean) == 0:
            return DriftResult(column=col, metric="ks_statistic", score=0.0, threshold=self.threshold)

        ks_stat, p_value = stats.ks_2samp(ref_clean, cur_clean)

        return DriftResult(
            column=col,
            metric="ks_statistic",
            score=round(ks_stat, 4),
            threshold=self.threshold,
            drifted=ks_stat > self.threshold,
            details={"p_value": round(p_value, 6)},
        )

    def _psi(self, ref_series: Any, cur_series: Any, col: str, bins: int = 10) -> DriftResult:
        """Population Stability Index for categorical / binned columns."""
        import numpy as np

        ref_counts = ref_series.value_counts(normalize=True)
        cur_counts = cur_series.value_counts(normalize=True)

        all_values = set(ref_counts.index) | set(cur_counts.index)
        psi_value = 0.0

        for val in all_values:
            p = ref_counts.get(val, 1e-6)
            q = cur_counts.get(val, 1e-6)
            p = max(p, 1e-6)
            q = max(q, 1e-6)
            psi_value += (p - q) * np.log(p / q)

        return DriftResult(
            column=col,
            metric="psi",
            score=round(psi_value, 4),
            threshold=self.threshold * 2,  # PSI thresholds are typically higher
            drifted=psi_value > self.threshold * 2,
        )
