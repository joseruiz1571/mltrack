"""Tests for the mltrack show CLI command."""

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
def sample_model(clean_db):
    """Create a sample model for testing."""
    return create_model({
        "model_name": "test-model",
        "vendor": "test-vendor",
        "model_version": "1.0",
        "risk_tier": "high",
        "use_case": "Testing the show command functionality",
        "business_owner": "Test Business Owner",
        "technical_owner": "Test Technical Owner",
        "deployment_date": date(2024, 6, 15),
        "deployment_environment": "prod",
        "api_endpoint": "https://api.example.com/v1",
        "data_classification": "confidential",
        "notes": "This is a test model with notes.",
    })


@pytest.fixture
def minimal_model(clean_db):
    """Create a model with minimal fields."""
    return create_model({
        "model_name": "minimal-model",
        "vendor": "minimal-vendor",
        "risk_tier": "low",
        "use_case": "Minimal test",
        "business_owner": "Owner",
        "technical_owner": "Tech",
        "deployment_date": date.today(),
    })


class TestShowCommand:
    """Tests for mltrack show command."""

    def test_show_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["show", "--help"])

        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
        assert "Model name or ID" in result.output

    def test_show_model_by_name(self, sample_model):
        """Test showing a model by name."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "test-model" in result.output
        assert "test-vendor" in result.output
        assert "HIGH" in result.output

    def test_show_model_by_id(self, sample_model):
        """Test showing a model by ID."""
        result = runner.invoke(app, ["show", sample_model.id])

        assert result.exit_code == 0
        assert "test-model" in result.output
        assert sample_model.id in result.output

    def test_show_nonexistent_model(self, clean_db):
        """Test showing a model that doesn't exist."""
        result = runner.invoke(app, ["show", "nonexistent"])

        assert result.exit_code == 1
        assert "Model not found" in result.output
        assert "nonexistent" in result.output
        assert "mltrack list" in result.output


class TestShowCommandDisplay:
    """Tests for show command display elements."""

    def test_shows_model_details_panel(self, sample_model):
        """Test that Model Details panel is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Model Details" in result.output

    def test_shows_identity_section(self, sample_model):
        """Test that Identity & Classification section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Identity" in result.output
        assert sample_model.id in result.output
        assert "test-vendor" in result.output

    def test_shows_risk_tier_with_review_cycle(self, sample_model):
        """Test that risk tier shows review cycle."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "HIGH" in result.output
        assert "90-day review cycle" in result.output

    def test_shows_use_case_section(self, sample_model):
        """Test that Use Case section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Use Case" in result.output
        assert "Testing the show command functionality" in result.output

    def test_shows_ownership_section(self, sample_model):
        """Test that Ownership section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Ownership" in result.output
        assert "Test Business Owner" in result.output
        assert "Test Technical Owner" in result.output

    def test_shows_deployment_section(self, sample_model):
        """Test that Deployment section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Deployment" in result.output
        assert "2024-06-15" in result.output
        assert "PROD" in result.output
        assert "https://api.example.com/v1" in result.output

    def test_shows_review_schedule_section(self, sample_model):
        """Test that Review Schedule section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Review Schedule" in result.output
        assert "Next Review" in result.output
        assert "Review Cycle" in result.output

    def test_shows_notes_when_present(self, sample_model):
        """Test that Notes section is displayed when notes exist."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Notes" in result.output
        assert "This is a test model with notes" in result.output

    def test_hides_notes_when_absent(self, minimal_model):
        """Test that Notes section is hidden when no notes."""
        result = runner.invoke(app, ["show", "minimal-model"])

        assert result.exit_code == 0
        # Notes panel should not appear for minimal model
        assert "This is a test model" not in result.output

    def test_shows_metadata_section(self, sample_model):
        """Test that Metadata section is displayed."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Metadata" in result.output
        assert "Created" in result.output
        assert "Last Updated" in result.output

    def test_shows_data_classification(self, sample_model):
        """Test that data classification is shown when present."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "Data Classification" in result.output
        assert "CONFIDENTIAL" in result.output

    def test_shows_version(self, sample_model):
        """Test that version is shown when present."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "v1.0" in result.output


class TestShowCommandCalculations:
    """Tests for calculated fields in show command."""

    def test_shows_days_deployed(self, sample_model):
        """Test that days since deployment is calculated."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        # Should show some time-based indication
        assert "ago" in result.output or "days" in result.output

    def test_shows_deployed_today_for_new_model(self, clean_db):
        """Test that 'Deployed today' is shown for same-day deployment."""
        create_model({
            "model_name": "today-model",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
        })

        result = runner.invoke(app, ["show", "today-model"])

        assert result.exit_code == 0
        assert "Deployed today" in result.output

    def test_shows_overdue_review(self, clean_db):
        """Test that overdue reviews are highlighted."""
        # Create model with past deployment and next_review_date
        create_model({
            "model_name": "overdue-model",
            "vendor": "test",
            "risk_tier": "critical",  # 30-day review cycle
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=60),
        })

        result = runner.invoke(app, ["show", "overdue-model"])

        assert result.exit_code == 0
        assert "OVERDUE" in result.output

    def test_shows_upcoming_review(self, clean_db):
        """Test that upcoming reviews within a week are highlighted."""
        # Create model with review due soon
        create_model({
            "model_name": "upcoming-model",
            "vendor": "test",
            "risk_tier": "low",  # 365-day review cycle
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
        })

        result = runner.invoke(app, ["show", "upcoming-model"])

        assert result.exit_code == 0
        # Should show days until review
        assert "Due in" in result.output


class TestShowCommandRiskTiers:
    """Tests for different risk tier displays."""

    def test_critical_risk_display(self, clean_db):
        """Test critical risk tier display."""
        create_model({
            "model_name": "critical-model",
            "vendor": "test",
            "risk_tier": "critical",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
        })

        result = runner.invoke(app, ["show", "critical-model"])

        assert result.exit_code == 0
        assert "CRITICAL" in result.output
        assert "30-day review cycle" in result.output

    def test_high_risk_display(self, sample_model):
        """Test high risk tier display."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "HIGH" in result.output
        assert "90-day review cycle" in result.output

    def test_medium_risk_display(self, clean_db):
        """Test medium risk tier display."""
        create_model({
            "model_name": "medium-model",
            "vendor": "test",
            "risk_tier": "medium",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
        })

        result = runner.invoke(app, ["show", "medium-model"])

        assert result.exit_code == 0
        assert "MEDIUM" in result.output
        assert "180-day review cycle" in result.output

    def test_low_risk_display(self, minimal_model):
        """Test low risk tier display."""
        result = runner.invoke(app, ["show", "minimal-model"])

        assert result.exit_code == 0
        assert "LOW" in result.output
        assert "365-day review cycle" in result.output


class TestShowCommandStatus:
    """Tests for different status displays."""

    def test_active_status_display(self, sample_model):
        """Test active status display."""
        result = runner.invoke(app, ["show", "test-model"])

        assert result.exit_code == 0
        assert "ACTIVE" in result.output
