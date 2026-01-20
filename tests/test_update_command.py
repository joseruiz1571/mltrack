"""Tests for the mltrack update CLI command."""

import pytest
from datetime import date, timedelta
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, get_model

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
def sample_model(clean_db):
    """Create a sample model for testing."""
    return create_model({
        "model_name": "test-model",
        "vendor": "test-vendor",
        "model_version": "1.0",
        "risk_tier": "high",
        "use_case": "Testing the update command",
        "business_owner": "Test Business Owner",
        "technical_owner": "Test Technical Owner",
        "deployment_date": date(2024, 6, 15),
        "deployment_environment": "prod",
        "status": "active",
    })


class TestUpdateCommand:
    """Tests for mltrack update command."""

    def test_update_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["update", "--help"])

        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
        assert "--risk-tier" in result.output
        assert "--status" in result.output
        assert "--yes" in result.output

    def test_update_by_name(self, sample_model):
        """Test updating a model by name."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "new-vendor",
            "-y",
        ])

        assert result.exit_code == 0
        assert "updated successfully" in result.output

        # Verify the change
        model = get_model("test-model")
        assert model.vendor == "new-vendor"

    def test_update_by_id(self, sample_model):
        """Test updating a model by ID."""
        result = runner.invoke(app, [
            "update", sample_model.id,
            "--vendor", "id-updated-vendor",
            "-y",
        ])

        assert result.exit_code == 0
        assert "updated successfully" in result.output

        # Verify the change
        model = get_model(sample_model.id)
        assert model.vendor == "id-updated-vendor"

    def test_update_nonexistent_model(self, clean_db):
        """Test updating a model that doesn't exist."""
        result = runner.invoke(app, [
            "update", "nonexistent",
            "--vendor", "test",
            "-y",
        ])

        assert result.exit_code == 1
        assert "Model not found" in result.output
        assert "nonexistent" in result.output

    def test_update_no_changes(self, sample_model):
        """Test update with no changes specified."""
        result = runner.invoke(app, ["update", "test-model"])

        assert result.exit_code == 0
        assert "No changes specified" in result.output


