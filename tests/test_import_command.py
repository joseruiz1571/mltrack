"""Tests for the import command."""

import csv
import json
import pytest
from datetime import date
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from mltrack.cli.main import app
from mltrack.cli.import_command import (
    _normalize_field_name,
    _parse_date,
    _parse_risk_tier,
    _parse_environment,
    _parse_data_classification,
    _map_record,
    _read_csv,
    _read_json,
    _validate_record,
)
from mltrack.models.ai_model import RiskTier, DeploymentEnvironment, DataClassification

runner = CliRunner()


# =============================================================================
# Unit Tests for Field Mapping Functions
# =============================================================================


class TestNormalizeFieldName:
    """Tests for _normalize_field_name function."""

    def test_exact_match(self):
        """Test exact field name match."""
        assert _normalize_field_name("model_name") == "model_name"
        assert _normalize_field_name("vendor") == "vendor"
        assert _normalize_field_name("risk_tier") == "risk_tier"

    def test_alias_match(self):
        """Test field name aliases."""
        assert _normalize_field_name("name") == "model_name"
        assert _normalize_field_name("model") == "model_name"
        assert _normalize_field_name("provider") == "vendor"
        assert _normalize_field_name("risk") == "risk_tier"
        assert _normalize_field_name("tier") == "risk_tier"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert _normalize_field_name("Model_Name") == "model_name"
        assert _normalize_field_name("VENDOR") == "vendor"
        assert _normalize_field_name("Risk_Tier") == "risk_tier"

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert _normalize_field_name("  name  ") == "model_name"
        assert _normalize_field_name(" vendor ") == "vendor"

    def test_hyphen_to_underscore(self):
        """Test hyphens converted to underscores."""
        assert _normalize_field_name("model-name") == "model_name"
        assert _normalize_field_name("risk-tier") == "risk_tier"
        assert _normalize_field_name("business-owner") == "business_owner"

    def test_unknown_field_returns_none(self):
        """Test unknown field returns None."""
        assert _normalize_field_name("unknown_field") is None
        assert _normalize_field_name("foo") is None


class TestParseDate:
    """Tests for _parse_date function."""

    def test_iso_format(self):
        """Test ISO format date parsing."""
        assert _parse_date("2025-01-15") == date(2025, 1, 15)
        assert _parse_date("2024-12-31") == date(2024, 12, 31)

    def test_slash_format(self):
        """Test slash format date parsing."""
        assert _parse_date("2025/01/15") == date(2025, 1, 15)

    def test_date_object_passthrough(self):
        """Test date object is returned as-is."""
        d = date(2025, 1, 15)
        assert _parse_date(d) == d

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert _parse_date("") is None
        assert _parse_date("   ") is None

    def test_invalid_date_returns_none(self):
        """Test invalid date returns None."""
        assert _parse_date("not-a-date") is None
        assert _parse_date("2025-13-01") is None
        assert _parse_date("invalid") is None


class TestParseRiskTier:
    """Tests for _parse_risk_tier function."""

    def test_valid_tiers(self):
        """Test valid risk tier values."""
        assert _parse_risk_tier("critical") == "critical"
        assert _parse_risk_tier("high") == "high"
        assert _parse_risk_tier("medium") == "medium"
        assert _parse_risk_tier("low") == "low"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert _parse_risk_tier("CRITICAL") == "critical"
        assert _parse_risk_tier("High") == "high"
        assert _parse_risk_tier("MEDIUM") == "medium"

    def test_whitespace_stripped(self):
        """Test whitespace is stripped."""
        assert _parse_risk_tier("  high  ") == "high"

    def test_invalid_returns_none(self):
        """Test invalid tier returns None."""
        assert _parse_risk_tier("extreme") is None
        assert _parse_risk_tier("invalid") is None
        assert _parse_risk_tier("") is None


class TestParseEnvironment:
    """Tests for _parse_environment function."""

    def test_valid_environments(self):
        """Test valid environment values."""
        assert _parse_environment("prod") == "prod"
        assert _parse_environment("staging") == "staging"
        assert _parse_environment("dev") == "dev"

    def test_aliases(self):
        """Test environment aliases."""
        assert _parse_environment("production") == "prod"
        assert _parse_environment("prd") == "prod"
        assert _parse_environment("development") == "dev"
        assert _parse_environment("stg") == "staging"
        assert _parse_environment("stage") == "staging"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert _parse_environment("PROD") == "prod"
        assert _parse_environment("Staging") == "staging"

    def test_invalid_returns_none(self):
        """Test invalid environment returns None."""
        assert _parse_environment("invalid") is None
        assert _parse_environment("test") is None


class TestParseDataClassification:
    """Tests for _parse_data_classification function."""

    def test_valid_classifications(self):
        """Test valid classification values."""
        assert _parse_data_classification("public") == "public"
        assert _parse_data_classification("internal") == "internal"
        assert _parse_data_classification("confidential") == "confidential"
        assert _parse_data_classification("restricted") == "restricted"

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert _parse_data_classification("PUBLIC") == "public"
        assert _parse_data_classification("Confidential") == "confidential"

    def test_invalid_returns_none(self):
        """Test invalid classification returns None."""
        assert _parse_data_classification("secret") is None
        assert _parse_data_classification("invalid") is None


