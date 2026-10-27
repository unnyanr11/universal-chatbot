"""Allowlisted local tool contracts; writes return proposed operations, never implicit execution."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import booking
from .context import database, identity, project_scope
from .database import Assistant
from .knowledge import retrieve

router = APIRouter(prefix="/v1/projects/{project_id}")


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArguments(ToolInput):
    pass


class AvailableInput(ToolInput):
    service_id: str = Field(min_length=1, max_length=100)


class KnowledgeInput(ToolInput):
    assistant_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=4000)


class BookingInput(ToolInput):
    slot_id: str = Field(min_length=1, max_length=100)


class RescheduleInput(BookingInput):
    booking_id: str = Field(min_length=1, max_length=100)


class CancelInput(ToolInput):
    booking_id: str = Field(min_length=1, max_length=100)


class ToolCall(ToolInput):
    name: str = Field(min_length=1, max_length=100)
    arguments: dict = Field(default_factory=dict)
    idempotency_key: str = Field(default="", max_length=100)
    dry_run: bool = False


class ServiceOutput(BaseModel):
    id: str
    name: str
    duration_minutes: int
    timezone: str
    location: str


class ServicesOutput(BaseModel):
    items: list[ServiceOutput]


class SlotOutput(BaseModel):
    staff: str | None = None
    slot_id: str
    service: str
    start_at: str
    end_at: str
    timezone: str
    location: str


class AvailableOutput(BaseModel):
    items: list[SlotOutput]
    lead_time_minutes: int
    capacity_per_slot: int


class PassageOutput(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    page: int
    text: str
    score: float


class SearchOutput(BaseModel):
    items: list[PassageOutput]


class OperationOutput(BaseModel):
    id: str
    kind: str
    state: str
    booking_id: str
    expires_at: int
    error: str
    preview: dict | None
    policy: str
    notification: str


CONTRACTS = {
    "list_services": (NoArguments, ServicesOutput, "read", "List approved local services"),
    "get_available_slots": (AvailableInput, AvailableOutput, "read", "Check live local capacity"),
    "search_knowledge": (
        KnowledgeInput,
        SearchOutput,
        "read",
        "Retrieve assistant-approved passages",
    ),
    "create_appointment": (
        BookingInput,
        OperationOutput,
        "write",
        "Propose an appointment; confirmation required",
    ),
    "reschedule_appointment": (
        RescheduleInput,
        OperationOutput,
        "write",
        "Propose an atomic replacement",
    ),
    "cancel_appointment": (
        CancelInput,
        OperationOutput,
        "write",
        "Propose cancellation of an owned booking",
    ),
}


def descriptors():
    items = [
        {
            "name": name,
            "version": 1,
            "description": description,
            "kind": kind,
            "status": "implemented-local",
            "input_schema": source.model_json_schema(),
            "output_schema": target.model_json_schema(),
            "permission_scope": "member:own-data",
            "confirmation": "required" if kind == "write" else "none",
            "timeout_seconds": 30,
            "retry_policy": "retry with same operation ID; reconcile writes before retrying",
            "idempotency": "required for writes",
            "handler": "server-owned",
            "reversibility": "separate authorised compensating operation"
            if kind == "write"
            else "not applicable",
        }
        for name, (source, target, kind, description) in CONTRACTS.items()
    ]
    items.append(
        {
            "name": "send_email",
            "kind": "write",
            "status": "unconfigured",
            "reason": "No reviewed delivery adapter or credentials configured",
        }
    )
    return items


@router.post("/tool-calls")
def call_tool(
    body: ToolCall, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    contract = CONTRACTS.get(body.name)
    if not contract:
        raise HTTPException(
            503 if body.name == "send_email" else 404,
            "TOOL_UNCONFIGURED" if body.name == "send_email" else "TOOL_NOT_ALLOWED",
        )
    source, target, kind, _ = contract
    try:
        inputs = source.model_validate(body.arguments)
    except ValidationError:
        raise HTTPException(422, "TOOL_ARGUMENTS_INVALID") from None
    if kind == "write" and body.dry_run:
        args = inputs.model_dump()
        if "booking_id" in args:
            owned = booking.own_booking(db, args["booking_id"], scope[0].id, session.user_id)
            slot_id = args.get("slot_id", owned.slot_id)
        else:
            slot_id = args["slot_id"]
        preview = booking.slot_details(db, slot_id, scope[0].id)
        return {
            "tool": body.name,
            "version": 1,
            "execution": "dry-run",
            "result": {
                "state": "simulated",
                "preview": preview,
                "arguments": args,
                "notice": "No operation, appointment or external write was created. Availability is not reserved.",
            },
        }
    if kind == "write":
        if len(body.idempotency_key) < 8:
            raise HTTPException(422, "WRITE_IDEMPOTENCY_KEY_REQUIRED")
        operation = {
            "create_appointment": "book",
            "reschedule_appointment": "reschedule",
            "cancel_appointment": "cancel",
        }[body.name]
        output = booking.propose(
            booking.Proposal(
                kind=operation, idempotency_key=body.idempotency_key, **inputs.model_dump()
            ),
            scope,
            session,
            db,
        )
    elif body.name == "list_services":
        output = booking.services(scope, db)
    elif body.name == "get_available_slots":
        output = booking.available_slots(inputs.service_id, scope, db)
    else:
        assistant = db.get(Assistant, inputs.assistant_id)
        if not assistant or assistant.project_id != scope[0].id:
            raise HTTPException(404, "ASSISTANT_NOT_FOUND")
        output = {"items": retrieve(db, assistant.id, inputs.query)}
    result = target.model_validate(output).model_dump()
    return {
        "tool": body.name,
        "version": 1,
        "result": result,
        "execution": "proposal-only" if kind == "write" else "read-completed",
    }
