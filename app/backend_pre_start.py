from sqlalchemy import Engine, text
from sqlmodel import Session
from tenacity import (
    after_log,
    before_log,
    retry,
    stop_after_attempt,
    wait_fixed,
)
from app.core.db import engine
from app.initial_data import init_db_data
import subprocess
import logging
from pathlib import Path
import sys

# Add app directory to path for Docker container BEFORE any app imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def init(db_engine: Engine) -> None:
    """Initialize database and wait for it to be ready."""
    try:
        with Session(db_engine) as session:
            # Try to create session to check if DB is awake
            session.exec(text("SELECT 1"))
            logger.info("Database is ready!")
    except Exception as e:
        logger.error(f"Database not ready: {e}")
        raise e


def main() -> None:
    """Run pre-start tasks."""
    logger.info("Running backend pre-start tasks...")

    # Step 1: Wait for database to be ready
    logger.info("Waiting for database to be ready...")
    init(engine)

    # Step 2: Run Alembic migrations
    logger.info("Running database migrations...")
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            cwd="/app",
        )
        logger.info("Migrations completed successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e}")
        raise e

    # Step 3: Seed initial data
    logger.info("Seeding initial data...")
    try:
        init_db_data()
        logger.info("Seed data completed!")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        raise e

    logger.info("Backend pre-start tasks completed successfully!")


if __name__ == "__main__":
    main()
