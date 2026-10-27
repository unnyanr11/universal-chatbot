"""Real local bookings: immutable proposals, atomic reservations and retry receipts."""

import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from .calendars import (
    bind_operation,
    eligible,
    reserve_resource,
    revalidate_operation,
    service_policy,
)
from .context import database, identity, project_scope
from .database import (
    AuditEvent,
    Booking,
    Operation,
    OperationPolicy,
    Reminder,
    Reservation,
    ResourceReservation,
    Service,
    ServicePolicy,
    Slot,
    SlotResource,
    Staff,
)

router = APIRouter(prefix="/v1/projects/{project_id}")


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(book|reschedule|cancel)$")
    slot_id: str = ""
    booking_id: str = ""
    idempotency_key: str = Field(min_length=8, max_length=100)


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def slot_details(db, slot_id, project_id):
    row = db.execute(
        select(Slot, Service)
        .join(Service)
        .where(Slot.id == slot_id, Service.project_id == project_id)
    ).first()
    if not row:
        raise HTTPException(404, "SLOT_NOT_FOUND")
    slot, service = row
    binding = db.get(SlotResource, slot.id)
    staff = db.get(Staff, binding.staff_id) if binding else None
    return {
        "staff": staff.name if staff else None,
        "slot_id": slot.id,
        "service": service.name,
        "start_at": iso(slot.start_at),
        "end_at": iso(slot.end_at),
        "timezone": service.timezone,
        "location": service.location,
    }


def receipt(db, op):
    binding = db.get(OperationPolicy, op.id)
    preview = (
        json.loads(binding.preview)
        if binding
        else (slot_details(db, op.slot_id, op.project_id) if op.slot_id else None)
    )
    policy_text = "Local demo: cancel or reschedule before the appointment starts. Preview does not reserve a slot."
    if binding:
        cutoff = preview["policy"]["cancellation_cutoff_minutes"]
        policy_text = f"Cancel or reschedule at least {cutoff} minutes before the appointment. Preview does not reserve capacity."
        if op.kind == "reschedule":
            original_cutoff = preview.get("source_cancellation_cutoff_minutes", 0)
            policy_text = f"Original appointment change cutoff: {original_cutoff} minutes. New appointment cancellation cutoff: {cutoff} minutes. Preview does not reserve capacity."
    return {
        "id": op.id,
        "kind": op.kind,
        "state": op.state,
        "booking_id": op.booking_id,
        "expires_at": op.expires_at,
        "error": op.error,
        "preview": preview,
        "policy": policy_text,
        "notification": "In-app only; no email or SMS sent.",
    }


def own_booking(db, booking_id, project_id, user_id):
    booking = db.scalar(
        select(Booking).where(
            Booking.id == booking_id, Booking.project_id == project_id, Booking.user_id == user_id
        )
    )
    if not booking:
        raise HTTPException(404, "BOOKING_NOT_FOUND")
    return booking


@router.get("/services")
def services(scope=Depends(project_scope), db=Depends(database)):
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "duration_minutes": s.duration_minutes,
                "timezone": s.timezone,
                "location": s.location,
            }
            for s in db.scalars(select(Service).where(Service.project_id == scope[0].id))
        ]
    }


@router.get("/services/{service_id}/slots")
def available_slots(service_id: str, scope=Depends(project_scope), db=Depends(database)):
    service = db.scalar(
        select(Service).where(Service.id == service_id, Service.project_id == scope[0].id)
    )
    if not service:
        raise HTTPException(404, "SERVICE_NOT_FOUND")
    service_config = db.get(ServicePolicy, service.id)
    lead = json.loads(service_config.configuration)["lead_time_minutes"] if service_config else 60
    window = (
        json.loads(service_config.configuration)["booking_window_days"] if service_config else 180
    )
    slots = db.scalars(
        select(Slot)
        .where(
            Slot.service_id == service_id,
            Slot.start_at > int(time.time()) + lead * 60,
            Slot.start_at <= int(time.time()) + window * 86400,
            ~Slot.id.in_(select(Reservation.slot_id)),
        )
        .order_by(Slot.start_at)
        .limit(100)
    )
    return {
        "items": [slot_details(db, s.id, scope[0].id) for s in slots if eligible(db, s)],
        "lead_time_minutes": lead,
        "capacity_per_slot": 1,
    }


