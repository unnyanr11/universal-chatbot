"""Actual local runtime acceptance, separate from deterministic test doubles."""

import asyncio
import json
import os
import platform
import tempfile
import time

from platform_api.database import Assistant, Document, Job, Organization, Project, connect
from platform_api.inference import OllamaProvider, embed_texts, stream_completion
from platform_api.migrate import migrate
from platform_api.semantic import semantic_retrieve
from platform_api.worker import run_once
from sqlalchemy import select


async def main():
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    embedding_model = os.environ["OLLAMA_EMBED_MODEL"]
    report = {
        "cpu": platform.machine(),
        "ram_gib": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1),
        "gpu": "not used",
        "models": [],
        "warning": "Runtime smoke; not a general answer-quality benchmark",
    }
    for model in ("smollm2:135m", "smollm2:360m"):
        provider = OllamaProvider(base, model)
        assert (await provider.check())["status"] == "available"
        start = time.monotonic()
        completion = await provider.complete("Write a short greeting.")
        assert isinstance(completion, str) and completion.strip()
        elapsed = time.monotonic() - start
        tokens = [chunk async for chunk in stream_completion(provider, "Write a short greeting.")]
        assert tokens and "".join(tokens).strip()
        report["models"].append(
            {
                "model": model,
                "completion_seconds": round(elapsed, 3),
                "stream_events": len(tokens),
                "completion_chars": len(completion),
            }
        )
    vectors = await embed_texts(base, embedding_model, ["bicycle repair", "cycle maintenance"])
    assert len(vectors) == 2 and len(vectors[0]) == len(vectors[1]) > 0
    report["embedding_model"], report["dimensions"] = embedding_model, len(vectors[0])
    with tempfile.TemporaryDirectory() as directory:
        url = f"sqlite:///{directory}/model.db"
        migrate(url)
        engine, sessions = connect(url)
        with sessions.begin() as db:
            db.add(Organization(id="demo", name="Demo"))
            db.flush()
            db.add(Project(id="demo", organization_id="demo", name="Demo"))
            db.flush()
            db.add(Assistant(id="demo", project_id="demo", name="Demo", welcome_message="Hello"))
            db.flush()
            db.add(
                Document(
                    id="demo",
                    assistant_id="demo",
                    title="Service",
                    content_hash="demo",
                    content=b"We provide bicycle repairs and cycle maintenance weekdays.",
                    kind="txt",
                )
            )
            db.flush()
            db.add(Job(document_id="demo"))
        assert await asyncio.to_thread(run_once, sessions)
        with sessions() as db:
            assert db.scalar(select(Document.status)) == "ready"
            hits = await semantic_retrieve(db, "demo", "cycle maintenance", "semantic", [])
            assert hits and hits[0]["document_id"] == "demo"
        from fastapi.testclient import TestClient
        from platform_api.app import create_app, passwords
        from platform_api.database import Membership, User

        with sessions.begin() as db:
            user = User(
                email="runtime@example.test",
                password_hash=passwords.hash("synthetic-runtime-password"),
            )
            db.add(user)
            db.flush()
            db.add(Membership(user_id=user.id, organization_id="demo", role="owner"))
        api = create_app(url, provider=provider)
        with TestClient(api) as client:
            login = client.post(
                "/v1/sessions",
                json={"email": "runtime@example.test", "password": "synthetic-runtime-password"},
            )
            assert login.status_code == 201
            response = client.post(
                "/v1/assistants/demo/chat",
                headers={
                    "Authorization": "Bearer " + login.json()["access_token"],
                    "Accept": "text/event-stream",
                },
                json={"text": "cycle maintenance", "mode": "local"},
            )
            assert (
                response.status_code == 200
                and "event: token" in response.text
                and "event: result" in response.text
            )
            report["authenticated_api_stream"] = "passed (runtime path, not answer-quality grading)"
        api.state.engine.dispose()
        engine.dispose()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
