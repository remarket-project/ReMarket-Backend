from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Synchronous engine used by tests and some startup scripts
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    """Compatibility helper used by tests/startup: create all tables.

    The test suite calls `init_db(session)`; older code expected a
    synchronous helper under `app.core.db`. Provide a thin wrapper that
    creates all metadata if not present.
    """
    # Ensure models are imported so metadata is populated
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(bind=engine)
