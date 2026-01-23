"""Tests for the sample-data command."""

import pytest
from datetime import date
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from mltrack.cli.main import app
from mltrack.cli.sample_data_command import (
    _generate_model_name,
    _generate_deployment_date,
    _generate_sample_model,
    VENDORS,
    USE_CASES,
    BUSINESS_OWNERS,
    TECHNICAL_OWNERS,
)
from mltrack.core.storage import REVIEW_FREQUENCY
from mltrack.models.ai_model import RiskTier

runner = CliRunner()


# =============================================================================
# Unit Tests for Helper Functions
# =============================================================================


class TestGenerateModelName:
    """Tests for _generate_model_name function."""

    def test_returns_base_name_when_unique(self):
        """Test returns base name when no conflicts."""
        name = _generate_model_name("Anthropic", "claude-3", set())
        assert name == "claude-3"

    def test_avoids_duplicates(self):
        """Test generates unique name when base exists."""
        existing = {"claude-3"}
        name = _generate_model_name("Anthropic", "claude-3", existing)
        assert name != "claude-3"
        assert "claude-3" in name

    def test_tries_suffixes(self):
        """Test tries various suffixes."""
        existing = {"claude-3"}
        name = _generate_model_name("Anthropic", "claude-3", existing)
        # Should try -prod, -v2, etc.
        assert name in ["claude-3-prod", "claude-3-v2", "claude-3-enterprise", "claude-3-fsi"]


class TestGenerateDeploymentDate:
    """Tests for _generate_deployment_date function."""

    def test_overdue_date_is_past_review_period(self):
        """Test overdue models have deployment date beyond review period."""
        today = date.today()

        for tier in RiskTier:
            deploy_date = _generate_deployment_date(tier, make_overdue=True)
            days_since = (today - deploy_date).days
            review_days = REVIEW_FREQUENCY[tier]
            assert days_since > review_days, f"Overdue {tier.value} should be past {review_days} days"

    def test_compliant_date_is_within_review_period(self):
        """Test compliant models have deployment date within review period."""
        today = date.today()

        for tier in RiskTier:
            deploy_date = _generate_deployment_date(tier, make_overdue=False)
            days_since = (today - deploy_date).days
            review_days = REVIEW_FREQUENCY[tier]
            assert days_since < review_days, f"Compliant {tier.value} should be within {review_days} days"

    def test_date_is_in_past(self):
        """Test generated date is always in the past."""
        today = date.today()
        for tier in RiskTier:
            for overdue in [True, False]:
                deploy_date = _generate_deployment_date(tier, overdue)
                assert deploy_date < today


class TestGenerateSampleModel:
    """Tests for _generate_sample_model function."""

    def test_returns_dict_with_required_fields(self):
        """Test generated model has all required fields."""
        model = _generate_sample_model(set())
        required = [
            "model_name",
            "vendor",
            "risk_tier",
            "use_case",
            "business_owner",
            "technical_owner",
            "deployment_date",
        ]
        for field in required:
            assert field in model, f"Missing required field: {field}"

    def test_vendor_is_valid(self):
        """Test vendor is from known list."""
        model = _generate_sample_model(set())
        valid_vendors = [v[0] for v in VENDORS]
        assert model["vendor"] in valid_vendors

    def test_risk_tier_is_valid(self):
        """Test risk tier is valid enum value."""
        model = _generate_sample_model(set())
        valid_tiers = [t.value for t in RiskTier]
        assert model["risk_tier"] in valid_tiers

    def test_business_owner_is_valid(self):
        """Test business owner is from list."""
        model = _generate_sample_model(set())
        assert model["business_owner"] in BUSINESS_OWNERS

    def test_technical_owner_is_valid(self):
        """Test technical owner is from list."""
        model = _generate_sample_model(set())
        assert model["technical_owner"] in TECHNICAL_OWNERS

    def test_generates_unique_names(self):
        """Test generates unique model names."""
        existing = set()
        names = []
        for _ in range(20):
            model = _generate_sample_model(existing)
            names.append(model["model_name"])
        # All names should be unique
        assert len(names) == len(set(names))


# =============================================================================
# Tests for Data Constants
# =============================================================================


class TestDataConstants:
    """Tests for sample data constants."""

    def test_vendors_have_models(self):
        """Test each vendor has associated model names."""
        for vendor_name, models in VENDORS:
            assert len(models) > 0, f"Vendor {vendor_name} has no models"

    def test_use_cases_have_risk_tiers(self):
        """Test each use case has a risk tier."""
        for use_case, risk_tier, vendors in USE_CASES:
            assert isinstance(risk_tier, RiskTier)
            assert len(vendors) > 0

    def test_use_cases_cover_all_risk_tiers(self):
        """Test use cases cover all risk tiers."""
        tiers_covered = {uc[1] for uc in USE_CASES}
        for tier in RiskTier:
            assert tier in tiers_covered, f"No use case for {tier.value}"

    def test_business_owners_not_empty(self):
        """Test business owners list is populated."""
        assert len(BUSINESS_OWNERS) >= 5

    def test_technical_owners_not_empty(self):
        """Test technical owners list is populated."""
        assert len(TECHNICAL_OWNERS) >= 5


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestSampleDataCLIHelp:
    """Tests for sample-data CLI help."""

    def test_help_shows_options(self):
        """Test help displays all options."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert result.exit_code == 0
        assert "--count" in result.output
        assert "--clear" in result.output
        assert "--overdue-percent" in result.output

    def test_help_shows_short_flags(self):
        """Test help shows short flags."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert "-n" in result.output
        assert "-c" in result.output


