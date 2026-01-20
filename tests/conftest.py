"""Pytest fixtures for MLTrack tests."""

import tempfile
from pathlib import Path

import pytest

from mltrack.core.database import Base, get_engine, init_db


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path for testing."""
    return tmp_path / "test_mltrack.db"


@pytest.fixture
def initialized_db(temp_db_path):
    """Initialize database and return path."""
    init_db(temp_db_path)
    return temp_db_path


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    from mltrack.models import AIModel  # Ensure models are loaded

    engine = get_engine(in_memory=True)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def sample_model_data():
    """Sample valid model data for testing."""
    from datetime import date

    return {
        "model_name": "fraud-detection-v1",
        "vendor": "in-house",
        "risk_tier": "high",
        "use_case": "Real-time fraud detection for payment transactions",
        "business_owner": "Risk Management Team",
        "technical_owner": "ML Platform Team",
        "deployment_date": date(2024, 1, 15),
        "deployment_environment": "prod",
        "model_version": "1.0.0",
        "data_classification": "confidential",
        "api_endpoint": "https://api.internal/fraud/v1",
    }


@pytest.fixture
def sample_model_data_minimal():
    """Minimal valid model data (required fields only)."""
    from datetime import date

    return {
        "model_name": "simple-model",
        "vendor": "openai",
        "risk_tier": "low",
        "use_case": "Customer support chatbot",
        "business_owner": "Support Team",
        "technical_owner": "IT Team",
        "deployment_date": date(2024, 6, 1),
    }
