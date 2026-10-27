"""Local human inbox. Private notes never enter the customer transcript or model context."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .context import database, identity, project_scope
from .database import Assistant, AuditEvent, Conversation, Message, SupportNote, SupportTicket
from .knowledge import citations

router = APIRouter(prefix="/v1/projects/{project_id}")
AGENTS = {"owner", "administrator", "support_agent"}


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str
    subject: str = Field(min_length=1, max_length=200)


class TicketAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(pattern="^(claim|resolve|resume)$")
    version: int = Field(ge=1)


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000)
    internal: bool = False


def require_agent(scope):
    if scope[1].role not in AGENTS:
        raise HTTPException(403, "AGENT_ROLE_REQUIRED")


def ticket_record(ticket):
    return {
        "id": ticket.id,
        "conversation_id": ticket.conversation_id,
        "subject": ticket.subject,
        "state": ticket.state,
        "assigned_to": ticket.assigned_to,
        "version": ticket.version,
        "created_at": ticket.created_at,
    }


def find_ticket(db, ticket_id, project_id):
    ticket = db.scalar(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id, SupportTicket.project_id == project_id
        )
    )
    if not ticket:
        raise HTTPException(404, "TICKET_NOT_FOUND")
    return ticket


@router.post("/tickets", status_code=201)
def request_handoff(
    body: Handoff, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    conversation = db.scalar(
        select(Conversation)
        .join(Assistant)
        .where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == session.user_id,
            Assistant.project_id == scope[0].id,
        )
    )
    if not conversation:
        raise HTTPException(404, "CONVERSATION_NOT_FOUND")
    ticket = db.scalar(
        select(SupportTicket).where(SupportTicket.conversation_id == conversation.id)
    )
    if ticket:
        return ticket_record(ticket)
    ticket = SupportTicket(
        project_id=scope[0].id,
        user_id=session.user_id,
        conversation_id=conversation.id,
        subject=body.subject,
    )
    db.add(ticket)
    try:
        db.flush()
        db.add(
            AuditEvent(
                project_id=scope[0].id,
                actor_id=session.user_id,
                kind="handoff_requested",
                object_id=ticket.id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "HANDOFF_ALREADY_REQUESTED") from None
    return ticket_record(ticket)


@router.get("/tickets")
def inbox(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    query = select(SupportTicket).where(SupportTicket.project_id == scope[0].id)
    if scope[1].role not in AGENTS:
        query = query.where(SupportTicket.user_id == session.user_id)
    return {
        "items": [
            ticket_record(t)
            for t in db.scalars(query.order_by(SupportTicket.created_at.desc()).limit(100))
        ]
    }


@router.get("/tickets/{ticket_id}")
def ticket_detail(
    ticket_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    ticket = find_ticket(db, ticket_id, scope[0].id)
    agent = scope[1].role in AGENTS
    if not agent and ticket.user_id != session.user_id:
        raise HTTPException(404, "TICKET_NOT_FOUND")
    conversation = db.get(Conversation, ticket.conversation_id)
    messages = [
        {
            "role": m.role,
            "text": m.text,
            "citations": citations(db, json.loads(m.citation_ids), conversation.assistant_id),
        }
        for m in db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
        )
    ]
    result = {**ticket_record(ticket), "messages": messages}
    if agent:
        result["notes"] = [
            {"text": n.text, "author_id": n.author_id}
            for n in db.scalars(
                select(SupportNote)
                .where(SupportNote.ticket_id == ticket.id)
                .order_by(SupportNote.created_at)
            )
        ]
    return result


@router.post("/tickets/{ticket_id}/state")
def change_state(
    ticket_id: str,
    body: TicketAction,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_agent(scope)
    ticket = find_ticket(db, ticket_id, scope[0].id)
    if ticket.assigned_to and ticket.assigned_to != session.user_id:
        raise HTTPException(409, "TICKET_OWNED_BY_ANOTHER_AGENT")
    target = {"claim": "assigned", "resolve": "resolved", "resume": "automated"}[body.action]
    if ticket.state in {"resolved", "automated"}:
        raise HTTPException(409, "TICKET_ALREADY_CLOSED")
    changed = db.execute(
        update(SupportTicket)
        .where(SupportTicket.id == ticket.id, SupportTicket.version == body.version)
        .values(state=target, assigned_to=session.user_id, version=SupportTicket.version + 1)
        .returning(SupportTicket.id)
    ).scalar_one_or_none()
    if not changed:
        db.rollback()
        raise HTTPException(409, "TICKET_CHANGED_REFRESH")
    db.add(
        AuditEvent(
            project_id=scope[0].id,
            actor_id=session.user_id,
            kind="handoff_" + body.action,
            object_id=ticket.id,
        )
    )
    db.commit()
    return ticket_record(ticket)


@router.post("/tickets/{ticket_id}/messages", status_code=201)
def agent_message(
    ticket_id: str,
    body: AgentMessage,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_agent(scope)
    ticket = find_ticket(db, ticket_id, scope[0].id)
    # Lock state with a no-op update so release/resolve cannot race a late agent reply.
    locked = db.execute(
        update(SupportTicket)
        .where(
            SupportTicket.id == ticket.id,
            SupportTicket.state == "assigned",
            SupportTicket.assigned_to == session.user_id,
        )
        .values(version=SupportTicket.version)
        .returning(SupportTicket.id)
    ).scalar_one_or_none()
    if not locked:
        raise HTTPException(409, "CLAIM_TICKET_BEFORE_REPLYING")
    if body.internal:
        db.add(SupportNote(ticket_id=ticket.id, author_id=session.user_id, text=body.text))
    else:
        db.add(Message(conversation_id=ticket.conversation_id, role="human", text=body.text))
    db.commit()
    return {"status": "saved", "visibility": "internal" if body.internal else "customer"}