@router.get("/bookings")
def bookings(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    return {
        "items": [
            {
                "id": b.id,
                "status": b.status,
                "version": b.version,
                **slot_details(db, b.slot_id, scope[0].id),
            }
            for b in db.scalars(
                select(Booking)
                .where(Booking.project_id == scope[0].id, Booking.user_id == session.user_id)
                .order_by(Booking.id)
                .limit(100)
            )
        ]
    }


@router.post("/operations", status_code=201)
def propose(
    body: Proposal, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    existing = db.scalar(
        select(Operation).where(
            Operation.project_id == scope[0].id,
            Operation.user_id == session.user_id,
            Operation.idempotency_key == body.idempotency_key,
        )
    )
    if existing:
        if (
            existing.kind,
            existing.slot_id,
            existing.booking_id if body.kind != "book" else "",
        ) != (
            body.kind,
            body.slot_id if body.kind != "cancel" else existing.slot_id,
            body.booking_id,
        ):
            raise HTTPException(409, "IDEMPOTENCY_ARGUMENT_MISMATCH")
        return receipt(db, existing)
    booking = None
    if body.kind != "book":
        booking = own_booking(db, body.booking_id, scope[0].id, session.user_id)
        if booking.status != "confirmed":
            raise HTTPException(409, "BOOKING_NOT_ACTIVE")
        old_slot = db.get(Slot, booking.slot_id)
        _, old_policy = service_policy(db, old_slot)
        if old_slot.start_at <= time.time() + old_policy.cancellation_cutoff_minutes * 60:
            raise HTTPException(409, "CHANGE_CUTOFF_PASSED")
    elif body.booking_id:
        raise HTTPException(422, "BOOK_DOES_NOT_ACCEPT_BOOKING_ID")
    slot_id = booking.slot_id if body.kind == "cancel" else body.slot_id
    slot_details(db, slot_id, scope[0].id)
    if body.kind != "cancel":
        slot = db.get(Slot, slot_id)
        configured, policy = service_policy(db, slot)
        if slot.start_at <= time.time() + (policy.lead_time_minutes * 60 if configured else 3600):
            raise HTTPException(409, "LEAD_TIME_REQUIRED")
        if db.get(Reservation, slot_id):
            raise HTTPException(409, "SLOT_UNAVAILABLE")
    op = Operation(
        project_id=scope[0].id,
        user_id=session.user_id,
        kind=body.kind,
        slot_id=slot_id,
        booking_id=body.booking_id,
        booking_version=booking.version if booking else 0,
        idempotency_key=body.idempotency_key,
    )
    db.add(op)
    try:
        db.flush()
        bind_operation(db, op, slot_details(db, slot_id, scope[0].id))
        db.add(
            AuditEvent(
                project_id=scope[0].id,
                actor_id=session.user_id,
                kind="operation_proposed",
                object_id=op.id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CONCURRENT_PROPOSAL_RETRY_SAME_KEY") from None
    return receipt(db, op)


@router.get("/operations/{operation_id}")
def operation(
    operation_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    op = db.scalar(
        select(Operation).where(
            Operation.id == operation_id,
            Operation.project_id == scope[0].id,
            Operation.user_id == session.user_id,
        )
    )
    if not op:
        raise HTTPException(404, "OPERATION_NOT_FOUND")
    return receipt(db, op)


@router.post("/operations/{operation_id}/confirm")
def confirm(
    operation_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    op = db.scalar(
        select(Operation).where(
            Operation.id == operation_id,
            Operation.project_id == scope[0].id,
            Operation.user_id == session.user_id,
        )
    )
    if not op:
        raise HTTPException(404, "OPERATION_NOT_FOUND")
    if op.state != "awaiting_confirmation":
        return receipt(db, op)
    if op.expires_at <= time.time():
        op.state = "expired"
        db.commit()
        return receipt(db, op)
    # Compare-and-swap prevents duplicate execution from parallel confirmations.
    claimed = db.execute(
        update(Operation)
        .where(Operation.id == op.id, Operation.state == "awaiting_confirmation")
        .values(state="running")
        .returning(Operation.id)
    ).scalar_one_or_none()
    if not claimed:
        db.rollback()
        return receipt(db, db.get(Operation, operation_id))
    try:
        slot = db.get(Slot, op.slot_id)
        revalidate_operation(db, op, slot)
        if slot.start_at <= time.time():
            raise ValueError("APPOINTMENT_TIME_UNAVAILABLE")
        if op.kind == "book":
            booking = Booking(project_id=op.project_id, user_id=session.user_id, slot_id=slot.id)
            db.add(booking)
            db.flush()
            db.add(Reservation(slot_id=slot.id, booking_id=booking.id))
            db.flush()  # Atomic unique constraint decides competing last-slot claims.
            reserve_resource(db, booking, slot)
            op.booking_id = booking.id
        else:
            booking = own_booking(db, op.booking_id, op.project_id, session.user_id)
            old_slot_id = booking.slot_id
            old_slot = db.get(Slot, old_slot_id)
            _, old_policy = service_policy(db, old_slot)
            if old_slot.start_at <= time.time() + old_policy.cancellation_cutoff_minutes * 60:
                raise ValueError("CHANGE_CUTOFF_PASSED")
            updated = db.execute(
                update(Booking)
                .where(
                    Booking.id == booking.id,
                    Booking.version == op.booking_version,
                    Booking.status == "confirmed",
                )
                .values(version=Booking.version + 1)
                .returning(Booking.id)
            ).scalar_one_or_none()
            if not updated:
                raise ValueError("BOOKING_CHANGED_REVIEW_AGAIN")
            # Both changes share one transaction. Rollback restores the original reservation.
            db.execute(delete(Reservation).where(Reservation.booking_id == booking.id))
            if op.kind == "reschedule":
                db.add(Reservation(slot_id=slot.id, booking_id=booking.id))
                db.flush()
                reserve_resource(db, booking, slot)
                booking.slot_id = slot.id
            else:
                db.execute(
                    delete(ResourceReservation).where(ResourceReservation.booking_id == booking.id)
                )
                booking.status = "cancelled"
            db.execute(
                update(Reminder)
                .where(Reminder.booking_id == booking.id, Reminder.status == "scheduled")
                .values(status="cancelled")
            )
        if op.kind != "cancel":
            db.add(
                Reminder(
                    booking_id=booking.id,
                    version=booking.version,
                    due_at=max(int(time.time()), slot.start_at - 86400),
                )
            )
        op.state = "succeeded"
        db.add(
            AuditEvent(
                project_id=scope[0].id,
                actor_id=session.user_id,
                kind="operation_succeeded",
                object_id=op.id,
            )
        )
        from .webhooks import enqueue

        enqueue(
            db,
            scope[0].id,
            "booking." + ("cancelled" if op.kind == "cancel" else "confirmed"),
            {"booking_id": op.booking_id, "operation_id": op.id, "kind": op.kind},
        )
        db.commit()
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        op = db.get(Operation, operation_id)
        if op.state == "awaiting_confirmation":
            op.state = "failed"
            op.error = "SLOT_UNAVAILABLE" if isinstance(exc, IntegrityError) else str(exc)
            db.add(
                AuditEvent(
                    project_id=scope[0].id,
                    actor_id=session.user_id,
                    kind="operation_failed",
                    object_id=op.id,
                )
            )
            db.commit()
    return receipt(db, op)


@router.get("/inbox")
def inbox(scope=Depends(project_scope), session=Depends(identity), db=Depends(database)):
    rows = db.execute(
        select(Reminder, Booking)
        .join(Booking)
        .where(
            Booking.project_id == scope[0].id,
            Booking.user_id == session.user_id,
            Reminder.status == "delivered",
            Booking.status == "confirmed",
            Reminder.version == Booking.version,
        )
        .limit(100)
    )
    return {
        "items": [
            {
                "id": r.id,
                "booking_id": b.id,
                "type": "appointment_reminder",
                **slot_details(db, b.slot_id, scope[0].id),
            }
            for r, b in rows
        ]
    }


@router.get("/tools")
def tools(scope=Depends(project_scope)):
    from .registry import descriptors

    return {"items": descriptors()}
