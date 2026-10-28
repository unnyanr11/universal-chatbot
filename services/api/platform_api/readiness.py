"""Installer acceptance checks; exits nonzero instead of declaring partial setup ready."""

import argparse
import asyncio
import os
import time

import httpx
from sqlalchemy import select, text

from .cloud import environment_provider
from .database import Document, User, connect, environment_database_url
from .inference import embed_texts


async def check(document_id=None, base_url="http://api:8000"):
    engine, sessions = connect(environment_database_url())
    try:
        with sessions() as db:
            db.execute(text("SELECT 1"))
            if not db.scalar(select(User.id).limit(1)):
                raise RuntimeError("No owner account exists. Rerun setup.")
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            for path in ("/health", "/"):
                response = await client.get(base_url + path)
                response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", ""):
                raise RuntimeError("Compiled application UI is unavailable")
        embedding = os.getenv("OLLAMA_EMBED_MODEL", "")
        base = os.environ["OLLAMA_BASE_URL"]
        provider = environment_provider()
        status = (await provider.check())["status"]
        if status in {"available", "configured"}:
            if not (await provider.complete("Say ready in one short sentence.")).strip():
                raise RuntimeError("Configured AI returned an empty response")
            print("Configured AI completion passed.")
        elif status != "unconfigured" or os.getenv("AI_PROVIDER", "ollama") != "ollama":
            raise RuntimeError("Configured AI is unavailable")
        if embedding:
            await embed_texts(base, embedding, ["Getting started with Assistant Studio"])
            print("Local embeddings passed.")
        if document_id:
            deadline = time.monotonic() + 120
            while True:
                with sessions() as db:
                    document = db.get(Document, document_id)
                    if not document or document.status == "failed":
                        raise RuntimeError("Starter document indexing failed. Inspect worker logs.")
                    if document.status == "ready":
                        if document.error:
                            raise RuntimeError(
                                "Starter document has an indexing warning. Inspect worker logs."
                            )
                        break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Worker did not index the starter guide within 120 seconds")
                await asyncio.sleep(2)
            print("Worker and starter document indexing passed.")
        print("Database, owner account and application UI passed.")
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document")
    args = parser.parse_args()
    asyncio.run(check(args.document))


if __name__ == "__main__":
    main()
