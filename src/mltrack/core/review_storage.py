"""Storage layer for ModelReview CRUD operations."""

from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from mltrack.core.database import session_scope, init_db
from mltrack.core.exceptions import DatabaseError
from mltrack.models.ai_model import AIModel
from mltrack.models.model_review import ModelReview, ReviewOutcome, compute_model_hash


def create_review(
    model: AIModel,
    reviewed_at: date,
    outcome: ReviewOutcome = ReviewOutcome.PASSED,
    reviewer: Optional[str] = None,
    notes: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> ModelReview:
    """Record a structured review event for a model.

    Creates an immutable ModelReview record including a SHA-256 hash of
    the model's current state, providing tamper evidence for audit purposes.

    Args:
        model: The AIModel that was reviewed
        reviewed_at: Date the review took place
        outcome: Review result — passed, warning, or failed
        reviewer: Name/identifier of who performed the review (optional)
        notes: Review notes (optional)
        db_path: Optional database path

    Returns:
        Created ModelReview instance

    Raises:
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    state_hash = compute_model_hash(model)

    review = ModelReview(
        model_id=model.id,
        model_name=model.model_name,
        reviewed_at=reviewed_at.isoformat(),
        reviewer=reviewer,
        outcome=outcome,
        notes=notes,
        model_state_hash=state_hash,
    )

    try:
        with session_scope(db_path) as session:
            session.add(review)
            session.flush()
            session.refresh(review)
            session.expunge(review)
            return review
    except SQLAlchemyError as e:
        raise DatabaseError("create_review", str(e))


def get_reviews_for_model(
    identifier: str,
    db_path: Optional[Path] = None,
) -> list[ModelReview]:
    """Get all review records for a model, ordered by review date descending.

    Args:
        identifier: Model name or ID
        db_path: Optional database path

    Returns:
        List of ModelReview instances (most recent first)

    Raises:
        DatabaseError: If database operation fails
    """
    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            stmt = (
                select(ModelReview)
                .where(
                    (ModelReview.model_id == identifier)
                    | (ModelReview.model_name == identifier)
                )
                .order_by(ModelReview.reviewed_at.desc(), ModelReview.created_at.desc())
            )
            reviews = list(session.execute(stmt).scalars().all())
            for review in reviews:
                session.expunge(review)
            return reviews
    except SQLAlchemyError as e:
        raise DatabaseError("get_reviews", str(e))


def get_review_count_for_model(
    identifier: str,
    db_path: Optional[Path] = None,
) -> int:
    """Get the total number of review records for a model.

    Args:
        identifier: Model name or ID
        db_path: Optional database path

    Returns:
        Count of review records

    Raises:
        DatabaseError: If database operation fails
    """
    from sqlalchemy import func

    init_db(db_path)

    try:
        with session_scope(db_path) as session:
            stmt = select(func.count(ModelReview.id)).where(
                (ModelReview.model_id == identifier)
                | (ModelReview.model_name == identifier)
            )
            return session.execute(stmt).scalar() or 0
    except SQLAlchemyError as e:
        raise DatabaseError("count_reviews", str(e))
