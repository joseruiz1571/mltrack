"""Database connection and session management."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from sqlalchemy.pool import StaticPool

# Default database location
DEFAULT_DB_PATH = Path.home() / ".mltrack" / "mltrack.db"

# Module-level engine cache for connection reuse
_engine_cache: dict[Path, Engine] = {}


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite foreign keys and WAL mode for better performance."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_engine(db_path: Path | None = None, in_memory: bool = False) -> Engine:
    """Create or retrieve cached database engine.

    Args:
        db_path: Path to SQLite database file. Defaults to ~/.mltrack/mltrack.db
        in_memory: If True, create an in-memory database (useful for testing)

    Returns:
        SQLAlchemy Engine instance
    """
    if in_memory:
        # In-memory database for testing - use StaticPool to share connection
        return create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    if db_path is None:
        db_path = DEFAULT_DB_PATH

    # Return cached engine if available
    if db_path in _engine_cache:
        return _engine_cache[db_path]

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create engine with connection pooling
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,  # Verify connections before use
        connect_args={"check_same_thread": False},
    )

    _engine_cache[db_path] = engine
    return engine


def get_session_factory(db_path: Path | None = None) -> sessionmaker[Session]:
    """Get a session factory for creating database sessions.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Session factory
    """
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(db_path: Path | None = None) -> Session:
    """Create a new database session.

    Args:
        db_path: Path to SQLite database file

    Returns:
        New SQLAlchemy Session
    """
    factory = get_session_factory(db_path)
    return factory()


@contextmanager
def session_scope(db_path: Path | None = None) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(model)
            # commits automatically on success, rolls back on exception

    Args:
        db_path: Path to SQLite database file

    Yields:
        SQLAlchemy Session
    """
    session = get_session(db_path)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(db_path: Path | None = None) -> None:
    """Initialize the database schema.

    Creates all tables defined in the models if they don't exist.
    Safe to call multiple times.

    Args:
        db_path: Path to SQLite database file
    """
    # Import models to ensure they're registered with Base
    from mltrack.models import AIModel  # noqa: F401

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def reset_db(db_path: Path | None = None) -> None:
    """Drop and recreate all tables. USE WITH CAUTION.

    Args:
        db_path: Path to SQLite database file
    """
    from mltrack.models import AIModel  # noqa: F401

    engine = get_engine(db_path)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_db_info(db_path: Path | None = None) -> dict:
    """Get database information for diagnostics.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Dictionary with database info
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    engine = get_engine(db_path)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT sqlite_version()"))
        sqlite_version = result.scalar()

        result = conn.execute(
            text("SELECT COUNT(*) FROM ai_models")
        )
        model_count = result.scalar()

    return {
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "sqlite_version": sqlite_version,
        "model_count": model_count,
    }
