"""Shared configuration and database connection utilities.

This module is the future canonical database layer for all microservices.
It reuses the connection implementation originally created in app/database.py,
with English identifiers.

It reads DATABASE_URL from the environment or from the .env file located
at the repository root. Never hardcode connection strings here.
"""

import logging
from pathlib import Path

import psycopg
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, where the local .env file is located.
BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    DATABASE_URL: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance. Importing this module validates that
# DATABASE_URL is configured; the value itself is never printed.
settings = Settings()


def get_connection(row_factory=None):
    """Open a new connection to the PostgreSQL database (NeonDB).

    Args:
        row_factory: Optional psycopg row factory (e.g. dict_row) so that
            services can receive rows as dictionaries.
    """
    if row_factory is None:
        return psycopg.connect(settings.DATABASE_URL)
    return psycopg.connect(settings.DATABASE_URL, row_factory=row_factory)


def check_connection() -> bool:
    """Return True if the database answers a read-only SELECT 1.

    Used by every microservice /health endpoint. This is a health probe:
    any failure means "not healthy", so database errors return False
    instead of raising, and unexpected errors are also contained (and
    logged) rather than propagated. Connection details are never exposed.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except psycopg.Error:
        logger.exception("Database health check failed")
        return False
    except Exception:
        logger.exception("Unexpected error during database health check")
        return False
