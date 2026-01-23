"""Tests for the mltrack add CLI command."""

import pytest
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import reset_db, init_db

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test.db"
    # Monkeypatch the default DB path
    monkeypatch.setattr("mltrack.core.database.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mltrack.core.storage.init_db", lambda p=None: init_db(db_path))
    init_db(db_path)
    yield db_path


class TestAddCommand:
    """Tests for mltrack add command."""

    def test_add_help_shows_options(self):
        """Test that --help shows all options including --interactive."""
        result = runner.invoke(app, ["add", "--help"])

        assert result.exit_code == 0
        assert "--interactive" in result.output
        assert "-i" in result.output
        assert "--name" in result.output
        assert "--vendor" in result.output
        assert "--risk-tier" in result.output
        assert "--use-case" in result.output
        assert "--business-owner" in result.output
        assert "--technical-owner" in result.output
        assert "--deployment-date" in result.output

    def test_add_model_with_required_fields(self, clean_db):
        """Test adding a model with only required fields."""
        result = runner.invoke(app, [
            "add",
            "--name", "test-model",
            "--vendor", "test-vendor",
            "--risk-tier", "low",
            "--use-case", "Testing purposes",
            "--business-owner", "Test Team",
            "--technical-owner", "Dev Team",
            "--deployment-date", "2024-01-15",
        ])

        assert result.exit_code == 0
        assert "Model Added Successfully" in result.output
        assert "test-model" in result.output
        assert "test-vendor" in result.output
        assert "LOW" in result.output

    def test_add_model_with_all_fields(self, clean_db):
        """Test adding a model with all fields."""
        result = runner.invoke(app, [
            "add",
            "--name", "full-model",
            "--vendor", "anthropic",
            "--risk-tier", "high",
            "--use-case", "Customer support chatbot",
            "--business-owner", "Support Team",
            "--technical-owner", "ML Platform",
            "--deployment-date", "2024-06-01",
            "--version", "3.5",
            "--environment", "prod",
            "--api-endpoint", "https://api.example.com",
            "--data-classification", "confidential",
            "--notes", "Production model",
        ])

        assert result.exit_code == 0
        assert "Model Added Successfully" in result.output
        assert "full-model" in result.output
        assert "HIGH" in result.output
        assert "PROD" in result.output
        assert "90 days" in result.output  # HIGH risk = 90 day review

    def test_add_model_critical_risk_30_day_review(self, clean_db):
        """Test that critical risk models get 30-day review cycle."""
        result = runner.invoke(app, [
            "add",
            "--name", "critical-model",
            "--vendor", "internal",
            "--risk-tier", "critical",
            "--use-case", "Trading signals",
            "--business-owner", "Trading Desk",
            "--technical-owner", "Quant Team",
            "--deployment-date", "2024-01-01",
        ])

        assert result.exit_code == 0
        assert "30 days" in result.output
        assert "CRITICAL" in result.output


class TestAddCommandValidation:
    """Tests for input validation."""

    def test_invalid_risk_tier_rejected(self, clean_db):
        """Test that invalid risk tier is rejected."""
        result = runner.invoke(app, [
            "add",
            "--name", "test",
            "--vendor", "test",
            "--risk-tier", "invalid",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
        ])

        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output
        assert "critical, high, medium, low" in result.output

    def test_invalid_date_format_rejected(self, clean_db):
        """Test that invalid date format is rejected."""
        result = runner.invoke(app, [
            "add",
            "--name", "test",
            "--vendor", "test",
            "--risk-tier", "low",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "01/15/2024",  # Wrong format
        ])

        assert result.exit_code == 1
        assert "Invalid date format" in result.output
        assert "YYYY-MM-DD" in result.output

    def test_invalid_environment_rejected(self, clean_db):
        """Test that invalid environment is rejected."""
        result = runner.invoke(app, [
            "add",
            "--name", "test",
            "--vendor", "test",
            "--risk-tier", "low",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
            "--environment", "qa",  # Invalid
        ])

        assert result.exit_code == 1
        assert "Invalid environment" in result.output
        assert "dev, staging, prod" in result.output

    def test_invalid_data_classification_rejected(self, clean_db):
        """Test that invalid data classification is rejected."""
        result = runner.invoke(app, [
            "add",
            "--name", "test",
            "--vendor", "test",
            "--risk-tier", "low",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
            "--data-classification", "secret",  # Invalid
        ])

        assert result.exit_code == 1
        assert "invalid data classification" in result.output.lower()

    def test_environment_aliases_work(self, clean_db):
        """Test that environment aliases like 'production' work."""
        result = runner.invoke(app, [
            "add",
            "--name", "alias-test",
            "--vendor", "test",
            "--risk-tier", "low",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
            "--environment", "production",  # Should map to "prod"
        ])

        assert result.exit_code == 0
        assert "PROD" in result.output

    def test_risk_tier_case_insensitive(self, clean_db):
        """Test that risk tier accepts any case."""
        result = runner.invoke(app, [
            "add",
            "--name", "case-test",
            "--vendor", "test",
            "--risk-tier", "HIGH",  # Uppercase
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
        ])

        assert result.exit_code == 0
        assert "HIGH" in result.output


