"""Additive schema revisions. These revisions add tables; future alterations need explicit DDL."""

import os

from sqlalchemy import text

from .database import Base, connect

SCHEMA_VERSION = 8


def migrate(url):
    engine, _ = connect(url)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        )
        version = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
        if version is not None and version not in range(1, SCHEMA_VERSION + 1):
            raise RuntimeError("Unsupported schema version")
        if (version or 0) < SCHEMA_VERSION:
            Base.metadata.create_all(conn)
            for revision in range((version or 0) + 1, SCHEMA_VERSION + 1):
                conn.execute(
                    text("INSERT INTO schema_version VALUES (:version)"), {"version": revision}
                )
    engine.dispose()


if __name__ == "__main__":
    migrate(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
