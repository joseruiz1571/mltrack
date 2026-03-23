"""ModelReview entity — structured, immutable audit trail for model reviews."""

import enum
import hashlib
import json
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from mltrack.core.database import Base


class ReviewOutcome(enum.Enum):
    """Outcome of a model compliance review."""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ModelReview(Base):
    """A single structured review event for an AI model.

    Each call to ``mltrack reviewed`` creates one immutable record here.
    The ``model_state_hash`` is a SHA-256 digest of the model's key fields
    at the moment of review, providing tamper-evidence: if a model's
    definition is changed after-the-fact, the hash will no longer match.

    Schema aligned with SR 11-7 audit trail requirements.
    """

    __tablename__ = "model_reviews"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Foreign key to the reviewed model
    model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Denormalized for readability in audit reports (survives model rename)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # When the review took place (user-supplied, may differ from created_at)
    reviewed_at: Mapped[date] = mapped_column(
        String(10), nullable=False  # stored as ISO date string "YYYY-MM-DD"
    )

    # Who performed the review (optional — not all teams track this yet)
    reviewer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Outcome of the review
    outcome: Mapped[ReviewOutcome] = mapped_column(
        Enum(ReviewOutcome), nullable=False, default=ReviewOutcome.PASSED
    )

    # Notes captured at review time
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SHA-256 hash of the model's key fields at time of review.
    # Allows future auditors to verify the model definition hasn't changed
    # since the review was recorded.
    model_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # When this record was inserted (always UTC, never modified)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    # Indexes for audit queries
    __table_args__ = (
        Index("ix_model_reviews_model_id", "model_id"),
        Index("ix_model_reviews_model_name", "model_name"),
        Index("ix_model_reviews_reviewed_at", "reviewed_at"),
        Index("ix_model_reviews_outcome", "outcome"),
    )

    def __repr__(self) -> str:
        return (
            f"<ModelReview(model='{self.model_name}', "
            f"reviewed_at={self.reviewed_at}, outcome={self.outcome.value})>"
        )


# Fields included in the model state hash.
# Excludes timestamps (last_review_date, next_review_date, created_at, updated_at)
# which change as a normal part of the review lifecycle.
_HASH_FIELDS = [
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
    "data_classification",
    "status",
]


def compute_model_hash(model) -> str:
    """Compute a SHA-256 hash of a model's key fields.

    The hash is deterministic: same field values always produce the same hash.
    If any of the hashed fields change after the review is recorded, the hash
    will no longer match the model's current state — providing tamper evidence.

    Args:
        model: An AIModel instance

    Returns:
        64-character hex digest string
    """
    state = {}
    for field in _HASH_FIELDS:
        value = getattr(model, field, None)
        # Normalize enums and dates to strings for stable serialization
        if hasattr(value, "value"):
            state[field] = value.value
        elif isinstance(value, date):
            state[field] = value.isoformat()
        else:
            state[field] = value

    canonical = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
