"""
Lineage graph — dataset→dataset, job→dataset, and column-level lineage.

Lineage answers: "Where did this data come from?"  and  "What breaks if I
change this column?"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LineageNode(BaseModel):
    """A node in the lineage graph (dataset, job, or model)."""

    id: str
    node_type: str  # dataset, job, model, column
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LineageEdge(BaseModel):
    """A directed edge in the lineage graph."""

    source_id: str
    target_id: str
    edge_type: str = "derived_from"  # derived_from, produced_by, column_map
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageGraph:
    """
    In-memory lineage graph with persistence.

    Tracks:
    - Dataset → Dataset (ETL lineage)
    - Job → Dataset (which job produced a dataset)
    - Column-level lineage (which source columns map to target columns)
    """

    def __init__(self, storage_path: str | Path = "./lineage") -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._nodes: dict[str, LineageNode] = {}
        self._edges: list[LineageEdge] = []
        self._load()

    # ── Node Management ─────────────────────────────────────────────────

    def add_node(self, node: LineageNode) -> None:
        self._nodes[node.id] = node
        self._persist()

    def get_node(self, node_id: str) -> LineageNode | None:
        return self._nodes.get(node_id)

    # ── Edge Management ─────────────────────────────────────────────────

    def add_edge(self, edge: LineageEdge) -> None:
        self._edges.append(edge)
        self._persist()

    def add_derivation(self, source_id: str, target_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Record that target_id was derived from source_id."""
        self.add_edge(LineageEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type="derived_from",
            metadata=metadata or {},
        ))

    def add_production(self, job_id: str, dataset_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Record that a job produced a dataset."""
        self.add_edge(LineageEdge(
            source_id=job_id,
            target_id=dataset_id,
            edge_type="produced_by",
            metadata=metadata or {},
        ))

    # ── Queries ─────────────────────────────────────────────────────────

    def get_upstream(self, node_id: str, depth: int = 10) -> dict[str, Any]:
        """Get all upstream nodes (where did this data come from?)."""
        visited: set[str] = set()
        tree = self._traverse_upstream(node_id, depth, visited)
        return tree

    def get_downstream(self, node_id: str, depth: int = 10) -> dict[str, Any]:
        """Get all downstream nodes (what depends on this?)."""
        visited: set[str] = set()
        tree = self._traverse_downstream(node_id, depth, visited)
        return tree

    def get_impact(self, node_id: str) -> list[str]:
        """Get all datasets/jobs that would be impacted by changes to this node."""
        downstream = self.get_downstream(node_id)
        impacted: list[str] = []
        self._flatten_tree(downstream, impacted)
        return impacted

    # ── Column-Level Lineage ────────────────────────────────────────────

    def add_column_lineage(
        self,
        source_dataset: str,
        source_column: str,
        target_dataset: str,
        target_column: str,
        transformation: str = "",
    ) -> None:
        """Track column-level lineage."""
        self.add_edge(LineageEdge(
            source_id=f"{source_dataset}.{source_column}",
            target_id=f"{target_dataset}.{target_column}",
            edge_type="column_map",
            metadata={"transformation": transformation},
        ))

    def get_column_lineage(self, dataset: str, column: str) -> list[LineageEdge]:
        """Get column-level lineage for a specific column."""
        target = f"{dataset}.{column}"
        return [e for e in self._edges if e.target_id == target and e.edge_type == "column_map"]

    # ── Traversal Helpers ───────────────────────────────────────────────

    def _traverse_upstream(self, node_id: str, depth: int, visited: set[str]) -> dict[str, Any]:
        if depth <= 0 or node_id in visited:
            return {"id": node_id, "children": []}

        visited.add(node_id)
        node = self._nodes.get(node_id)
        upstream_edges = [e for e in self._edges if e.target_id == node_id]

        children = []
        for edge in upstream_edges:
            child = self._traverse_upstream(edge.source_id, depth - 1, visited)
            child["edge_type"] = edge.edge_type
            children.append(child)

        return {
            "id": node_id,
            "name": node.name if node else node_id,
            "type": node.node_type if node else "unknown",
            "children": children,
        }

    def _traverse_downstream(self, node_id: str, depth: int, visited: set[str]) -> dict[str, Any]:
        if depth <= 0 or node_id in visited:
            return {"id": node_id, "children": []}

        visited.add(node_id)
        node = self._nodes.get(node_id)
        downstream_edges = [e for e in self._edges if e.source_id == node_id]

        children = []
        for edge in downstream_edges:
            child = self._traverse_downstream(edge.target_id, depth - 1, visited)
            child["edge_type"] = edge.edge_type
            children.append(child)

        return {
            "id": node_id,
            "name": node.name if node else node_id,
            "type": node.node_type if node else "unknown",
            "children": children,
        }

    def _flatten_tree(self, tree: dict[str, Any], result: list[str]) -> None:
        node_id = tree.get("id", "")
        if node_id and node_id not in result:
            result.append(node_id)
        for child in tree.get("children", []):
            self._flatten_tree(child, result)

    # ── Persistence ─────────────────────────────────────────────────────

    def _persist(self) -> None:
        data = {
            "nodes": {k: v.model_dump() for k, v in self._nodes.items()},
            "edges": [e.model_dump() for e in self._edges],
        }
        (self.storage_path / "lineage.json").write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        path = self.storage_path / "lineage.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._nodes = {k: LineageNode(**v) for k, v in data.get("nodes", {}).items()}
            self._edges = [LineageEdge(**e) for e in data.get("edges", [])]
        except Exception as exc:
            logger.warning("Failed to load lineage graph: %s", exc)
