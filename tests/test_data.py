"""Tests for the data engineering layer."""

import pytest
from clickml_pro.data.schema.manager import SchemaManager, ColumnSchema, SchemaVersion


class TestSchemaManager:
    def test_register_and_get_schema(self, tmp_path):
        mgr = SchemaManager(storage_dir=tmp_path)
        columns = [
            ColumnSchema(name="id", dtype="integer", nullable=False),
            ColumnSchema(name="name", dtype="string"),
        ]
        schema = SchemaVersion(dataset="users", columns=columns)
        mgr.register(schema)
        result = mgr.get_latest("users")

        assert result is not None
        assert result.dataset == "users"
        assert len(result.columns) == 2

    def test_version_increments(self, tmp_path):
        mgr = SchemaManager(storage_dir=tmp_path)
        cols_v1 = [ColumnSchema(name="id", dtype="integer")]
        cols_v2 = [ColumnSchema(name="id", dtype="integer"), ColumnSchema(name="email", dtype="string")]

        mgr.register(SchemaVersion(dataset="users", columns=cols_v1))
        mgr.register(SchemaVersion(dataset="users", columns=cols_v2))
        result = mgr.get_latest("users")

        assert result.version == 2

    def test_get_nonexistent(self, tmp_path):
        mgr = SchemaManager(storage_dir=tmp_path)
        assert mgr.get_latest("nonexistent") is None


class TestDataContracts:
    def test_validate_contract(self):
        from clickml_pro.data.schema.contracts import DataContract, validate_contract

        contract = DataContract(
            name="test",
            dataset="test_ds",
            expectations=[
                {"type": "row_count", "params": {"min": 1, "max": 1000}}
            ],
        )
        # Just check the contract model is valid
        assert contract.name == "test"
        assert len(contract.expectations) == 1
