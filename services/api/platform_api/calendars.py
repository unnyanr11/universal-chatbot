"""Staff calendars and versioned local availability policies; absolute slots remain authoritative."""

import json
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from .context import database, project_scope, require_writer
from .database import (
    OperationPolicy,
    ResourceReservation,
    Service,
    ServicePolicy,
    Slot,
    SlotResource,
    Staff,
)

router = APIRouter(prefix="/v1/projects/{project_id}")


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opening_hours: dict[str, list[tuple[str, str]]] = Field(
        default_factory=lambda: {
            str(day): [("09:00", "12:00"), ("13:00", "17:00")] for day in range(5)
        }
    )
    holidays: list[date] = Field(default_factory=list, max_length=100)
    buffer_before_minutes: int = Field(default=0, ge=0, le=120)
    buffer_after_minutes: int = Field(default=0, ge=0, le=120)
    lead_time_minutes: int = Field(default=60, ge=0, le=43200)
    cancellation_cutoff_minutes: int = Field(default=60, ge=0, le=43200)
    booking_window_days: int = Field(default=30, ge=1, le=180)

    @model_validator(mode="after")
    def valid_hours(self):
        for day, periods in self.opening_hours.items():
            if day not in {str(i) for i in range(7)} or len(periods) > 4:
                raise ValueError("Invalid weekday or too many periods")
            previous_end = "00:00"
            for start, end in sorted(periods):
                for value in (start, end):
                    parsed = datetime.strptime(value, "%H:%M")
                    if parsed.strftime("%H:%M") != value:
                        raise ValueError("Use HH:MM opening times")
                if start >= end or start < previous_end:
                    raise ValueError("Opening periods must not overlap or cross midnight")
                previous_end = end
        return self


class StaffInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


class ServiceInput(StaffInput):
    staff_id: str
    duration_minutes: int = Field(default=30, ge=5, le=240)
    timezone: str = "Asia/Kolkata"
    location: str = Field(default="Service desk", min_length=1, max_length=200)
    policy: Policy = Field(default_factory=Policy)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown timezone") from None
        return value


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    policy: Policy


class GenerateSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    days: int = Field(default=14, ge=1, le=30)


def service_policy(db, slot):
    policy = db.get(ServicePolicy, slot.service_id)
    return policy, Policy.model_validate_json(policy.configuration) if policy else Policy(
        cancellation_cutoff_minutes=0
    )


def eligible(db, slot, exclude_booking="", lock=False):
    binding = db.get(SlotResource, slot.id)
    policy, config = service_policy(db, slot)
    if not policy or not binding:
        return not policy  # Legacy fixed slots retain their original per-slot capacity.
    if binding.policy_revision != policy.revision:
        return False
    if lock:
        db.execute(update(Staff).where(Staff.id == binding.staff_id).values(name=Staff.name))
    start = slot.start_at - config.buffer_before_minutes * 60
    end = slot.end_at + config.buffer_after_minutes * 60
    overlap = db.scalar(
        select(ResourceReservation.booking_id)
        .where(
            ResourceReservation.staff_id == binding.staff_id,
            ResourceReservation.booking_id != exclude_booking,
            ResourceReservation.start_at < end,
            ResourceReservation.end_at > start,
        )
        .limit(1)
    )
    return overlap is None


def bind_operation(db, operation, preview):
    slot = db.get(Slot, operation.slot_id)
    policy, config = service_policy(db, slot)
    if policy:
        if not eligible(db, slot, operation.booking_id) and operation.kind != "cancel":
            raise HTTPException(409, "STAFF_CAPACITY_UNAVAILABLE")
        details = {
            **preview,
            "policy": config.model_dump(mode="json"),
            "staff": db.get(Staff, policy.staff_id).name,
        }
        db.add(
            OperationPolicy(
                operation_id=operation.id, revision=policy.revision, preview=json.dumps(details)
            )
        )


def revalidate_operation(db, operation, slot):
    policy, config = service_policy(db, slot)
    binding = db.get(OperationPolicy, operation.id)
    if policy and (not binding or binding.revision != policy.revision):
        raise ValueError("CALENDAR_POLICY_CHANGED_REVIEW_AGAIN")
    lead = config.lead_time_minutes * 60 if policy else 3600
    if operation.kind != "cancel":
        if slot.start_at <= time.time() + lead:
            raise ValueError("LEAD_TIME_REQUIRED")
        if policy and slot.start_at > time.time() + config.booking_window_days * 86400:
            raise ValueError("OUTSIDE_BOOKING_WINDOW")
        if not eligible(db, slot, operation.booking_id, lock=True):
            raise ValueError("STAFF_CAPACITY_UNAVAILABLE")


def reserve_resource(db, booking, slot):
    db.execute(delete(ResourceReservation).where(ResourceReservation.booking_id == booking.id))
    binding = db.get(SlotResource, slot.id)
    policy, config = service_policy(db, slot)
    if binding and policy:
        db.add(
            ResourceReservation(
                booking_id=booking.id,
                staff_id=binding.staff_id,
                start_at=slot.start_at - config.buffer_before_minutes * 60,
                end_at=slot.end_at + config.buffer_after_minutes * 60,
            )
        )


@router.get("/staff")
def staff(scope=Depends(project_scope), db=Depends(database)):
    return {
        "items": [
            {"id": s.id, "name": s.name}
            for s in db.scalars(select(Staff).where(Staff.project_id == scope[0].id).limit(100))
        ]
    }


@router.post("/staff", status_code=201)
def create_staff(body: StaffInput, scope=Depends(project_scope), db=Depends(database)):
    require_writer(scope)
    staff = Staff(project_id=scope[0].id, name=body.name)
    db.add(staff)
    db.commit()
    return {"id": staff.id, "name": staff.name}


