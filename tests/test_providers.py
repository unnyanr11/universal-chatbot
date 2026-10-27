"""Offline wire contracts and tenant/secret boundaries. No paid API requests in tests."""

import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from platform_api.cloud import PRESETS, CloudProvider, endpoint
from platform_api.database import AssistantProvider, Membership
from platform_api.inference import ProviderUnavailable
from platform_api.providers import unseal
from test_foundation import auth
from test_knowledge import bot_id, upload_ready


def wire(provider, stream):
    if not stream:
        return (
            {
                "content": [{"type": "text", "text": "Warranty is twelve months [1]."}],
                "stop_reason": "end_turn",
            }
            if provider == "claude"
            else {
                "choices": [
                    {
                        "message": {
                            "content": "Warranty is twelve months [1].",
                            "reasoning_content": "PRIVATE_THINKING",
                        },
                        "finish_reason": "stop",
                    }
                ]
            }
        )
    events = (
        [
            {"type": "ping"},
            {
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": "PRIVATE_THINKING"},
            },
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Warranty is twelve months [1]."},
            },
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
            {"type": "message_stop"},
        ]
        if provider == "claude"
        else [
            {"choices": [{"delta": {"reasoning_content": "PRIVATE_THINKING"}}]},
            {"choices": [{"delta": {"content": "Warranty is twelve months [1]."}}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
    )
    return "".join("data: " + json.dumps(event) + "\r\n\r\n" for event in events) + (
        "" if provider == "claude" else "data: [DONE]\n\n"
    )


@pytest.mark.parametrize("name", [*PRESETS, "custom"])
def test_provider_completion_and_stream_wire_contracts(name, monkeypatch):
    monkeypatch.setenv("AI_CUSTOM_BASE_URLS", "https://approved.example.test/v1")
    base = "https://approved.example.test/v1" if name == "custom" else ""
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append((request, body))
        assert body["model"] == "account-model"
        assert body["messages"] == [{"role": "user", "content": "approved prompt"}]
        assert body["max_completion_tokens" if name == "openai" else "max_tokens"] == 1024
        if name == "claude":
            assert request.headers["x-api-key"] == "synthetic-secret-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert "authorization" not in request.headers
            assert str(request.url).endswith("/messages")
        else:
            assert request.headers["authorization"] == "Bearer synthetic-secret-key"
            assert str(request.url).endswith("/chat/completions")
        if body["stream"]:
            return httpx.Response(
                200, text=wire(name, True), headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json=wire(name, False))

    provider = CloudProvider(
        name, "account-model", "synthetic-secret-key", base, transport=httpx.MockTransport(handler)
    )

    async def run():
        assert (await provider.check())["status"] == "configured"
        assert not requests  # Metadata checks must not incur provider charges.
        assert await provider.complete("approved prompt") == "Warranty is twelve months [1]."
        chunks = [chunk async for chunk in provider.stream("approved prompt")]
        assert "".join(chunks) == "Warranty is twelve months [1]."
        assert provider._gate._value == 1

    asyncio.run(run())
    assert len(requests) == 2


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "PROVIDER_AUTHENTICATION_FAILED"),
        (403, "PROVIDER_AUTHENTICATION_FAILED"),
        (429, "PROVIDER_RATE_LIMITED"),
        (400, "PROVIDER_REQUEST_REJECTED"),
        (503, "PROVIDER_UNAVAILABLE"),
        (302, "PROVIDER_UNAVAILABLE"),
    ],
)
def test_provider_errors_are_sanitized_without_retries_or_redirects(status, code):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            status,
            text="synthetic-secret-key PRIVATE_RESPONSE",
            headers={"location": "https://unapproved.example.test"},
        )

    provider = CloudProvider(
        "openai", "account-model", "synthetic-secret-key", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderUnavailable) as failure:
        asyncio.run(provider.complete("hello"))
    assert failure.value.code == code
    assert "synthetic-secret-key" not in str(failure.value)
    assert len(seen) == 1


@pytest.mark.parametrize(
    "data",
    [
        'data: {"choices":[{"delta":{"content":"unfinished"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n\n',
        'data: {"error":{"message":"PRIVATE_RESPONSE"}}\n\n',
        "data: [DONE]\n\n",
        "data: not-json\n\n",
    ],
)
def test_incomplete_or_invalid_streams_fail_and_release_capacity(data):
    provider = CloudProvider(
        "openai",
        "account-model",
        "synthetic-secret-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=data, headers={"content-type": "text/event-stream"}
            )
        ),
    )

    async def run():
        with pytest.raises(ProviderUnavailable):
            _ = [chunk async for chunk in provider.stream("hello")]
        assert provider._gate._value == 1

    asyncio.run(run())


