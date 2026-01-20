"""Tests for database layer - schema, constraints, and initialization."""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mltrack.core.database import (
    Base,
    get_engine,
    init_db,
    get_session,
    session_scope,
    reset_db,
)
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    DataClassification,
    ModelStatus,
)


class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_init_db_creates_tables(self, tmp_path):
        """Test that init_db creates the ai_models table."""
        db_path = tmp_path / "test.db"

        init_db(db_path)

        engine = get_engine(db_path)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "ai_models" in tables

    def test_init_db_creates_correct_columns(self, tmp_path):
        """Test that all expected columns are created."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        engine = get_engine(db_path)
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("ai_models")}

        expected_columns = {
            "id",
            "model_name",
            "vendor",
            "risk_tier",
            "use_case",
            "business_owner",
            "technical_owner",
            "deployment_date",
            "model_version",
            "deployment_environment",
            "api_endpoint",
            "last_review_date",
            "next_review_date",
            "data_classification",
            "status",
            "notes",
            "created_at",
            "updated_at",
        }

        assert columns == expected_columns

    def test_init_db_creates_indexes(self, tmp_path):
        """Test that indexes are created for performance."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        engine = get_engine(db_path)
        inspector = inspect(engine)
        indexes = inspector.get_indexes("ai_models")
        index_names = {idx["name"] for idx in indexes}

        # Check for our custom indexes
        assert "ix_ai_models_risk_tier" in index_names
        assert "ix_ai_models_status" in index_names
        assert "ix_ai_models_next_review" in index_names
        assert "ix_ai_models_vendor" in index_names

    def test_init_db_is_idempotent(self, tmp_path):
        """Test that init_db can be called multiple times safely."""
        db_path = tmp_path / "test.db"

        # Call multiple times - should not raise
        init_db(db_path)
        init_db(db_path)
        init_db(db_path)

        engine = get_engine(db_path)
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "ai_models" in tables

    def test_reset_db_drops_and_recreates(self, tmp_path):
        """Test that reset_db clears all data."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        # Add a model
        with session_scope(db_path) as session:
            model = AIModel(
                model_name="test-model",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)

        # Reset
        reset_db(db_path)

        # Verify empty
        with session_scope(db_path) as session:
            count = session.query(AIModel).count()
            assert count == 0


class TestModelCreation:
    """Tests for creating models at the database level."""

    def test_create_model_generates_uuid(self, tmp_path):
        """Test that model ID is auto-generated as UUID."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="uuid-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()

            assert model.id is not None
            assert len(model.id) == 36  # UUID format

    def test_create_model_sets_timestamps(self, tmp_path):
        """Test that created_at and updated_at are auto-set."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="timestamp-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()

            assert model.created_at is not None
            assert model.updated_at is not None
            assert isinstance(model.created_at, datetime)

    def test_create_model_default_status_is_active(self, tmp_path):
        """Test that default status is ACTIVE."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="status-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()

            assert model.status == ModelStatus.ACTIVE

    def test_create_model_with_all_fields(self, tmp_path):
        """Test creating a model with all fields populated."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="full-model",
                vendor="anthropic",
                risk_tier=RiskTier.CRITICAL,
                use_case="Customer support AI",
                business_owner="Support Team",
                technical_owner="ML Platform",
                deployment_date=date(2024, 1, 15),
                model_version="3.5",
                deployment_environment=DeploymentEnvironment.PROD,
                api_endpoint="https://api.example.com/v1",
                last_review_date=date(2024, 1, 1),
                next_review_date=date(2024, 4, 1),
                data_classification=DataClassification.CONFIDENTIAL,
                status=ModelStatus.ACTIVE,
                notes="Production model for customer support",
            )
            session.add(model)
            session.flush()

            # Verify all fields
            assert model.model_name == "full-model"
            assert model.vendor == "anthropic"
            assert model.risk_tier == RiskTier.CRITICAL
            assert model.deployment_environment == DeploymentEnvironment.PROD
            assert model.data_classification == DataClassification.CONFIDENTIAL


class TestModelRetrieval:
    """Tests for reading models from the database."""

    def test_retrieve_model_by_id(self, tmp_path):
        """Test retrieving a model by its ID."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        # Create
        with session_scope(db_path) as session:
            model = AIModel(
                model_name="retrieve-test",
                vendor="test",
                risk_tier=RiskTier.MEDIUM,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()
            model_id = model.id

        # Retrieve in new session
        with session_scope(db_path) as session:
            retrieved = session.get(AIModel, model_id)

            assert retrieved is not None
            assert retrieved.model_name == "retrieve-test"
            assert retrieved.risk_tier == RiskTier.MEDIUM

    def test_retrieve_model_by_name_query(self, tmp_path):
        """Test retrieving a model by name using query."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="query-test",
                vendor="test",
                risk_tier=RiskTier.HIGH,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)

        with session_scope(db_path) as session:
            retrieved = session.query(AIModel).filter(
                AIModel.model_name == "query-test"
            ).first()

            assert retrieved is not None
            assert retrieved.risk_tier == RiskTier.HIGH

    def test_retrieve_nonexistent_returns_none(self, tmp_path):
        """Test that retrieving non-existent model returns None."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            retrieved = session.get(AIModel, "nonexistent-uuid")

            assert retrieved is None


class TestModelUpdate:
    """Tests for updating models in the database."""

    def test_update_single_field(self, tmp_path):
        """Test updating a single field."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="update-test",
                vendor="original",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()
            model_id = model.id

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            model.vendor = "updated"

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            assert model.vendor == "updated"

    def test_update_enum_field(self, tmp_path):
        """Test updating an enum field."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="enum-update-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()
            model_id = model.id

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            model.risk_tier = RiskTier.CRITICAL
            model.status = ModelStatus.DEPRECATED

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            assert model.risk_tier == RiskTier.CRITICAL
            assert model.status == ModelStatus.DEPRECATED


class TestModelDeletion:
    """Tests for deleting models from the database."""

    def test_delete_model(self, tmp_path):
        """Test deleting a model."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="delete-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)
            session.flush()
            model_id = model.id

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            session.delete(model)

        with session_scope(db_path) as session:
            model = session.get(AIModel, model_id)
            assert model is None

    def test_delete_reduces_count(self, tmp_path):
        """Test that delete reduces the model count."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        # Create two models
        with session_scope(db_path) as session:
            for i in range(2):
                model = AIModel(
                    model_name=f"count-test-{i}",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

        with session_scope(db_path) as session:
            assert session.query(AIModel).count() == 2

        # Delete one
        with session_scope(db_path) as session:
            model = session.query(AIModel).first()
            session.delete(model)

        with session_scope(db_path) as session:
            assert session.query(AIModel).count() == 1


class TestUniquenessConstraint:
    """Tests for uniqueness constraint on model_name."""

    def test_duplicate_name_raises_integrity_error(self, tmp_path):
        """Test that duplicate model_name raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model1 = AIModel(
                model_name="duplicate-name",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model1)

        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(db_path) as session:
                model2 = AIModel(
                    model_name="duplicate-name",  # Same name
                    vendor="different",
                    risk_tier=RiskTier.HIGH,
                    use_case="different",
                    business_owner="different",
                    technical_owner="different",
                    deployment_date=date.today(),
                )
                session.add(model2)

        assert "UNIQUE constraint failed" in str(exc_info.value)

    def test_different_names_allowed(self, tmp_path):
        """Test that different model names are allowed."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            for i in range(3):
                model = AIModel(
                    model_name=f"unique-name-{i}",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

        with session_scope(db_path) as session:
            count = session.query(AIModel).count()
            assert count == 3


class TestRequiredFieldsConstraint:
    """Tests for NOT NULL constraints on required fields."""

    def test_missing_model_name_raises_error(self, tmp_path):
        """Test that missing model_name raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name=None,  # Required field
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

    def test_missing_vendor_raises_error(self, tmp_path):
        """Test that missing vendor raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="test",
                    vendor=None,  # Required field
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

    def test_missing_risk_tier_raises_error(self, tmp_path):
        """Test that missing risk_tier raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="test",
                    vendor="test",
                    risk_tier=None,  # Required field
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

    def test_missing_business_owner_raises_error(self, tmp_path):
        """Test that missing business_owner raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="test",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner=None,  # Required field
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)

    def test_missing_technical_owner_raises_error(self, tmp_path):
        """Test that missing technical_owner raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="test",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner=None,  # Required field
                    deployment_date=date.today(),
                )
                session.add(model)

    def test_missing_deployment_date_raises_error(self, tmp_path):
        """Test that missing deployment_date raises IntegrityError."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(IntegrityError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="test",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=None,  # Required field
                )
                session.add(model)

    def test_optional_fields_can_be_null(self, tmp_path):
        """Test that optional fields can be NULL."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="minimal-model",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
                # All optional fields left as None
                model_version=None,
                deployment_environment=None,
                api_endpoint=None,
                last_review_date=None,
                next_review_date=None,
                data_classification=None,
                notes=None,
            )
            session.add(model)
            session.flush()

            assert model.id is not None
            assert model.model_version is None
            assert model.notes is None


class TestSessionScope:
    """Tests for session_scope context manager."""

    def test_session_scope_commits_on_success(self, tmp_path):
        """Test that session_scope commits on successful exit."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with session_scope(db_path) as session:
            model = AIModel(
                model_name="commit-test",
                vendor="test",
                risk_tier=RiskTier.LOW,
                use_case="testing",
                business_owner="tester",
                technical_owner="tester",
                deployment_date=date.today(),
            )
            session.add(model)

        # Verify committed in new session
        with session_scope(db_path) as session:
            count = session.query(AIModel).count()
            assert count == 1

    def test_session_scope_rollbacks_on_exception(self, tmp_path):
        """Test that session_scope rolls back on exception."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(ValueError):
            with session_scope(db_path) as session:
                model = AIModel(
                    model_name="rollback-test",
                    vendor="test",
                    risk_tier=RiskTier.LOW,
                    use_case="testing",
                    business_owner="tester",
                    technical_owner="tester",
                    deployment_date=date.today(),
                )
                session.add(model)
                raise ValueError("Simulated error")

        # Verify rolled back
        with session_scope(db_path) as session:
            count = session.query(AIModel).count()
            assert count == 0
