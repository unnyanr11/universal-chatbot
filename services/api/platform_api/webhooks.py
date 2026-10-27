"""Signed, durable, at-least-once event delivery to explicitly approved destinations."""

import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select, update

from .context import database, identity, project_scope
from .database import WebhookDelivery, WebhookEndpoint
from .inference import ProviderUnavailable
from .management import audit
from .providers import open_secret, seal
from .remote import RemoteError, fetch

router = APIRouter(prefix="/v1/projects/{project_id}")


def approved_urls():
    return {url.strip() for url in os.getenv("WEBHOOK_ALLOWED_URLS", "").split(",") if url.strip()}


def enqueue(db, project_id, event, payload):
    for endpoint in db.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.project_id == project_id, WebhookEndpoint.enabled.is_(True)
        )
    ):
        db.add(
            WebhookDelivery(
                endpoint_id=endpoint.id, event=event, payload=json.dumps(payload, sort_keys=True)
            )
        )


def manager(scope):
    if scope[1].role not in {"owner", "administrator"}:
        raise HTTPException(403, "WEBHOOK_ADMIN_REQUIRED")


class EndpointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(max_length=1000)


@router.get("/webhooks")
def endpoints(scope=Depends(project_scope), db=Depends(database)):
    manager(scope)
    rows = list(
        db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.project_id == scope[0].id))
    )
    return {
        "approved_urls": sorted(approved_urls()),
        "items": [
            {
                "id": row.id,
                "url": row.url,
                "enabled": row.enabled,
                "deliveries": [
                    {
                        "id": delivery.id,
                        "event": delivery.event,
                        "state": delivery.state,
                        "attempts": delivery.attempts,
                        "error": delivery.error,
                    }
                    for delivery in db.scalars(
                        select(WebhookDelivery)
                        .where(WebhookDelivery.endpoint_id == row.id)
                        .order_by(WebhookDelivery.due_at.desc())
                        .limit(20)
                    )
                ],
            }
            for row in rows
        ],
    }


@router.post("/webhooks", status_code=201)
def create(
    body: EndpointInput,
    scope=Depends(project_scope),
    session=Depends(identity),
    db=Depends(database),
):
    manager(scope)
    if body.url not in approved_urls() or not body.url.startswith("https://"):
        raise HTTPException(422, "WEBHOOK_URL_NOT_APPROVED")
    if (
        len(
            list(
                db.scalars(
                    select(WebhookEndpoint.id).where(WebhookEndpoint.project_id == scope[0].id)
                )
            )
        )
        >= 5
    ):
        raise HTTPException(409, "WEBHOOK_LIMIT_REACHED")
    secret = secrets.token_urlsafe(32)
    endpoint = WebhookEndpoint(project_id=scope[0].id, url=body.url, secret="")
    db.add(endpoint)
    db.flush()
    try:
        endpoint.secret = seal(endpoint.id, secret)
    except ProviderUnavailable:
        db.rollback()
        raise HTTPException(503, "WEBHOOK_ENCRYPTION_KEY_UNAVAILABLE") from None
    audit(db, scope[0].id, session.user_id, "webhook_created", endpoint.id)
    db.commit()
    return {"id": endpoint.id, "secret": secret}


@router.delete("/webhooks/{endpoint_id}", status_code=204)
def disable(
    endpoint_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    manager(scope)
    endpoint = db.get(WebhookEndpoint, endpoint_id)
    if not endpoint or endpoint.project_id != scope[0].id:
        raise HTTPException(404, "WEBHOOK_NOT_FOUND")
    endpoint.enabled = False
    endpoint.secret = ""
    db.execute(
        update(WebhookDelivery)
        .where(
            WebhookDelivery.endpoint_id == endpoint.id,
            WebhookDelivery.state.in_(["pending", "sending"]),
        )
        .values(state="cancelled")
    )
    audit(db, scope[0].id, session.user_id, "webhook_disabled", endpoint.id)
    db.commit()


def deliver_once(sessions):
    now, token = int(time.time()), secrets.token_hex(16)
    with sessions.begin() as db:
        db.execute(
            update(WebhookDelivery)
            .where(
                WebhookDelivery.state == "sending",
                WebhookDelivery.lease_until < now,
                WebhookDelivery.attempts >= 5,
            )
            .values(state="failed", error="WEBHOOK_RETRY_BUDGET_EXHAUSTED")
        )
        ready = or_(
            and_(WebhookDelivery.state == "pending", WebhookDelivery.due_at <= now),
            and_(WebhookDelivery.state == "sending", WebhookDelivery.lease_until < now),
        )
        candidate = db.scalar(
            select(WebhookDelivery.id)
            .where(ready, WebhookDelivery.attempts < 5)
            .order_by(WebhookDelivery.due_at)
            .limit(1)
        )
        if not candidate:
            return False
        claimed = db.execute(
            update(WebhookDelivery)
            .where(WebhookDelivery.id == candidate, ready)
            .values(
                state="sending",
                attempts=WebhookDelivery.attempts + 1,
                lease_token=token,
                lease_until=now + 60,
            )
            .returning(WebhookDelivery.id)
        ).scalar_one_or_none()
        if not claimed:
            return False
    error = ""
    with sessions() as db:
        row = db.get(WebhookDelivery, claimed)
        endpoint = db.get(WebhookEndpoint, row.endpoint_id)
        if not endpoint or not endpoint.enabled or endpoint.url not in approved_urls():
            error = "WEBHOOK_DISABLED_OR_NOT_APPROVED"
        else:
            try:
                secret = open_secret(endpoint.id, endpoint.secret)
                data = json.dumps(
                    {"id": row.id, "type": row.event, "data": json.loads(row.payload)},
                    separators=(",", ":"),
                ).encode()
                timestamp = str(int(time.time()))
                signature = hmac.new(
                    secret.encode(), timestamp.encode() + b"." + data, hashlib.sha256
                ).hexdigest()
                status, _, _, _ = fetch(
                    endpoint.url,
                    method="POST",
                    body=data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Assistant-Event": row.id,
                        "X-Assistant-Timestamp": timestamp,
                        "X-Assistant-Signature": "sha256=" + signature,
                    },
                )
                if not 200 <= status < 300:
                    error = "WEBHOOK_HTTP_FAILURE"
            except (RemoteError, ValueError, RuntimeError):
                error = "WEBHOOK_DELIVERY_FAILED"
            except ProviderUnavailable:
                error = "WEBHOOK_SECRET_UNAVAILABLE"
    with sessions.begin() as db:
        row = db.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.id == claimed,
                WebhookDelivery.lease_token == token,
                WebhookDelivery.state == "sending",
            )
        )
        if row:
            row.error = error
            row.state = ("failed" if row.attempts >= 5 else "pending") if error else "sent"
            row.due_at = int(time.time()) + min(3600, 30 * 2**row.attempts)
    return True
