"""Additive schema revisions. These revisions add tables; future alterations need explicit DDL."""

from sqlalchemy import text

from .database import Base, connect, environment_database_url, is_supabase_database

SCHEMA_VERSION = 9


def protect_supabase_tables(conn):
    """The application API owns authorization; browser Data API access is denied."""
    quote = conn.dialect.identifier_preparer.quote
    for name in [*Base.metadata.tables, "schema_version"]:
        table = "public." + quote(name)
        conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(text(f"REVOKE ALL ON TABLE {table} FROM PUBLIC, anon, authenticated"))


def migrate(url):
    engine, _ = connect(url)
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # Transaction-scoped: safe with pooled connections and overlapping deployments.
            conn.execute(text("SELECT pg_advisory_xact_lock(1430340432, 1)"))
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        )
        version = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
        if version is not None and version not in range(1, SCHEMA_VERSION + 1):
            raise RuntimeError("Unsupported schema version")
        if (version or 0) < SCHEMA_VERSION:
            Base.metadata.create_all(conn)
            if version == 8:
                conn.execute(
                    text(
                        "ALTER TABLE assistant_integrations ADD COLUMN support_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE assistant_integrations ADD COLUMN bookings_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            for revision in range((version or 0) + 1, SCHEMA_VERSION + 1):
                conn.execute(
                    text("INSERT INTO schema_version VALUES (:version)"), {"version": revision}
                )
        if is_supabase_database(url):
            protect_supabase_tables(conn)
    engine.dispose()


if __name__ == "__main__":
    migrate(environment_database_url())
