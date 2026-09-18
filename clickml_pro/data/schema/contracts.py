"""
Data contracts — formal agreements between data producers and consumers.

A data contract defines:
- Expected schema (columns, types, nullability)
- Quality expectations (freshness, completeness, uniqueness)
- SLAs (max latency, availability)
- Ownership and contact info
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QualityExpectation(BaseModel):
    """A single data quality expectation."""

    column: str = ""           # empty means table-level
    check: str = ""            # not_null, unique, range, regex, freshness, row_count
    parameters: dict[str, Any] = Field(default_factory=dict)
    severity: str = "error"    # error, warning, info


class SLA(BaseModel):
    """Service Level Agreement for a data contract."""

    max_latency_minutes: int = 60
    freshness_minutes: int = 120
    availability_pct: float = 99.9
    min_row_count: int = 0


class DataContract(BaseModel):
    """A formal contract between data producer and consumer."""

    name: str
    version: int = 1
    dataset: str
    schema_version: int = 0   # 0 = latest
    owner: str = ""
    team: str = ""
    description: str = ""
    expectations: list[QualityExpectation] = Field(default_factory=list)
    sla: SLA = Field(default_factory=SLA)
    consumers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ContractValidationResult(BaseModel):
    """Result of validating data against a contract."""

    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    checks_total: int = 0


def load_contract(path: str | Path) -> DataContract:
    """Load a data contract from YAML or JSON."""
    path = Path(path)
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        raw = yaml.safe_load(text)
    else:
        raw = json.loads(text)
    return DataContract(**raw)


def validate_contract(path: str | Path) -> ContractValidationResult:
    """Validate a data contract file (structural validation only)."""
    result = ContractValidationResult()
    try:
        contract = load_contract(path)
        result.checks_total = len(contract.expectations) + 3  # + schema, SLA, ownership

        # Check ownership
        if not contract.owner:
            result.warnings.append("No owner specified")
        else:
            result.checks_passed += 1

        # Check schema ref
        if contract.schema_version == 0:
            result.warnings.append("schema_version=0 (will use latest)")
        result.checks_passed += 1

        # Check SLA
        if contract.sla.max_latency_minutes <= 0:
            result.errors.append("SLA max_latency_minutes must be > 0")
            result.checks_failed += 1
        else:
            result.checks_passed += 1

        # Validate expectations
        for exp in contract.expectations:
            if not exp.check:
                result.errors.append(f"Expectation missing 'check' field: {exp}")
                result.checks_failed += 1
            else:
                result.checks_passed += 1

        result.valid = len(result.errors) == 0
        return result

    except Exception as exc:
        result.valid = False
        result.errors.append(f"Failed to parse contract: {exc}")
        return result


def evaluate_contract(contract: DataContract, data: Any) -> ContractValidationResult:
    """Evaluate a data contract against actual data (pandas DataFrame)."""
    result = ContractValidationResult()
    result.checks_total = len(contract.expectations)

    try:
        import pandas as pd

        df: pd.DataFrame = data

        for exp in contract.expectations:
            try:
                passed = _evaluate_expectation(df, exp)
                if passed:
                    result.checks_passed += 1
                else:
                    if exp.severity == "error":
                        result.errors.append(f"FAILED: {exp.check} on '{exp.column}'")
                        result.checks_failed += 1
                    else:
                        result.warnings.append(f"WARNING: {exp.check} on '{exp.column}'")
                        result.checks_passed += 1
            except Exception as e:
                result.errors.append(f"Error evaluating {exp.check}: {e}")
                result.checks_failed += 1

        result.valid = len(result.errors) == 0
        return result

    except ImportError:
        result.errors.append("pandas not installed")
        result.valid = False
        return result


def _evaluate_expectation(df: Any, exp: QualityExpectation) -> bool:
    """Evaluate a single quality expectation."""
    import pandas as pd

    check = exp.check
    col = exp.column
    params = exp.parameters

    if check == "not_null":
        return df[col].notna().all()

    elif check == "unique":
        return df[col].is_unique

    elif check == "row_count":
        min_count = params.get("min", 0)
        max_count = params.get("max", float("inf"))
        return min_count <= len(df) <= max_count

    elif check == "range":
        min_val = params.get("min")
        max_val = params.get("max")
        series = df[col]
        if min_val is not None and series.min() < min_val:
            return False
        if max_val is not None and series.max() > max_val:
            return False
        return True

    elif check == "regex":
        pattern = params.get("pattern", "")
        return df[col].astype(str).str.match(pattern).all()

    elif check == "accepted_values":
        values = set(params.get("values", []))
        return set(df[col].dropna().unique()).issubset(values)

    else:
        logger.warning("Unknown check type: %s", check)
        return True
