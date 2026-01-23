"""Tests for the mltrack validate CLI command."""

import json
import pytest
from datetime import date, timedelta
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
def compliant_model(clean_db):
    """Create a fully compliant model."""
    return create_model({
        "model_name": "compliant-model",
        "vendor": "test-vendor",
        "risk_tier": "low",
        "use_case": "Testing validation",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today(),
        "deployment_environment": "dev",  # Not prod, so no data_classification needed
        "status": "active",
    })


@pytest.fixture
def non_compliant_model(clean_db):
    """Create a model with compliance issues."""
    # Create with overdue review (critical risk, deployed 60 days ago)
    return create_model({
        "model_name": "non-compliant-model",
        "vendor": "test-vendor",
        "risk_tier": "critical",  # 30-day review cycle
        "use_case": "Testing validation failures",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today() - timedelta(days=60),
        "deployment_environment": "prod",
        # Missing data_classification for prod
        "status": "active",
    })


@pytest.fixture
def multiple_models(clean_db):
    """Create multiple models with varying compliance."""
    models = []

    # Compliant model
    models.append(create_model({
        "model_name": "model-compliant",
        "vendor": "vendor-a",
        "risk_tier": "low",
        "use_case": "Compliant model",
        "business_owner": "Owner A",
        "technical_owner": "Tech A",
        "deployment_date": date.today(),
        "status": "active",
    }))

    # Non-compliant: overdue review
    models.append(create_model({
        "model_name": "model-overdue",
        "vendor": "vendor-b",
        "risk_tier": "critical",
        "use_case": "Overdue review",
        "business_owner": "Owner B",
        "technical_owner": "Tech B",
        "deployment_date": date.today() - timedelta(days=60),
        "status": "active",
    }))

    # Non-compliant: missing data classification in prod
    models.append(create_model({
        "model_name": "model-missing-classification",
        "vendor": "vendor-c",
        "risk_tier": "high",
        "use_case": "Missing data classification",
        "business_owner": "Owner C",
        "technical_owner": "Tech C",
        "deployment_date": date.today(),
        "deployment_environment": "prod",
        "status": "active",
    }))

    return models


class TestValidateCommand:
    """Tests for mltrack validate command."""

    def test_validate_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["validate", "--help"])

        assert result.exit_code == 0
        assert "--all" in result.output
        assert "--model-id" in result.output
        assert "--risk" in result.output
        assert "--verbose" in result.output
        assert "--json" in result.output

    def test_validate_no_filter_shows_usage(self, clean_db):
        """Test that running without filter shows usage."""
        result = runner.invoke(app, ["validate"])

        assert result.exit_code == 0
        assert "Please specify which models to validate" in result.output

    def test_validate_empty_inventory(self, clean_db):
        """Test validating empty inventory."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 0
        assert "No models in inventory" in result.output


class TestValidateAllModels:
    """Tests for --all flag."""

    def test_validate_all_compliant(self, compliant_model):
        """Test validating when all models are compliant."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 0
        assert "100.0%" in result.output or "ALL COMPLIANT" in result.output

    def test_validate_all_with_failures(self, multiple_models):
        """Test validating with some failures."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 1
        assert "Failed Validation" in result.output
        assert "model-overdue" in result.output
        assert "model-missing-classification" in result.output

    def test_validate_shows_compliance_rate(self, multiple_models):
        """Test that compliance rate is shown."""
        result = runner.invoke(app, ["validate", "--all"])

        assert "Compliance Rate" in result.output
        assert "33.3%" in result.output  # 1 of 3 compliant


class TestValidateSpecificModel:
    """Tests for --model-id flag."""

    def test_validate_specific_model_pass(self, compliant_model):
        """Test validating a compliant model."""
        result = runner.invoke(app, ["validate", "-m", "compliant-model"])

        assert result.exit_code == 0
        assert "PASS" in result.output or "100.0%" in result.output

    def test_validate_specific_model_fail(self, non_compliant_model):
        """Test validating a non-compliant model."""
        result = runner.invoke(app, ["validate", "-m", "non-compliant-model"])

        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_validate_nonexistent_model(self, clean_db):
        """Test validating a model that doesn't exist."""
        result = runner.invoke(app, ["validate", "-m", "nonexistent"])

        assert result.exit_code == 1
        assert "Model not found" in result.output


