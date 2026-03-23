"""Tests for the mltrack reviewed CLI command."""

import pytest
from datetime import date, timedelta
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, get_model, REVIEW_FREQUENCY

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
        "model_name": "review-test-model",
        "vendor": "test-vendor",
        "risk_tier": "high",  # 90-day review cycle
        "use_case": "Testing reviewed command",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today() - timedelta(days=100),
        "status": "active",
    })


@pytest.fixture
def overdue_model(clean_db):
    """Create a model with overdue review."""
    return create_model({
        "model_name": "overdue-model",
        "vendor": "test-vendor",
        "risk_tier": "critical",  # 30-day review cycle
        "use_case": "Testing overdue review",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today() - timedelta(days=60),
        "status": "active",
    })


class TestReviewedCommand:
    """Tests for mltrack reviewed command."""

    def test_reviewed_help(self):
        """Test that --help shows usage information."""
        result = runner.invoke(app, ["reviewed", "--help"])

        assert result.exit_code == 0
        assert "IDENTIFIER" in result.output
        assert "--date" in result.output
        assert "--notes" in result.output

    def test_reviewed_nonexistent_model(self, clean_db):
        """Test reviewing a model that doesn't exist."""
        result = runner.invoke(app, ["reviewed", "nonexistent"])

        assert result.exit_code == 1
        assert "Model not found" in result.output

    def test_reviewed_by_name(self, sample_model):
        """Test recording a review by model name."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0
        assert "Review Recorded" in result.output

    def test_reviewed_by_id(self, sample_model):
        """Test recording a review by model ID."""
        result = runner.invoke(app, ["reviewed", sample_model.id])

        assert result.exit_code == 0
        assert "Review Recorded" in result.output


class TestReviewedDateHandling:
    """Tests for date handling in reviewed command."""

    def test_reviewed_default_today(self, sample_model):
        """Test that default date is today."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0

        model = get_model("review-test-model")
        assert model.last_review_date == date.today()

    def test_reviewed_explicit_today(self, sample_model):
        """Test using 'today' keyword."""
        result = runner.invoke(app, ["reviewed", "review-test-model", "-d", "today"])

        assert result.exit_code == 0

        model = get_model("review-test-model")
        assert model.last_review_date == date.today()

    def test_reviewed_specific_date(self, sample_model):
        """Test using specific date."""
        result = runner.invoke(app, [
            "reviewed", "review-test-model",
            "--date", "2025-06-15",
        ])

        assert result.exit_code == 0

        model = get_model("review-test-model")
        assert model.last_review_date == date(2025, 6, 15)

    def test_reviewed_invalid_date(self, sample_model):
        """Test invalid date format."""
        result = runner.invoke(app, [
            "reviewed", "review-test-model",
            "--date", "15/06/2025",
        ])

        assert result.exit_code == 1
        assert "Invalid date format" in result.output


