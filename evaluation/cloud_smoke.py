"""Opt-in real cloud acceptance. Set AI_PROVIDER, AI_MODEL and AI_API_KEY locally; usage may be billed."""

import asyncio
import os

from platform_api.cloud import environment_provider


async def main():
    if os.getenv("AI_PROVIDER", "ollama") == "ollama" or not os.getenv("AI_API_KEY"):
        raise SystemExit(
            "Set a cloud AI_PROVIDER, AI_MODEL and AI_API_KEY; this test makes two billed-capable calls."
        )
    provider = environment_provider()
    assert (await provider.complete("Reply with one short greeting.")).strip()
    parts = [part async for part in provider.stream("Reply with one short greeting.")]
    assert "".join(parts).strip()
    print(f"{provider.name}: real completion and streaming passed. No answer-quality claim.")


if __name__ == "__main__":
    asyncio.run(main())
