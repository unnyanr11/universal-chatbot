"""Server-created chat controls. Generated text can neither manufacture nor execute them."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from . import booking
from .context import database, identity, project_scope
from .database import ChatAction, Message

router = APIRouter(prefix="/v1/projects/{project_id}/chat-actions")


def intent(text):
    command = re.sub(
        r"^(?:please |can you |could you |i want to |i need to |i would like to |help me )",
        "",
        text.strip().lower(),
    )
    if re.match(
        r"^(book|schedule)\s+(?:(?:a|an|my)\s+)?(?:appointment|slot|consultation|service)\b",
        command,
    ):
        return "book"
    if re.match(r"^reschedule\s+(?:(?:a|an|my|the)\s+)?(?:appointment|booking)\b", command):
        return "reschedule"
    if re.match(r"^cancel\s+(?:(?:a|an|my|the)\s+)?(?:appointment|booking)\b", command):
        return "cancel"
    return None


def reference(action):
    return {
        "id": action.id,
        "kind": action.kind,
        "project_id": action.project_id,
        "type": "appointment_form",
    }


def create_card(db, conversation_id, project_id, user_id, text, kind):
    db.add(Message(conversation_id=conversation_id, role="user", text=text))
    message = Message(
        conversation_id=conversation_id,
        role="assistant",
        text="Choose the exact details below. No appointment changes until you review and confirm.",
    )
    db.add(message)
    db.flush()
    action = ChatAction(message_id=message.id, project_id=project_id, user_id=user_id, kind=kind)
    db.add(action)
    db.commit()
    return {
        "conversation_id": conversation_id,
        "text": message.text,
        "citations": [],
        "mode": "action_form",
        "generation_streaming": False,
        "action": reference(action),
    }


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str = Field(default="", max_length=100)
    booking_id: str = Field(default="", max_length=100)


def own_action(db, action_id, scope, session):
    action = db.scalar(
        select(ChatAction).where(
            ChatAction.id == action_id,
            ChatAction.project_id == scope[0].id,
            ChatAction.user_id == session.user_id,
        )
    )
    if not action:
        raise HTTPException(404, "CHAT_ACTION_NOT_FOUND")
    return action


@router.get("/{action_id}")
def action_detail(
    action_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    action = own_action(db, action_id, scope, session)
    return {
        **reference(action),
        "services": booking.services(scope, db)["items"],
        "bookings": booking.bookings(scope, session, db)["items"],
        "operation": booking.receipt(db, db.get(booking.Operation, action.operation_id))
        if action.operation_id
        else None,
    }


@router.post("/{action_id}/propose")
def propose(
    action_id: str,
    body: ActionInput,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    action = own_action(db, action_id, scope, session)
    if action.operation_id:
        operation = db.get(booking.Operation, action.operation_id)
        if (action.kind != "cancel" and body.slot_id != operation.slot_id) or (
            action.kind != "book" and body.booking_id != operation.booking_id
        ):
            raise HTTPException(409, "ACTION_IMMUTABLE_CREATE_NEW_REQUEST")
        return booking.receipt(db, operation)
    result = booking.propose(
        booking.Proposal(
            kind=action.kind,
            slot_id=body.slot_id,
            booking_id=body.booking_id,
            idempotency_key="chat:" + action.id,
        ),
        scope,
        session,
        db,
    )
    action.operation_id = result["id"]
    db.commit()
    return result