class TestValidateByRisk:
    """Tests for --risk flag."""

    def test_validate_by_risk_tier(self, multiple_models):
        """Test validating by risk tier."""
        result = runner.invoke(app, ["validate", "--risk", "critical"])

        assert result.exit_code == 1
        assert "model-overdue" in result.output
        assert "model-compliant" not in result.output  # Low risk

    def test_validate_invalid_risk_tier(self, clean_db):
        """Test validating with invalid risk tier."""
        result = runner.invoke(app, ["validate", "--risk", "invalid"])

        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output

    def test_validate_risk_no_models(self, compliant_model):
        """Test validating risk tier with no matching models."""
        # compliant_model is LOW risk
        result = runner.invoke(app, ["validate", "--risk", "critical"])

        assert result.exit_code == 0
        assert "No models found" in result.output


class TestValidationRules:
    """Tests for individual validation rules."""

    def test_validates_review_schedule(self, clean_db):
        """Test that overdue reviews are flagged."""
        create_model({
            "model_name": "overdue-review",
            "vendor": "test",
            "risk_tier": "critical",  # 30-day review
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=60),
            "status": "active",
        })

        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 1
        assert "Review overdue" in result.output
        assert "30 days" in result.output  # Critical review cycle

    def test_validates_production_data_classification(self, clean_db):
        """Test that production models need data classification."""
        create_model({
            "model_name": "prod-no-classification",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "deployment_environment": "prod",
            # Missing data_classification
            "status": "active",
        })

        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 1
        assert "data classification" in result.output.lower()

    def test_non_prod_doesnt_need_classification(self, clean_db):
        """Test that non-production models don't need data classification."""
        create_model({
            "model_name": "dev-no-classification",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "deployment_environment": "dev",
            # No data_classification - OK for dev
            "status": "active",
        })

        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 0  # Should pass

    def test_decommissioned_skips_review_check(self, clean_db):
        """Test that decommissioned models skip review validation."""
        create_model({
            "model_name": "decommissioned-model",
            "vendor": "test",
            "risk_tier": "critical",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=365),  # Very old
            "status": "decommissioned",
        })

        result = runner.invoke(app, ["validate", "--all"])

        # Should pass - decommissioned models skip review check
        assert result.exit_code == 0


class TestValidateOutput:
    """Tests for validate command output formats."""

    def test_verbose_shows_passing_models(self, multiple_models):
        """Test that --verbose shows passing models."""
        result = runner.invoke(app, ["validate", "--all", "-v"])

        assert "Passed Validation" in result.output
        assert "model-compliant" in result.output
        assert "PASS" in result.output

    def test_json_output_format(self, multiple_models):
        """Test JSON output format."""
        result = runner.invoke(app, ["validate", "--all", "--json"])

        # Parse JSON
        data = json.loads(result.output)

        assert "summary" in data
        assert "results" in data
        assert data["summary"]["total_models"] == 3
        assert data["summary"]["passed_models"] == 1
        assert data["summary"]["failed_models"] == 2

    def test_json_includes_violations(self, non_compliant_model):
        """Test that JSON output includes violations."""
        result = runner.invoke(app, ["validate", "--all", "--json"])

        data = json.loads(result.output)

        assert len(data["results"]) == 1
        assert data["results"][0]["passed"] is False
        assert len(data["results"][0]["violations"]) > 0

    def test_shows_violation_summary(self, multiple_models):
        """Test that violation summary is shown."""
        result = runner.invoke(app, ["validate", "--all"])

        assert "Violation Summary" in result.output


class TestValidateExitCodes:
    """Tests for validate command exit codes."""

    def test_exit_code_0_on_all_pass(self, compliant_model):
        """Test exit code 0 when all models pass."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 0

    def test_exit_code_1_on_failures(self, non_compliant_model):
        """Test exit code 1 when models fail."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 1

    def test_json_exit_code_reflects_status(self, non_compliant_model):
        """Test that JSON output uses correct exit code."""
        result = runner.invoke(app, ["validate", "--all", "--json"])

        assert result.exit_code == 1  # Has failures


class TestValidateSummary:
    """Tests for validation summary display."""

    def test_shows_total_models(self, multiple_models):
        """Test that total model count is shown."""
        result = runner.invoke(app, ["validate", "--all"])

        assert "Total Models" in result.output
        assert "3" in result.output

    def test_shows_passed_count(self, multiple_models):
        """Test that passed count is shown."""
        result = runner.invoke(app, ["validate", "--all"])

        assert "Passed" in result.output

    def test_shows_failed_count(self, multiple_models):
        """Test that failed count is shown."""
        result = runner.invoke(app, ["validate", "--all"])

        assert "Failed" in result.output

    def test_all_compliant_shows_green(self, compliant_model):
        """Test that 100% compliance shows success indicator."""
        result = runner.invoke(app, ["validate", "--all"])

        assert result.exit_code == 0
        assert "100.0%" in result.output or "ALL COMPLIANT" in result.output
