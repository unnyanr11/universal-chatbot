import json

from platform_api.database import Embedding, Message
from sqlalchemy import select
from test_foundation import auth
from test_knowledge import bot_id, upload_ready


def test_chunked_request_body_limit(setup):
    client, _ = setup
    response = client.post(
        "/v1/sessions",
        content=(b"x" * 100000 for _ in range(24)),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_BODY_LIMIT"


def test_streaming_tokens_remain_provisional_until_validated(setup, monkeypatch):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    upload_ready(client, app, h, assistant, "Warranty lasts twelve months.")

    async def stream(provider, prompt):
        yield "Warranty lasts "
        yield "twelve months [1]."

    monkeypatch.setattr("platform_api.streaming.stream_completion", stream)
    response = client.post(
        f"/v1/assistants/{assistant}/chat",
        headers={**h, "Accept": "text/event-stream"},
        json={"text": "warranty", "mode": "local"},
    )
    assert response.status_code == 200
    assert response.text.count("event: token") == 2
    assert "event: result" in response.text and '"generation_streaming": true' in response.text
    with app.state.sessions() as db:
        assert (
            db.scalars(select(Message).where(Message.role == "assistant")).one().text
            == "Warranty lasts twelve months [1]."
        )


def test_semantic_boundary_reports_unconfigured_and_is_tenant_filtered(setup, monkeypatch):
    client, app = setup
    h = auth(client)
    assistant = bot_id(client, h)
    upload_ready(client, app, h, assistant, "Warranty terms.")
    root = f"/v1/assistants/{assistant}"
    monkeypatch.delenv("OLLAMA_EMBED_MODEL", raising=False)
    assert client.get(root + "/search?q=warranty&method=semantic", headers=h).status_code == 503
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "deterministic-test-model")

    async def embed(*args):
        return [[1.0, 0.0]]

    monkeypatch.setattr("platform_api.semantic.embed_texts", embed)
    chunks = client.get(root + "/search?q=warranty", headers=h).json()["items"]
    with app.state.sessions.begin() as db:
        db.add(
            Embedding(
                chunk_id=chunks[0]["chunk_id"],
                model="deterministic-test-model",
                vector=json.dumps([1.0, 0.0]),
            )
        )
    response = client.get(root + "/search?q=guarantee&method=hybrid", headers=h)
    assert (
        response.status_code == 200
        and response.json()["items"][0]["document_id"] == chunks[0]["document_id"]
    )
    assert (
        client.get(
            root + "/search?q=warranty&method=semantic", headers=auth(client, "harbor")
        ).status_code
        == 404
    )
