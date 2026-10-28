import httpx
import pytest
from fastapi.testclient import TestClient
from platform_api.app import create_app
from platform_api.bootstrap import initialize_from_environment
from platform_api.database import Assistant, User, connect
from platform_api.migrate import migrate
from sqlalchemy import func, select


@pytest.mark.parametrize(
    "path,filename",
    [("/", "index.html"), ("/chat.html", "chat.html"), ("/demo-embed.html", "demo-embed.html")],
)
def test_bound_frontend_preserves_policy_without_forwarding_credentials(
    tmp_path, monkeypatch, path, filename
):
    monkeypatch.setenv("FRONTEND_INTERNAL_URL", "http://admin.internal")
    original_client = httpx.AsyncClient
    requests = []

    def frontend(request):
        requests.append(request)
        return httpx.Response(
            200,
            text="<!doctype html><title>Studio</title>",
            headers={"content-security-policy": "frame-ancestors *", "set-cookie": "bad=1"},
        )

    def bound_client(**kwargs):
        assert kwargs["trust_env"] is False
        return original_client(**kwargs, transport=httpx.MockTransport(frontend))

    monkeypatch.setattr(httpx, "AsyncClient", bound_client)
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as client:
        response = client.get(
            path + "?identity=secret",
            headers={"Authorization": "Bearer secret", "Cookie": "s=secret"},
        )
        assert response.status_code == 200
        assert response.headers["content-security-policy"].endswith("frame-ancestors 'self'")
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers
        assert client.get("/v1/projects").status_code == 401
        assert client.get("/health").status_code == 200
    assert len(requests) == 1
    assert str(requests[0].url) == f"http://admin.internal/admin/{filename}"
    assert "authorization" not in requests[0].headers
    assert "cookie" not in requests[0].headers
    app.state.engine.dispose()


@pytest.mark.parametrize("status", [302, 404, 500])
def test_frontend_failure_does_not_serve_redirects_or_error_bodies(tmp_path, monkeypatch, status):
    monkeypatch.setenv("FRONTEND_INTERNAL_URL", "http://admin.internal")
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            **kwargs,
            transport=httpx.MockTransport(lambda _: httpx.Response(status, text="private")),
        ),
    )
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FRONTEND_UNAVAILABLE"
    assert "private" not in response.text
    app.state.engine.dispose()


def test_vercel_requires_postgres_and_accepts_provider_connection_urls(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        connect("sqlite:///./assistant.db")
    for scheme in ("postgres", "postgresql", "postgresql+psycopg"):
        engine, _ = connect(f"{scheme}://test:test@localhost/assistant")
        assert engine.url.drivername == "postgresql+psycopg"
        engine.dispose()


def test_environment_bootstrap_creates_only_one_owner_and_preserves_password(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'bootstrap.db'}"
    migrate(url)
    engine, sessions = connect(url)
    monkeypatch.setenv("BOOTSTRAP_OWNER_EMAIL", "owner@example.test")
    monkeypatch.setenv("BOOTSTRAP_OWNER_PASSWORD", "first-private-password")
    monkeypatch.setenv("BOOTSTRAP_ORGANIZATION", "My business")
    assert initialize_from_environment(sessions)["created"] is True
    with sessions() as db:
        original_hash = db.scalar(select(User.password_hash))
    monkeypatch.setenv("BOOTSTRAP_OWNER_PASSWORD", "different-private-password")
    assert initialize_from_environment(sessions) == {"created": False}
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Assistant)) == 1
        assert db.scalar(select(User.password_hash)) == original_hash
    engine.dispose()


def test_environment_bootstrap_skips_absent_values_and_redacts_invalid_input(monkeypatch):
    monkeypatch.delenv("BOOTSTRAP_OWNER_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_OWNER_PASSWORD", raising=False)
    assert initialize_from_environment(None) == {"created": False}
    monkeypatch.setenv("BOOTSTRAP_OWNER_EMAIL", "owner@example.test")
    monkeypatch.setenv("BOOTSTRAP_OWNER_PASSWORD", "secret")
    with pytest.raises(RuntimeError) as error:
        initialize_from_environment(None)
    assert "secret" not in str(error.value)
    assert error.value.__suppress_context__ is True
