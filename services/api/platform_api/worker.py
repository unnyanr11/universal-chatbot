"""Durable leased ingestion and idempotent in-app reminder delivery."""

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time

from sqlalchemy import and_, or_, select, update

from .database import Chunk, Document, Embedding, Job, Reminder, connect
from .inference import ProviderUnavailable, embed_texts


def run_once(sessions):
    now = int(time.time())
    token = secrets.token_hex(16)
    with sessions.begin() as db:
        exhausted = list(
            db.scalars(
                select(Job).where(Job.state == "running", Job.lease_until < now, Job.attempts >= 3)
            )
        )
        for failed in exhausted:
            failed.state = "failed"
            document = db.get(Document, failed.document_id)
            if document:
                document.status = "failed"
                document.error = "Worker retry budget exhausted. Delete and re-upload the source."
        candidate = db.scalar(
            select(Job.id)
            .where(
                Job.attempts < 3,
                or_(Job.state == "queued", and_(Job.state == "running", Job.lease_until < now)),
            )
            .order_by(Job.id)
            .limit(1)
        )
        claimed = None
        if candidate:
            claimed = db.execute(
                update(Job)
                .where(
                    Job.id == candidate,
                    Job.attempts < 3,
                    or_(Job.state == "queued", and_(Job.state == "running", Job.lease_until < now)),
                )
                .values(
                    state="running",
                    lease_until=now + 60,
                    lease_token=token,
                    attempts=Job.attempts + 1,
                )
                .returning(Job.document_id)
            ).scalar_one_or_none()
        db.execute(
            update(Reminder)
            .where(Reminder.status == "scheduled", Reminder.due_at <= now)
            .values(status="delivered")
        )
    if not claimed:
        return False
    with sessions() as db:
        document = db.get(Document, claimed)
        if not document:
            return True
        data, kind = document.content, document.kind
    try:
        result = subprocess.run(
            [sys.executable, "-m", "platform_api.extract", kind],
            input=data,
            capture_output=True,
            timeout=20,
            check=True,
        )
        chunks = json.loads(result.stdout)
        failure = ""
    except (subprocess.SubprocessError, ValueError):
        chunks, failure = [], "Extraction failed or exceeded limits; use UTF-8 text or a text PDF."
    embeddings, embedding_warning = [], ""
    model = os.getenv("OLLAMA_EMBED_MODEL", "")
    if model and chunks and not failure and len(chunks) <= 64:
        try:
            for offset in range(0, len(chunks), 16):
                with sessions.begin() as lease_db:
                    lease_db.execute(
                        update(Job)
                        .where(Job.document_id == claimed, Job.lease_token == token)
                        .values(lease_until=int(time.time()) + 90)
                    )
                embeddings.extend(
                    asyncio.run(
                        embed_texts(
                            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                            model,
                            [chunk["text"] for chunk in chunks[offset : offset + 16]],
                        )
                    )
                )
        except ProviderUnavailable:
            embeddings = []
            embedding_warning = "Lexical index ready; local semantic indexing failed."
    if model and len(chunks) > 64:
        embedding_warning = (
            "Lexical index ready; semantic indexing is limited to 64 chunks per document."
        )
    with sessions.begin() as db:
        # Deleted documents/jobs or superseded leases cannot be resurrected.
        owned = db.execute(
            update(Job)
            .where(Job.document_id == claimed, Job.lease_token == token)
            .values(state="failed" if failure else "succeeded")
            .returning(Job.id)
        ).scalar_one_or_none()
        document = db.get(Document, claimed)
        if owned and document:
            document.status = "failed" if failure else "ready"
            document.error = failure or embedding_warning
            for i, chunk in enumerate(chunks):
                record = Chunk(document_id=claimed, ordinal=i, **chunk)
                db.add(record)
                if embeddings:
                    db.flush()
                    db.add(
                        Embedding(chunk_id=record.id, model=model, vector=json.dumps(embeddings[i]))
                    )
    return True


def main():
    engine, sessions = connect(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
    try:
        while True:
            if not run_once(sessions):
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
