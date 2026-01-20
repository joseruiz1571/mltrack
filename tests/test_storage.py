"""Tests for storage layer CRUD operations."""

from datetime import date, timedelta

import pytest

from mltrack.core.storage import (
    create_model,
    get_model,
    get_all_models,
    update_model,
    delete_model,
    get_models_needing_review,
    get_risk_distribution,
    REVIEW_FREQUENCY,
)
from mltrack.core.exceptions import (
    ModelNotFoundError,
    ModelAlreadyExistsError,
    ValidationError,
)
from mltrack.models import RiskTier, ModelStatus


class TestCreateModel:
    """Tests for create_model function."""

    def test_create_model_with_all_fields(self, initialized_db, sample_model_data):
        """Test creating a model with all fields populated."""
        model = create_model(sample_model_data, initialized_db)

        assert model.id is not None
        assert model.model_name == "fraud-detection-v1"
        assert model.vendor == "in-house"
        assert model.risk_tier == RiskTier.HIGH
        assert model.status == ModelStatus.ACTIVE
        assert model.created_at is not None

    def test_create_model_minimal_fields(self, initialized_db, sample_model_data_minimal):
        """Test creating a model with only required fields."""
        model = create_model(sample_model_data_minimal, initialized_db)

        assert model.id is not None
        assert model.model_name == "simple-model"
        assert model.status == ModelStatus.ACTIVE

    def test_create_model_calculates_next_review_date(self, initialized_db, sample_model_data):
        """Test that next_review_date is calculated from risk tier."""
        model = create_model(sample_model_data, initialized_db)

        expected_date = sample_model_data["deployment_date"] + timedelta(
            days=REVIEW_FREQUENCY[RiskTier.HIGH]
        )
        assert model.next_review_date == expected_date

    def test_create_model_missing_required_field(self, initialized_db):
        """Test that missing required fields raise ValidationError."""
        incomplete_data = {
            "model_name": "incomplete-model",
            "vendor": "test",
            # Missing: risk_tier, use_case, business_owner, technical_owner, deployment_date
        }

        with pytest.raises(ValidationError) as exc_info:
            create_model(incomplete_data, initialized_db)

        assert "required" in str(exc_info.value).lower()

    def test_create_model_invalid_risk_tier(self, initialized_db, sample_model_data_minimal):
        """Test that invalid risk tier raises ValidationError."""
        sample_model_data_minimal["risk_tier"] = "invalid"

        with pytest.raises(ValidationError) as exc_info:
            create_model(sample_model_data_minimal, initialized_db)

        assert "risk_tier" in str(exc_info.value)

    def test_create_model_duplicate_name(self, initialized_db, sample_model_data):
        """Test that duplicate model name raises ModelAlreadyExistsError."""
        create_model(sample_model_data, initialized_db)

        with pytest.raises(ModelAlreadyExistsError) as exc_info:
            create_model(sample_model_data, initialized_db)

        assert "fraud-detection-v1" in str(exc_info.value)

    def test_create_model_converts_string_enums(self, initialized_db, sample_model_data_minimal):
        """Test that string enum values are converted correctly."""
        sample_model_data_minimal["risk_tier"] = "CRITICAL"  # uppercase
        sample_model_data_minimal["deployment_environment"] = "PROD"

        model = create_model(sample_model_data_minimal, initialized_db)

        assert model.risk_tier == RiskTier.CRITICAL


class TestGetModel:
    """Tests for get_model function."""

    def test_get_model_by_id(self, initialized_db, sample_model_data):
        """Test retrieving model by ID."""
        created = create_model(sample_model_data, initialized_db)

        found = get_model(created.id, initialized_db)

        assert found.id == created.id
        assert found.model_name == created.model_name

    def test_get_model_by_name(self, initialized_db, sample_model_data):
        """Test retrieving model by name."""
        created = create_model(sample_model_data, initialized_db)

        found = get_model("fraud-detection-v1", initialized_db)

        assert found.id == created.id

    def test_get_model_not_found(self, initialized_db):
        """Test that non-existent model raises ModelNotFoundError."""
        with pytest.raises(ModelNotFoundError) as exc_info:
            get_model("nonexistent", initialized_db)

        assert "nonexistent" in str(exc_info.value)