# =============================================================================
# Unit Tests for Record Mapping
# =============================================================================


class TestMapRecord:
    """Tests for _map_record function."""

    def test_maps_required_fields(self):
        """Test mapping of required fields."""
        raw = {
            "name": "test-model",
            "vendor": "Anthropic",
            "risk_tier": "high",
            "use_case": "Test use case",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "2025-01-15",
        }
        mapped, errors = _map_record(raw)
        assert not errors
        assert mapped["model_name"] == "test-model"
        assert mapped["vendor"] == "Anthropic"
        assert mapped["risk_tier"] == "high"
        assert mapped["deployment_date"] == date(2025, 1, 15)

    def test_maps_optional_fields(self):
        """Test mapping of optional fields."""
        raw = {
            "name": "test-model",
            "vendor": "Anthropic",
            "risk_tier": "high",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "2025-01-15",
            "environment": "prod",
            "version": "1.0.0",
            "notes": "Test notes",
        }
        mapped, errors = _map_record(raw)
        assert not errors
        assert mapped["deployment_environment"] == "prod"
        assert mapped["model_version"] == "1.0.0"
        assert mapped["notes"] == "Test notes"

    def test_reports_missing_required_fields(self):
        """Test error reporting for missing required fields."""
        raw = {
            "name": "test-model",
            # Missing vendor, risk_tier, etc.
        }
        mapped, errors = _map_record(raw)
        assert len(errors) > 0
        assert any("Missing required field" in e for e in errors)

    def test_reports_invalid_risk_tier(self):
        """Test error reporting for invalid risk tier."""
        raw = {
            "name": "test-model",
            "vendor": "Anthropic",
            "risk_tier": "extreme",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "2025-01-15",
        }
        mapped, errors = _map_record(raw)
        assert any("Invalid risk tier" in e for e in errors)

    def test_reports_invalid_date(self):
        """Test error reporting for invalid date."""
        raw = {
            "name": "test-model",
            "vendor": "Anthropic",
            "risk_tier": "high",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "not-a-date",
        }
        mapped, errors = _map_record(raw)
        assert any("Invalid date format" in e for e in errors)

    def test_strips_whitespace(self):
        """Test whitespace is stripped from values."""
        raw = {
            "name": "  test-model  ",
            "vendor": " Anthropic ",
            "risk_tier": "high",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "2025-01-15",
        }
        mapped, errors = _map_record(raw)
        assert mapped["model_name"] == "test-model"
        assert mapped["vendor"] == "Anthropic"


# =============================================================================
# Unit Tests for File Reading
# =============================================================================


class TestReadCsv:
    """Tests for _read_csv function."""

    def test_reads_valid_csv(self, tmp_path):
        """Test reading valid CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier\n"
            "model-1,Anthropic,high\n"
            "model-2,OpenAI,low\n"
        )
        records = _read_csv(csv_file)
        assert len(records) == 2
        assert records[0]["name"] == "model-1"
        assert records[1]["vendor"] == "OpenAI"

    def test_handles_empty_csv(self, tmp_path):
        """Test handling empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("name,vendor,risk_tier\n")
        records = _read_csv(csv_file)
        assert len(records) == 0


class TestReadJson:
    """Tests for _read_json function."""

    def test_reads_array_json(self, tmp_path):
        """Test reading JSON array."""
        json_file = tmp_path / "test.json"
        json_file.write_text('[{"name": "model-1"}, {"name": "model-2"}]')
        records = _read_json(json_file)
        assert len(records) == 2

    def test_reads_object_with_models_key(self, tmp_path):
        """Test reading JSON object with 'models' key."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"models": [{"name": "model-1"}]}')
        records = _read_json(json_file)
        assert len(records) == 1

    def test_reads_object_with_data_key(self, tmp_path):
        """Test reading JSON object with 'data' key."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"data": [{"name": "model-1"}]}')
        records = _read_json(json_file)
        assert len(records) == 1

    def test_reads_single_object(self, tmp_path):
        """Test reading single JSON object."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"name": "model-1", "vendor": "Anthropic"}')
        records = _read_json(json_file)
        assert len(records) == 1


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestImportCLIHelp:
    """Tests for import CLI help."""

    def test_help_shows_options(self):
        """Test help displays all options."""
        result = runner.invoke(app, ["import", "--help"])
        assert result.exit_code == 0
        assert "--validate" in result.output
        assert "--update" in result.output
        assert "--continue-on-error" in result.output
        assert "--dry-run" in result.output

    def test_help_shows_short_flags(self):
        """Test help shows short flags."""
        result = runner.invoke(app, ["import", "--help"])
        assert "-v" in result.output
        assert "-u" in result.output
        assert "-c" in result.output


class TestImportCSV:
    """Tests for CSV import."""

    def test_validate_valid_csv(self, tmp_path):
        """Test validating valid CSV file."""
        csv_file = tmp_path / "valid.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,high,Test use case,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 0
        assert "Validation Passed" in result.output

    def test_validate_invalid_csv(self, tmp_path):
        """Test validating invalid CSV file."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,invalid,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output

    def test_dry_run_csv(self, tmp_path):
        """Test dry run with CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--dry-run"])
        assert result.exit_code == 0
        assert "Dry Run" in result.output
        assert "Would import" in result.output


class TestImportJSON:
    """Tests for JSON import."""

    def test_validate_valid_json(self, tmp_path):
        """Test validating valid JSON file."""
        json_file = tmp_path / "valid.json"
        json_file.write_text(json.dumps([{
            "name": "model-1",
            "vendor": "Anthropic",
            "risk_tier": "high",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": "2025-01-15",
        }]))
        result = runner.invoke(app, ["import", str(json_file), "--validate"])
        assert result.exit_code == 0
        assert "Validation Passed" in result.output

    def test_validate_invalid_json(self, tmp_path):
        """Test validating invalid JSON file."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text(json.dumps([{
            "name": "model-1",
            # Missing required fields
        }]))
        result = runner.invoke(app, ["import", str(json_file), "--validate"])
        assert result.exit_code == 1
        assert "validation errors" in result.output


