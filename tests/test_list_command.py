"""Tests for the mltrack list CLI command."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model

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
def sample_models(clean_db):
    """Create sample models for testing."""
    from datetime import date

    models = [
        {
            "model_name": "fraud-detector",
            "vendor": "in-house",
            "risk_tier": "critical",
            "use_case": "Real-time fraud detection for payments",
            "business_owner": "Risk Team",
            "technical_owner": "ML Platform",
            "deployment_date": date(2024, 1, 15),
            "deployment_environment": "prod",
        },
        {
            "model_name": "claude-assistant",
            "vendor": "anthropic",
            "risk_tier": "high",
            "use_case": "Customer support chatbot",
            "business_owner": "Support Team",
            "technical_owner": "AI Team",
            "deployment_date": date(2024, 3, 1),
            "deployment_environment": "prod",
        },
        {
            "model_name": "sentiment-analyzer",
            "vendor": "in-house",
            "risk_tier": "low",
            "use_case": "Social media sentiment analysis",
            "business_owner": "Marketing",
            "technical_owner": "Data Team",
            "deployment_date": date(2024, 6, 1),
            "deployment_environment": "staging",
        },
    ]

    created = []
    for data in models:
        created.append(create_model(data))

    return created


class TestListCommand:
    """Tests for mltrack list command."""

    def test_list_help_shows_options(self):
        """Test that --help shows all options."""
        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        assert "--risk" in result.output
        assert "--vendor" in result.output
        assert "--environment" in result.output
        assert "--status" in result.output
        assert "--verbose" in result.output
        assert "--json" in result.output
        assert "--output" in result.output

    def test_list_empty_inventory(self, clean_db):
        """Test listing when no models exist."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No models in inventory" in result.output
        assert "mltrack add" in result.output

    def test_list_shows_all_models(self, sample_models):
        """Test that list shows all models."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "fraud-detector" in result.output
        assert "claude-assistant" in result.output
        assert "sentiment-analyzer" in result.output
        assert "3 models" in result.output

    def test_list_shows_risk_distribution(self, sample_models):
        """Test that list shows risk distribution summary."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Risk distribution" in result.output
        assert "CRITICAL" in result.output
        assert "HIGH" in result.output
        assert "LOW" in result.output


