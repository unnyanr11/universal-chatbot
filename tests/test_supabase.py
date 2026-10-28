import pytest
from platform_api.app import create_app
from platform_api.database import connect, is_supabase_database
from sqlalchemy import event
from sqlalchemy.pool import NullPool


@pytest.mark.parametrize(
    "url,expected",
    [
        ("postgresql://postgres:test@db.example.supabase.co/postgres", True),
        (
            "postgresql://postgres.example:test@aws-1-eu-west-1.pooler.supabase.com:6543/postgres",
            True,
        ),
        ("postgresql://postgres:test@localhost/postgres", False),
        ("postgresql://postgres:test@db.example.supabase.co.invalid/postgres", False),
        ("sqlite:///./test.db", False),
    ],
)
def test_supabase_host_detection(url, expected):
    assert is_supabase_database(url) is expected


@pytest.mark.parametrize(
    "ssl_query,sslmode", [("", "require"), ("?sslmode=verify-full", "verify-full")]
)
def test_supabase_connection_uses_pooler_compatible_driver_options(ssl_query, sslmode):
    engine, _ = connect(
        "postgresql://postgres.example:test@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
        + ssl_query
    )
    assert isinstance(engine.pool, NullPool)
    captured = {}

    class StopBeforeNetwork(Exception):
        pass

    @event.listens_for(engine, "do_connect")
    def capture_parameters(dialect, connection_record, args, parameters):
        captured.update(parameters)
        raise StopBeforeNetwork

    with pytest.raises(StopBeforeNetwork):
        engine.connect()
    assert captured["prepare_threshold"] is None
    assert captured["sslmode"] == sslmode
    engine.dispose()


def test_supabase_override_selects_application_database_without_changing_fallback(
    tmp_path, monkeypatch
):
    fallback = f"sqlite:///{tmp_path / 'fallback.db'}"
    selected = f"sqlite:///{tmp_path / 'selected.db'}"
    monkeypatch.setenv("DATABASE_URL", fallback)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", selected)
    app = create_app()
    assert str(app.state.engine.url) == selected
    app.state.engine.dispose()
    monkeypatch.delenv("SUPABASE_DATABASE_URL")
    app = create_app()
    assert str(app.state.engine.url) == fallback
    app.state.engine.dispose()