def test_custom_endpoint_is_operator_approved_and_presets_cannot_be_redirected(monkeypatch):
    monkeypatch.setenv(
        "AI_CUSTOM_BASE_URLS", "https://allowed.example.test/v1,http://private-inference:8000/v1"
    )
    assert (
        endpoint("custom", "https://allowed.example.test/v1/") == "https://allowed.example.test/v1"
    )
    assert (
        endpoint("custom", "http://private-inference:8000/v1") == "http://private-inference:8000/v1"
    )
    for url in (
        "http://169.254.169.254",
        "http://localhost:8000",
        "https://allowed.example.test.evil/v1",
        "https://user:secret@allowed.example.test/v1",
        "https://allowed.example.test/v1?q=secret",
    ):
        with pytest.raises(ValueError):
            endpoint("custom", url)
    with pytest.raises(ValueError):
        endpoint("openai", "https://allowed.example.test/v1")


def settings(client, headers, assistant, **changes):
    payload = {
        "revision": 0,
        "provider": "nvidia",
        "model": "account-model",
        "api_key": "synthetic-secret-key",
        "allow_external": True,
    }
    payload.update(changes)
    return client.put(f"/v1/assistants/{assistant}/provider", headers=headers, json=payload)


def test_provider_keys_are_scoped_encrypted_write_only_and_revision_guarded(setup, monkeypatch):
    client, app = setup
    monkeypatch.setenv("PROVIDER_SECRET_KEY", Fernet.generate_key().decode())
    headers = auth(client)
    assistant = bot_id(client, headers)
    root = f"/v1/assistants/{assistant}/provider"
    assert settings(client, headers, assistant, allow_external=False).status_code == 422
    saved = settings(client, headers, assistant)
    assert saved.status_code == 200 and saved.json()["has_key"]
    assert "synthetic-secret-key" not in saved.text
    assert "encrypted_key" not in client.get(root, headers=headers).text
    with app.state.sessions() as db:
        row = db.get(AssistantProvider, assistant)
        assert "synthetic-secret-key" not in row.encrypted_key
        assert unseal(row) == "synthetic-secret-key"
        row.assistant_id = "different-assistant"
        with pytest.raises(ProviderUnavailable):
            unseal(row)
    assert settings(client, headers, assistant).status_code == 409
    assert (
        settings(
            client, headers, assistant, revision=1, api_key=None, model="another-model"
        ).status_code
        == 200
    )
    assert (
        settings(
            client, headers, assistant, revision=2, provider="deepseek", api_key=None
        ).status_code
        == 422
    )
    assert client.get(root, headers=auth(client, "harbor")).status_code == 404
    with app.state.sessions.begin() as db:
        db.get(Membership, ("cedar", "cedar")).role = "developer"
    assert settings(client, headers, assistant, revision=2).status_code == 403
    assert client.post(root + "/test", headers=headers).status_code == 403
    with app.state.sessions.begin() as db:
        db.get(Membership, ("cedar", "cedar")).role = "owner"
    assert client.delete(root + "?revision=1", headers=headers).status_code == 409
    assert client.delete(root + "?revision=2", headers=headers).status_code == 204
    assert not client.get(root, headers=headers).json()["has_key"]


def test_cloud_chat_uses_saved_provider_and_retains_grounding_and_secret_boundaries(
    setup, monkeypatch
):
    client, app = setup
    monkeypatch.setenv("PROVIDER_SECRET_KEY", Fernet.generate_key().decode())
    headers = auth(client)
    assistant = bot_id(client, headers)
    upload_ready(client, app, headers, assistant, "Warranty lasts twelve months.")
    sent = []

    def handler(request):
        assert request.url.host == "integrate.api.nvidia.com"
        body = json.loads(request.content)
        sent.append(body)
        if body["stream"]:
            return httpx.Response(
                200, text=wire("nvidia", True), headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json=wire("nvidia", False))

    def factory(*args, **kwargs):
        return CloudProvider(*args, **kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("platform_api.providers.CloudProvider", factory)
    assert settings(client, headers, assistant).status_code == 200
    root = f"/v1/assistants/{assistant}"
    assert client.post(root + "/provider/test", headers=headers).status_code == 200
    response = client.post(
        root + "/chat", headers=headers, json={"text": "warranty", "mode": "model"}
    )
    assert response.status_code == 200 and response.json()["citations"]
    streamed = client.post(
        root + "/chat",
        headers={**headers, "Accept": "text/event-stream"},
        json={"text": "warranty", "mode": "model"},
    )
    assert "event: token" in streamed.text and "event: result" in streamed.text
    assert '"mode": "model"' in streamed.text
    assert "PRIVATE_THINKING" not in streamed.text
    assert "synthetic-secret-key" not in str(sent) + response.text + streamed.text
    assert "Warranty lasts twelve months" in sent[-1]["messages"][0]["content"]
    monkeypatch.setenv("PROVIDER_SECRET_KEY", Fernet.generate_key().decode())
    assert (
        client.post(root + "/provider/test", headers=headers).json()["error"]["code"]
        == "PROVIDER_SECRET_KEY_UNAVAILABLE"
    )


def test_cancelled_provider_stream_releases_admission_immediately():
    provider = CloudProvider(
        "openai",
        "account-model",
        "synthetic-secret-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text=wire("openai", True), headers={"content-type": "text/event-stream"}
            )
        ),
    )

    async def run():
        stream = provider.stream("hello")
        assert await anext(stream)
        assert provider._gate._value == 0
        await stream.aclose()
        assert provider._gate._value == 1

    asyncio.run(run())