class TestGetAllModels:
    """Tests for get_all_models function."""

    def test_get_all_models_empty(self, initialized_db):
        """Test listing models when database is empty."""
        models = get_all_models(initialized_db)

        assert models == []

    def test_get_all_models_returns_all(self, initialized_db, sample_model_data, sample_model_data_minimal):
        """Test listing returns all models."""
        create_model(sample_model_data, initialized_db)
        create_model(sample_model_data_minimal, initialized_db)

        models = get_all_models(initialized_db)

        assert len(models) == 2

    def test_get_all_models_filter_by_status(self, initialized_db, sample_model_data, sample_model_data_minimal):
        """Test filtering models by status."""
        create_model(sample_model_data, initialized_db)
        sample_model_data_minimal["status"] = "deprecated"
        create_model(sample_model_data_minimal, initialized_db)

        active_models = get_all_models(initialized_db, status=ModelStatus.ACTIVE)

        assert len(active_models) == 1
        assert active_models[0].model_name == "fraud-detection-v1"

    def test_get_all_models_filter_by_risk_tier(self, initialized_db, sample_model_data, sample_model_data_minimal):
        """Test filtering models by risk tier."""
        create_model(sample_model_data, initialized_db)  # HIGH
        create_model(sample_model_data_minimal, initialized_db)  # LOW

        high_risk = get_all_models(initialized_db, risk_tier=RiskTier.HIGH)

        assert len(high_risk) == 1
        assert high_risk[0].risk_tier == RiskTier.HIGH


class TestUpdateModel:
    """Tests for update_model function."""

    def test_update_model_single_field(self, initialized_db, sample_model_data):
        """Test updating a single field."""
        created = create_model(sample_model_data, initialized_db)

        updated = update_model(
            created.id,
            {"notes": "Updated notes"},
            initialized_db,
        )

        assert updated.notes == "Updated notes"
        assert updated.model_name == created.model_name  # unchanged

    def test_update_model_multiple_fields(self, initialized_db, sample_model_data):
        """Test updating multiple fields."""
        created = create_model(sample_model_data, initialized_db)

        updated = update_model(
            created.id,
            {
                "model_version": "2.0.0",
                "status": "deprecated",
            },
            initialized_db,
        )

        assert updated.model_version == "2.0.0"
        assert updated.status == ModelStatus.DEPRECATED

    def test_update_model_by_name(self, initialized_db, sample_model_data):
        """Test updating model by name."""
        create_model(sample_model_data, initialized_db)

        updated = update_model(
            "fraud-detection-v1",
            {"notes": "Found by name"},
            initialized_db,
        )

        assert updated.notes == "Found by name"

    def test_update_model_not_found(self, initialized_db):
        """Test updating non-existent model raises error."""
        with pytest.raises(ModelNotFoundError):
            update_model("nonexistent", {"notes": "test"}, initialized_db)

    def test_update_risk_tier_recalculates_review_date(self, initialized_db, sample_model_data):
        """Test that changing risk tier updates next_review_date."""
        created = create_model(sample_model_data, initialized_db)
        original_review_date = created.next_review_date

        updated = update_model(
            created.id,
            {"risk_tier": "critical"},
            initialized_db,
        )

        # CRITICAL has shorter review period than HIGH
        assert updated.next_review_date != original_review_date


class TestDeleteModel:
    """Tests for delete_model function."""

    def test_delete_model_by_id(self, initialized_db, sample_model_data):
        """Test deleting model by ID."""
        created = create_model(sample_model_data, initialized_db)

        result = delete_model(created.id, initialized_db)

        assert result is True
        with pytest.raises(ModelNotFoundError):
            get_model(created.id, initialized_db)

    def test_delete_model_by_name(self, initialized_db, sample_model_data):
        """Test deleting model by name."""
        create_model(sample_model_data, initialized_db)

        result = delete_model("fraud-detection-v1", initialized_db)

        assert result is True

    def test_delete_model_not_found(self, initialized_db):
        """Test deleting non-existent model raises error."""
        with pytest.raises(ModelNotFoundError):
            delete_model("nonexistent", initialized_db)


class TestReportingQueries:
    """Tests for reporting/query functions."""

    def test_get_models_needing_review(self, initialized_db, sample_model_data):
        """Test finding models with upcoming reviews."""
        # Create model with review date in past
        sample_model_data["next_review_date"] = date.today() - timedelta(days=10)
        create_model(sample_model_data, initialized_db)

        needing_review = get_models_needing_review(initialized_db, days_ahead=0)

        assert len(needing_review) == 1

    def test_get_risk_distribution(self, initialized_db, sample_model_data, sample_model_data_minimal):
        """Test risk distribution calculation."""
        create_model(sample_model_data, initialized_db)  # HIGH
        create_model(sample_model_data_minimal, initialized_db)  # LOW

        distribution = get_risk_distribution(initialized_db)

        assert distribution["high"] == 1
        assert distribution["low"] == 1
        assert distribution["medium"] == 0
        assert distribution["critical"] == 0