class TestImportWithDatabase:
    """Tests for actual database imports."""

    def test_import_creates_models(self, tmp_path):
        """Test import creates models in database."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "import-test-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )

        with patch("mltrack.cli.import_command.create_model") as mock_create:
            with patch("mltrack.cli.import_command.get_model") as mock_get:
                from mltrack.core.exceptions import ModelNotFoundError
                mock_get.side_effect = ModelNotFoundError("import-test-1")
                mock_create.return_value = MagicMock()

                result = runner.invoke(app, ["import", str(csv_file)])
                assert result.exit_code == 0
                assert "Created" in result.output
                mock_create.assert_called_once()

    def test_import_skips_existing(self, tmp_path):
        """Test import skips existing models."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "existing-model,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )

        with patch("mltrack.cli.import_command.get_model") as mock_get:
            mock_get.return_value = MagicMock()  # Model exists

            result = runner.invoke(app, ["import", str(csv_file)])
            assert result.exit_code == 0
            assert "Skipped" in result.output

    def test_import_updates_with_flag(self, tmp_path):
        """Test import updates existing with --update flag."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "existing-model,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )

        with patch("mltrack.cli.import_command.get_model") as mock_get:
            with patch("mltrack.cli.import_command.update_model") as mock_update:
                mock_get.return_value = MagicMock()  # Model exists

                result = runner.invoke(app, ["import", str(csv_file), "--update"])
                assert result.exit_code == 0
                assert "Updated" in result.output
                mock_update.assert_called_once()


class TestImportErrorHandling:
    """Tests for import error handling."""

    def test_unsupported_file_type(self, tmp_path):
        """Test error for unsupported file type."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not csv or json")
        result = runner.invoke(app, ["import", str(txt_file)])
        assert result.exit_code == 1
        assert "Unsupported file type" in result.output

    def test_file_not_found(self):
        """Test error for non-existent file."""
        result = runner.invoke(app, ["import", "/nonexistent/file.csv"])
        assert result.exit_code != 0

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("name,vendor,risk_tier\n")
        result = runner.invoke(app, ["import", str(csv_file)])
        assert "No records found" in result.output

    def test_continue_on_error_flag(self, tmp_path):
        """Test --continue-on-error imports valid records."""
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "valid-model,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
            "invalid-model,OpenAI,extreme,Test,Owner,Tech,2025-01-15\n"
        )

        with patch("mltrack.cli.import_command.create_model") as mock_create:
            with patch("mltrack.cli.import_command.get_model") as mock_get:
                from mltrack.core.exceptions import ModelNotFoundError
                mock_get.side_effect = ModelNotFoundError("model")
                mock_create.return_value = MagicMock()

                result = runner.invoke(app, ["import", str(csv_file), "--continue-on-error"])
                assert result.exit_code == 0
                assert "Created: 1" in result.output
                assert "Failed: 1" in result.output


class TestImportFieldVariations:
    """Tests for various field name formats."""

    def test_accepts_provider_as_vendor(self, tmp_path):
        """Test 'provider' accepted as vendor field."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,provider,risk_tier,use_case,business_owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_accepts_risk_as_risk_tier(self, tmp_path):
        """Test 'risk' accepted as risk_tier field."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk,use_case,business_owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_accepts_deployed_as_deployment_date(self, tmp_path):
        """Test 'deployed' accepted as deployment_date field."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,business_owner,technical_owner,deployed\n"
            "model-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_accepts_owner_as_business_owner(self, tmp_path):
        """Test 'owner' accepted as business_owner field."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "name,vendor,risk_tier,use_case,owner,technical_owner,deployment_date\n"
            "model-1,Anthropic,high,Test,Owner,Tech,2025-01-15\n"
        )
        result = runner.invoke(app, ["import", str(csv_file), "--validate"])
        assert result.exit_code == 0
        assert "Valid" in result.output
