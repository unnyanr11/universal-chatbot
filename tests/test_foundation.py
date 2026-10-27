import asyncio
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from platform_api.app import create_app, digest
from platform_api.database import Membership, Session
from platform_api.inference import OllamaProvider, ProviderUnavailable


def auth(client, name="cedar"):
    response = client.post(
        "/v1/sessions", json={"email": f"{name}@example.test", "password": "a-long-test-password"}
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authentication_and_validation_redaction(setup):
    client, _ = setup
    assert client.get("/v1/projects").status_code == 401
    response = client.post("/v1/sessions", json={"email": "x", "password": "PRIVATE_VALUE"})
    assert response.status_code == 422
    assert "PRIVATE_VALUE" not in response.text
    assert response.headers["X-Request-ID"]
    assert (
        client.post(
            "/v1/sessions", json={"email": "no@example.test", "password": "wrong"}
        ).status_code
        == 401
    )


def test_tenant_isolation_and_role_enforcement(setup):
    client, _ = setup
    owner = auth(client)
    analyst = auth(client, "harbor")
    assert [p["id"] for p in client.get("/v1/projects", headers=owner).json()["items"]] == ["cedar"]
    assert client.get("/v1/projects/harbor/assistants", headers=owner).status_code == 404
    assert (
        client.post(
            "/v1/projects/harbor/assistants", headers=owner, json={"name": "attack"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/v1/projects/harbor/assistants", headers=analyst, json={"name": "denied"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/projects/cedar/assistants", headers=owner, json={"name": "Helpful assistant"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/v1/projects/cedar/assistants",
            headers=owner,
            json={"name": "bad", "organization_id": "harbor"},
        ).status_code
        == 422
    )


def test_revocation_expiry_and_membership_removal(setup):
    client, app = setup
    headers = auth(client)
    with app.state.sessions.begin() as db:
        db.delete(db.get(Membership, ("cedar", "cedar")))
    assert client.get("/v1/projects/cedar/assistants", headers=headers).status_code == 404
    assert client.delete("/v1/sessions/current", headers=headers).status_code == 204
    assert client.get("/v1/projects", headers=headers).status_code == 401
    headers = auth(client)
    with app.state.sessions.begin() as db:
        db.get(Session, digest(headers["Authorization"].split()[1])).expires_at = (
            int(time.time()) - 1
        )
    assert client.get("/v1/projects", headers=headers).status_code == 401


def test_login_budget_is_durable(setup, monkeypatch):
    import importlib
    from types import SimpleNamespace

    module = importlib.import_module("platform_api.app")
    now = time.time()
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: now))
    client, app = setup
    for _ in range(20):
        assert (
            client.post("/v1/sessions", json={"email": "a@b", "password": "wrong"}).status_code
            == 401
        )
    second = TestClient(create_app(app.state.engine.url.render_as_string(hide_password=False)))
    assert (
        second.post("/v1/sessions", json={"email": "a@b", "password": "wrong"}).status_code == 429
    )
    second.app.state.engine.dispose()


def test_unconfigured_provider_never_fakes_success(setup):
    client, _ = setup
    headers = auth(client)
    assert client.get("/v1/provider", headers=headers).json()["status"] == "unconfigured"
    assert (
        client.post(
            "/v1/projects/cedar/inference-check", headers=headers, json={"text": "Hello"}
        ).status_code
        == 503
    )


def test_ollama_contract_and_transport_failure(monkeypatch):
    """Transport double verifies adapter wire format; this is not real inference acceptance."""
    original = httpx.AsyncClient

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test:small"}]})
        assert b'"num_predict":256' in request.content
        return httpx.Response(200, json={"message": {"content": "adapter test only"}})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    provider = OllamaProvider("http://localhost:11434", "test:small")
    assert asyncio.run(provider.check())["status"] == "available"
    assert asyncio.run(provider.complete("Hello")) == "adapter test only"

    def failure(request):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(failure), **kwargs),
    )
    assert asyncio.run(provider.check())["status"] == "unavailable"
    with pytest.raises(ProviderUnavailable):
        asyncio.run(provider.complete("Hello"))
