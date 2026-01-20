"""Configuration management."""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration."""

    db_path: Path = Path.home() / ".mltrack" / "mltrack.db"

    # Review frequency defaults by risk tier (in days)
    review_frequency_high: int = 90
    review_frequency_medium: int = 180
    review_frequency_low: int = 365


# Global config instance
config = Config()
