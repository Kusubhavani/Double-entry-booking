from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging
import os

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use DATABASE_URL from environment or settings
database_url = os.getenv('DATABASE_URL', settings.DATABASE_URL)

engine = create_engine(
    database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
    isolation_level="REPEATABLE_READ"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()

@contextmanager
def transaction():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Function to run migrations on startup
def run_migrations():
    """Run database migrations on application startup"""
    from alembic.config import Config
    from alembic import command
    
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise

# Function to check if migrations are needed
def check_migrations():
    """Check if database migrations are up-to-date"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    
    try:
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        
        # Get current head revision
        head_revision = script.get_current_head()
        
        logger.info(f"Current head revision: {head_revision}")
        return True
    except Exception as e:
        logger.error(f"Failed to check migrations: {e}")
        return False