class TestSampleDataGeneration:
    """Tests for sample data generation."""

    def test_generates_requested_count(self):
        """Test generates the requested number of models."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test"
                mock_model.vendor = "Test"
                mock_model.risk_tier = RiskTier.MEDIUM
                mock_model.use_case = "Test"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "5"])

        assert result.exit_code == 0
        assert mock_create.call_count == 5

    def test_shows_success_message(self):
        """Test shows success message with summary."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test"
                mock_model.vendor = "Test"
                mock_model.risk_tier = RiskTier.MEDIUM
                mock_model.use_case = "Test"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "3"])

        assert result.exit_code == 0
        assert "Sample Data Generated" in result.output

    def test_shows_risk_distribution(self):
        """Test shows risk tier distribution in output."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test"
                mock_model.vendor = "Test"
                mock_model.risk_tier = RiskTier.HIGH
                mock_model.use_case = "Test"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "3"])

        assert result.exit_code == 0
        assert "Risk Distribution" in result.output


class TestSampleDataClear:
    """Tests for --clear flag."""

    def test_clear_deletes_existing(self):
        """Test --clear deletes existing models."""
        mock_model = MagicMock()
        mock_model.model_name = "existing-model"

        with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
            with patch("mltrack.cli.sample_data_command.delete_model") as mock_delete:
                with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
                    # First call returns existing, second call returns empty
                    mock_get.side_effect = [[mock_model], []]

                    new_model = MagicMock()
                    new_model.model_name = "new"
                    new_model.vendor = "Test"
                    new_model.risk_tier = RiskTier.LOW
                    new_model.use_case = "Test"
                    new_model.deployment_environment = None
                    new_model.next_review_date = date.today()
                    mock_create.return_value = new_model

                    result = runner.invoke(app, ["sample-data", "--clear", "--count", "1"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("existing-model")

    def test_clear_shows_message(self):
        """Test --clear shows clearing message."""
        mock_model = MagicMock()
        mock_model.model_name = "existing"

        with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
            with patch("mltrack.cli.sample_data_command.delete_model"):
                with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
                    mock_get.side_effect = [[mock_model], []]
                    new_model = MagicMock()
                    new_model.model_name = "new"
                    new_model.vendor = "Test"
                    new_model.risk_tier = RiskTier.LOW
                    new_model.use_case = "Test"
                    new_model.deployment_environment = None
                    new_model.next_review_date = date.today()
                    mock_create.return_value = new_model

                    result = runner.invoke(app, ["sample-data", "--clear", "--count", "1"])

        assert "Clearing" in result.output


class TestSampleDataOverduePercent:
    """Tests for --overdue-percent flag."""

    def test_overdue_percent_option_exists(self):
        """Test --overdue-percent option is available."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert "--overdue-percent" in result.output

    def test_overdue_percent_default(self):
        """Test default overdue percent is 25."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert "25" in result.output


class TestSampleDataValidation:
    """Tests for input validation."""

    def test_count_minimum_enforced(self):
        """Test count has minimum of 1."""
        result = runner.invoke(app, ["sample-data", "--count", "0"])
        assert result.exit_code != 0

    def test_count_maximum_enforced(self):
        """Test count has maximum of 100."""
        result = runner.invoke(app, ["sample-data", "--count", "101"])
        assert result.exit_code != 0

    def test_overdue_percent_minimum(self):
        """Test overdue percent minimum is 0."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert "0<=x<=100" in result.output

    def test_overdue_percent_maximum(self):
        """Test overdue percent maximum is 100."""
        result = runner.invoke(app, ["sample-data", "--help"])
        assert "0<=x<=100" in result.output


class TestSampleDataOutput:
    """Tests for output formatting."""

    def test_shows_compliance_stats(self):
        """Test shows compliance statistics."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test"
                mock_model.vendor = "Test"
                mock_model.risk_tier = RiskTier.MEDIUM
                mock_model.use_case = "Test"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "3"])

        assert result.exit_code == 0
        assert "Compliance" in result.output
        assert "Compliant" in result.output

    def test_shows_environment_distribution(self):
        """Test shows environment distribution."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test"
                mock_model.vendor = "Test"
                mock_model.risk_tier = RiskTier.MEDIUM
                mock_model.use_case = "Test"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "3"])

        assert result.exit_code == 0
        assert "Environment" in result.output
        assert "Production" in result.output

    def test_shows_sample_models(self):
        """Test shows example created models."""
        with patch("mltrack.cli.sample_data_command.create_model") as mock_create:
            with patch("mltrack.cli.sample_data_command.get_all_models") as mock_get:
                mock_get.return_value = []
                mock_model = MagicMock()
                mock_model.model_name = "test-model-name"
                mock_model.vendor = "TestVendor"
                mock_model.risk_tier = RiskTier.HIGH
                mock_model.use_case = "Test use case description"
                mock_model.deployment_environment = None
                mock_model.next_review_date = date.today()
                mock_create.return_value = mock_model

                result = runner.invoke(app, ["sample-data", "--count", "3"])

        assert result.exit_code == 0
        assert "Sample models created" in result.output
