"""Model CRUD operations.

This module re-exports storage functions for backwards compatibility.
For new code, prefer importing directly from mltrack.core.storage.
"""

from mltrack.core.storage import (
    create_model,
    get_model,
    get_all_models,
    update_model,
    delete_model,
)

__all__ = [
    "create_model",
    "get_model",
    "get_all_models",
    "update_model",
    "delete_model",
]
