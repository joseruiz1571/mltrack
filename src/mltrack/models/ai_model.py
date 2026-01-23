"""AI Model entity definition."""

import enum
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Date, DateTime, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column

from mltrack.core.database import Base


class RiskTier(enum.Enum):
    """Model risk classification aligned with SR 11-7.

    Review frequency defaults:
    - CRITICAL: 30 days
    - HIGH: 90 days
    - MEDIUM: 180 days
    - LOW: 365 days
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DeploymentEnvironment(enum.Enum):
    """Deployment environment for the model."""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class DataClassification(enum.Enum):
    """Data sensitivity classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ModelStatus(enum.Enum):
    """Model lifecycle status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DECOMMISSIONED = "decommissioned"


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class AIModel(Base):
    """Represents a deployed AI model in the inventory.

    Schema aligned with NIST AI RMF and SR 11-7 requirements.
    """

    __tablename__ = "ai_models"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Core required fields
    model_name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(Enum(RiskTier), nullable=False)
    use_case: Mapped[str] = mapped_column(Text, nullable=False)
    business_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    technical_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    deployment_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Deployment metadata
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    deployment_environment: Mapped[Optional[DeploymentEnvironment]] = mapped_column(
        Enum(DeploymentEnvironment), nullable=True
    )
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Compliance fields
    last_review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Data governance
    data_classification: Mapped[Optional[DataClassification]] = mapped_column(
        Enum(DataClassification), nullable=True
    )

    # Lifecycle
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus), default=ModelStatus.ACTIVE, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_ai_models_risk_tier", "risk_tier"),
        Index("ix_ai_models_status", "status"),
        Index("ix_ai_models_next_review", "next_review_date"),
        Index("ix_ai_models_vendor", "vendor"),
        Index("ix_ai_models_environment", "deployment_environment"),
        # Composite indexes for common filter combinations
        Index("ix_ai_models_status_risk", "status", "risk_tier"),
        Index("ix_ai_models_status_env", "status", "deployment_environment"),
        Index("ix_ai_models_status_vendor", "status", "vendor"),
        # Index for review queries (status + next_review_date)
        Index("ix_ai_models_active_reviews", "status", "next_review_date"),
    )

    def __repr__(self) -> str:
        return f"<AIModel(name='{self.model_name}', risk_tier={self.risk_tier.value}, status={self.status.value})>"
