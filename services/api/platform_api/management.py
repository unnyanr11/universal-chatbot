"""Versioned assistant configuration, user controls and measured project operations."""

import json
import os
import re
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .context import assistant_scope, database, identity, project_scope, require_writer
from .database import (
    Assistant,
    AssistantSettings,
    AssistantVersion,
    AuditEvent,
    Booking,
    ChatAction,
    Conversation,
    Document,
    Membership,
    Message,
    Operation,
    OperationPolicy,
    Organization,
    Project,
    Reminder,
    Reservation,
    ResourceReservation,
    Session,
    SupportNote,
    SupportTicket,
    User,
    UserMemory,
    WorkflowRun,
)

router = APIRouter(prefix="/v1")


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    welcome_message: str = Field(default="How can I help?", max_length=1000)
    description: str = Field(default="", max_length=1000)
    color: str = Field(default="#1e5548", pattern=r"^#[0-9a-fA-F]{6}$")
    tone: str = Field(default="friendly", pattern="^(friendly|formal|concise)$")
    timezone: str = "Asia/Kolkata"
    languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1, max_length=10)
    suggested_questions: list[str] = Field(default_factory=list, max_length=6)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown timezone") from None
        return value

    @field_validator("suggested_questions", "languages", "allowed_domains")
    @classmethod
    def bounded_strings(cls, values):
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("Invalid configuration item")
        return values

    @field_validator("allowed_domains")
    @classmethod
    def valid_domains(cls, values):
        if any(not re.fullmatch(r"[a-zA-Z0-9.-]+(?::[0-9]{1,5})?", v) for v in values):
            raise ValueError("Use host names without paths or schemes")
        return values


class SaveConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    configuration: Configuration


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=500)
    consent: bool
    retention_days: int = Field(default=30, ge=1, le=90)


class Erasure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str


def settings_record(db, assistant):
    settings = db.get(AssistantSettings, assistant.id)
    default = Configuration(
        name=assistant.name, welcome_message=assistant.welcome_message
    ).model_dump()
    return {
        "revision": settings.revision if settings else 0,
        "published_version": settings.published_version if settings else 0,
        "configuration": json.loads(settings.configuration) if settings else default,
    }


def audit(db, project, actor, kind, object_id):
    db.add(AuditEvent(project_id=project, actor_id=actor, kind=kind, object_id=object_id))


@router.get("/me")
def me(session=Depends(identity), db=Depends(database)):
    user = db.get(User, session.user_id)
    return {
        "id": user.id,
        "email": user.email,
        "memberships": [
            {"organization_id": m.organization_id, "role": m.role}
            for m in db.scalars(select(Membership).where(Membership.user_id == user.id))
        ],
    }


@router.delete("/me/sessions", status_code=204)
def revoke_all_sessions(session=Depends(identity), db=Depends(database)):
    db.execute(delete(Session).where(Session.user_id == session.user_id))
    db.commit()


@router.get("/assistants/{assistant_id}/configuration")
def configuration(scope=Depends(assistant_scope), db=Depends(database)):
    return settings_record(db, scope[0])