@router.post("/services", status_code=201)
def create_service(body: ServiceInput, scope=Depends(project_scope), db=Depends(database)):
    require_writer(scope)
    staff = db.scalar(
        select(Staff).where(Staff.id == body.staff_id, Staff.project_id == scope[0].id)
    )
    if not staff:
        raise HTTPException(404, "STAFF_NOT_FOUND")
    service = Service(
        project_id=scope[0].id,
        name=body.name,
        duration_minutes=body.duration_minutes,
        timezone=body.timezone,
        location=body.location,
    )
    db.add(service)
    db.flush()
    db.add(
        ServicePolicy(
            service_id=service.id, staff_id=staff.id, configuration=body.policy.model_dump_json()
        )
    )
    db.commit()
    return {"id": service.id, "name": service.name}


def scoped_service(db, service_id, project_id):
    service = db.scalar(
        select(Service).where(Service.id == service_id, Service.project_id == project_id)
    )
    if not service:
        raise HTTPException(404, "SERVICE_NOT_FOUND")
    return service


@router.get("/services/{service_id}/policy")
def get_policy(service_id: str, scope=Depends(project_scope), db=Depends(database)):
    service = scoped_service(db, service_id, scope[0].id)
    policy = db.get(ServicePolicy, service.id)
    return {
        "revision": policy.revision if policy else 0,
        "policy": json.loads(policy.configuration) if policy else None,
        "staff_id": policy.staff_id if policy else None,
    }


@router.put("/services/{service_id}/policy")
def update_policy(
    service_id: str, body: PolicyUpdate, scope=Depends(project_scope), db=Depends(database)
):
    require_writer(scope)
    service = scoped_service(db, service_id, scope[0].id)
    changed = db.execute(
        update(ServicePolicy)
        .where(ServicePolicy.service_id == service.id, ServicePolicy.revision == body.revision)
        .values(configuration=body.policy.model_dump_json(), revision=ServicePolicy.revision + 1)
        .returning(ServicePolicy.service_id)
    ).scalar_one_or_none()
    if not changed:
        raise HTTPException(409, "POLICY_CHANGED_OR_LEGACY_SERVICE")
    db.commit()
    return {"revision": body.revision + 1}


def local_timestamp(day, clock, zone):
    naive = datetime.fromisoformat(f"{day.isoformat()}T{clock}")
    first, second = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None  # Ambiguous/nonexistent DST times are skipped, never silently guessed.
    if first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
        return None
    return int(first.timestamp())


@router.post("/services/{service_id}/generate-slots")
def generate_slots(
    service_id: str, body: GenerateSlots, scope=Depends(project_scope), db=Depends(database)
):
    require_writer(scope)
    service = scoped_service(db, service_id, scope[0].id)
    policy = db.get(ServicePolicy, service.id)
    if not policy:
        raise HTTPException(409, "CREATE_A_MANAGED_SERVICE_FIRST")
    config, zone = Policy.model_validate_json(policy.configuration), ZoneInfo(service.timezone)
    today = datetime.now(zone).date()
    if body.start_date < today or body.start_date + timedelta(days=body.days) > today + timedelta(
        days=config.booking_window_days
    ):
        raise HTTPException(422, "SCHEDULE_OUTSIDE_BOOKING_WINDOW")
    existing = {
        s.start_at: s for s in db.scalars(select(Slot).where(Slot.service_id == service.id))
    }
    created, skipped, skipped_slots = 0, 0, 0
    for offset in range(body.days):
        day = body.start_date + timedelta(days=offset)
        if day in config.holidays:
            continue
        for start_clock, end_clock in config.opening_hours.get(str(day.weekday()), []):
            start, end = (
                local_timestamp(day, start_clock, zone),
                local_timestamp(day, end_clock, zone),
            )
            if start is None or end is None:
                skipped += 1
                continue
            at = start + config.buffer_before_minutes * 60
            while at + (service.duration_minutes + config.buffer_after_minutes) * 60 <= end:
                local_start = datetime.fromtimestamp(at, zone)
                local_end = datetime.fromtimestamp(at + service.duration_minutes * 60, zone)
                if (
                    local_timestamp(local_start.date(), local_start.strftime("%H:%M"), zone) is None
                    or local_timestamp(local_end.date(), local_end.strftime("%H:%M"), zone) is None
                ):
                    skipped_slots += 1
                    at += (
                        service.duration_minutes
                        + config.buffer_before_minutes
                        + config.buffer_after_minutes
                    ) * 60
                    continue
                if at > time.time() + config.lead_time_minutes * 60:
                    slot = existing.get(at)
                    if not slot:
                        slot = Slot(
                            service_id=service.id,
                            start_at=at,
                            end_at=at + service.duration_minutes * 60,
                        )
                        db.add(slot)
                        db.flush()
                        db.add(
                            SlotResource(
                                slot_id=slot.id,
                                staff_id=policy.staff_id,
                                policy_revision=policy.revision,
                            )
                        )
                        created += 1
                    else:
                        binding = db.get(SlotResource, slot.id)
                        if binding:
                            binding.policy_revision = policy.revision
                at += (
                    service.duration_minutes
                    + config.buffer_before_minutes
                    + config.buffer_after_minutes
                ) * 60
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "CONCURRENT_SCHEDULE_GENERATION_RETRY") from None
    return {
        "created": created,
        "skipped_dst_periods": skipped,
        "skipped_dst_slots": skipped_slots,
        "revision": policy.revision,
    }
