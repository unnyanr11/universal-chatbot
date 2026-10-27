"""Small tenant-filtered vector index in the relational DB; no new database dependency."""

import json
import math
import os

from fastapi import HTTPException
from sqlalchemy import select

from .database import AssistantSettings, AssistantVersion, Chunk, Document, Embedding
from .inference import ProviderUnavailable, embed_texts


async def semantic_retrieve(db, assistant_id, query, method, lexical):
    model = os.getenv("OLLAMA_EMBED_MODEL", "")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    try:
        vector = (await embed_texts(base_url, model, [query]))[0]
    except ProviderUnavailable:
        raise HTTPException(503, "LOCAL_EMBEDDINGS_UNAVAILABLE") from None
    rows = db.execute(
        select(Embedding, Chunk, Document)
        .join(Chunk, Embedding.chunk_id == Chunk.id)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Document.assistant_id == assistant_id,
            Document.status == "ready",
            Embedding.model == model,
        )
        .limit(5000)
    ).all()
    settings = db.get(AssistantSettings, assistant_id)
    if settings and settings.published_version:
        version = db.scalar(
            select(AssistantVersion).where(
                AssistantVersion.assistant_id == assistant_id,
                AssistantVersion.number == settings.published_version,
            )
        )
        manifest = (
            {d["id"]: d["hash"] for d in json.loads(version.configuration)["knowledge"]}
            if version
            else {}
        )
        rows = [(e, c, d) for e, c, d in rows if manifest.get(d.id) == d.content_hash]
    if not rows:
        raise HTTPException(409, "SEMANTIC_INDEX_NOT_READY")
    scored = []
    norm = math.sqrt(sum(x * x for x in vector))
    for embedding, chunk, doc in rows:
        other = json.loads(embedding.vector)
        if len(other) != len(vector):
            continue
        denominator = norm * math.sqrt(sum(x * x for x in other))
        cosine = (
            sum(a * b for a, b in zip(vector, other, strict=True)) / denominator
            if denominator
            else 0
        )
        if cosine > 0:
            scored.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": doc.id,
                    "title": doc.title,
                    "page": chunk.page,
                    "text": chunk.text,
                    "score": cosine,
                }
            )
    scored.sort(key=lambda p: p["score"], reverse=True)
    if method == "semantic":
        return scored[:4]
    # Reciprocal rank fusion uses ranks rather than mixing incompatible score scales.
    fused = {}
    for ranking in (scored[:20], lexical):
        for rank, passage in enumerate(ranking, 1):
            current = fused.setdefault(passage["chunk_id"], {**passage, "score": 0})
            current["score"] += 1 / (60 + rank)
    return sorted(fused.values(), key=lambda p: p["score"], reverse=True)[:4]
