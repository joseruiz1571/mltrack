"""Tests for the ModelReview audit trail and review_storage module."""

import pytest
from datetime import date, timedelta
from typer.testing import CliRunner

from mltrack.cli.main import app
from mltrack.core.database import init_db
from mltrack.core.storage import create_model, get_model, update_model
from mltrack.core.review_storage import (
    create_review,
    get_reviews_for_model,
    get_review_count_for_model,
)
from mltrack.models.model_review import ReviewOutcome, compute_model_hash

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("mltrack.core.database.DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr("mltrack.core.storage.init_db", lambda p=None: init_db(db_path))
    monkeypatch.setattr("mltrack.core.review_storage.init_db", lambda p=None: init_db(db_path))
    init_db(db_path)
    yield db_path


@pytest.fixture
def sample_model(clean_db):
    """Create a sample model for testing."""
    return create_model({
        "model_name": "audit-trail-test-model",
        "vendor": "test-vendor",
        "risk_tier": "high",
        "use_case": "Testing audit trail functionality",
        "business_owner": "Business Owner",
        "technical_owner": "Technical Owner",
        "deployment_date": date.today() - timedelta(days=100),
        "deployment_environment": "prod",
        "data_classification": "confidential",
    })


class TestComputeModelHash:
    """Tests for the model state hash function."""

    def test_hash_is_64_char_hex(self, sample_model):
        """Hash should be a 64-character hex string (SHA-256)."""
        h = compute_model_hash(sample_model)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_model_produces_same_hash(self, sample_model):
        """Same model fields always produce the same hash (deterministic)."""
        h1 = compute_model_hash(sample_model)
        h2 = compute_model_hash(sample_model)
        assert h1 == h2

    def test_different_models_produce_different_hashes(self, clean_db):
        """Two different models should produce different hashes."""
        model_a = create_model({
            "model_name": "model-alpha",
            "vendor": "vendor-a",
            "risk_tier": "high",
            "use_case": "Use case A",
            "business_owner": "Owner A",
            "technical_owner": "Tech A",
            "deployment_date": date.today(),
        })
        model_b = create_model({
            "model_name": "model-beta",
            "vendor": "vendor-b",
            "risk_tier": "low",
            "use_case": "Use case B",
            "business_owner": "Owner B",
            "technical_owner": "Tech B",
            "deployment_date": date.today(),
        })
        assert compute_model_hash(model_a) != compute_model_hash(model_b)

    def test_hash_changes_when_model_fields_change(self, sample_model):
        """If model definition changes, the hash should no longer match."""
        original_hash = compute_model_hash(sample_model)

        # Update a key field
        updated_model = update_model(
            sample_model.model_name,
            {"use_case": "Changed use case — different from original"},
        )
        new_hash = compute_model_hash(updated_model)

        assert original_hash != new_hash

    def test_hash_excludes_review_timestamps(self, sample_model):
        """last_review_date and next_review_date changes should not affect hash."""
        hash_before = compute_model_hash(sample_model)

        # Update only the review dates (normal lifecycle events)
        updated_model = update_model(
            sample_model.model_name,
            {"last_review_date": date.today()},
        )
        hash_after = compute_model_hash(updated_model)

        # Hash should be stable across review date changes
        assert hash_before == hash_after


class TestCreateReview:
    """Tests for the create_review storage function."""

    def test_creates_review_record(self, sample_model):
        """create_review should persist a ModelReview record."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
            outcome=ReviewOutcome.PASSED,
        )
        assert review.id is not None
        assert review.model_id == sample_model.id
        assert review.model_name == sample_model.model_name
        assert review.outcome == ReviewOutcome.PASSED

    def test_review_stores_state_hash(self, sample_model):
        """Review record should contain the model state hash."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
        )
        expected_hash = compute_model_hash(sample_model)
        assert review.model_state_hash == expected_hash

    def test_review_stores_reviewed_at_date(self, sample_model):
        """reviewed_at should be stored as the supplied date."""
        review_date = date.today() - timedelta(days=5)
        review = create_review(model=sample_model, reviewed_at=review_date)
        assert review.reviewed_at == review_date.isoformat()

    def test_review_stores_optional_reviewer(self, sample_model):
        """reviewer field should be stored when provided."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
            reviewer="Jane Smith",
        )
        assert review.reviewer == "Jane Smith"

    def test_review_stores_notes(self, sample_model):
        """Notes should be stored in the review record."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
            notes="Quarterly review completed. No issues found.",
        )
        assert review.notes == "Quarterly review completed. No issues found."

    def test_review_defaults_to_passed_outcome(self, sample_model):
        """Default outcome should be PASSED when not specified."""
        review = create_review(model=sample_model, reviewed_at=date.today())
        assert review.outcome == ReviewOutcome.PASSED

    def test_review_warning_outcome(self, sample_model):
        """WARNING outcome should be stored correctly."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
            outcome=ReviewOutcome.WARNING,
        )
        assert review.outcome == ReviewOutcome.WARNING

    def test_review_failed_outcome(self, sample_model):
        """FAILED outcome should be stored correctly."""
        review = create_review(
            model=sample_model,
            reviewed_at=date.today(),
            outcome=ReviewOutcome.FAILED,
        )
        assert review.outcome == ReviewOutcome.FAILED


class TestGetReviewsForModel:
    """Tests for the get_reviews_for_model storage function."""

    def test_returns_empty_list_for_unreviewed_model(self, sample_model):
        """Model with no reviews should return empty list."""
        reviews = get_reviews_for_model(sample_model.model_name)
        assert reviews == []

    def test_returns_reviews_after_recording(self, sample_model):
        """Should return reviews after they are created."""
        create_review(model=sample_model, reviewed_at=date.today())
        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 1

    def test_accumulates_multiple_reviews(self, sample_model):
        """Multiple reviews should all be returned."""
        create_review(
            model=sample_model,
            reviewed_at=date.today() - timedelta(days=90),
            notes="First review",
        )
        create_review(
            model=sample_model,
            reviewed_at=date.today() - timedelta(days=30),
            notes="Second review",
        )
        create_review(
            model=sample_model,
            reviewed_at=date.today(),
            notes="Third review",
        )

        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 3

    def test_lookup_by_model_id(self, sample_model):
        """Should be retrievable by model ID as well as name."""
        create_review(model=sample_model, reviewed_at=date.today())

        by_name = get_reviews_for_model(sample_model.model_name)
        by_id = get_reviews_for_model(sample_model.id)

        assert len(by_name) == 1
        assert len(by_id) == 1
        assert by_name[0].id == by_id[0].id

    def test_returns_most_recent_first(self, sample_model):
        """Reviews should be returned most recent first."""
        older_date = date.today() - timedelta(days=60)
        newer_date = date.today() - timedelta(days=10)

        create_review(model=sample_model, reviewed_at=older_date, notes="Older")
        create_review(model=sample_model, reviewed_at=newer_date, notes="Newer")

        reviews = get_reviews_for_model(sample_model.model_name)
        assert reviews[0].reviewed_at == newer_date.isoformat()
        assert reviews[1].reviewed_at == older_date.isoformat()

    def test_reviews_isolated_per_model(self, clean_db):
        """Reviews for one model should not appear on another."""
        model_a = create_model({
            "model_name": "model-a",
            "vendor": "v",
            "risk_tier": "low",
            "use_case": "A",
            "business_owner": "O",
            "technical_owner": "T",
            "deployment_date": date.today(),
        })
        model_b = create_model({
            "model_name": "model-b",
            "vendor": "v",
            "risk_tier": "low",
            "use_case": "B",
            "business_owner": "O",
            "technical_owner": "T",
            "deployment_date": date.today(),
        })

        create_review(model=model_a, reviewed_at=date.today())
        create_review(model=model_a, reviewed_at=date.today())

        reviews_b = get_reviews_for_model(model_b.model_name)
        assert len(reviews_b) == 0


class TestReviewCountForModel:
    """Tests for the get_review_count_for_model storage function."""

    def test_zero_count_for_unreviewed(self, sample_model):
        """Count should be 0 for a model with no reviews."""
        assert get_review_count_for_model(sample_model.model_name) == 0

    def test_count_increments_with_each_review(self, sample_model):
        """Count should reflect the number of reviews recorded."""
        create_review(model=sample_model, reviewed_at=date.today())
        assert get_review_count_for_model(sample_model.model_name) == 1

        create_review(model=sample_model, reviewed_at=date.today())
        assert get_review_count_for_model(sample_model.model_name) == 2


class TestReviewedCommandAuditTrail:
    """Integration tests: mltrack reviewed command writes to audit trail."""

    def test_reviewed_command_creates_audit_record(self, sample_model):
        """mltrack reviewed should create a ModelReview record."""
        count_before = get_review_count_for_model(sample_model.model_name)

        result = runner.invoke(app, ["reviewed", sample_model.model_name])
        assert result.exit_code == 0

        count_after = get_review_count_for_model(sample_model.model_name)
        assert count_after == count_before + 1

    def test_reviewed_command_with_outcome_flag(self, sample_model):
        """--outcome flag should be stored in the review record."""
        runner.invoke(
            app,
            ["reviewed", sample_model.model_name, "--outcome", "warning"],
        )
        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 1
        assert reviews[0].outcome == ReviewOutcome.WARNING

    def test_reviewed_command_with_reviewer_flag(self, sample_model):
        """--reviewer flag should be stored in the review record."""
        runner.invoke(
            app,
            ["reviewed", sample_model.model_name, "--reviewer", "Jane Smith"],
        )
        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 1
        assert reviews[0].reviewer == "Jane Smith"

    def test_reviewed_command_notes_go_to_review_record(self, sample_model):
        """--notes should be stored in the review record, not appended to model notes."""
        model_before = get_model(sample_model.model_name)
        original_notes = model_before.notes

        runner.invoke(
            app,
            ["reviewed", sample_model.model_name, "--notes", "Q1 review completed"],
        )

        # Model notes should be unchanged
        model_after = get_model(sample_model.model_name)
        assert model_after.notes == original_notes

        # Review record should have the notes
        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 1
        assert reviews[0].notes == "Q1 review completed"

    def test_multiple_reviews_accumulate(self, sample_model):
        """Running mltrack reviewed multiple times should accumulate records."""
        runner.invoke(app, ["reviewed", sample_model.model_name, "--notes", "First"])
        runner.invoke(app, ["reviewed", sample_model.model_name, "--notes", "Second"])
        runner.invoke(app, ["reviewed", sample_model.model_name, "--notes", "Third"])

        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 3

    def test_reviewed_command_hash_matches_model_state(self, sample_model):
        """Hash stored in review should match the model's state at review time."""
        runner.invoke(app, ["reviewed", sample_model.model_name])

        reviews = get_reviews_for_model(sample_model.model_name)
        assert len(reviews) == 1

        current_model = get_model(sample_model.model_name)
        expected_hash = compute_model_hash(current_model)
        assert reviews[0].model_state_hash == expected_hash

    def test_invalid_outcome_flag_exits_nonzero(self, sample_model):
        """Invalid --outcome value should exit with non-zero code."""
        result = runner.invoke(
            app,
            ["reviewed", sample_model.model_name, "--outcome", "invalid-outcome"],
        )
        assert result.exit_code != 0
