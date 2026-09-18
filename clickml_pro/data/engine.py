"""
Multi-engine data execution layer.

Teams don't standardise on a single tool — this layer provides a unified
interface that delegates to pandas, polars, DuckDB, or Spark as needed.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EngineType(str, Enum):
    PANDAS = "pandas"
    POLARS = "polars"
    DUCKDB = "duckdb"
    SPARK = "spark"


class DataEngine(ABC):
    """Abstract interface for a data execution engine."""

    @abstractmethod
    def read(self, source: dict[str, Any]) -> Any:
        """Read data from a source configuration."""

    @abstractmethod
    def transform(self, data: Any, operations: list[dict[str, Any]]) -> Any:
        """Apply a sequence of transformations."""

    @abstractmethod
    def write(self, data: Any, sink: dict[str, Any]) -> str:
        """Write data to a sink and return the output path/reference."""

    @abstractmethod
    def sql(self, query: str, **kwargs: Any) -> Any:
        """Execute a SQL query against loaded data."""


class PandasEngine(DataEngine):
    """Pandas-based data engine."""

    def read(self, source: dict[str, Any]) -> Any:
        import pandas as pd

        fmt = source.get("format", "csv")
        path = source.get("path", "")
        conn_str = source.get("connection_string")

        if conn_str and source.get("query"):
            return pd.read_sql(source["query"], conn_str)

        readers = {
            "csv": pd.read_csv,
            "parquet": pd.read_parquet,
            "json": pd.read_json,
            "excel": pd.read_excel,
        }
        reader = readers.get(fmt)
        if reader is None:
            raise ValueError(f"Unsupported format: {fmt}")
        return reader(path, **source.get("options", {}))

    def transform(self, data: Any, operations: list[dict[str, Any]]) -> Any:
        import pandas as pd

        df: pd.DataFrame = data
        for op in operations:
            op_type = op.get("type", "")
            if op_type == "filter":
                df = df.query(op["expression"])
            elif op_type == "select":
                df = df[op["columns"]]
            elif op_type == "rename":
                df = df.rename(columns=op["mapping"])
            elif op_type == "drop_nulls":
                df = df.dropna(subset=op.get("columns"))
            elif op_type == "sort":
                df = df.sort_values(op["by"], ascending=op.get("ascending", True))
            elif op_type == "aggregate":
                df = df.groupby(op["group_by"]).agg(op["aggregations"]).reset_index()
            elif op_type == "sql":
                import duckdb
                df = duckdb.sql(op["query"]).df()
            else:
                logger.warning("Unknown transform: %s", op_type)
        return df

    def write(self, data: Any, sink: dict[str, Any]) -> str:
        import pandas as pd

        df: pd.DataFrame = data
        fmt = sink.get("format", "parquet")
        path = sink.get("path", "output.parquet")

        writers = {
            "csv": df.to_csv,
            "parquet": df.to_parquet,
            "json": df.to_json,
        }
        writer = writers.get(fmt)
        if writer is None:
            raise ValueError(f"Unsupported sink format: {fmt}")
        writer(path, index=False)
        logger.info("Data written to %s (%s)", path, fmt)
        return path

    def sql(self, query: str, **kwargs: Any) -> Any:
        import duckdb
        return duckdb.sql(query).df()


class PolarsEngine(DataEngine):
    """Polars-based data engine (fast, Rust-backed)."""

    def read(self, source: dict[str, Any]) -> Any:
        import polars as pl

        fmt = source.get("format", "csv")
        path = source.get("path", "")

        readers = {
            "csv": pl.read_csv,
            "parquet": pl.read_parquet,
            "json": pl.read_json,
        }
        reader = readers.get(fmt)
        if reader is None:
            raise ValueError(f"Unsupported format for Polars: {fmt}")
        return reader(path)

    def transform(self, data: Any, operations: list[dict[str, Any]]) -> Any:
        import polars as pl

        df: pl.DataFrame = data
        for op in operations:
            op_type = op.get("type", "")
            if op_type == "filter":
                df = df.filter(pl.sql_expr(op["expression"]))
            elif op_type == "select":
                df = df.select(op["columns"])
            elif op_type == "rename":
                df = df.rename(op["mapping"])
            elif op_type == "drop_nulls":
                df = df.drop_nulls(subset=op.get("columns"))
            elif op_type == "sort":
                df = df.sort(op["by"], descending=not op.get("ascending", True))
            else:
                logger.warning("Unknown transform: %s", op_type)
        return df

    def write(self, data: Any, sink: dict[str, Any]) -> str:
        fmt = sink.get("format", "parquet")
        path = sink.get("path", "output.parquet")

        if fmt == "parquet":
            data.write_parquet(path)
        elif fmt == "csv":
            data.write_csv(path)
        elif fmt == "json":
            data.write_json(path)
        else:
            raise ValueError(f"Unsupported sink format: {fmt}")
        return path

    def sql(self, query: str, **kwargs: Any) -> Any:
        import polars as pl
        return pl.SQLContext(frames=kwargs).execute(query).collect()


class DuckDBEngine(DataEngine):
    """DuckDB-based data engine (analytical queries)."""

    def __init__(self) -> None:
        self._conn: Any = None

    @property
    def conn(self) -> Any:
        if self._conn is None:
            import duckdb
            self._conn = duckdb.connect()
        return self._conn

    def read(self, source: dict[str, Any]) -> Any:
        path = source.get("path", "")
        fmt = source.get("format", "auto")
        if fmt == "auto":
            return self.conn.sql(f"SELECT * FROM '{path}'").df()
        return self.conn.sql(f"SELECT * FROM read_{fmt}('{path}')").df()

    def transform(self, data: Any, operations: list[dict[str, Any]]) -> Any:
        self.conn.register("__input", data)
        for op in operations:
            if op.get("type") == "sql":
                data = self.conn.sql(op["query"]).df()
        return data

    def write(self, data: Any, sink: dict[str, Any]) -> str:
        path = sink.get("path", "output.parquet")
        fmt = sink.get("format", "parquet")
        self.conn.register("__output", data)
        self.conn.sql(f"COPY __output TO '{path}' (FORMAT '{fmt}')")
        return path

    def sql(self, query: str, **kwargs: Any) -> Any:
        return self.conn.sql(query).df()


def get_engine(engine_type: str | EngineType) -> DataEngine:
    """Factory — return the requested data engine."""
    if isinstance(engine_type, str):
        engine_type = EngineType(engine_type)

    engines: dict[EngineType, type[DataEngine]] = {
        EngineType.PANDAS: PandasEngine,
        EngineType.POLARS: PolarsEngine,
        EngineType.DUCKDB: DuckDBEngine,
    }

    cls = engines.get(engine_type)
    if cls is None:
        raise ValueError(f"Engine '{engine_type}' not yet supported. Available: {list(engines.keys())}")
    return cls()
