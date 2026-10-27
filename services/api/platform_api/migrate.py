"""Explicit initial schema migration. Future schema changes require numbered migrations."""

import os

from sqlalchemy import text

from .database import Base, connect


def migrate(url):
    engine, _ = connect(url)
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        )
        version = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
        if version is None:
            Base.metadata.create_all(conn)
            conn.execute(text("INSERT INTO schema_version VALUES (1)"))
        elif version not in (1, 2):
            raise RuntimeError("Unsupported schema version")
        if version != 2:
            Base.metadata.create_all(conn)
            conn.execute(text("INSERT INTO schema_version VALUES (2)"))
    engine.dispose()


if __name__ == "__main__":
    migrate(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
