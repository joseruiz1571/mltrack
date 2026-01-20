"""Tests for the mltrack delete CLI command."""

import pytest
from datetime import date
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, get_model
from mltrack.core.exceptions import ModelNotFoundError

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
        "model_name": "delete-test-model",
        "vendor": "test-vendor",
        "risk_tier": "high",
        "use_case": "Testing the delete command",
        "business_owner": "Test Business Owner",
        "technical_owner": "Test Technical Owner",
        "deployment_date": date(2024, 6, 15),
        "deployment_environment": "prod",
        "status": "active",
    })


class TestDeleteCommand:
    """Tests for mltrack delete command."""

    def test_delete_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["delete", "--help"])

        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
        assert "--soft" in result.output
        assert "--yes" in result.output

    def test_delete_nonexistent_model(self, clean_db):
        """Test deleting a model that doesn't exist."""
        result = runner.invoke(app, ["delete", "nonexistent", "-y"])

        assert result.exit_code == 1
        assert "Model not found" in result.output
        assert "nonexistent" in result.output

    def test_delete_by_name(self, sample_model):
        """Test deleting a model by name."""
        result = runner.invoke(app, ["delete", "delete-test-model", "-y"])

        assert result.exit_code == 0
        assert "permanently deleted" in result.output

        # Verify model is gone
        with pytest.raises(ModelNotFoundError):
            get_model("delete-test-model")

    def test_delete_by_id(self, sample_model):
        """Test deleting a model by ID."""
        model_id = sample_model.id

        result = runner.invoke(app, ["delete", model_id, "-y"])

        assert result.exit_code == 0
        assert "permanently deleted" in result.output

        # Verify model is gone
        with pytest.raises(ModelNotFoundError):
            get_model(model_id)


class TestDeleteCommandConfirmation:
    """Tests for delete command confirmation."""

    def test_shows_model_details_before_delete(self, sample_model):
        """Test that model details are shown before deletion."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "delete-test-model" in result.output
        assert "test-vendor" in result.output
        assert "HIGH" in result.output
        assert "Test Business Owner" in result.output

    def test_shows_warning_message(self, sample_model):
        """Test that warning message is shown."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "permanently delete" in result.output.lower() or "cannot be undone" in result.output.lower()

    def test_cancel_does_not_delete(self, sample_model):
        """Test that cancelling does not delete the model."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Verify model still exists
        model = get_model("delete-test-model")
        assert model is not None

    def test_confirm_deletes_model(self, sample_model):
        """Test that confirming deletes the model."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="y\n")

        assert result.exit_code == 0
        assert "permanently deleted" in result.output

        # Verify model is gone
        with pytest.raises(ModelNotFoundError):
            get_model("delete-test-model")

    def test_yes_flag_skips_confirmation(self, sample_model):
        """Test that --yes flag skips confirmation."""
        result = runner.invoke(app, ["delete", "delete-test-model", "-y"])

        assert result.exit_code == 0
        assert "Permanently delete" not in result.output  # No prompt shown
        assert "permanently deleted" in result.output

    def test_default_confirmation_is_no(self, sample_model):
        """Test that default confirmation is No (safe default)."""
        # Just press Enter without typing y or n
        result = runner.invoke(app, ["delete", "delete-test-model"], input="\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Model should still exist
        model = get_model("delete-test-model")
        assert model is not None


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_delete_sets_decommissioned(self, sample_model):
        """Test that soft delete sets status to decommissioned."""
        result = runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        assert result.exit_code == 0
        assert "decommissioned" in result.output.lower()

        # Verify model still exists but is decommissioned
        model = get_model("delete-test-model")
        assert model.status.value == "decommissioned"

    def test_soft_delete_shows_different_message(self, sample_model):
        """Test that soft delete shows appropriate message."""
        result = runner.invoke(app, ["delete", "delete-test-model", "--soft"], input="n\n")

        assert result.exit_code == 0
        assert "Decommission" in result.output
        assert "audit" in result.output.lower()

    def test_soft_delete_preserves_model(self, sample_model):
        """Test that soft delete preserves model data."""
        original_id = sample_model.id
        original_vendor = sample_model.vendor

        result = runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        assert result.exit_code == 0

        # Model should still exist with same data
        model = get_model("delete-test-model")
        assert model.id == original_id
        assert model.vendor == original_vendor
        assert model.status.value == "decommissioned"

    def test_soft_delete_already_decommissioned(self, sample_model):
        """Test soft delete on already decommissioned model."""
        # First soft delete
        runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        # Try to soft delete again
        result = runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        assert result.exit_code == 0
        assert "already decommissioned" in result.output.lower()

    def test_soft_delete_can_still_be_viewed(self, sample_model):
        """Test that soft-deleted model can still be viewed with show command."""
        runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        # Should still be viewable
        result = runner.invoke(app, ["show", "delete-test-model"])

        assert result.exit_code == 0
        assert "delete-test-model" in result.output
        assert "DECOMMISSIONED" in result.output


class TestDeleteCommandDisplay:
    """Tests for delete command display elements."""

    def test_shows_model_summary_table(self, sample_model):
        """Test that model summary is displayed."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output
        assert "Vendor" in result.output
        assert "Risk Tier" in result.output

    def test_hard_delete_shows_red_warning(self, sample_model):
        """Test that hard delete shows strong warning."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "WARNING" in result.output or "cannot be undone" in result.output.lower()

    def test_suggests_soft_delete(self, sample_model):
        """Test that hard delete suggests using --soft."""
        result = runner.invoke(app, ["delete", "delete-test-model"], input="n\n")

        assert result.exit_code == 0
        assert "--soft" in result.output

    def test_success_message_includes_model_name(self, sample_model):
        """Test that success message includes model name."""
        result = runner.invoke(app, ["delete", "delete-test-model", "-y"])

        assert result.exit_code == 0
        assert "delete-test-model" in result.output

    def test_soft_delete_success_shows_view_hint(self, sample_model):
        """Test that soft delete success shows how to view model."""
        result = runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        assert result.exit_code == 0
        assert "mltrack show" in result.output


class TestDeleteCommandIntegration:
    """Integration tests for delete command."""

    def test_deleted_model_not_in_list(self, sample_model):
        """Test that deleted model doesn't appear in list."""
        # Hard delete
        runner.invoke(app, ["delete", "delete-test-model", "-y"])

        # Check list
        result = runner.invoke(app, ["list"])

        assert "delete-test-model" not in result.output

    def test_decommissioned_model_hidden_from_active_list(self, sample_model):
        """Test that decommissioned model is hidden from active list."""
        # Soft delete
        runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        # Check list with active status filter
        result = runner.invoke(app, ["list", "--status", "active"])

        assert "delete-test-model" not in result.output

    def test_decommissioned_model_visible_with_status_filter(self, sample_model):
        """Test that decommissioned model is visible with status filter."""
        # Soft delete
        runner.invoke(app, ["delete", "delete-test-model", "--soft", "-y"])

        # Check list with decommissioned filter
        result = runner.invoke(app, ["list", "--status", "decommissioned"])

        assert "delete-test-model" in result.output

    def test_hard_delete_cannot_be_recovered(self, sample_model):
        """Test that hard delete is permanent."""
        model_id = sample_model.id

        # Hard delete
        runner.invoke(app, ["delete", "delete-test-model", "-y"])

        # Try to get by both name and ID
        with pytest.raises(ModelNotFoundError):
            get_model("delete-test-model")

        with pytest.raises(ModelNotFoundError):
            get_model(model_id)
