"""Custom exceptions for MLTrack."""


class MLTrackError(Exception):
    """Base exception for all MLTrack errors."""
    pass


class ModelNotFoundError(MLTrackError):
    """Raised when a model is not found in the database."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Model not found: {identifier}")


class ModelAlreadyExistsError(MLTrackError):
    """Raised when attempting to create a model that already exists."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model already exists: {model_name}")


class ValidationError(MLTrackError):
    """Raised when model data fails validation."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error for '{field}': {message}")


class DatabaseError(MLTrackError):
    """Raised when a database operation fails."""

    def __init__(self, operation: str, details: str):
        self.operation = operation
        self.details = details
        super().__init__(f"Database error during {operation}: {details}")
