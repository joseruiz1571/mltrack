"""Tests for the export command."""

import csv
import json
import pytest
from datetime import date, datetime, timezone
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from mltrack.cli.main import app
from mltrack.cli.export_command import (
    _parse_risk_tier,
    _parse_environment,
    _parse_status,
    _filter_models,
    _model_to_dict,
    EXPORT_FIELDS,
    CSV_HEADERS,
)
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    ModelStatus,
)

runner = CliRunner()


def _create_mock_model(
    name: str = "test-model",
    vendor: str = "test-vendor",
    risk_tier: RiskTier = RiskTier.MEDIUM,
    status: ModelStatus = ModelStatus.ACTIVE,
    environment: DeploymentEnvironment | None = None,
) -> AIModel:
    """Create a mock AIModel for testing."""
    model = MagicMock(spec=AIModel)
    model.model_name = name
    model.vendor = vendor
    model.risk_tier = risk_tier
    model.status = status
    model.deployment_environment = environment
    model.use_case = "Test use case"
    model.business_owner = "Test Owner"
    model.technical_owner = "Tech Owner"
    model.deployment_date = date(2025, 1, 15)
    model.model_version = "1.0.0"
    model.api_endpoint = "https://api.example.com"
    model.data_classification = None
    model.last_review_date = None
    model.next_review_date = date(2025, 4, 15)
    model.notes = "Test notes"
    model.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    model.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return model


# =============================================================================
# Unit Tests for Parsing Functions
# =============================================================================


class TestParseRiskTier:
    """Tests for _parse_risk_tier function."""

    def test_valid_tiers(self):
        """Test valid risk tier parsing."""
        assert _parse_risk_tier("critical") == RiskTier.CRITICAL
        assert _parse_risk_tier("high") == RiskTier.HIGH
        assert _parse_risk_tier("medium") == RiskTier.MEDIUM
        assert _parse_risk_tier("low") == RiskTier.LOW

    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        assert _parse_risk_tier("CRITICAL") == RiskTier.CRITICAL
        assert _parse_risk_tier("High") == RiskTier.HIGH

    def test_invalid_returns_none(self):
        """Test invalid value returns None."""
        assert _parse_risk_tier("invalid") is None
        assert _parse_risk_tier("extreme") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_risk_tier(None) is None


class TestParseEnvironment:
    """Tests for _parse_environment function."""

    def test_valid_environments(self):
        """Test valid environment parsing."""
        assert _parse_environment("prod") == DeploymentEnvironment.PROD
        assert _parse_environment("staging") == DeploymentEnvironment.STAGING
        assert _parse_environment("dev") == DeploymentEnvironment.DEV

    def test_aliases(self):
        """Test environment aliases."""
        assert _parse_environment("production") == DeploymentEnvironment.PROD
        assert _parse_environment("stage") == DeploymentEnvironment.STAGING
        assert _parse_environment("development") == DeploymentEnvironment.DEV

    def test_invalid_returns_none(self):
        """Test invalid value returns None."""
        assert _parse_environment("invalid") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_environment(None) is None


class TestParseStatus:
    """Tests for _parse_status function."""

    def test_valid_statuses(self):
        """Test valid status parsing."""
        assert _parse_status("active") == ModelStatus.ACTIVE
        assert _parse_status("deprecated") == ModelStatus.DEPRECATED
        assert _parse_status("decommissioned") == ModelStatus.DECOMMISSIONED

    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        assert _parse_status("ACTIVE") == ModelStatus.ACTIVE
        assert _parse_status("Deprecated") == ModelStatus.DEPRECATED

    def test_invalid_returns_none(self):
        """Test invalid value returns None."""
        assert _parse_status("invalid") is None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert _parse_status(None) is None


# =============================================================================
# Unit Tests for Filter Function
# =============================================================================


