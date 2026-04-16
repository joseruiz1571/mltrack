"""MLflow Model Registry adapter for MLTrack discovery.

Connects to an MLflow tracking server and surfaces all registered models
so MLTrack can compare them against its governance inventory.

Requires: pip install mlflow  (or pip install mltrack[mlflow])
"""

from datetime import datetime
from typing import Optional

from mltrack.core.registry import DiscoveredModel, RegistryAdapter

try:
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MlflowClient = None  # keeps the name patchable in tests
    MLFLOW_AVAILABLE = False


class MlflowAdapter(RegistryAdapter):
    """Adapter for MLflow Model Registry.

    Discovers all registered models from an MLflow tracking server and
    returns them as DiscoveredModel objects for governance comparison.

    Authentication is handled by MLflow's standard mechanisms:
    - MLFLOW_TRACKING_URI environment variable
    - MLFLOW_TRACKING_USERNAME / MLFLOW_TRACKING_PASSWORD for basic auth
    - ~/.mlflow/credentials for stored credentials

    Args:
        tracking_uri: MLflow tracking server URI (e.g. "http://localhost:5000",
                      "databricks", "s3://my-bucket/mlflow"). If not provided,
                      falls back to MLFLOW_TRACKING_URI env var, then ./mlruns.
    """

    def __init__(self, tracking_uri: Optional[str] = None):
        if not MLFLOW_AVAILABLE:
            raise ImportError(
                "mlflow is required for MlflowAdapter.\n"
                "Install it with: pip install mlflow\n"
                "Or: pip install 'mltrack[mlflow]'"
            )
        self._tracking_uri = tracking_uri
        self._client = MlflowClient(tracking_uri)

    @property
    def source_name(self) -> str:
        return "mlflow"

    def test_connection(self) -> bool:
        """Verify the MLflow server is reachable and responds to queries."""
        try:
            self._client.search_registered_models(max_results=1)
            return True
        except Exception:
            return False

    def discover(self) -> list[DiscoveredModel]:
        """Return all models registered in the MLflow Model Registry.

        Raises:
            ConnectionError: If the tracking server is unreachable or returns
                             an unexpected error.
        """
        try:
            registered_models = self._client.search_registered_models()
        except Exception as e:
            raise ConnectionError(
                f"Failed to query MLflow registry: {e}"
            ) from e

        return [self._to_discovered(m) for m in registered_models]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_discovered(self, m) -> DiscoveredModel:
        """Map an MLflow RegisteredModel object to DiscoveredModel."""
        return DiscoveredModel(
            name=m.name,
            source="mlflow",
            version=self._best_version(m.latest_versions),
            created_at=self._parse_timestamp(m.creation_timestamp),
            description=m.description or None,
            tags=dict(m.tags) if m.tags else {},
        )

    @staticmethod
    def _best_version(latest_versions) -> Optional[str]:
        """Pick the most production-relevant version string.

        MLflow's latest_versions returns one entry per lifecycle stage.
        Priority: Production → Staging → first available.
        """
        if not latest_versions:
            return None

        for v in latest_versions:
            if v.current_stage == "Production":
                return v.version

        for v in latest_versions:
            if v.current_stage == "Staging":
                return v.version

        return latest_versions[0].version

    @staticmethod
    def _parse_timestamp(ts_ms) -> Optional[datetime]:
        """Convert MLflow's millisecond epoch timestamp to datetime."""
        if not ts_ms:
            return None
        return datetime.fromtimestamp(ts_ms / 1000)
