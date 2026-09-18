"""
Schema manager — versioned schema definitions with ownership tracking.

Every dataset has a schema.  Schemas are versioned, immutable once published,
and include ownership, compatibility rules, and downstream impact metadata.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ColumnType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    BINARY = "binary"


class ColumnSchema(BaseModel):
    """Definition of a single column in a dataset schema."""

    name: str
    dtype: ColumnType
    nullable: bool = True
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    pii: bool = False  # Personally identifiable information flag


class SchemaVersion(BaseModel):
    """A versioned, immutable schema definition."""

    dataset: str
    version: int = 1
    columns: list[ColumnSchema] = Field(default_factory=list)
    owner: str = ""
    team: str = ""
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    compatibility: str = "backward"  # backward, forward, full, none
    deprecated: bool = False
    deprecation_note: str = ""


class SchemaLifecycle(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class SchemaManager:
    """
    Manages dataset schemas with versioning, ownership, and lifecycle.

    Storage is file-based (JSON) for portability.  Can be swapped to a
    database backend in production.
    """

    def __init__(self, storage_dir: str | Path = "./schemas") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def register(self, schema: SchemaVersion) -> SchemaVersion:
        """Register a new schema version (immutable once saved)."""
        dataset_dir = self.storage_dir / schema.dataset
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # Auto-increment version
        existing = self.list_versions(schema.dataset)
        if existing:
            schema.version = max(s.version for s in existing) + 1

        # Check compatibility
        if existing and schema.compatibility != "none":
            self._check_compatibility(existing[-1], schema)

        path = dataset_dir / f"v{schema.version}.json"
        path.write_text(schema.model_dump_json(indent=2))
        logger.info("Schema registered: %s v%d", schema.dataset, schema.version)
        return schema

    def get_latest(self, dataset: str) -> SchemaVersion | None:
        """Get the latest schema version for a dataset."""
        versions = self.list_versions(dataset)
        return versions[-1] if versions else None

    def get_version(self, dataset: str, version: int) -> SchemaVersion | None:
        """Get a specific schema version."""
        path = self.storage_dir / dataset / f"v{version}.json"
        if not path.exists():
            return None
        return SchemaVersion(**json.loads(path.read_text()))

    def list_versions(self, dataset: str) -> list[SchemaVersion]:
        """List all versions of a dataset schema."""
        dataset_dir = self.storage_dir / dataset
        if not dataset_dir.exists():
            return []
        files = sorted(dataset_dir.glob("v*.json"))
        return [SchemaVersion(**json.loads(f.read_text())) for f in files]

    def list_datasets(self) -> list[str]:
        """List all datasets with registered schemas."""
        return [d.name for d in self.storage_dir.iterdir() if d.is_dir()]

    def deprecate(self, dataset: str, version: int, note: str = "") -> bool:
        """Mark a schema version as deprecated."""
        schema = self.get_version(dataset, version)
        if schema is None:
            return False
        schema.deprecated = True
        schema.deprecation_note = note
        path = self.storage_dir / dataset / f"v{version}.json"
        path.write_text(schema.model_dump_json(indent=2))
        logger.info("Schema deprecated: %s v%d", dataset, version)
        return True

    def diff(self, dataset: str, v1: int, v2: int) -> dict[str, Any]:
        """Show the diff between two schema versions."""
        s1 = self.get_version(dataset, v1)
        s2 = self.get_version(dataset, v2)
        if s1 is None or s2 is None:
            raise ValueError(f"Schema version not found: {dataset} v{v1} or v{v2}")

        cols1 = {c.name: c for c in s1.columns}
        cols2 = {c.name: c for c in s2.columns}

        added = [c for name, c in cols2.items() if name not in cols1]
        removed = [c for name, c in cols1.items() if name not in cols2]
        modified = []
        for name in set(cols1) & set(cols2):
            if cols1[name] != cols2[name]:
                modified.append({
                    "column": name,
                    "before": cols1[name].model_dump(),
                    "after": cols2[name].model_dump(),
                })

        return {
            "dataset": dataset,
            "from_version": v1,
            "to_version": v2,
            "added": [c.model_dump() for c in added],
            "removed": [c.model_dump() for c in removed],
            "modified": modified,
        }

    def _check_compatibility(self, old: SchemaVersion, new: SchemaVersion) -> None:
        """Check backward/forward compatibility between schema versions."""
        old_cols = {c.name for c in old.columns}
        new_cols = {c.name for c in new.columns}

        if new.compatibility == "backward":
            # New schema must be readable by old consumers
            removed = old_cols - new_cols
            if removed:
                raise ValueError(
                    f"Backward incompatible: columns removed: {removed}. "
                    "Set compatibility='none' to force."
                )

            # Check nullability changes (making non-nullable → nullable is OK)
            old_map = {c.name: c for c in old.columns}
            for col in new.columns:
                if col.name in old_map:
                    old_col = old_map[col.name]
                    if old_col.nullable and not col.nullable:
                        raise ValueError(
                            f"Backward incompatible: column '{col.name}' "
                            "changed from nullable to non-nullable."
                        )
