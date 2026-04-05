"""Registry discovery layer — abstract interface for ML platform backends.

MLTrack is a governance overlay, not a duplicate registry. This module defines
the contract that platform-specific adapters (MLflow, SageMaker, Azure ML, Vertex)
implement to surface models that may not yet be tracked in MLTrack's inventory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DiscoveredModel:
    """A model found in an external registry but not necessarily tracked by MLTrack.

    Contains the minimum metadata needed to decide whether to import it
    into the governance inventory. Platform-specific fields go in `extra`.
    """

    name: str
    source: str  # e.g. "mlflow", "sagemaker", "azure-ml", "vertex"
    version: str | None = None
    created_at: datetime | None = None
    description: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Name with version for display."""
        if self.version:
            return f"{self.name} (v{self.version})"
        return self.name


class RegistryAdapter(ABC):
    """Abstract base class for ML platform registry adapters.

    Each adapter connects to one external registry and returns a list of
    DiscoveredModel objects. The adapter is responsible for authentication
    and connection management.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Short identifier for this registry (e.g. 'mlflow', 'sagemaker')."""
        ...

    @abstractmethod
    def discover(self) -> list[DiscoveredModel]:
        """Return all models visible in this registry.

        Raises:
            ConnectionError: If the registry is unreachable.
            PermissionError: If credentials are invalid or insufficient.
        """
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify that the registry is reachable and credentials work."""
        ...


def find_untracked(
    discovered: list[DiscoveredModel],
    tracked_names: set[str],
) -> list[DiscoveredModel]:
    """Compare discovered models against MLTrack's inventory.

    Args:
        discovered: Models found in external registry.
        tracked_names: Set of model names already in MLTrack.

    Returns:
        Models that exist in the registry but not in MLTrack's inventory.
    """
    return [m for m in discovered if m.name not in tracked_names]