class TestFilterModels:
    """Tests for _filter_models function."""

    def test_no_filters_returns_all(self):
        """Test no filters returns all models."""
        models = [_create_mock_model(name="m1"), _create_mock_model(name="m2")]
        result = _filter_models(models)
        assert len(result) == 2

    def test_filter_by_risk_tier(self):
        """Test filtering by risk tier."""
        models = [
            _create_mock_model(name="critical", risk_tier=RiskTier.CRITICAL),
            _create_mock_model(name="high", risk_tier=RiskTier.HIGH),
            _create_mock_model(name="low", risk_tier=RiskTier.LOW),
        ]
        result = _filter_models(models, risk_tier=RiskTier.CRITICAL)
        assert len(result) == 1
        assert result[0].model_name == "critical"

    def test_filter_by_vendor(self):
        """Test filtering by vendor."""
        models = [
            _create_mock_model(name="m1", vendor="Anthropic"),
            _create_mock_model(name="m2", vendor="OpenAI"),
        ]
        result = _filter_models(models, vendor="anthropic")
        assert len(result) == 1
        assert result[0].model_name == "m1"

    def test_filter_by_environment(self):
        """Test filtering by environment."""
        models = [
            _create_mock_model(name="prod", environment=DeploymentEnvironment.PROD),
            _create_mock_model(name="dev", environment=DeploymentEnvironment.DEV),
        ]
        result = _filter_models(models, environment=DeploymentEnvironment.PROD)
        assert len(result) == 1
        assert result[0].model_name == "prod"

    def test_filter_by_status(self):
        """Test filtering by status."""
        models = [
            _create_mock_model(name="active", status=ModelStatus.ACTIVE),
            _create_mock_model(name="deprecated", status=ModelStatus.DEPRECATED),
        ]
        result = _filter_models(models, status=ModelStatus.ACTIVE)
        assert len(result) == 1
        assert result[0].model_name == "active"

    def test_combined_filters(self):
        """Test combining multiple filters."""
        models = [
            _create_mock_model(
                name="match",
                risk_tier=RiskTier.HIGH,
                environment=DeploymentEnvironment.PROD,
            ),
            _create_mock_model(
                name="no-match",
                risk_tier=RiskTier.LOW,
                environment=DeploymentEnvironment.PROD,
            ),
        ]
        result = _filter_models(
            models,
            risk_tier=RiskTier.HIGH,
            environment=DeploymentEnvironment.PROD,
        )
        assert len(result) == 1
        assert result[0].model_name == "match"


# =============================================================================
# Unit Tests for Model Conversion
# =============================================================================


class TestModelToDict:
    """Tests for _model_to_dict function."""

    def test_converts_all_fields(self):
        """Test all export fields are included."""
        model = _create_mock_model()
        data = _model_to_dict(model)
        for field in EXPORT_FIELDS:
            assert field in data

    def test_converts_enums_to_strings(self):
        """Test enum values are converted to strings."""
        model = _create_mock_model(
            risk_tier=RiskTier.HIGH,
            status=ModelStatus.ACTIVE,
            environment=DeploymentEnvironment.PROD,
        )
        data = _model_to_dict(model)
        assert data["risk_tier"] == "high"
        assert data["status"] == "active"
        assert data["deployment_environment"] == "prod"

    def test_converts_dates_to_iso(self):
        """Test dates are converted to ISO format."""
        model = _create_mock_model()
        data = _model_to_dict(model)
        assert data["deployment_date"] == "2025-01-15"
        assert data["next_review_date"] == "2025-04-15"

    def test_handles_none_values(self):
        """Test None values are converted to empty string."""
        model = _create_mock_model()
        model.data_classification = None
        model.last_review_date = None
        data = _model_to_dict(model)
        assert data["data_classification"] == ""
        assert data["last_review_date"] == ""


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestExportCLIHelp:
    """Tests for export CLI help."""

    def test_help_shows_options(self):
        """Test help displays all options."""
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "--risk" in result.output
        assert "--vendor" in result.output
        assert "--environment" in result.output
        assert "--status" in result.output
        assert "--template" in result.output
        assert "--machine-headers" in result.output
        assert "--compact" in result.output

    def test_help_shows_short_flags(self):
        """Test help shows short flags."""
        result = runner.invoke(app, ["export", "--help"])
        assert "-r" in result.output
        assert "-V" in result.output
        assert "-e" in result.output
        assert "-s" in result.output
        assert "-t" in result.output


