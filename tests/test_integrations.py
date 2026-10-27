"""Public integration acceptance; network fetch/delivery doubles are explicit."""

import base64
import hashlib
import hmac
import io
import json
import secrets
import time
import zipfile

import pytest
from cryptography.fernet import Fernet
from platform_api.database import WebhookDelivery
from platform_api.remote import Page, RemoteError, public_address
from platform_api.webhooks import deliver_once
from sqlalchemy import select
from test_foundation import auth
from test_knowledge import bot_id, upload_ready


def publish(client, headers, assistant, **changes):
    root = f"/v1/assistants/{assistant}"
    config = client.get(root + "/configuration", headers=headers).json()
    config["configuration"].update(changes)
    saved = client.put(
        root + "/configuration",
        headers=headers,
        json={"revision": config["revision"], "configuration": config["configuration"]},
    )
    assert saved.status_code == 200, saved.text
    result = client.post(
        root + "/publish", headers=headers, json={"revision": saved.json()["revision"]}
    )
    assert result.status_code == 200, result.text
    return result.json()


def enable(client, headers, assistant, **changes):
    root = f"/v1/assistants/{assistant}/integration"
    current = client.get(root, headers=headers).json()
    body = {
        "revision": current["revision"],
        "enabled": True,
        "lead_capture": True,
        "support_enabled": True,
        "bookings_enabled": True,
        "daily_limit": 100,
    }
    body.update(changes)
    result = client.put(root, headers=headers, json=body)
    assert result.status_code == 200, result.text
    return result.json()


