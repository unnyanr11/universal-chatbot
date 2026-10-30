from uuid import uuid4

import pytest
from platform_api import registration
from platform_api.database import PublicWorkspace, User
from sqlalchemy import func, select


def configure(monkeypatch):
    monkeypatch.setenv("PUBLIC_SIGNUP_ENABLED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "synthetic-public-key")


def test_registration_closed_by_default_and_validation_redacts_password(setup, monkeypatch):
    client, _ = setup
    monkeypatch.delenv("PUBLIC_SIGNUP_ENABLED", raising=False)
    assert client.get("/v1/registration").json()["enabled"] is False
    assert (
        client.post(
            "/v1/registrations",
            json={
                "email": "a@example.test",
                "password": "synthetic-long-password",
                "workspace_name": "A",
            },
        ).status_code
        == 403
    )
    response = client.post(
        "/v1/registrations",
        json={"email": "a@example.test", "password": "secret", "workspace_name": "A"},
    )
    assert response.status_code == 422
    assert "secret" not in response.text


def test_signup_is_rate_limited_and_does_not_create_unverified_workspaces(setup, monkeypatch):
    client, app = setup
    configure(monkeypatch)
    monkeypatch.setattr(registration.time, "time", lambda: 1000000)
    calls = []

    async def auth(path, payload):
        calls.append((path, payload))
        return {"id": str(uuid4())}

    monkeypatch.setattr(registration, "auth_request", auth)
    for _ in range(10):
        response = client.post(
            "/v1/registrations",
            json={
                "email": " NEW@EXAMPLE.TEST ",
                "password": "synthetic-long-password",
                "workspace_name": " New business ",
            },
        )
        assert response.status_code == 202
        assert response.json() == {"status": "check_email"}
    assert calls[0][1]["email"] == "new@example.test"
    assert calls[0][1]["data"] == {"workspace_name": "New business"}
    assert (
        client.post(
            "/v1/registrations",
            json={
                "email": "new@example.test",
                "password": "synthetic-long-password",
                "workspace_name": "New business",
            },
        ).status_code
        == 429
    )
    assert len(calls) == 10
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 2


def test_confirmed_public_user_has_isolated_workspace_and_cannot_spend_operator_key(
    setup, monkeypatch
):
    client, app = setup
    configure(monkeypatch)
    subject = str(uuid4())
    from platform_api.cloud import CloudProvider

    app.state.provider = CloudProvider("gemini", "operator-model", "operator-private-api-key")

    async def auth(path, payload):
        return {
            "user": {
                "id": subject,
                "email": payload["email"],
                "email_confirmed_at": "2026-10-30T00:00:00Z",
                "user_metadata": {
                    "workspace_name": "New business",
                    "role": "administrator",
                    "organization_id": "cedar",
                },
            }
        }

    monkeypatch.setattr(registration, "auth_request", auth)
    payload = {"email": "new@example.test", "password": "synthetic-long-password"}
    login = client.post("/v1/sessions", json=payload)
    assert login.status_code == 201
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    projects = client.get("/v1/projects", headers=headers).json()["items"]
    assert len(projects) == 1 and projects[0]["role"] == "owner"
    assert projects[0]["organization_id"] != "cedar"
    project = projects[0]["id"]
    assert client.get("/v1/projects/cedar/assistants", headers=headers).status_code == 404
    assistant = client.get(f"/v1/projects/{project}/assistants", headers=headers).json()["items"][
        0
    ]["id"]
    config = client.get(f"/v1/assistants/{assistant}/provider", headers=headers).json()
    assert config["requires_own_key"] is True
    assert config["has_key"] is False and config["model"] == ""
    assert (
        client.post(
            f"/v1/projects/{project}/inference-check",
            headers=headers,
            json={"text": "spend operator key"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/v1/assistants/{assistant}/provider",
            headers=headers,
            json={"revision": 0, "provider": "ollama", "model": "operator-model"},
        ).status_code
        == 403
    )
    assert (
        client.post(f"/v1/assistants/{assistant}/provider/test", headers=headers).status_code == 503
    )
    repeated = client.post("/v1/sessions", json=payload)
    assert repeated.status_code == 201
    for index in range(2):
        new = client.post("/v1/organizations", headers=headers, json={"name": f"Another {index}"})
        assert new.status_code == 201
        with app.state.sessions() as db:
            assert db.get(PublicWorkspace, new.json()["organization_id"])
    assert (
        client.post("/v1/organizations", headers=headers, json={"name": "Too many"}).status_code
        == 409
    )


@pytest.mark.parametrize("confirmed", [None, ""])
def test_unconfirmed_email_cannot_create_a_workspace(setup, monkeypatch, confirmed):
    client, _ = setup
    configure(monkeypatch)

    async def auth(path, payload):
        return {
            "user": {"id": str(uuid4()), "email": payload["email"], "email_confirmed_at": confirmed}
        }

    monkeypatch.setattr(registration, "auth_request", auth)
    response = client.post(
        "/v1/sessions", json={"email": "new@example.test", "password": "synthetic-long-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "EMAIL_CONFIRMATION_REQUIRED"


def test_existing_owner_keeps_local_login_and_external_auth_cannot_take_over(setup, monkeypatch):
    client, _ = setup
    configure(monkeypatch)

    async def unexpected(*args):
        raise AssertionError("Local owner must not use remote authentication")

    monkeypatch.setattr(registration, "auth_request", unexpected)
    assert (
        client.post(
            "/v1/sessions", json={"email": "cedar@example.test", "password": "a-long-test-password"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/v1/sessions", json={"email": "cedar@example.test", "password": "wrong"}
        ).status_code
        == 401
    )


def test_supabase_auth_boundary_sanitizes_upstream_errors(monkeypatch):
    import asyncio

    import httpx
    from fastapi import HTTPException

    configure(monkeypatch)
    original = httpx.AsyncClient
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(
            400,
            json={
                "error_code": "email_not_confirmed",
                "msg": "private-password must not be reflected",
            },
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(response)),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            registration.auth_request(
                "token?grant_type=password",
                {"email": "a@example.test", "password": "private-password"},
            )
        )
    assert error.value.detail == "EMAIL_CONFIRMATION_REQUIRED"
    assert "private-password" not in str(error.value)
    assert requests[0].url.host == "example.supabase.co"
    assert requests[0].url.params["grant_type"] == "password"
    assert requests[0].headers["apikey"] == "synthetic-public-key"


def test_public_source_and_assistant_limits(setup, monkeypatch):
    from platform_api.database import Assistant, Document

    client, app = setup
    with app.state.sessions.begin() as db:
        db.add(PublicWorkspace(organization_id="cedar"))
        assistant = db.scalar(select(Assistant).where(Assistant.project_id == "cedar"))
        assistant_id = assistant.id
        for index in range(50):
            db.add(
                Document(
                    assistant_id=assistant_id,
                    title=f"Source {index}",
                    content_hash=str(index),
                    content=b"test",
                    kind="txt",
                )
            )
        for index in range(9):
            db.add(Assistant(project_id="cedar", name=f"Assistant {index}", welcome_message="Hi"))
    login = client.post(
        "/v1/sessions", json={"email": "cedar@example.test", "password": "a-long-test-password"}
    )
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (
        client.post(
            "/v1/projects/cedar/assistants", headers=headers, json={"name": "Too many"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/v1/assistants/{assistant_id}/documents",
            headers=headers,
            files={"file": ("new.txt", b"New knowledge", "text/plain")},
        ).status_code
        == 409
    )


def test_public_password_change_uses_supabase_and_revokes_application_sessions(setup, monkeypatch):
    from platform_api.database import PublicAccount

    client, app = setup
    configure(monkeypatch)
    subject = str(uuid4())
    with app.state.sessions.begin() as db:
        db.add(PublicAccount(user_id="cedar", subject=subject))
    calls = []

    async def auth(path, payload, **kwargs):
        calls.append((path, payload, kwargs))
        return {
            "access_token": "synthetic-supabase-session",
            "user": {
                "id": subject,
                "email": "cedar@example.test",
                "email_confirmed_at": "2026-10-30T00:00:00Z",
            },
        }

    monkeypatch.setattr(registration, "auth_request", auth)
    login = client.post(
        "/v1/sessions",
        json={"email": "cedar@example.test", "password": "external-account-password"},
    )
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    response = client.post(
        "/v1/me/password",
        headers=headers,
        json={
            "current_password": "external-account-password",
            "new_password": "different-external-password",
        },
    )
    assert response.status_code == 204
    assert calls[-1] == (
        "user",
        {"password": "different-external-password"},
        {"method": "PUT", "access_token": "synthetic-supabase-session"},
    )
    assert client.get("/v1/projects", headers=headers).status_code == 401
