"""Tests for the registry discovery layer."""

import pytest
from datetime import datetime

from mltrack.core.registry import DiscoveredModel, RegistryAdapter, find_untracked
from mltrack.adapters.mock_adapter import MockAdapter, DEFAULT_MOCK_MODELS


# --- DiscoveredModel ---

class TestDiscoveredModel:
    """DiscoveredModel dataclass behavior."""

    def test_basic_creation(self):
        model = DiscoveredModel(name="test-model", source="mlflow")
        assert model.name == "test-model"
        assert model.source == "mlflow"
        assert model.version is None
        assert model.tags == {}
        assert model.extra == {}

    def test_full_creation(self):
        model = DiscoveredModel(
            name="fraud-v2",
            source="sagemaker",
            version="2.1.0",
            created_at=datetime(2026, 1, 15),
            description="Fraud detection model",
            tags={"team": "risk"},
            extra={"arn": "arn:aws:sagemaker:us-east-1:123:model/fraud-v2"},
        )
        assert model.version == "2.1.0"
        assert model.tags["team"] == "risk"
        assert "arn" in model.extra

    def test_display_name_with_version(self):
        model = DiscoveredModel(name="fraud-v2", source="mlflow", version="3.0")
        assert model.display_name == "fraud-v2 (v3.0)"

    def test_display_name_without_version(self):
        model = DiscoveredModel(name="fraud-v2", source="mlflow")
        assert model.display_name == "fraud-v2"


# --- RegistryAdapter ABC ---

class TestRegistryAdapterABC:
    """ABC contract enforcement."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            RegistryAdapter()

    def test_incomplete_subclass_fails(self):
        class IncompleteAdapter(RegistryAdapter):
            @property
            def source_name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteAdapter()

    def test_complete_subclass_works(self):
        class MinimalAdapter(RegistryAdapter):
            @property
            def source_name(self):
                return "minimal"

            def discover(self):
                return []

            def test_connection(self):
                return True

        adapter = MinimalAdapter()
        assert adapter.source_name == "minimal"
        assert adapter.discover() == []
        assert adapter.test_connection() is True


# --- MockAdapter ---

class TestMockAdapter:
    """MockAdapter behavior."""

    def test_default_models(self):
        adapter = MockAdapter()
        models = adapter.discover()
        assert len(models) == len(DEFAULT_MOCK_MODELS)
        assert all(isinstance(m, DiscoveredModel) for m in models)

    def test_source_name(self):
        adapter = MockAdapter()
        assert adapter.source_name == "mock"

    def test_custom_models(self):
        custom = [DiscoveredModel(name="custom", source="mock")]
        adapter = MockAdapter(models=custom)
        assert len(adapter.discover()) == 1
        assert adapter.discover()[0].name == "custom"

    def test_empty_models(self):
        adapter = MockAdapter(models=[])
        assert adapter.discover() == []

    def test_connected(self):
        adapter = MockAdapter()
        assert adapter.test_connection() is True

    def test_disconnected(self):
        adapter = MockAdapter(connected=False)
        assert adapter.test_connection() is False

    def test_discover_when_disconnected_raises(self):
        adapter = MockAdapter(connected=False)
        with pytest.raises(ConnectionError):
            adapter.discover()

    def test_default_models_have_financial_services_context(self):
        adapter = MockAdapter()
        models = adapter.discover()
        # All default mocks should have source="mock"
        assert all(m.source == "mock" for m in models)
        # All should have descriptions
        assert all(m.description for m in models)
        # All should have versions
        assert all(m.version for m in models)

    def test_discover_returns_copies(self):
        """Discover returns a new list each time, not a reference."""
        adapter = MockAdapter()
        list1 = adapter.discover()
        list2 = adapter.discover()
        assert list1 is not list2


# --- find_untracked ---

class TestFindUntracked:
    """Comparing discovered models against MLTrack inventory."""

    def test_all_untracked(self):
        discovered = [
            DiscoveredModel(name="model-a", source="mock"),
            DiscoveredModel(name="model-b", source="mock"),
        ]
        tracked = set()
        result = find_untracked(discovered, tracked)
        assert len(result) == 2

    def test_all_tracked(self):
        discovered = [
            DiscoveredModel(name="model-a", source="mock"),
            DiscoveredModel(name="model-b", source="mock"),
        ]
        tracked = {"model-a", "model-b"}
        result = find_untracked(discovered, tracked)
        assert len(result) == 0

    def test_mixed(self):
        discovered = [
            DiscoveredModel(name="tracked-model", source="mock"),
            DiscoveredModel(name="untracked-model", source="mock"),
        ]
        tracked = {"tracked-model"}
        result = find_untracked(discovered, tracked)
        assert len(result) == 1
        assert result[0].name == "untracked-model"

    def test_empty_discovered(self):
        result = find_untracked([], {"model-a"})
        assert result == []

    def test_empty_both(self):
        result = find_untracked([], set())
        assert result == []

    def test_preserves_order(self):
        discovered = [
            DiscoveredModel(name="c-model", source="mock"),
            DiscoveredModel(name="a-model", source="mock"),
            DiscoveredModel(name="b-model", source="mock"),
        ]
        result = find_untracked(discovered, set())
        assert [m.name for m in result] == ["c-model", "a-model", "b-model"]

    def test_with_mock_adapter_and_inventory(self):
        """Integration: mock adapter output compared against tracked names."""
        adapter = MockAdapter()
        discovered = adapter.discover()

        # Simulate: two of the mock models are already tracked
        tracked = {DEFAULT_MOCK_MODELS[0].name, DEFAULT_MOCK_MODELS[1].name}
        untracked = find_untracked(discovered, tracked)

        assert len(untracked) == len(DEFAULT_MOCK_MODELS) - 2
        assert all(m.name not in tracked for m in untracked)