def guest(client, assistant, assertion=""):
    response = client.post(
        f"/v1/public/assistants/{assistant}/sessions", json={"identity_token": assertion}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def assertion(assistant, secret, subject="customer-123", **changes):
    claims = {
        "assistant_id": assistant,
        "sub": subject,
        "exp": int(time.time()) + 120,
        "nonce": secrets.token_urlsafe(24),
    }
    claims.update(changes)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    signature = (
        base64.urlsafe_b64encode(hmac.digest(secret.encode(), payload.encode(), "sha256"))
        .decode()
        .rstrip("=")
    )
    return payload + "." + signature


def test_public_guest_is_published_scoped_owned_and_usage_limited(setup):
    client, app = setup
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    assert client.post(f"/v1/public/assistants/{assistant}/sessions", json={}).status_code == 404
    publish(client, owner, assistant)
    enable(client, owner, assistant, daily_limit=2)
    visitor = guest(client, assistant)
    other = guest(client, assistant)
    first = client.post(root + "/chat", headers=visitor, json={"text": "hello"})
    assert first.status_code == 200
    conversation = first.json()["conversation_id"]
    assert client.get(root + "/conversations/" + conversation, headers=other).status_code == 404
    for path in (
        "/v1/projects",
        "/v1/me",
        root + "/documents",
        root + "/configuration",
        root + "/provider",
        "/v1/projects/cedar/bookings",
    ):
        assert client.get(path, headers=visitor).status_code == 403, path
    assert (
        client.post(root + "/chat", headers=visitor, json={"text": "hello again"}).status_code
        == 200
    )
    assert client.post(root + "/chat", headers=other, json={"text": "third"}).status_code == 429
    assert (
        client.post(
            root + "/chat", headers=owner, json={"text": "owner remains usable"}
        ).status_code
        == 200
    )
    enable(client, owner, assistant, enabled=False)
    assert client.get(root + "/widget-info", headers=visitor).status_code == 401


def test_signed_identity_is_one_use_expiring_scoped_and_stable(setup, monkeypatch):
    client, app = setup
    monkeypatch.setenv("PROVIDER_SECRET_KEY", Fernet.generate_key().decode())
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    publish(client, owner, assistant)
    enable(client, owner, assistant)
    secret = client.post(root + "/identity-secret", headers=owner).json()["secret"]
    signed = assertion(assistant, secret)
    visitor = guest(client, assistant, signed)
    assert client.get(root + "/widget-info", headers=visitor).json()["verified"]
    assert client.get("/v1/projects/cedar/bookings", headers=visitor).status_code == 200
    conversation = client.post(root + "/chat", headers=visitor, json={"text": "hello"}).json()[
        "conversation_id"
    ]
    second = guest(client, assistant, assertion(assistant, secret))
    assert client.get(root + "/conversations/" + conversation, headers=second).status_code == 200
    for token in (
        signed,
        assertion(assistant, secret, exp=int(time.time()) - 1),
        assertion("different-assistant", secret),
        assertion(assistant, "wrong-secret"),
    ):
        assert (
            client.post(
                f"/v1/public/assistants/{assistant}/sessions", json={"identity_token": token}
            ).status_code
            == 401
        )
    independent = guest(
        client, assistant, assertion(assistant, secret, subject="different-customer")
    )
    assert (
        client.get(root + "/conversations/" + conversation, headers=independent).status_code == 404
    )


def test_preview_uses_draft_knowledge_without_leaking_it_publicly(setup):
    client, app = setup
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    upload_ready(client, app, owner, assistant, "Public warranty lasts twelve months.")
    publish(client, owner, assistant)
    enable(client, owner, assistant)
    upload_ready(
        client, app, owner, assistant, "Unpublished confidential zephyr policy.", "draft.txt"
    )
    public = guest(client, assistant)
    answer = client.post(root + "/chat", headers=public, json={"text": "zephyr"}).json()
    assert not answer["citations"] and "confidential" not in answer["text"]
    preview = client.post(root + "/preview", headers=owner)
    assert preview.status_code == 200
    headers = {"Authorization": "Bearer " + preview.json()["access_token"]}
    result = client.post(root + "/chat", headers=headers, json={"text": "zephyr"})
    assert result.status_code == 200 and "confidential" in result.json()["text"]
    assert client.get(root + "/widget-info", headers=headers).json()["preview"]
    assert client.post(root + "/leads", headers=headers, json={}).status_code == 403
    assert client.put(root + "/integration", headers=headers, json={}).status_code == 403
    assert client.get(root + "/configuration", headers=headers).status_code == 403


def test_website_review_templates_branding_and_installation_checker(setup, monkeypatch):
    client, app = setup
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    page = {
        "url": "https://business.example/about",
        "title": "Business",
        "text": "Approved warranty terms.",
        "color": "#123456",
        "font_family": "georgia",
        "scripts": [
            {
                "src": "https://chat.example/widget-loader.js",
                "data-assistant": assistant,
                "data-public": "1",
            }
        ],
    }
    monkeypatch.setattr("platform_api.integrations.read_page", lambda url: page)
    review = client.post(root + "/website-review", headers=owner, json={"url": page["url"]})
    assert review.status_code == 201
    assert not client.get(root + "/documents", headers=owner).json()["items"]
    accepted = client.post(
        root + "/website-import",
        headers=owner,
        json={"review_id": review.json()["id"], "accepted": False},
    )
    assert accepted.status_code == 409
    assert (
        client.post(
            root + "/website-import",
            headers=auth(client, "harbor"),
            json={"review_id": review.json()["id"], "accepted": True},
        ).status_code
        == 404
    )
    assert (
        client.post(
            root + "/website-import",
            headers=owner,
            json={"review_id": review.json()["id"], "accepted": True},
        ).status_code
        == 202
    )
    template = client.post(
        root + "/template", headers=owner, json={"template": "faq", "revision": 0}
    )
    assert template.status_code == 200
    publish(
        client,
        owner,
        assistant,
        allowed_domains=["business.example"],
        color=page["color"],
        font_family=page["font_family"],
    )
    enable(client, owner, assistant)
    checker = client.post(
        root + "/installation-check",
        headers=owner,
        json={"url": page["url"], "app_origin": "https://chat.example"},
    )
    assert checker.status_code == 200 and checker.json()["ready"]
    assert "Static HTML" in checker.json()["note"]
    assert client.get(root + "/diagnostics", headers=owner).status_code == 200
    assert client.get(root + "/diagnostics", headers=auth(client, "harbor")).status_code == 404


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "224.0.0.1"]
)
def test_import_dns_rejects_nonpublic_targets(address, monkeypatch):
    monkeypatch.setattr(
        "platform_api.remote.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", (address, 443))],
    )
    with pytest.raises(RemoteError):
        public_address("untrusted.example")


def test_html_extraction_ignores_scripts_and_limits_style_suggestions():
    page = Page()
    page.feed(
        '<title>Our business</title><meta name="theme-color" content="#123abc"><body style="font-family:Georgia"><h1>Warranty</h1><script>STEAL_SECRET()</script><style>PRIVATE_STYLE</style><p>Twelve months.</p>'
    )
    assert "STEAL_SECRET" not in "".join(page.parts) and "PRIVATE_STYLE" not in "".join(page.parts)
    assert "Twelve months" in "".join(page.parts)
    assert page.color == "#123abc" and page.font == "georgia"


