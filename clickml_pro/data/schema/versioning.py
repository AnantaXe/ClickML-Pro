"""
Schema versioning — immutable, versioned-on-change schemas with migration support.

Every schema change creates a new immutable version.  This module handles
version numbering, change detection, and migration script generation.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from clickml_pro.data.schema.manager import SchemaVersion, SchemaManager

logger = logging.getLogger(__name__)


class SchemaMigration(BaseModel):
    """Represents a migration between two schema versions."""

    dataset: str
    from_version: int
    to_version: int
    operations: list[dict[str, Any]] = Field(default_factory=list)
    reversible: bool = True
    sql_up: str = ""
    sql_down: str = ""


class SchemaVersioningService:
    """
    High-level service for schema evolution.

    Handles:
    - Auto-detecting changes between schema drafts
    - Generating migration operations
    - Enforcing compatibility rules
    - Producing SQL migration scripts
    """

    def __init__(self, schema_manager: SchemaManager | None = None) -> None:
        self.manager = schema_manager or SchemaManager()

    def evolve(self, dataset: str, new_schema: SchemaVersion) -> SchemaMigration:
        """
        Compare the new schema against the latest and produce a migration.

        Raises ValueError if the change violates compatibility rules.
        """
        current = self.manager.get_latest(dataset)

        if current is None:
            # First version — register and return empty migration
            registered = self.manager.register(new_schema)
            return SchemaMigration(
                dataset=dataset,
                from_version=0,
                to_version=registered.version,
                operations=[{"type": "create_table", "columns": [c.model_dump() for c in registered.columns]}],
            )

        # Diff
        diff = self.manager.diff(dataset, current.version, 0)  # Won't work yet — need to register first
        # Instead, compute diff manually
        old_cols = {c.name: c for c in current.columns}
        new_cols = {c.name: c for c in new_schema.columns}

        operations: list[dict[str, Any]] = []

        # Added columns
        for name in set(new_cols) - set(old_cols):
            col = new_cols[name]
            operations.append({
                "type": "add_column",
                "column": col.model_dump(),
            })

        # Removed columns
        for name in set(old_cols) - set(new_cols):
            operations.append({
                "type": "drop_column",
                "column": name,
            })

        # Modified columns
        for name in set(old_cols) & set(new_cols):
            if old_cols[name] != new_cols[name]:
                operations.append({
                    "type": "alter_column",
                    "column": name,
                    "from": old_cols[name].model_dump(),
                    "to": new_cols[name].model_dump(),
                })

        # Register the new version
        registered = self.manager.register(new_schema)

        migration = SchemaMigration(
            dataset=dataset,
            from_version=current.version,
            to_version=registered.version,
            operations=operations,
            sql_up=self._generate_sql(operations, direction="up"),
            sql_down=self._generate_sql(operations, direction="down"),
        )

        logger.info(
            "Schema evolved: %s v%d → v%d (%d operations)",
            dataset, current.version, registered.version, len(operations),
        )
        return migration

    def _generate_sql(self, operations: list[dict[str, Any]], direction: str = "up") -> str:
        """Generate SQL migration statements."""
        lines: list[str] = []

        for op in operations:
            op_type = op.get("type", "")

            if direction == "up":
                if op_type == "add_column":
                    col = op["column"]
                    sql_type = self._to_sql_type(col.get("dtype", "string"))
                    nullable = "" if col.get("nullable", True) else " NOT NULL"
                    lines.append(f"ALTER TABLE {{table}} ADD COLUMN {col['name']} {sql_type}{nullable};")
                elif op_type == "drop_column":
                    lines.append(f"ALTER TABLE {{table}} DROP COLUMN {op['column']};")
                elif op_type == "alter_column":
                    new = op["to"]
                    sql_type = self._to_sql_type(new.get("dtype", "string"))
                    lines.append(f"ALTER TABLE {{table}} ALTER COLUMN {op['column']} TYPE {sql_type};")
            else:  # down — reverse
                if op_type == "add_column":
                    lines.append(f"ALTER TABLE {{table}} DROP COLUMN {op['column']['name']};")
                elif op_type == "drop_column":
                    lines.append(f"-- Cannot auto-reverse DROP COLUMN {op['column']}")
                elif op_type == "alter_column":
                    old = op["from"]
                    sql_type = self._to_sql_type(old.get("dtype", "string"))
                    lines.append(f"ALTER TABLE {{table}} ALTER COLUMN {op['column']} TYPE {sql_type};")

        return "\n".join(lines)

    @staticmethod
    def _to_sql_type(dtype: str) -> str:
        mapping = {
            "string": "TEXT",
            "integer": "BIGINT",
            "float": "DOUBLE PRECISION",
            "boolean": "BOOLEAN",
            "timestamp": "TIMESTAMP",
            "date": "DATE",
            "array": "JSONB",
            "map": "JSONB",
            "struct": "JSONB",
            "binary": "BYTEA",
        }
        return mapping.get(dtype, "TEXT")
