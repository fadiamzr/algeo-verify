"""
Algeo Verify — Database Engine & Session
SQLite for local development, PostgreSQL for production.
Reads DATABASE_URL from config (which loads .env).
"""

from sqlmodel import SQLModel, Session, create_engine

from app.config import get_settings

# ── Engine ────────────────────────────────────────────────────────────
_settings = get_settings()

# SQLite requires connect_args for thread-safety; PostgreSQL does not.
_is_sqlite = _settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    _settings.DATABASE_URL,
    echo=_settings.DEBUG,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)


# ── Table creation ────────────────────────────────────────────────────
def create_db_and_tables() -> None:
    """Create all SQLModel tables.  Safe to call multiple times."""
    from app.models import (  # noqa: F401
        Wilaya, Commune, AddressVerification,
        VerificationRecord, APILog,
        User, Admin, DeliveryAgent, Delivery, Feedback,
    )
    SQLModel.metadata.create_all(engine)


# ── Session dependency (for FastAPI) ──────────────────────────────────
def get_session():
    """Yield a database session — use as a FastAPI `Depends()`."""
    with Session(engine) as session:
        yield session