class TestListFilters:
    """Tests for list command filtering."""

    def test_filter_by_risk_tier(self, sample_models):
        """Test filtering by risk tier."""
        result = runner.invoke(app, ["list", "--risk", "critical"])

        assert result.exit_code == 0
        assert "fraud-detector" in result.output
        assert "claude-assistant" not in result.output
        assert "sentiment-analyzer" not in result.output
        assert "1 models" in result.output

    def test_filter_by_vendor(self, sample_models):
        """Test filtering by vendor."""
        result = runner.invoke(app, ["list", "--vendor", "in-house"])

        assert result.exit_code == 0
        assert "fraud-detector" in result.output
        assert "sentiment-analyzer" in result.output
        assert "claude-assistant" not in result.output
        assert "2 models" in result.output

    def test_filter_by_environment(self, sample_models):
        """Test filtering by environment."""
        result = runner.invoke(app, ["list", "--environment", "prod"])

        assert result.exit_code == 0
        assert "fraud-detector" in result.output
        assert "claude-assistant" in result.output
        assert "sentiment-analyzer" not in result.output
        assert "2 models" in result.output

    def test_filter_by_status(self, sample_models):
        """Test filtering by status."""
        result = runner.invoke(app, ["list", "--status", "active"])

        assert result.exit_code == 0
        # All models are active by default
        assert "3 models" in result.output

    def test_multiple_filters(self, sample_models):
        """Test combining multiple filters."""
        result = runner.invoke(app, [
            "list",
            "--vendor", "in-house",
            "--environment", "prod",
        ])

        assert result.exit_code == 0
        assert "fraud-detector" in result.output
        assert "sentiment-analyzer" not in result.output  # staging
        assert "claude-assistant" not in result.output  # anthropic
        assert "1 models" in result.output

    def test_filter_no_results(self, sample_models):
        """Test filter with no matching results."""
        result = runner.invoke(app, ["list", "--vendor", "nonexistent"])

        assert result.exit_code == 0
        assert "no models" in result.output.lower()
        assert "vendor=nonexistent" in result.output

    def test_invalid_risk_tier_filter(self, sample_models):
        """Test invalid risk tier filter."""
        result = runner.invoke(app, ["list", "--risk", "invalid"])

        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output

    def test_invalid_status_filter(self, sample_models):
        """Test invalid status filter."""
        result = runner.invoke(app, ["list", "--status", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.output

    def test_invalid_environment_filter(self, sample_models):
        """Test invalid environment filter."""
        result = runner.invoke(app, ["list", "--environment", "invalid"])

        assert result.exit_code == 1
        assert "Invalid environment" in result.output

    def test_environment_aliases(self, sample_models):
        """Test environment filter accepts aliases."""
        result = runner.invoke(app, ["list", "--environment", "production"])

        assert result.exit_code == 0
        assert "2 models" in result.output  # prod models


class TestListOutputFormats:
    """Tests for list command output formats."""

    def test_verbose_output(self, sample_models):
        """Test verbose output shows more columns."""
        result = runner.invoke(app, ["list", "--verbose"])

        assert result.exit_code == 0
        assert "Business Owner" in result.output or "B…" in result.output
        assert "Technical Owner" in result.output or "T…" in result.output

    def test_json_output(self, sample_models):
        """Test JSON output format."""
        result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0

        # Parse JSON output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

        # Check structure
        model = data[0]
        assert "id" in model
        assert "model_name" in model
        assert "vendor" in model
        assert "risk_tier" in model

    def test_json_output_with_filter(self, sample_models):
        """Test JSON output with filter applied."""
        result = runner.invoke(app, ["list", "--json", "--risk", "critical"])

        assert result.exit_code == 0

        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["model_name"] == "fraud-detector"
        assert data[0]["risk_tier"] == "critical"

    def test_csv_export(self, sample_models, tmp_path):
        """Test CSV export."""
        output_path = tmp_path / "export.csv"

        result = runner.invoke(app, ["list", "--output", str(output_path)])

        assert result.exit_code == 0
        assert "Exported 3 models" in result.output
        assert output_path.exists()

        # Verify CSV content
        content = output_path.read_text()
        assert "model_name" in content  # Header
        assert "fraud-detector" in content
        assert "claude-assistant" in content

    def test_csv_export_with_filter(self, sample_models, tmp_path):
        """Test CSV export with filter."""
        output_path = tmp_path / "filtered.csv"

        result = runner.invoke(app, [
            "list",
            "--output", str(output_path),
            "--risk", "high",
        ])

        assert result.exit_code == 0
        assert "Exported 1 models" in result.output

        content = output_path.read_text()
        assert "claude-assistant" in content
        assert "fraud-detector" not in content

    def test_csv_export_empty_result(self, sample_models, tmp_path):
        """Test CSV export with no results."""
        output_path = tmp_path / "empty.csv"

        result = runner.invoke(app, [
            "list",
            "--output", str(output_path),
            "--vendor", "nonexistent",
        ])

        assert result.exit_code == 0
        assert "No models to export" in result.output


class TestListTableDisplay:
    """Tests for list command table display."""

    def test_table_shows_model_names(self, sample_models):
        """Test that table displays model names."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Model Name" in result.output
        assert "fraud-detector" in result.output

    def test_table_shows_risk_tiers(self, sample_models):
        """Test that table displays risk tiers."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Risk" in result.output
        assert "CRITICAL" in result.output
        assert "HIGH" in result.output
        assert "LOW" in result.output

    def test_table_shows_vendors(self, sample_models):
        """Test that table displays vendors."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Vendor" in result.output
        assert "in-house" in result.output
        assert "anthropic" in result.output

    def test_table_shows_status(self, sample_models):
        """Test that table displays status."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Status" in result.output
        assert "ACTIVE" in result.output

    def test_long_use_case_truncated(self, clean_db):
        """Test that long use cases are truncated."""
        from datetime import date

        create_model({
            "model_name": "long-use-case-model",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "This is a very long use case description that should be truncated in the table display to keep things readable",
            "business_owner": "Test",
            "technical_owner": "Test",
            "deployment_date": date(2024, 1, 1),
        })

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "..." in result.output  # Truncation indicator
