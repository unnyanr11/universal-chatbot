"""Provisional text events followed by an authoritative, access-checked final result."""

import json
import re
import time
from contextlib import aclosing

from fastapi.responses import StreamingResponse
from sqlalchemy import select

from .database import Conversation, Membership, Message, Session, SupportTicket
from .inference import ProviderUnavailable, stream_completion


def event(kind, payload):
    return f"event: {kind}\ndata: {json.dumps(payload)}\n\n"


def chat_stream(
    request,
    assistant,
    session,
    conversation_id,
    question,
    evidence,
    prompt,
    *,
    provider=None,
    mode="local",
):
    from .knowledge import citations

    assistant_id, project_id = assistant.id, assistant.project_id
    session_digest, user_id = session.digest, session.user_id

    async def events():
        from .database import Project

        yield event("meta", {"conversation_id": conversation_id, "provisional": True})
        answer = ""
        try:
            async with aclosing(
                stream_completion(
                    provider if provider is not None else request.app.state.provider, prompt
                )
            ) as tokens:
                async for token in tokens:
                    if await request.is_disconnected():
                        return
                    answer += token
                    if len(answer) > 16000:
                        raise ProviderUnavailable("Output budget exceeded")
                    yield event("token", {"text": token})
            with request.app.state.sessions() as db:
                current = db.get(Session, session_digest)
                project = db.get(Project, project_id)
                if (
                    not current
                    or current.expires_at <= time.time()
                    or not project
                    or not db.get(Membership, (user_id, project.organization_id))
                ):
                    yield event("error", {"code": "SESSION_OR_ACCESS_REVOKED"})
                    return
                conversation = db.get(Conversation, conversation_id)
                if (
                    not conversation
                    or conversation.user_id != user_id
                    or conversation.assistant_id != assistant_id
                ):
                    yield event("error", {"code": "CONVERSATION_REMOVED"})
                    return
                active = citations(db, [e["chunk_id"] for e in evidence], assistant_id)
                handoff = db.scalar(
                    select(SupportTicket).where(
                        SupportTicket.conversation_id == conversation_id,
                        SupportTicket.state.in_(["open", "assigned"]),
                    )
                )
                numbers = [int(n) for n in re.findall(r"\[(\d+)\]", answer)]
                if handoff:
                    answer, active = "Automated replies paused for human support.", []
                elif len(active) != len(evidence):
                    answer, active = "The sources changed. Please ask again.", []
                elif not numbers or any(n < 1 or n > len(evidence) for n in numbers):
                    answer, active = (
                        "The model did not return valid citations. Please use source passage mode.",
                        [],
                    )
                db.add(Message(conversation_id=conversation_id, role="user", text=question))
                db.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        text=answer,
                        citation_ids=json.dumps([c["chunk_id"] for c in active]),
                    )
                )
                db.commit()
            yield event(
                "result",
                {
                    "conversation_id": conversation_id,
                    "text": answer,
                    "citations": active,
                    "mode": mode,
                    "generation_streaming": True,
                },
            )
        except ProviderUnavailable as exc:
            yield event("error", {"code": exc.code})
        yield event("done", {})

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )
