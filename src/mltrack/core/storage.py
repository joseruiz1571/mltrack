"""Storage layer for AI model CRUD operations."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mltrack.core.database import session_scope, init_db
from mltrack.core.exceptions import (
    ModelNotFoundError,
    ModelAlreadyExistsError,
    ValidationError,
    DatabaseError,
)
from mltrack.models.ai_model import (
    AIModel,
    RiskTier,
    DeploymentEnvironment,
    DataClassification,
    ModelStatus,
)

# Review frequency in days based on risk tier (SR 11-7 aligned)
REVIEW_FREQUENCY = {
    RiskTier.CRITICAL: 30,
    RiskTier.HIGH: 90,
    RiskTier.MEDIUM: 180,
    RiskTier.LOW: 365,
}

# Required fields for model creation
REQUIRED_FIELDS = [
    "model_name",
    "vendor",
    "risk_tier",
    "use_case",
    "business_owner",
    "technical_owner",
    "deployment_date",
]


def _validate_model_data(data: dict[str, Any], is_update: bool = False) -> None:
    """Validate model data before create/update.

    Args:
        data: Dictionary of model fields
        is_update: If True, skip required field validation

    Raises:
        ValidationError: If validation fails
    """
    if not is_update:
        for field in REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                raise ValidationError(field, "This field is required")

    # Validate model_name format
    if "model_name" in data:
        name = data["model_name"]
        if not name or not name.strip():
            raise ValidationError("model_name", "Cannot be empty")
        if len(name) > 255:
            raise ValidationError("model_name", "Cannot exceed 255 characters")

    # Validate risk_tier enum
    if "risk_tier" in data:
        tier = data["risk_tier"]
        if isinstance(tier, str):
            try:
                data["risk_tier"] = RiskTier(tier.lower())
            except ValueError:
                valid = [t.value for t in RiskTier]
                raise ValidationError(
                    "risk_tier", f"Must be one of: {', '.join(valid)}"
                )

    # Validate deployment_environment enum
    if "deployment_environment" in data and data["deployment_environment"]:
        env = data["deployment_environment"]
        if isinstance(env, str):
            try:
                data["deployment_environment"] = DeploymentEnvironment(env.lower())
            except ValueError:
                valid = [e.value for e in DeploymentEnvironment]
                raise ValidationError(
                    "deployment_environment", f"Must be one of: {', '.join(valid)}"
                )

    # Validate data_classification enum
    if "data_classification" in data and data["data_classification"]:
        classification = data["data_classification"]
        if isinstance(classification, str):
            try:
                data["data_classification"] = DataClassification(classification.lower())
            except ValueError:
                valid = [c.value for c in DataClassification]
                raise ValidationError(
                    "data_classification", f"Must be one of: {', '.join(valid)}"
                )

    # Validate status enum
    if "status" in data and data["status"]:
        status = data["status"]
        if isinstance(status, str):
            try:
                data["status"] = ModelStatus(status.lower())
            except ValueError:
                valid = [s.value for s in ModelStatus]
                raise ValidationError(
                    "status", f"Must be one of: {', '.join(valid)}"
                )

    # Validate deployment_date
    if "deployment_date" in data:
        dep_date = data["deployment_date"]
        if isinstance(dep_date, str):
            try:
                data["deployment_date"] = date.fromisoformat(dep_date)
            except ValueError:
                raise ValidationError(
                    "deployment_date", "Must be a valid date (YYYY-MM-DD)"
                )


def _calculate_next_review_date(risk_tier: RiskTier, from_date: date | None = None) -> date:
    """Calculate next review date based on risk tier.

    Args:
        risk_tier: Model's risk classification
        from_date: Starting date (defaults to today)

    Returns:
        Next review date
    """
    if from_date is None:
        from_date = date.today()
    days = REVIEW_FREQUENCY[risk_tier]
    return from_date + timedelta(days=days)


def create_model(model_data: dict[str, Any], db_path: Path | None = None) -> AIModel:
    """Create a new AI model in the database.

    Args:
        model_data: Dictionary containing model fields
        db_path: Optional database path

    Returns:
        Created AIModel instance

    Raises:
        ValidationError: If required fields are missing or invalid
        ModelAlreadyExistsError: If model with same name exists
        DatabaseError: If database operation fails
    """
    # Ensure database is initialized
    init_db(db_path)

    # Validate input
    _validate_model_data(model_data, is_update=False)

    # Calculate next_review_date if not provided
    if "next_review_date" not in model_data or model_data["next_review_date"] is None:
        model_data["next_review_date"] = _calculate_next_review_date(
            model_data["risk_tier"],
            model_data["deployment_date"],
        )

    try:
        with session_scope(db_path) as session:
            model = AIModel(**model_data)
            session.add(model)
            session.flush()  # Get the ID
            session.refresh(model)
            # Detach from session for return
            session.expunge(model)
            return model
    except IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            raise ModelAlreadyExistsError(model_data["model_name"])
        raise DatabaseError("create", str(e))
    except SQLAlchemyError as e:
        raise DatabaseError("create", str(e))


def create_models_batch(
    models_data: list[dict[str, Any]],
    db_path: Path | None = None,
    batch_size: int = 100,
    skip_existing: bool = False,
) -> tuple[int, int, list[str]]:
    """Create multiple models in batches for better performance.

    Args:
        models_data: List of dictionaries containing model fields
        db_path: Optional database path
        batch_size: Number of models to insert per transaction
        skip_existing: If True, skip models with duplicate names instead of failing

    Returns:
        Tuple of (created_count, skipped_count, error_messages)

    Raises:
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    created_count = 0
    skipped_count = 0
    errors: list[str] = []

    # Process in batches
    for i in range(0, len(models_data), batch_size):
        batch = models_data[i:i + batch_size]

        try:
            with session_scope(db_path) as session:
                for model_data in batch:
                    try:
                        # Validate input
                        _validate_model_data(model_data.copy(), is_update=False)

                        # Calculate next_review_date if not provided
                        if "next_review_date" not in model_data or model_data["next_review_date"] is None:
                            model_data["next_review_date"] = _calculate_next_review_date(
                                model_data["risk_tier"] if isinstance(model_data["risk_tier"], RiskTier)
                                else RiskTier(model_data["risk_tier"].lower()),
                                model_data["deployment_date"],
                            )

                        model = AIModel(**model_data)
                        session.add(model)
                        session.flush()  # Flush to catch duplicates early
                        created_count += 1

                    except IntegrityError:
                        session.rollback()
                        if skip_existing:
                            skipped_count += 1
                        else:
                            errors.append(f"Duplicate: {model_data.get('model_name', 'unknown')}")
                    except ValidationError as e:
                        errors.append(f"{model_data.get('model_name', 'unknown')}: {e.message}")

        except SQLAlchemyError as e:
            errors.append(f"Batch {i // batch_size + 1} failed: {str(e)}")

    return created_count, skipped_count, errors


def get_model(identifier: str, db_path: Path | None = None) -> AIModel:
    """Get a model by ID or name.

    Args:
        identifier: Model ID (UUID) or model_name
        db_path: Optional database path

    Returns:
        AIModel instance

    Raises:
        ModelNotFoundError: If model not found
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            # Try to find by ID or name
            stmt = select(AIModel).where(
                or_(AIModel.id == identifier, AIModel.model_name == identifier)
            )
            model = session.execute(stmt).scalar_one_or_none()

            if model is None:
                raise ModelNotFoundError(identifier)

            session.expunge(model)
            return model
    except ModelNotFoundError:
        raise
    except SQLAlchemyError as e:
        raise DatabaseError("get", str(e))


def get_all_models(
    db_path: Path | None = None,
    status: ModelStatus | None = None,
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[AIModel]:
    """Get all models with optional filtering and pagination.

    Args:
        db_path: Optional database path
        status: Filter by status
        risk_tier: Filter by risk tier
        vendor: Filter by vendor
        limit: Maximum number of models to return
        offset: Number of models to skip

    Returns:
        List of AIModel instances

    Raises:
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            stmt = select(AIModel)

            if status is not None:
                stmt = stmt.where(AIModel.status == status)
            if risk_tier is not None:
                stmt = stmt.where(AIModel.risk_tier == risk_tier)
            if vendor is not None:
                stmt = stmt.where(AIModel.vendor == vendor)

            stmt = stmt.order_by(AIModel.model_name)

            # Apply pagination
            if offset is not None and offset > 0:
                stmt = stmt.offset(offset)
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)

            models = list(session.execute(stmt).scalars().all())

            for model in models:
                session.expunge(model)

            return models
    except SQLAlchemyError as e:
        raise DatabaseError("list", str(e))


def get_model_count(
    db_path: Path | None = None,
    status: ModelStatus | None = None,
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
) -> int:
    """Get count of models matching filters (for pagination).

    Args:
        db_path: Optional database path
        status: Filter by status
        risk_tier: Filter by risk tier
        vendor: Filter by vendor

    Returns:
        Count of matching models

    Raises:
        DatabaseError: If database operation fails
    """
    from sqlalchemy import func

    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            stmt = select(func.count(AIModel.id))

            if status is not None:
                stmt = stmt.where(AIModel.status == status)
            if risk_tier is not None:
                stmt = stmt.where(AIModel.risk_tier == risk_tier)
            if vendor is not None:
                stmt = stmt.where(AIModel.vendor == vendor)

            return session.execute(stmt).scalar() or 0
    except SQLAlchemyError as e:
        raise DatabaseError("count", str(e))


def update_model(
    identifier: str,
    updates: dict[str, Any],
    db_path: Path | None = None,
) -> AIModel:
    """Update an existing model.

    Args:
        identifier: Model ID or name
        updates: Dictionary of fields to update
        db_path: Optional database path

    Returns:
        Updated AIModel instance

    Raises:
        ModelNotFoundError: If model not found
        ValidationError: If update data is invalid
        ModelAlreadyExistsError: If renaming to existing name
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    # Validate update data
    _validate_model_data(updates, is_update=True)

    # We need the current model to determine the correct base date for review calculation
    # Defer next_review_date calculation until we have the model

    try:
        with session_scope(db_path) as session:
            stmt = select(AIModel).where(
                or_(AIModel.id == identifier, AIModel.model_name == identifier)
            )
            model = session.execute(stmt).scalar_one_or_none()

            if model is None:
                raise ModelNotFoundError(identifier)

            # Determine if we need to recalculate next_review_date
            recalc_review = False
            if "risk_tier" in updates or "last_review_date" in updates:
                if "next_review_date" not in updates:
                    recalc_review = True

            # Apply updates
            for key, value in updates.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            # Recalculate next_review_date if needed
            if recalc_review:
                # Priority: last_review_date > deployment_date > today
                base_date = model.last_review_date or model.deployment_date or date.today()
                model.next_review_date = _calculate_next_review_date(
                    model.risk_tier,
                    base_date,
                )

            session.flush()
            session.refresh(model)
            session.expunge(model)
            return model
    except ModelNotFoundError:
        raise
    except IntegrityError as e:
        if "UNIQUE constraint failed" in str(e):
            raise ModelAlreadyExistsError(updates.get("model_name", identifier))
        raise DatabaseError("update", str(e))
    except SQLAlchemyError as e:
        raise DatabaseError("update", str(e))


def delete_model(identifier: str, db_path: Path | None = None) -> bool:
    """Delete a model from the database.

    Args:
        identifier: Model ID or name
        db_path: Optional database path

    Returns:
        True if deleted successfully

    Raises:
        ModelNotFoundError: If model not found
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            stmt = select(AIModel).where(
                or_(AIModel.id == identifier, AIModel.model_name == identifier)
            )
            model = session.execute(stmt).scalar_one_or_none()

            if model is None:
                raise ModelNotFoundError(identifier)

            session.delete(model)
            return True
    except ModelNotFoundError:
        raise
    except SQLAlchemyError as e:
        raise DatabaseError("delete", str(e))


def get_models_needing_review(
    db_path: Path | None = None,
    days_ahead: int = 30,
) -> list[AIModel]:
    """Get models with upcoming or overdue reviews.

    Args:
        db_path: Optional database path
        days_ahead: Number of days to look ahead

    Returns:
        List of models needing review, sorted by next_review_date
    """
    init_db(db_path)

    cutoff_date = date.today() + timedelta(days=days_ahead)

    try:
        with session_scope(db_path) as session:
            stmt = (
                select(AIModel)
                .where(AIModel.status == ModelStatus.ACTIVE)
                .where(AIModel.next_review_date <= cutoff_date)
                .order_by(AIModel.next_review_date)
            )
            models = list(session.execute(stmt).scalars().all())

            for model in models:
                session.expunge(model)

            return models
    except SQLAlchemyError as e:
        raise DatabaseError("query", str(e))


def get_risk_distribution(db_path: Path | None = None) -> dict[str, int]:
    """Get count of active models by risk tier.

    Args:
        db_path: Optional database path

    Returns:
        Dictionary mapping risk tier to count
    """
    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            models = session.execute(
                select(AIModel).where(AIModel.status == ModelStatus.ACTIVE)
            ).scalars().all()

            distribution = {tier.value: 0 for tier in RiskTier}
            for model in models:
                distribution[model.risk_tier.value] += 1

            return distribution
    except SQLAlchemyError as e:
        raise DatabaseError("query", str(e))


def iter_all_models(
    db_path: Path | None = None,
    status: ModelStatus | None = None,
    risk_tier: RiskTier | None = None,
    vendor: str | None = None,
    chunk_size: int = 100,
):
    """Iterate over all models in chunks for memory-efficient processing.

    This is useful for large exports where loading all models at once
    would consume too much memory.

    Args:
        db_path: Optional database path
        status: Filter by status
        risk_tier: Filter by risk tier
        vendor: Filter by vendor
        chunk_size: Number of models to fetch per chunk

    Yields:
        AIModel instances

    Raises:
        DatabaseError: If database operation fails
    """
    from typing import Generator

    init_db(db_path)

    offset = 0
    while True:
        models = get_all_models(
            db_path=db_path,
            status=status,
            risk_tier=risk_tier,
            vendor=vendor,
            limit=chunk_size,
            offset=offset,
        )

        if not models:
            break

        for model in models:
            yield model

        if len(models) < chunk_size:
            break

        offset += chunk_size
