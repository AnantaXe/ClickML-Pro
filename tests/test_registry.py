"""Tests for model registry."""

import pytest
from clickml_pro.registry.model_registry import (
    ModelRegistry,
    RegisteredModel,
    ModelLineage,
    ModelStatus,
)


class TestModelRegistry:
    def test_register_and_retrieve(self, tmp_path):
        registry = ModelRegistry(storage_dir=tmp_path)
        model = RegisteredModel(
            name="test-model",
            lineage=ModelLineage(base_model="bert-base"),
        )
        entry = registry.register(model)

        assert entry.name == "test-model"
        assert entry.version == 1

        models = registry.list_models()
        assert len(models) == 1

    def test_version_auto_increments(self, tmp_path):
        registry = ModelRegistry(storage_dir=tmp_path)
        registry.register(RegisteredModel(name="m"))
        entry2 = registry.register(RegisteredModel(name="m"))

        assert entry2.version == 2

    def test_promote_model(self, tmp_path):
        registry = ModelRegistry(storage_dir=tmp_path)
        registry.register(RegisteredModel(name="m"))

        ok = registry.promote("m", 1, ModelStatus.STAGING)
        assert ok is True

        model = registry.get_model("m", 1)
        assert model.status == ModelStatus.STAGING

    def test_search(self, tmp_path):
        registry = ModelRegistry(storage_dir=tmp_path)
        registry.register(RegisteredModel(name="llama-7b", tags=["7b"]))
        registry.register(RegisteredModel(name="bert-base", tags=["base"]))

        results = registry.search("llama")
        assert len(results) == 1
        assert results[0].name == "llama-7b"