class TestExportCSV:
    """Tests for CSV export."""

    def test_exports_csv_file(self, tmp_path):
        """Test basic CSV export."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model(name="test-model")]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(app, ["export", str(output_file)])

        assert result.exit_code == 0
        assert "Export Successful" in result.output
        assert output_file.exists()

    def test_csv_has_headers(self, tmp_path):
        """Test CSV file has headers."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model()]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            runner.invoke(app, ["export", str(output_file)])

        with open(output_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert "Model Name" in headers  # Human-readable header

    def test_csv_machine_headers(self, tmp_path):
        """Test CSV with machine-readable headers."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model()]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            runner.invoke(app, ["export", str(output_file), "--machine-headers"])

        with open(output_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert "model_name" in headers  # Machine-readable header

    def test_csv_contains_data(self, tmp_path):
        """Test CSV file contains model data."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model(name="my-model", vendor="Anthropic")]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            runner.invoke(app, ["export", str(output_file)])

        content = output_file.read_text()
        assert "my-model" in content
        assert "Anthropic" in content


class TestExportJSON:
    """Tests for JSON export."""

    def test_exports_json_file(self, tmp_path):
        """Test basic JSON export."""
        output_file = tmp_path / "export.json"
        models = [_create_mock_model()]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(app, ["export", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

    def test_json_structure(self, tmp_path):
        """Test JSON has expected structure."""
        output_file = tmp_path / "export.json"
        models = [_create_mock_model(), _create_mock_model(name="m2")]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            runner.invoke(app, ["export", str(output_file)])

        data = json.loads(output_file.read_text())
        assert "exported_at" in data
        assert "count" in data
        assert data["count"] == 2
        assert "models" in data
        assert len(data["models"]) == 2

    def test_json_compact_mode(self, tmp_path):
        """Test compact JSON output."""
        output_file = tmp_path / "export.json"
        models = [_create_mock_model()]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            runner.invoke(app, ["export", str(output_file), "--compact"])

        content = output_file.read_text()
        # Compact JSON should be on fewer lines
        assert content.count("\n") < 5


class TestExportTemplate:
    """Tests for template export."""

    def test_exports_template(self, tmp_path):
        """Test template export creates file."""
        output_file = tmp_path / "template.csv"
        result = runner.invoke(app, ["export", str(output_file), "--template"])

        assert result.exit_code == 0
        assert "Template Created" in result.output
        assert output_file.exists()

    def test_template_has_headers_only(self, tmp_path):
        """Test template has headers but no data."""
        output_file = tmp_path / "template.csv"
        runner.invoke(app, ["export", str(output_file), "--template"])

        with open(output_file) as f:
            lines = f.readlines()
            assert len(lines) == 1  # Headers only

    def test_template_has_all_fields(self, tmp_path):
        """Test template has all export fields."""
        output_file = tmp_path / "template.csv"
        runner.invoke(app, ["export", str(output_file), "--template"])

        with open(output_file) as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert len(headers) == len(EXPORT_FIELDS)

    def test_template_json_error(self, tmp_path):
        """Test template mode errors for JSON."""
        output_file = tmp_path / "template.json"
        result = runner.invoke(app, ["export", str(output_file), "--template"])
        assert result.exit_code == 1
        assert "only supports CSV" in result.output


class TestExportFiltering:
    """Tests for filtered exports."""

    def test_filter_by_risk(self, tmp_path):
        """Test filtering by risk tier."""
        output_file = tmp_path / "export.csv"
        models = [
            _create_mock_model(name="high", risk_tier=RiskTier.HIGH),
            _create_mock_model(name="low", risk_tier=RiskTier.LOW),
        ]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(app, ["export", str(output_file), "--risk", "high"])

        assert result.exit_code == 0
        assert "1 model(s)" in result.output
        content = output_file.read_text()
        assert "high" in content

    def test_filter_by_vendor(self, tmp_path):
        """Test filtering by vendor."""
        output_file = tmp_path / "export.csv"
        models = [
            _create_mock_model(name="m1", vendor="Anthropic"),
            _create_mock_model(name="m2", vendor="OpenAI"),
        ]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(
                app, ["export", str(output_file), "--vendor", "anthropic"]
            )

        assert result.exit_code == 0
        assert "1 model(s)" in result.output

    def test_filter_shows_in_output(self, tmp_path):
        """Test filter is shown in success message."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model(risk_tier=RiskTier.HIGH)]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(app, ["export", str(output_file), "--risk", "high"])

        assert "Filters:" in result.output
        assert "risk=high" in result.output

    def test_no_matching_models_warning(self, tmp_path):
        """Test warning when no models match filter."""
        output_file = tmp_path / "export.csv"
        models = [_create_mock_model(risk_tier=RiskTier.LOW)]

        with patch("mltrack.cli.export_command.get_all_models") as mock_get:
            mock_get.return_value = models
            result = runner.invoke(
                app, ["export", str(output_file), "--risk", "critical"]
            )

        assert result.exit_code == 0
        assert "No models found" in result.output


class TestExportErrorHandling:
    """Tests for export error handling."""

    def test_unsupported_file_type(self, tmp_path):
        """Test error for unsupported file type."""
        output_file = tmp_path / "export.txt"
        result = runner.invoke(app, ["export", str(output_file)])
        assert result.exit_code == 1
        assert "Unsupported file type" in result.output

    def test_invalid_risk_tier(self, tmp_path):
        """Test error for invalid risk tier."""
        output_file = tmp_path / "export.csv"
        result = runner.invoke(app, ["export", str(output_file), "--risk", "invalid"])
        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output

    def test_invalid_environment(self, tmp_path):
        """Test error for invalid environment."""
        output_file = tmp_path / "export.csv"
        result = runner.invoke(
            app, ["export", str(output_file), "--environment", "invalid"]
        )
        assert result.exit_code == 1
        assert "Invalid environment" in result.output

    def test_invalid_status(self, tmp_path):
        """Test error for invalid status."""
        output_file = tmp_path / "export.csv"
        result = runner.invoke(app, ["export", str(output_file), "--status", "invalid"])
        assert result.exit_code == 1
        assert "Invalid status" in result.output


class TestExportFields:
    """Tests for export field coverage."""

    def test_all_fields_in_export(self):
        """Test all expected fields are in EXPORT_FIELDS."""
        expected = [
            "model_name",
            "vendor",
            "risk_tier",
            "use_case",
            "business_owner",
            "technical_owner",
            "deployment_date",
            "model_version",
            "deployment_environment",
            "api_endpoint",
            "data_classification",
            "status",
            "last_review_date",
            "next_review_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        for field in expected:
            assert field in EXPORT_FIELDS

    def test_csv_headers_defined(self):
        """Test all export fields have CSV headers."""
        for field in EXPORT_FIELDS:
            assert field in CSV_HEADERS