class TestNextReviewCalculation:
    """Tests for next_review_date calculation."""

    def test_calculates_next_review_critical(self, clean_db):
        """Test next review calculation for critical risk."""
        model = create_model({
            "model_name": "critical-model",
            "vendor": "test",
            "risk_tier": "critical",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today() - timedelta(days=60),
            "status": "active",
        })

        result = runner.invoke(app, ["reviewed", "critical-model"])

        assert result.exit_code == 0

        updated = get_model("critical-model")
        expected_next = date.today() + timedelta(days=30)
        assert updated.next_review_date == expected_next

    def test_calculates_next_review_high(self, sample_model):
        """Test next review calculation for high risk."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0

        updated = get_model("review-test-model")
        expected_next = date.today() + timedelta(days=90)
        assert updated.next_review_date == expected_next

    def test_calculates_next_review_medium(self, clean_db):
        """Test next review calculation for medium risk."""
        create_model({
            "model_name": "medium-model",
            "vendor": "test",
            "risk_tier": "medium",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "status": "active",
        })

        result = runner.invoke(app, ["reviewed", "medium-model"])

        assert result.exit_code == 0

        updated = get_model("medium-model")
        expected_next = date.today() + timedelta(days=180)
        assert updated.next_review_date == expected_next

    def test_calculates_next_review_low(self, clean_db):
        """Test next review calculation for low risk."""
        create_model({
            "model_name": "low-model",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "status": "active",
        })

        result = runner.invoke(app, ["reviewed", "low-model"])

        assert result.exit_code == 0

        updated = get_model("low-model")
        expected_next = date.today() + timedelta(days=365)
        assert updated.next_review_date == expected_next

    def test_next_review_based_on_review_date(self, sample_model):
        """Test that next_review is calculated from last_review_date."""
        review_date = date(2025, 6, 15)

        result = runner.invoke(app, [
            "reviewed", "review-test-model",
            "--date", "2025-06-15",
        ])

        assert result.exit_code == 0

        updated = get_model("review-test-model")
        # High risk = 90 days
        expected_next = review_date + timedelta(days=90)
        assert updated.next_review_date == expected_next


class TestReviewedNotes:
    """Tests for notes handling in reviewed command.

    Notes are now stored in the ModelReview audit trail (model_reviews table),
    not appended to AIModel.notes. AIModel.notes is for general model-level
    notes; ModelReview.notes captures review-specific observations.
    """

    def test_reviewed_with_notes(self, sample_model):
        """Test adding notes with review — notes go to audit trail."""
        result = runner.invoke(app, [
            "reviewed", "review-test-model",
            "-n", "Quarterly review completed",
        ])

        assert result.exit_code == 0
        # Notes appear in the reviewed output summary
        assert "Review note" in result.output
        assert "Quarterly review completed" in result.output
        # AIModel.notes is unchanged — notes live in ModelReview
        model = get_model("review-test-model")
        assert model.notes is None or "Quarterly review completed" not in (model.notes or "")

    def test_reviewed_notes_go_to_audit_trail_not_model(self, sample_model):
        """Notes should be in the ModelReview record, not AIModel.notes."""
        from mltrack.core.review_storage import get_reviews_for_model

        runner.invoke(app, [
            "reviewed", "review-test-model",
            "-n", "Test note for audit trail",
        ])

        reviews = get_reviews_for_model("review-test-model")
        assert len(reviews) == 1
        assert reviews[0].notes == "Test note for audit trail"

        # Model-level notes field should be untouched
        model = get_model("review-test-model")
        assert model.notes is None or "Test note for audit trail" not in (model.notes or "")

    def test_reviewed_preserves_existing_model_notes(self, clean_db):
        """Existing AIModel.notes should be unchanged after mltrack reviewed."""
        create_model({
            "model_name": "notes-model",
            "vendor": "test",
            "risk_tier": "low",
            "use_case": "Test",
            "business_owner": "Owner",
            "technical_owner": "Tech",
            "deployment_date": date.today(),
            "notes": "Existing notes here",
            "status": "active",
        })

        result = runner.invoke(app, [
            "reviewed", "notes-model",
            "-n", "New review note",
        ])

        assert result.exit_code == 0

        model = get_model("notes-model")
        # Existing notes unchanged
        assert "Existing notes here" in model.notes
        # Review note NOT appended to model-level notes
        assert "New review note" not in model.notes


class TestReviewedOutput:
    """Tests for reviewed command output."""

    def test_shows_model_name(self, sample_model):
        """Test that model name is shown."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0
        assert "review-test-model" in result.output

    def test_shows_risk_tier(self, sample_model):
        """Test that risk tier is shown."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0
        assert "HIGH" in result.output

    def test_shows_review_cycle(self, sample_model):
        """Test that review cycle is shown."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0
        assert "90 days" in result.output

    def test_shows_new_dates(self, sample_model):
        """Test that new dates are shown."""
        result = runner.invoke(app, ["reviewed", "review-test-model"])

        assert result.exit_code == 0
        assert "Last Review (now)" in result.output
        assert "Next Review (now)" in result.output

    def test_shows_overdue_indicator(self, overdue_model):
        """Test that overdue indicator is shown for previously overdue models."""
        result = runner.invoke(app, ["reviewed", "overdue-model"])

        assert result.exit_code == 0
        assert "overdue" in result.output.lower()


class TestReviewedValidationIntegration:
    """Tests for reviewed command integration with validation."""

    def test_reviewed_fixes_overdue_validation(self, overdue_model):
        """Test that reviewing fixes validation failures."""
        # First verify it fails validation
        result = runner.invoke(app, ["validate", "-m", "overdue-model"])
        assert result.exit_code == 1
        assert "overdue" in result.output.lower()

        # Record review
        result = runner.invoke(app, ["reviewed", "overdue-model"])
        assert result.exit_code == 0

        # Now should pass validation
        result = runner.invoke(app, ["validate", "-m", "overdue-model"])
        assert result.exit_code == 0
        assert "100.0%" in result.output or "ALL COMPLIANT" in result.output
