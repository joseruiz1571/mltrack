"""Tests for the MLflow registry adapter.

All MLflow client calls are mocked — no MLflow server required to run these.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

from mltrack.core.registry import DiscoveredModel


# ---------------------------------------------------------------------------
# Helpers — synthetic MLflow objects matching real API shape
# ---------------------------------------------------------------------------

def _make_version(version: str, stage: str = "None", run_id: str = ""):
    """Create a mock ModelVersion (matches mlflow.entities.model_registry.ModelVersion)."""
    v = MagicMock()
    v.version = version
    v.current_stage = stage
    v.run_id = run_id or None
    return v


def _make_registered_model(
    name: str,
    description: str = "",
    tags: dict = None,
    creation_timestamp: int = 1776372167000,
    latest_versions: list = None,
):
    """Create a mock RegisteredModel matching real MLflow API shape from Jose's explore output."""
    m = MagicMock()
    m.name = name
    m.description = description
    m.tags = tags or {}
    m.creation_timestamp = creation_timestamp
    m.latest_versions = latest_versions or [_make_version("1")]
    return m


# ---------------------------------------------------------------------------
# Fixture — patches MlflowClient so no real mlflow server is needed
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Patch MlflowClient and MLFLOW_AVAILABLE so no real mlflow install is needed."""
    with patch("mltrack.adapters.mlflow_adapter.MLFLOW_AVAILABLE", True), \
         patch("mltrack.adapters.mlflow_adapter.MlflowClient") as MockClient:
        client_instance = MagicMock()
        MockClient.return_value = client_instance
        yield client_instance


@pytest.fixture
def adapter(mock_client):
    """Return a MlflowAdapter backed by the mock client."""
    from mltrack.adapters.mlflow_adapter import MlflowAdapter
    return MlflowAdapter(tracking_uri="http://localhost:5000")


# ---------------------------------------------------------------------------
# MlflowAdapter — instantiation
# ---------------------------------------------------------------------------

class TestMlflowAdapterInit:
    def test_source_name(self, adapter):
        assert adapter.source_name == "mlflow"

    def test_accepts_tracking_uri(self, mock_client):
        from mltrack.adapters.mlflow_adapter import MlflowAdapter
        a = MlflowAdapter(tracking_uri="http://remote:5000")
        assert a.source_name == "mlflow"

    def test_accepts_no_uri(self, mock_client):
        from mltrack.adapters.mlflow_adapter import MlflowAdapter
        a = MlflowAdapter()  # falls back to env var / ./mlruns
        assert a.source_name == "mlflow"

    def test_raises_import_error_when_mlflow_missing(self):
        with patch("mltrack.adapters.mlflow_adapter.MLFLOW_AVAILABLE", False):
            from mltrack.adapters.mlflow_adapter import MlflowAdapter
            with pytest.raises(ImportError, match="mlflow is required"):
                MlflowAdapter()


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestMlflowAdapterConnection:
    def test_returns_true_when_server_responds(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = []
        assert adapter.test_connection() is True

    def test_returns_false_on_connection_error(self, adapter, mock_client):
        mock_client.search_registered_models.side_effect = Exception("Connection refused")
        assert adapter.test_connection() is False

    def test_returns_false_on_auth_error(self, adapter, mock_client):
        mock_client.search_registered_models.side_effect = PermissionError("Unauthorized")
        assert adapter.test_connection() is False


# ---------------------------------------------------------------------------
# discover — field mapping (using Jose's real output as the reference shape)
# ---------------------------------------------------------------------------

class TestMlflowAdapterDiscover:
    def test_returns_list_of_discovered_models(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("fraud-detection-v2"),
        ]
        results = adapter.discover()
        assert len(results) == 1
        assert isinstance(results[0], DiscoveredModel)

    def test_name_maps_correctly(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("fraud-detection-v2"),
        ]
        assert adapter.discover()[0].name == "fraud-detection-v2"

    def test_source_is_mlflow(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("any-model"),
        ]
        assert adapter.discover()[0].source == "mlflow"

    def test_description_maps_correctly(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("fraud-detection-v2", description="Real-time fraud scoring"),
        ]
        assert adapter.discover()[0].description == "Real-time fraud scoring"

    def test_empty_description_becomes_none(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("model", description=""),
        ]
        assert adapter.discover()[0].description is None

    def test_tags_map_correctly(self, adapter, mock_client):
        """Tags come back as a dict from MLflow — matches Jose's explore output."""
        mock_client.search_registered_models.return_value = [
            _make_registered_model("fraud-detection-v2", tags={"env": "production", "team": "risk"}),
        ]
        result = adapter.discover()[0]
        assert result.tags == {"env": "production", "team": "risk"}

    def test_empty_tags_become_empty_dict(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("model", tags={}),
        ]
        assert adapter.discover()[0].tags == {}

    def test_creation_timestamp_converts_from_milliseconds(self, adapter, mock_client):
        """1776372167155 ms → April 2026 (matches Jose's real output)."""
        mock_client.search_registered_models.return_value = [
            _make_registered_model("model", creation_timestamp=1776372167155),
        ]
        created_at = adapter.discover()[0].created_at
        assert isinstance(created_at, datetime)
        assert created_at.year == 2026

    def test_null_timestamp_becomes_none(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("model", creation_timestamp=0),
        ]
        assert adapter.discover()[0].created_at is None

    def test_multiple_models_all_returned(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = [
            _make_registered_model("fraud-detection-v2"),
            _make_registered_model("credit-risk-lgd"),
            _make_registered_model("kyc-classifier"),
        ]
        results = adapter.discover()
        assert len(results) == 3
        names = [r.name for r in results]
        assert "fraud-detection-v2" in names
        assert "credit-risk-lgd" in names
        assert "kyc-classifier" in names

    def test_empty_registry_returns_empty_list(self, adapter, mock_client):
        mock_client.search_registered_models.return_value = []
        assert adapter.discover() == []

    def test_connection_error_raises(self, adapter, mock_client):
        mock_client.search_registered_models.side_effect = Exception("Server unreachable")
        with pytest.raises(ConnectionError, match="Failed to query MLflow registry"):
            adapter.discover()


# ---------------------------------------------------------------------------
# _best_version — version selection logic
# ---------------------------------------------------------------------------

class TestBestVersion:
    """Version selection: Production > Staging > first available."""

    def setup_method(self):
        from mltrack.adapters.mlflow_adapter import MlflowAdapter
        # Bypass __init__ to test the static method directly
        self._fn = MlflowAdapter._best_version

    def test_no_versions_returns_none(self):
        assert self._fn([]) is None

    def test_null_versions_returns_none(self):
        assert self._fn(None) is None

    def test_single_version_no_stage(self):
        versions = [_make_version("1", stage="None")]
        assert self._fn(versions) == "1"

    def test_prefers_production_over_staging(self):
        versions = [
            _make_version("1", stage="Staging"),
            _make_version("2", stage="Production"),
        ]
        assert self._fn(versions) == "2"

    def test_prefers_staging_over_none(self):
        versions = [
            _make_version("1", stage="None"),
            _make_version("2", stage="Staging"),
        ]
        assert self._fn(versions) == "2"

    def test_falls_back_to_first_when_no_stage(self):
        versions = [
            _make_version("3", stage="None"),
            _make_version("1", stage="Archived"),
        ]
        assert self._fn(versions) == "3"

    def test_production_wins_regardless_of_order(self):
        versions = [
            _make_version("5", stage="Staging"),
            _make_version("3", stage="Production"),
            _make_version("7", stage="None"),
        ]
        assert self._fn(versions) == "3"


# ---------------------------------------------------------------------------
# _parse_timestamp
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def setup_method(self):
        from mltrack.adapters.mlflow_adapter import MlflowAdapter
        self._fn = MlflowAdapter._parse_timestamp

    def test_converts_milliseconds_to_datetime(self):
        # 1776372167155 ms is April 2026
        result = self._fn(1776372167155)
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_zero_returns_none(self):
        assert self._fn(0) is None

    def test_none_returns_none(self):
        assert self._fn(None) is None
