"""Report generation service.

This module re-exports storage functions for backwards compatibility.
For new code, prefer importing directly from mltrack.core.storage.
"""

from mltrack.core.storage import (
    get_models_needing_review,
    get_risk_distribution,
)

__all__ = [
    "get_models_needing_review",
    "get_risk_distribution",
]
