"""Local inference boundary; no fake fallback or executable model output."""

from typing import Protocol

import httpx


class ProviderUnavailable(Exception):
    pass


class ModelProvider(Protocol):
    async def check(self) -> dict: ...


class OllamaProvider:
    def __init__(self, base_url: str, model: str = ""):
        self.base_url = base_url
        self.model = model

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
                        "options": {"num_predict": 256, "num_ctx": 2048},
                    },
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderUnavailable("Local inference failed; no answer was generated") from exc