class TestUpdateCommandFields:
    """Tests for updating specific fields."""

    def test_update_risk_tier(self, sample_model):
        """Test updating risk tier."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--risk-tier", "critical",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.risk_tier.value == "critical"

    def test_update_risk_tier_recalculates_review_date(self, sample_model):
        """Test that updating risk tier recalculates next review date."""
        original_model = get_model("test-model")
        original_next_review = original_model.next_review_date

        result = runner.invoke(app, [
            "update", "test-model",
            "--risk-tier", "critical",  # 30-day cycle vs 90-day
            "-y",
        ])

        assert result.exit_code == 0
        assert "Review Cycle" in result.output
        assert "30 days" in result.output

        # Next review should be recalculated
        model = get_model("test-model")
        assert model.next_review_date != original_next_review

    def test_update_status(self, sample_model):
        """Test updating status."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--status", "deprecated",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.status.value == "deprecated"

    def test_update_multiple_fields(self, sample_model):
        """Test updating multiple fields at once."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "multi-vendor",
            "--risk-tier", "low",
            "--notes", "Updated multiple fields",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.vendor == "multi-vendor"
        assert model.risk_tier.value == "low"
        assert model.notes == "Updated multiple fields"

    def test_update_name(self, sample_model):
        """Test renaming a model."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--name", "renamed-model",
            "-y",
        ])

        assert result.exit_code == 0

        # Old name should not exist
        with pytest.raises(Exception):
            get_model("test-model")

        # New name should work
        model = get_model("renamed-model")
        assert model.model_name == "renamed-model"

    def test_update_environment(self, sample_model):
        """Test updating deployment environment."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--environment", "staging",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.deployment_environment.value == "staging"

    def test_update_deployment_date(self, sample_model):
        """Test updating deployment date."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--deployment-date", "2025-01-01",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.deployment_date == date(2025, 1, 1)

    def test_update_last_review_date(self, sample_model):
        """Test setting last review date."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--last-review-date", "2025-01-15",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        assert model.last_review_date == date(2025, 1, 15)


class TestUpdateCommandValidation:
    """Tests for update command validation."""

    def test_invalid_risk_tier(self, sample_model):
        """Test that invalid risk tier is rejected."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--risk-tier", "invalid",
            "-y",
        ])

        assert result.exit_code == 1
        assert "Invalid risk tier" in result.output

    def test_invalid_status(self, sample_model):
        """Test that invalid status is rejected."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--status", "invalid",
            "-y",
        ])

        assert result.exit_code == 1
        assert "Invalid status" in result.output

    def test_invalid_environment(self, sample_model):
        """Test that invalid environment is rejected."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--environment", "invalid",
            "-y",
        ])

        assert result.exit_code == 1
        assert "Invalid environment" in result.output

    def test_invalid_date_format(self, sample_model):
        """Test that invalid date format is rejected."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--deployment-date", "01/15/2025",
            "-y",
        ])

        assert result.exit_code == 1
        assert "Invalid date format" in result.output

    def test_duplicate_name_rejected(self, sample_model, clean_db):
        """Test that renaming to existing name is rejected."""
        # Create another model
        create_model({
            "model_name": "other-model",
            "vendor": "other",
            "risk_tier": "low",
            "use_case": "Other",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
        })

        result = runner.invoke(app, [
            "update", "test-model",
            "--name", "other-model",
            "-y",
        ])

        assert result.exit_code == 1
        assert "already exists" in result.output


class TestUpdateCommandConfirmation:
    """Tests for update command confirmation."""

    def test_shows_comparison_table(self, sample_model):
        """Test that comparison table is shown."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "new-vendor",
        ], input="n\n")  # Cancel

        assert result.exit_code == 0
        assert "Proposed Changes" in result.output
        assert "Current Value" in result.output
        assert "New Value" in result.output
        assert "test-vendor" in result.output  # Old value
        assert "new-vendor" in result.output  # New value

    def test_cancel_does_not_apply_changes(self, sample_model):
        """Test that cancelling does not apply changes."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "should-not-apply",
        ], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Verify change was not applied
        model = get_model("test-model")
        assert model.vendor == "test-vendor"

    def test_confirm_applies_changes(self, sample_model):
        """Test that confirming applies changes."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "confirmed-vendor",
        ], input="y\n")

        assert result.exit_code == 0
        assert "updated successfully" in result.output

        # Verify change was applied
        model = get_model("test-model")
        assert model.vendor == "confirmed-vendor"

    def test_yes_flag_skips_confirmation(self, sample_model):
        """Test that --yes flag skips confirmation."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "yes-flag-vendor",
            "-y",
        ])

        assert result.exit_code == 0
        assert "Apply these changes?" not in result.output
        assert "updated successfully" in result.output

        # Verify change was applied
        model = get_model("test-model")
        assert model.vendor == "yes-flag-vendor"


class TestUpdateCommandDisplay:
    """Tests for update command display elements."""

    def test_shows_model_name_in_header(self, sample_model):
        """Test that model name is shown in header."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "test",
            "-y",
        ])

        assert result.exit_code == 0
        assert "test-model" in result.output

    def test_shows_risk_tier_change_with_review_cycle(self, sample_model):
        """Test that risk tier change shows review cycle update."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--risk-tier", "critical",
            "-y",
        ])

        assert result.exit_code == 0
        assert "Review Cycle" in result.output
        assert "90 days" in result.output  # Old
        assert "30 days" in result.output  # New

    def test_success_message_shows_show_command(self, sample_model):
        """Test that success message shows how to view details."""
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "test",
            "-y",
        ])

        assert result.exit_code == 0
        assert "mltrack show" in result.output


class TestUpdateCommandTimestamp:
    """Tests for automatic timestamp updates."""

    def test_updated_at_changes(self, sample_model):
        """Test that updated_at timestamp is updated."""
        original_updated_at = sample_model.updated_at

        # Small delay to ensure timestamp difference
        result = runner.invoke(app, [
            "update", "test-model",
            "--vendor", "timestamp-test",
            "-y",
        ])

        assert result.exit_code == 0

        model = get_model("test-model")
        # updated_at should be different (newer)
        assert model.updated_at >= original_updated_at