def test_lead_consent_and_signed_durable_webhook_delivery(setup, monkeypatch):
    client, app = setup
    monkeypatch.setenv("PROVIDER_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WEBHOOK_ALLOWED_URLS", "https://receiver.example/events")
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    publish(client, owner, assistant)
    enable(client, owner, assistant)
    created = client.post(
        "/v1/projects/cedar/webhooks",
        headers=owner,
        json={"url": "https://receiver.example/events"},
    )
    assert created.status_code == 201, created.text
    secret = created.json()["secret"]
    assert secret not in client.get("/v1/projects/cedar/webhooks", headers=owner).text
    public = guest(client, assistant)
    body = {
        "name": "Customer",
        "email": "visitor@example.test",
        "message": "Please contact me",
        "consent": False,
    }
    assert client.post(root + "/leads", headers=public, json=body).status_code == 422
    body["consent"] = True
    assert client.post(root + "/leads", headers=public, json=body).status_code == 201
    assert client.get(root + "/leads", headers=public).status_code == 403
    assert client.get(root + "/leads", headers=owner).json()["items"][0]["email"] == body["email"]
    requests = []

    def deliver(url, *, method, body, headers):
        requests.append(body)
        expected = (
            "sha256="
            + hmac.new(
                secret.encode(),
                headers["X-Assistant-Timestamp"].encode() + b"." + body,
                hashlib.sha256,
            ).hexdigest()
        )
        assert headers["X-Assistant-Signature"] == expected
        assert method == "POST" and url == "https://receiver.example/events"
        assert b"visitor@example.test" not in body and b"Please contact me" not in body
        return (503 if len(requests) == 1 else 204), "", b"", url

    monkeypatch.setattr("platform_api.webhooks.fetch", deliver)
    assert deliver_once(app.state.sessions)
    with app.state.sessions.begin() as db:
        delivery = db.scalar(select(WebhookDelivery))
        assert delivery.state == "pending" and delivery.attempts == 1
        delivery.due_at = 0
    assert deliver_once(app.state.sessions)
    assert requests[0] == requests[1]
    with app.state.sessions() as db:
        assert db.scalar(select(WebhookDelivery)).state == "sent"
    assert (
        client.delete(
            "/v1/projects/cedar/webhooks/" + created.json()["id"], headers=owner
        ).status_code
        == 204
    )


def test_webhook_restart_exhaustion_and_plugin_zip(setup):
    client, app = setup
    owner = auth(client)
    data = client.get("/v1/downloads/wordpress")
    assert data.status_code == 200
    with zipfile.ZipFile(io.BytesIO(data.content)) as archive:
        code = archive.read("universal-chatbot/universal-chatbot.php").decode()
        assert "wp_enqueue_script" in code and "current_user_can" in code
    # No endpoint is created when a tenant tries an unapproved URL.
    assert (
        client.post(
            "/v1/projects/cedar/webhooks", headers=owner, json={"url": "https://unapproved.example"}
        ).status_code
        == 422
    )


def test_faq_widget_can_disable_optional_business_writes(setup):
    client, app = setup
    owner = auth(client)
    assistant = bot_id(client, owner)
    root = f"/v1/assistants/{assistant}"
    publish(client, owner, assistant)
    enable(
        client, owner, assistant, support_enabled=False, bookings_enabled=False, lead_capture=False
    )
    visitor = guest(client, assistant)
    info = client.get(root + "/widget-info", headers=visitor).json()
    assert not info["support_enabled"] and not info["bookings_enabled"] and not info["lead_capture"]
    answer = client.post(
        root + "/chat", headers=visitor, json={"text": "Book an appointment"}
    ).json()
    assert answer["mode"] == "booking_unavailable" and "action" not in answer
    assert client.post("/v1/projects/cedar/tickets", headers=visitor, json={}).status_code == 403


def test_revision_eight_migrates_optional_features_disabled(tmp_path):
    from platform_api.database import connect
    from platform_api.migrate import migrate
    from sqlalchemy import text

    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    engine, _ = connect(url)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)"))
        db.execute(text("INSERT INTO schema_version VALUES (8)"))
        db.execute(
            text(
                "CREATE TABLE assistant_integrations (assistant_id TEXT PRIMARY KEY, enabled BOOLEAN NOT NULL, lead_capture BOOLEAN NOT NULL, daily_limit INTEGER NOT NULL, revision INTEGER NOT NULL, identity_secret TEXT NOT NULL)"
            )
        )
        db.execute(
            text("INSERT INTO assistant_integrations VALUES ('existing', TRUE, FALSE, 100, 1, '')")
        )
    migrate(url)
    migrate(url)
    with engine.connect() as db:
        row = db.execute(
            text("SELECT enabled, support_enabled, bookings_enabled FROM assistant_integrations")
        ).one()
        assert row[0] and not row[1] and not row[2]
        assert db.execute(text("SELECT MAX(version) FROM schema_version")).scalar() == 9
    engine.dispose()
