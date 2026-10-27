"""Local inference boundary; no fake fallback or executable model output."""

import asyncio
from typing import Protocol

import httpx


class ProviderUnavailable(Exception):
    def __init__(self, message=None, *, code="INFERENCE_UNAVAILABLE"):
        super().__init__(message or code)
        self.code = code


class ModelProvider(Protocol):
    async def check(self) -> dict: ...
    async def complete(self, prompt: str) -> str: ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str = ""):
        self.base_url = base_url
        self.model = model
        self._gate = asyncio.Semaphore(1)

    async def check(self):
        if not self.model:
            return {
                "status": "unconfigured",
                "reason": "Set OLLAMA_MODEL after hardware/licence review",
            }
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                names = {item["name"] for item in response.json()["models"]}
            return {"status": "available" if self.model in names else "model_missing"}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {"status": "unavailable", "reason": "Cannot verify local model server"}

    async def complete(self, prompt: str):
        try:
            await asyncio.wait_for(self._gate.acquire(), timeout=0.1)
        except TimeoutError:
            raise ProviderUnavailable("Local inference is busy; retry later") from None
        try:
            async with asyncio.timeout(65):
                return await self._complete(prompt)
        except TimeoutError:
            raise ProviderUnavailable("Local inference exceeded its total deadline") from None
        finally:
            self._gate.release()

    def stream(self, prompt):
        return _ollama_stream(self, prompt)

    async def _complete(self, prompt: str):
        if not self.model:
            raise ProviderUnavailable("Local model is unconfigured")
        try:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {"num_predict": 256, "num_ctx": 4096},
                    },
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderUnavailable("Local inference failed; no answer was generated") from exc


async def embed_texts(base_url: str, model: str, texts: list[str]) -> list[list[float]]:
    """Optional local embeddings; a missing index is never reported as semantic success."""
    import math

    if not model:
        raise ProviderUnavailable("Embedding model is unconfigured")
    if not 1 <= len(texts) <= 16:
        raise ProviderUnavailable("Embedding batch must contain 1 to 16 inputs")
    try:
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            response = await client.post(
                f"{base_url}/api/embed", json={"model": model, "input": texts, "truncate": True}
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        if len(vectors) != len(texts) or any(
            not v
            or len(v) > 4096
            or any(not isinstance(n, (float, int)) or not math.isfinite(n) for n in v)
            for v in vectors
        ):
            raise ValueError("Invalid embedding response")
        return vectors
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ProviderUnavailable("Local embeddings unavailable") from exc


async def _ollama_stream(provider: OllamaProvider, prompt: str):
    """Yield actual model tokens with bounded admission and cancellation cleanup."""
    import json

    if not provider.model:
        raise ProviderUnavailable("Local model is unconfigured")
    try:
        await asyncio.wait_for(provider._gate.acquire(), timeout=0.1)
    except TimeoutError:
        raise ProviderUnavailable("Local model is busy") from None
    try:
        async with asyncio.timeout(65):
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    f"{provider.base_url}/api/chat",
                    json={
                        "model": provider.model,
                        "stream": True,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {"num_predict": 256, "num_ctx": 4096},
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            payload = json.loads(line)
                            if payload.get("error"):
                                raise ProviderUnavailable("Local model stream failed")
                            content = payload.get("message", {}).get("content", "")
                            if content:
                                yield content
    except (httpx.HTTPError, ValueError, KeyError, TimeoutError) as exc:
        raise ProviderUnavailable("Local model stream failed") from exc
    finally:
        provider._gate.release()


def stream_completion(provider, prompt):
    return provider.stream(prompt)
