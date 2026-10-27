"""Bounded text-only provider adapters. No tools, automatic retries or credential redirects."""

import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx

from .inference import ProviderUnavailable

PRESETS = {
    "openai": ("OpenAI", "https://api.openai.com/v1"),
    "gemini": ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    "claude": ("Anthropic Claude", "https://api.anthropic.com/v1"),
    "kimi": ("Moonshot Kimi", "https://api.moonshot.ai/v1"),
    "nvidia": ("NVIDIA", "https://integrate.api.nvidia.com/v1"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com"),
}


def endpoint(provider, base_url=""):
    if provider in PRESETS:
        expected = PRESETS[provider][1]
        if base_url and base_url.rstrip("/") != expected:
            raise ValueError("Preset endpoints cannot be changed; use an approved custom endpoint")
        return expected
    if provider != "custom":
        raise ValueError("Unknown provider")
    base_url = base_url.rstrip("/")
    parts = urlsplit(base_url)
    approved = {
        url.strip().rstrip("/")
        for url in os.getenv("AI_CUSTOM_BASE_URLS", "").split(",")
        if url.strip()
    }
    if (
        base_url not in approved
        or parts.scheme not in {"https", "http"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Custom endpoint must be approved in the server's AI_CUSTOM_BASE_URLS")
    return base_url


def failure(status):
    if status in {401, 403}:
        return "PROVIDER_AUTHENTICATION_FAILED"
    if status == 429:
        return "PROVIDER_RATE_LIMITED"
    if 400 <= status < 500:
        return "PROVIDER_REQUEST_REJECTED"
    return "PROVIDER_UNAVAILABLE"


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        )
    return ""


async def sse_data(response):
    buffer, data = "", []
    total = 0
    async for chunk in response.aiter_text():
        total += len(chunk)
        buffer += chunk
        if total > 2_000_000 or len(buffer) > 65536:
            raise ValueError("Provider response budget exceeded")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if not line:
                if data:
                    yield "\n".join(data)
                    data = []
            elif line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
                if sum(map(len, data)) > 65536:
                    raise ValueError("Provider event budget exceeded")
    if buffer.strip() or data:
        raise ValueError("Provider stream ended inside an event")


class CloudProvider:
    def __init__(
        self,
        provider,
        model,
        api_key,
        base_url="",
        max_tokens=1024,
        token_parameter="max_tokens",
        gate=None,
        transport=None,
    ):
        self.name = provider
        self.model = model
        self.api_key = api_key
        self.base_url = endpoint(provider, base_url)
        self.max_tokens = max_tokens
        self.token_parameter = "max_completion_tokens" if provider == "openai" else token_parameter
        self._gate = gate if gate is not None else asyncio.Semaphore(1)
        self.transport = transport

    async def check(self):
        # Checking metadata must not make a billed request. The explicit test uses complete().
        return {
            "status": "configured" if self.model and self.api_key else "unconfigured",
            "provider": self.name,
            "model": self.model,
        }

    def request(self, prompt, stream):
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        headers = {"Authorization": "Bearer " + self.api_key}
        path = "/chat/completions"
        if self.name == "claude":
            headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
            path = "/messages"
            body["max_tokens"] = self.max_tokens
        else:
            body[self.token_parameter] = self.max_tokens
        return path, headers, body

    async def _generate(self, prompt, streaming):
        if not self.model or not self.api_key:
            raise ProviderUnavailable(code="PROVIDER_NOT_CONFIGURED")
        try:
            await asyncio.wait_for(self._gate.acquire(), timeout=0.1)
        except TimeoutError:
            raise ProviderUnavailable(code="PROVIDER_BUSY") from None
        try:
            async with asyncio.timeout(65):
                path, headers, body = self.request(prompt, streaming)
                async with httpx.AsyncClient(
                    timeout=60, trust_env=False, follow_redirects=False, transport=self.transport
                ) as client:
                    async with client.stream(
                        "POST", self.base_url + path, headers=headers, json=body
                    ) as response:
                        if response.status_code != 200:
                            raise ProviderUnavailable(code=failure(response.status_code))
                        if not streaming:
                            raw = bytearray()
                            async for block in response.aiter_bytes():
                                raw.extend(block)
                                if len(raw) > 1_000_000:
                                    raise ValueError("Provider response too large")
                            payload = json.loads(raw)
                            if self.name == "claude":
                                reason = payload.get("stop_reason")
                                answer = text_content(payload["content"])
                            else:
                                choice = payload["choices"][0]
                                reason = choice.get("finish_reason")
                                answer = text_content(choice["message"].get("content"))
                            self.validate_stop(reason)
                            if not answer.strip() or len(answer) > 16000:
                                raise ValueError("Empty or oversized provider answer")
                            yield answer
                            return
                        if "text/event-stream" not in response.headers.get("content-type", ""):
                            raise ValueError("Expected SSE")
                        finished, length = False, 0
                        async for data in sse_data(response):
                            if data == "[DONE]":
                                finished = True
                                break
                            payload = json.loads(data)
                            if "error" in payload or payload.get("type") == "error":
                                raise ProviderUnavailable(code="PROVIDER_STREAM_FAILED")
                            answer = ""
                            if self.name == "claude":
                                if payload.get("type") == "message_stop":
                                    finished = True
                                if payload.get("type") == "message_delta":
                                    self.validate_stop(payload.get("delta", {}).get("stop_reason"))
                                delta = payload.get("delta", {})
                                if (
                                    payload.get("type") == "content_block_delta"
                                    and delta.get("type") == "text_delta"
                                ):
                                    answer = text_content(delta.get("text"))
                            else:
                                choices = payload.get("choices", [])
                                if choices:
                                    choice = choices[0]
                                    reason = choice.get("finish_reason")
                                    self.validate_stop(reason)
                                    if reason:
                                        finished = True
                                    answer = text_content(choice.get("delta", {}).get("content"))
                            length += len(answer)
                            if length > 16000:
                                raise ValueError("Output budget exceeded")
                            if answer:
                                yield answer
                        if not finished or not length:
                            raise ValueError("Empty or interrupted provider stream")
        except httpx.TimeoutException:
            raise ProviderUnavailable(code="PROVIDER_TIMEOUT") from None
        except TimeoutError:
            raise ProviderUnavailable(code="PROVIDER_TIMEOUT") from None
        except httpx.HTTPError:
            raise ProviderUnavailable(code="PROVIDER_UNAVAILABLE") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderUnavailable(code="PROVIDER_RESPONSE_INVALID") from None
        finally:
            self._gate.release()

    @staticmethod
    def validate_stop(reason):
        if reason in {"length", "max_tokens", "tool_calls", "tool_use"}:
            raise ProviderUnavailable(code="PROVIDER_OUTPUT_LIMIT_OR_UNEXPECTED_TOOL")

    async def complete(self, prompt):
        return "".join([chunk async for chunk in self._generate(prompt, False)])

    def stream(self, prompt):
        return self._generate(prompt, True)


def environment_provider(gate=None):
    from .inference import OllamaProvider

    provider = os.getenv("AI_PROVIDER", "ollama")
    if provider == "ollama":
        result = OllamaProvider(
            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), os.getenv("OLLAMA_MODEL", "")
        )
        if gate is not None:
            result._gate = gate
        return result
    return CloudProvider(
        provider,
        os.getenv("AI_MODEL", ""),
        os.getenv("AI_API_KEY", ""),
        os.getenv("AI_BASE_URL", ""),
        max_tokens=int(os.getenv("AI_MAX_OUTPUT_TOKENS", "1024")),
        token_parameter=os.getenv("AI_TOKEN_PARAMETER", "max_tokens"),
        gate=gate,
    )