class TestAddCommandErrors:
    """Tests for error handling."""

    def test_duplicate_name_shows_error(self, clean_db):
        """Test that duplicate model name shows helpful error."""
        # Add first model
        runner.invoke(app, [
            "add",
            "--name", "duplicate-test",
            "--vendor", "test",
            "--risk-tier", "low",
            "--use-case", "test",
            "--business-owner", "test",
            "--technical-owner", "test",
            "--deployment-date", "2024-01-01",
        ])

        # Try to add duplicate
        result = runner.invoke(app, [
            "add",
            "--name", "duplicate-test",
            "--vendor", "different",
            "--risk-tier", "high",
            "--use-case", "different",
            "--business-owner", "different",
            "--technical-owner", "different",
            "--deployment-date", "2024-01-01",
        ])

        assert result.exit_code == 1
        assert "already exists" in result.output
        assert "duplicate-test" in result.output

    def test_missing_required_fields_shows_helpful_error(self, clean_db):
        """Test that missing required fields shows helpful error message."""
        result = runner.invoke(app, [
            "add",
            "--name", "incomplete",
            # Missing other required fields
        ])

        assert result.exit_code == 1
        assert "Missing required fields" in result.output
        assert "--vendor" in result.output
        assert "--risk-tier" in result.output
        assert "--interactive" in result.output  # Suggests interactive mode

    def test_missing_all_fields_shows_all_missing(self, clean_db):
        """Test that missing all fields lists them all."""
        result = runner.invoke(app, ["add"])

        assert result.exit_code == 1
        assert "Missing required fields" in result.output
        assert "--name" in result.output
        assert "--vendor" in result.output
        assert "--risk-tier" in result.output
        assert "--use-case" in result.output
        assert "--business-owner" in result.output
        assert "--technical-owner" in result.output
        assert "--deployment-date" in result.output


class TestAddCommandInteractive:
    """Tests for interactive mode."""

    def test_interactive_flag_exists(self):
        """Test that --interactive flag is available."""
        result = runner.invoke(app, ["add", "--help"])

        assert "--interactive" in result.output
        assert "-i" in result.output
        # The flag description should mention guided prompts
        assert "guided prompts" in result.output.lower() or "interactive" in result.output.lower()

    def test_interactive_mode_prompts_for_fields(self, clean_db):
        """Test that interactive mode prompts for all fields."""
        # Simulate user input for all prompts
        user_input = "\n".join([
            "interactive-test",  # name
            "test-vendor",       # vendor
            "high",              # risk tier
            "Testing interactive mode",  # use case
            "Test Business Owner",  # business owner
            "Test Tech Owner",   # technical owner
            "2024-06-15",        # deployment date
            "",                  # version (skip)
            "",                  # environment (skip)
            "",                  # api endpoint (skip)
            "",                  # data classification (skip)
            "",                  # notes (skip)
            "y",                 # confirm save
        ])

        result = runner.invoke(app, ["add", "--interactive"], input=user_input)

        assert result.exit_code == 0
        assert "Model Added Successfully" in result.output
        assert "interactive-test" in result.output

    def test_interactive_mode_shows_confirmation(self, clean_db):
        """Test that interactive mode shows confirmation before saving."""
        user_input = "\n".join([
            "confirm-test",
            "vendor",
            "low",
            "Test use case",
            "Business",
            "Technical",
            "2024-01-01",
            "",  # skip optional fields
            "",
            "",
            "",
            "",
            "y",  # confirm
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        assert "Model Summary" in result.output
        assert "Save this model?" in result.output
        assert result.exit_code == 0

    def test_interactive_mode_cancel_does_not_save(self, clean_db):
        """Test that cancelling in interactive mode does not save."""
        user_input = "\n".join([
            "cancelled-model",
            "vendor",
            "low",
            "Test use case",
            "Business",
            "Technical",
            "2024-01-01",
            "",
            "",
            "",
            "",
            "",
            "n",  # cancel
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        assert "Model Added Successfully" not in result.output

    def test_interactive_validates_risk_tier(self, clean_db):
        """Test that interactive mode validates risk tier input."""
        user_input = "\n".join([
            "validation-test",
            "vendor",
            "invalid",  # First attempt - invalid
            "high",     # Second attempt - valid
            "Test use case",
            "Business",
            "Technical",
            "2024-01-01",
            "",
            "",
            "",
            "",
            "",
            "y",
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        assert "Invalid risk tier" in result.output
        assert result.exit_code == 0  # Eventually succeeds

    def test_interactive_validates_date_format(self, clean_db):
        """Test that interactive mode validates date format."""
        user_input = "\n".join([
            "date-validation-test",
            "vendor",
            "low",
            "Test use case",
            "Business",
            "Technical",
            "01/15/2024",  # Invalid format
            "2024-01-15",  # Valid format
            "",
            "",
            "",
            "",
            "",
            "y",
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        assert "Invalid date format" in result.output
        assert result.exit_code == 0  # Eventually succeeds

    def test_interactive_shows_review_frequency_hints(self, clean_db):
        """Test that interactive mode shows risk tier review frequency hints."""
        user_input = "\n".join([
            "hints-test",
            "vendor",
            "critical",
            "Test",
            "Business",
            "Technical",
            "2024-01-01",
            "",
            "",
            "",
            "",
            "",
            "y",
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        # Should show review frequency hints
        assert "30 days" in result.output  # critical
        assert "90 days" in result.output  # high (shown in hints)

    def test_interactive_uses_today_as_default_date(self, clean_db):
        """Test that interactive mode defaults deployment date to today."""
        from datetime import date

        today = date.today().isoformat()

        user_input = "\n".join([
            "default-date-test",
            "vendor",
            "low",
            "Test",
            "Business",
            "Technical",
            "",  # Accept default (today)
            "",
            "",
            "",
            "",
            "",
            "y",
        ])

        result = runner.invoke(app, ["add", "-i"], input=user_input)

        assert result.exit_code == 0
        assert today in result.output
