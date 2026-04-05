"""Mock registry adapter for testing and demos.

Returns a configurable set of DiscoveredModel objects without
requiring any external service connection.
"""

from datetime import datetime

from mltrack.core.registry import DiscoveredModel, RegistryAdapter


# Realistic financial services models for demo/testing
DEFAULT_MOCK_MODELS = [
    DiscoveredModel(
        name="fraud-detection-v3",
        source="mock",
        version="3.1.0",
        created_at=datetime(2026, 1, 15, 10, 30),
        description="Real-time transaction fraud scoring model",
        tags={"team": "risk-engineering", "env": "production"},
    ),
    DiscoveredModel(
        name="credit-risk-lgd",
        source="mock",
        version="2.0.1",
        created_at=datetime(2025, 11, 3, 14, 0),
        description="Loss-given-default model for credit portfolio",
        tags={"team": "credit-analytics", "env": "production"},
    ),
    DiscoveredModel(
        name="kyc-document-classifier",
        source="mock",
        version="1.4.0",
        created_at=datetime(2026, 3, 20, 9, 15),
        description="KYC document type classification for onboarding",
        tags={"team": "compliance-engineering", "env": "staging"},
    ),
    DiscoveredModel(
        name="churn-predictor-retail",
        source="mock",
        version="1.0.0",
        created_at=datetime(2026, 2, 8, 16, 45),
        description="Customer churn prediction for retail banking",
        tags={"team": "marketing-analytics", "env": "production"},
    ),
    DiscoveredModel(
        name="aml-transaction-monitor",
        source="mock",
        version="4.2.0",
        created_at=datetime(2025, 9, 12, 11, 0),
        description="Anti-money laundering transaction pattern detection",
        tags={"team": "financial-crime", "env": "production"},
    ),
]


class MockAdapter(RegistryAdapter):
    """Mock adapter that returns predefined models for testing/demos.

    Args:
        models: List of DiscoveredModel to return. Defaults to realistic
                financial services examples.
        connected: Whether test_connection() should succeed.
    """

    def __init__(
        self,
        models: list[DiscoveredModel] | None = None,
        connected: bool = True,
    ):
        self._models = models if models is not None else DEFAULT_MOCK_MODELS
        self._connected = connected

    @property
    def source_name(self) -> str:
        return "mock"

    def discover(self) -> list[DiscoveredModel]:
        if not self._connected:
            raise ConnectionError("Mock adapter is configured as disconnected")
        return list(self._models)

    def test_connection(self) -> bool:
        return self._connected