@router.put("/assistants/{assistant_id}/configuration")
def save_configuration(
    body: SaveConfiguration,
    scope=Depends(assistant_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_writer(scope)
    assistant = scope[0]
    settings = db.get(AssistantSettings, assistant.id)
    data = body.configuration.model_dump()
    if not settings:
        if body.revision != 0:
            raise HTTPException(409, "CONFIGURATION_CHANGED_REFRESH")
        settings = AssistantSettings(assistant_id=assistant.id, configuration=json.dumps(data))
        db.add(settings)
    else:
        changed = db.execute(
            update(AssistantSettings)
            .where(
                AssistantSettings.assistant_id == assistant.id,
                AssistantSettings.revision == body.revision,
            )
            .values(configuration=json.dumps(data), revision=AssistantSettings.revision + 1)
            .returning(AssistantSettings.assistant_id)
        ).scalar_one_or_none()
        if not changed:
            raise HTTPException(409, "CONFIGURATION_CHANGED_REFRESH")
    assistant.name, assistant.welcome_message = data["name"], data["welcome_message"]
    audit(db, assistant.project_id, session.user_id, "configuration_saved", assistant.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CONFIGURATION_CHANGED_REFRESH") from None
    return settings_record(db, assistant)


@router.post("/assistants/{assistant_id}/publish")
def publish(
    body: Revision, scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)
):
    require_writer(scope)
    assistant = scope[0]
    settings = db.get(AssistantSettings, assistant.id)
    if not settings or settings.revision != body.revision:
        raise HTTPException(409, "SAVE_CURRENT_CONFIGURATION_FIRST")
    locked = db.execute(
        update(AssistantSettings)
        .where(
            AssistantSettings.assistant_id == assistant.id,
            AssistantSettings.revision == body.revision,
        )
        .values(revision=AssistantSettings.revision + 1)
        .returning(AssistantSettings.assistant_id)
    ).scalar_one_or_none()
    if not locked:
        raise HTTPException(409, "CONFIGURATION_CHANGED_REFRESH")
    number = (
        db.scalar(
            select(func.max(AssistantVersion.number)).where(
                AssistantVersion.assistant_id == assistant.id
            )
        )
        or 0
    ) + 1
    snapshot = {
        "configuration": json.loads(settings.configuration),
        "knowledge": [
            {"id": d.id, "hash": d.content_hash}
            for d in db.scalars(
                select(Document).where(
                    Document.assistant_id == assistant.id, Document.status == "ready"
                )
            )
        ],
        "prompt_version": 1,
        "tool_version": 1,
        "model": os.getenv("OLLAMA_MODEL", ""),
        "retrieval": "lexical-v1",
    }
    db.add(
        AssistantVersion(
            assistant_id=assistant.id, number=number, configuration=json.dumps(snapshot)
        )
    )
    settings.published_version = number
    assistant.status, assistant.version = "published", number
    audit(db, assistant.project_id, session.user_id, "assistant_published", assistant.id)
    db.commit()
    return {**settings_record(db, assistant), "manifest": snapshot}


@router.get("/assistants/{assistant_id}/versions")
def versions(scope=Depends(assistant_scope), db=Depends(database)):
    require_writer(scope)
    return {
        "items": [
            {
                "number": v.number,
                "published_at": v.published_at,
                "manifest": json.loads(v.configuration),
            }
            for v in db.scalars(
                select(AssistantVersion)
                .where(AssistantVersion.assistant_id == scope[0].id)
                .order_by(AssistantVersion.number.desc())
                .limit(100)
            )
        ]
    }


@router.post("/assistants/{assistant_id}/versions/{number}/restore")
def restore(
    number: int,
    body: Revision,
    scope=Depends(assistant_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_writer(scope)
    version = db.scalar(
        select(AssistantVersion).where(
            AssistantVersion.assistant_id == scope[0].id, AssistantVersion.number == number
        )
    )
    if not version:
        raise HTTPException(404, "VERSION_NOT_FOUND")
    data = json.loads(version.configuration)["configuration"]
    changed = db.execute(
        update(AssistantSettings)
        .where(
            AssistantSettings.assistant_id == scope[0].id,
            AssistantSettings.revision == body.revision,
        )
        .values(
            configuration=json.dumps(data),
            published_version=number,
            revision=AssistantSettings.revision + 1,
        )
        .returning(AssistantSettings.assistant_id)
    ).scalar_one_or_none()
    if not changed:
        raise HTTPException(409, "CONFIGURATION_CHANGED_REFRESH")
    scope[0].name, scope[0].welcome_message, scope[0].version = (
        data["name"],
        data["welcome_message"],
        number,
    )
    audit(db, scope[0].project_id, session.user_id, "version_restored", scope[0].id)
    db.commit()
    return settings_record(db, scope[0])


@router.get("/projects/{project_id}/memories")
def memories(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    return {
        "items": [
            {
                "id": m.id,
                "text": m.text,
                "expires_at": m.expires_at,
                "source": "explicit user consent",
                "purpose": "optional user preference",
            }
            for m in db.scalars(
                select(UserMemory).where(
                    UserMemory.project_id == scope[0].id,
                    UserMemory.user_id == session.user_id,
                    UserMemory.expires_at > time.time(),
                )
            )
        ]
    }


@router.post("/projects/{project_id}/memories", status_code=201)
def remember(
    body: MemoryInput, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    if not body.consent:
        raise HTTPException(422, "EXPLICIT_MEMORY_CONSENT_REQUIRED")
    if (
        db.scalar(
            select(func.count())
            .select_from(UserMemory)
            .where(UserMemory.user_id == session.user_id, UserMemory.project_id == scope[0].id)
        )
        >= 20
    ):
        raise HTTPException(409, "MEMORY_LIMIT_20")
    memory = UserMemory(
        project_id=scope[0].id,
        user_id=session.user_id,
        text=body.text,
        expires_at=int(time.time()) + body.retention_days * 86400,
    )
    db.add(memory)
    db.commit()
    return {"id": memory.id, "expires_at": memory.expires_at}


@router.delete("/projects/{project_id}/memories/{memory_id}", status_code=204)
def forget(
    memory_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    memory = db.scalar(
        select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.project_id == scope[0].id,
            UserMemory.user_id == session.user_id,
        )
    )
    if not memory:
        raise HTTPException(404, "MEMORY_NOT_FOUND")
    db.delete(memory)
    db.commit()


@router.get("/projects/{project_id}/my-data")
def export_my_data(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    from .knowledge import transcript

    conversation_rows = db.scalars(
        select(Conversation)
        .join(Assistant)
        .where(Assistant.project_id == scope[0].id, Conversation.user_id == session.user_id)
    ).all()
    result = {
        "conversations": [],
        "bookings": [],
        "memories": [],
        "operations": [],
        "workflow_runs": [],
    }
    for conversation in conversation_rows:
        result["conversations"].append(
            {
                "id": conversation.id,
                **transcript(
                    conversation.id,
                    (db.get(Assistant, conversation.assistant_id), scope[1]),
                    session,
                    db,
                ),
            }
        )
    for key, model in [
        ("bookings", Booking),
        ("memories", UserMemory),
        ("operations", Operation),
        ("workflow_runs", WorkflowRun),
    ]:
        for row in db.scalars(
            select(model).where(model.project_id == scope[0].id, model.user_id == session.user_id)
        ):
            result[key].append(
                {column.name: getattr(row, column.name) for column in model.__table__.columns}
            )
    return result


@router.delete("/projects/{project_id}/my-data", status_code=204)
def erase_my_data(
    body: Erasure, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    if body.confirmation != "DELETE MY WORKSPACE DATA":
        raise HTTPException(422, "EXACT_ERASURE_CONFIRMATION_REQUIRED")
    conversations = list(
        db.scalars(
            select(Conversation.id)
            .join(Assistant)
            .where(Assistant.project_id == scope[0].id, Conversation.user_id == session.user_id)
        )
    )
    tickets = select(SupportTicket.id).where(SupportTicket.conversation_id.in_(conversations))
    db.execute(delete(SupportNote).where(SupportNote.ticket_id.in_(tickets)))
    db.execute(delete(SupportTicket).where(SupportTicket.conversation_id.in_(conversations)))
    db.execute(
        delete(ChatAction).where(
            ChatAction.message_id.in_(
                select(Message.id).where(Message.conversation_id.in_(conversations))
            )
        )
    )
    db.execute(delete(Message).where(Message.conversation_id.in_(conversations)))
    db.execute(delete(Conversation).where(Conversation.id.in_(conversations)))
    bookings = select(Booking.id).where(
        Booking.project_id == scope[0].id, Booking.user_id == session.user_id
    )
    db.execute(delete(ResourceReservation).where(ResourceReservation.booking_id.in_(bookings)))
    db.execute(
        delete(OperationPolicy).where(
            OperationPolicy.operation_id.in_(
                select(Operation.id).where(
                    Operation.project_id == scope[0].id, Operation.user_id == session.user_id
                )
            )
        )
    )
    db.execute(delete(Reservation).where(Reservation.booking_id.in_(bookings)))
    db.execute(delete(Reminder).where(Reminder.booking_id.in_(bookings)))
    db.execute(delete(Booking).where(Booking.id.in_(bookings)))
    for model in (Operation, UserMemory, WorkflowRun):
        db.execute(
            delete(model).where(model.project_id == scope[0].id, model.user_id == session.user_id)
        )
    # Pseudonymise existing audit actor references; retain payload-free operational events.
    db.execute(
        update(AuditEvent)
        .where(AuditEvent.project_id == scope[0].id, AuditEvent.actor_id == session.user_id)
        .values(actor_id="erased")
    )
    db.commit()


@router.get("/projects/{project_id}/analytics")
def analytics(scope=Depends(project_scope), db=Depends(database)):
    if scope[1].role not in {"owner", "administrator", "analyst", "support_agent"}:
        raise HTTPException(403, "ANALYTICS_ROLE_REQUIRED")

    def grouped(model, field):
        return dict(
            db.execute(
                select(field, func.count()).where(model.project_id == scope[0].id).group_by(field)
            ).all()
        )

    conversation_count = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .join(Assistant)
        .where(Assistant.project_id == scope[0].id)
    )
    return {
        "conversations": conversation_count,
        "booking_states": grouped(Booking, Booking.status),
        "operation_states": grouped(Operation, Operation.state),
        "ticket_states": grouped(SupportTicket, SupportTicket.state),
        "definitions": {
            "conversations": "Count of stored conversations, not resolved requests",
            "booking_states": "Current stored bookings grouped by authoritative status",
            "operation_states": "All stored proposals, including failed/expired/unconfirmed",
        },
        "model_latency": None,
        "estimated_cost": None,
    }


@router.get("/projects/{project_id}/audit")
def audit_events(scope=Depends(project_scope), db=Depends(database)):
    if scope[1].role not in {"owner", "administrator", "analyst"}:
        raise HTTPException(403, "AUDIT_ROLE_REQUIRED")
    return {
        "items": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "kind": e.kind,
                "object_id": e.object_id,
                "created_at": e.created_at,
            }
            for e in db.scalars(
                select(AuditEvent)
                .where(AuditEvent.project_id == scope[0].id)
                .order_by(AuditEvent.created_at.desc())
                .limit(100)
            )
        ]
    }


class OrganisationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


@router.post("/organizations", status_code=201)
def create_organization(body: OrganisationInput, session=Depends(identity), db=Depends(database)):
    organization = Organization(name=body.name)
    db.add(organization)
    db.flush()
    db.add(Membership(user_id=session.user_id, organization_id=organization.id, role="owner"))
    project = Project(organization_id=organization.id, name=body.name + " workspace")
    db.add(project)
    db.flush()
    audit(db, project.id, session.user_id, "organization_created", organization.id)
    db.commit()
    return {"organization_id": organization.id, "project_id": project.id}
