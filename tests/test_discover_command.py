"""Tests for the mltrack discover CLI command."""

import json
import pytest
from datetime import date
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model
from mltrack.adapters.mock_adapter import DEFAULT_MOCK_MODELS

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("mltrack.core.database.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mltrack.core.storage.init_db", lambda p=None: init_db(db_path))
    init_db(db_path)
    yield db_path


@pytest.fixture
def tracked_mock_model(clean_db):
    """Register the first mock model in MLTrack so it appears as 'tracked'."""
    return create_model({
        "model_name": DEFAULT_MOCK_MODELS[0].name,
        "vendor": "in-house",
        "risk_tier": "high",
        "use_case": "Fraud detection",
        "business_owner": "Risk Team",
        "technical_owner": "ML Platform",
        "deployment_date": date.today(),
        "deployment_environment": "prod",
    })


# --- Basic invocation ---

class TestDiscoverBasic:
    def test_runs_with_default_source(self):
        result = runner.invoke(app, ["discover"])
        # default source is mock; should not crash
        assert result.exit_code in (0, 1)  # 0=no gaps, 1=gaps found
        assert "mock" in result.output.lower() or "discovered" in result.output.lower()

    def test_runs_with_explicit_mock_source(self):
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert result.exit_code in (0, 1)

    def test_invalid_source_exits_1(self):
        result = runner.invoke(app, ["discover", "--source", "mlflow"])
        assert result.exit_code == 1
        assert "Unknown registry source" in result.output or "mlflow" in result.output

    def test_invalid_source_shows_valid_options(self):
        result = runner.invoke(app, ["discover", "--source", "unknown"])
        assert "mock" in result.output


# --- Governance gap detection ---

class TestGovernanceGaps:
    def test_empty_inventory_shows_all_as_untracked(self, clean_db):
        """With no models in MLTrack, all discovered models are gaps."""
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert result.exit_code == 1  # gaps found → non-zero
        assert "NOT TRACKED" in result.output

    def test_exit_0_when_all_tracked(self, clean_db):
        """When every discovered model is in MLTrack, exit 0."""
        for m in DEFAULT_MOCK_MODELS:
            create_model({
                "model_name": m.name,
                "vendor": "in-house",
                "risk_tier": "medium",
                "use_case": "Testing",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
            })
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert result.exit_code == 0

    def test_partial_tracking_shows_gap(self, tracked_mock_model):
        """One tracked, rest untracked → exit 1, table shows both statuses."""
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert result.exit_code == 1
        assert "tracked" in result.output
        assert "NOT TRACKED" in result.output

    def test_untracked_only_hides_tracked_models(self, tracked_mock_model):
        """--untracked-only should not show already-tracked models."""
        result = runner.invoke(app, ["discover", "--source", "mock", "--untracked-only"])
        assert result.exit_code == 1
        # The tracked model name should not appear in the table
        assert DEFAULT_MOCK_MODELS[0].name not in result.output

    def test_untracked_only_exits_0_when_fully_covered(self, clean_db):
        """--untracked-only with full coverage: no table rows, exit 0."""
        for m in DEFAULT_MOCK_MODELS:
            create_model({
                "model_name": m.name,
                "vendor": "in-house",
                "risk_tier": "low",
                "use_case": "Testing",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
            })
        result = runner.invoke(app, ["discover", "--source", "mock", "--untracked-only"])
        assert result.exit_code == 0
        assert "Fully Covered" in result.output or "No governance gaps" in result.output.lower()


# --- JSON output ---

class TestDiscoverJsonOutput:
    def test_json_flag_produces_valid_json(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "source" in data
        assert "summary" in data
        assert "untracked_models" in data

    def test_json_source_field(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        data = json.loads(result.output)
        assert data["source"] == "mock"

    def test_json_summary_counts(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        data = json.loads(result.output)
        summary = data["summary"]
        assert summary["discovered"] == len(DEFAULT_MOCK_MODELS)
        assert summary["tracked"] == 0
        assert summary["untracked"] == len(DEFAULT_MOCK_MODELS)
        assert summary["governance_gap"] is True

    def test_json_no_gap_when_all_tracked(self, clean_db):
        for m in DEFAULT_MOCK_MODELS:
            create_model({
                "model_name": m.name,
                "vendor": "in-house",
                "risk_tier": "low",
                "use_case": "Testing",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
            })
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        data = json.loads(result.output)
        assert data["summary"]["governance_gap"] is False
        assert data["summary"]["untracked"] == 0
        assert data["untracked_models"] == []

    def test_json_untracked_models_have_required_fields(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        data = json.loads(result.output)
        for model in data["untracked_models"]:
            assert "name" in model
            assert "version" in model
            assert "source" in model

    def test_json_exit_1_with_gaps(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        assert result.exit_code == 1

    def test_json_exit_0_without_gaps(self, clean_db):
        for m in DEFAULT_MOCK_MODELS:
            create_model({
                "model_name": m.name,
                "vendor": "in-house",
                "risk_tier": "low",
                "use_case": "Testing",
                "business_owner": "Owner",
                "technical_owner": "Tech",
                "deployment_date": date.today(),
            })
        result = runner.invoke(app, ["discover", "--source", "mock", "--json"])
        assert result.exit_code == 0


# --- Display content ---

class TestDiscoverDisplay:
    def test_shows_model_names_in_table(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock"])
        for m in DEFAULT_MOCK_MODELS:
            assert m.name in result.output

    def test_shows_versions_in_table(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock"])
        for m in DEFAULT_MOCK_MODELS:
            if m.version:
                assert m.version in result.output

    def test_shows_governance_gap_summary(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert "GOVERNANCE GAPS" in result.output

    def test_shows_add_suggestion_when_gaps_exist(self, clean_db):
        result = runner.invoke(app, ["discover", "--source", "mock"])
        assert "mltrack add" in result.output
