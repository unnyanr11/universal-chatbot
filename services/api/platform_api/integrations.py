"""Reviewed onboarding, constrained public sessions, installation checks and diagnostics."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urljoin, urlsplit

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from .context import assistant_scope, database, digest, identity, require_writer
from .database import (
    Assistant,
    AssistantIntegration,
    AssistantSettings,
    AssistantVersion,
    Document,
    IdentityNonce,
    IntegrationCounter,
    Job,
    Lead,
    Membership,
    Project,
    Session,
    User,
    VisitorIdentity,
    WebsiteReview,
    WidgetSession,
)
from .inference import ProviderUnavailable
from .management import Configuration, SaveConfiguration, audit, save_configuration, settings_record
from .providers import cipher, resolve_provider, seal
from .remote import RemoteError, read_page

router = APIRouter(prefix="/v1")
TEMPLATES = {
    "faq": {
        "name": "Business FAQ",
        "description": "Answers from your approved business information.",
        "welcome_message": "Hello! What would you like to know?",
        "suggested_questions": ["What services do you offer?", "What are your opening hours?"],
    },
    "leads": {
        "name": "Enquiry assistant",
        "description": "Help visitors understand the business and submit an enquiry with consent.",
        "welcome_message": "Tell us what you need. You can leave an enquiry for our team.",
        "suggested_questions": ["How can your team help me?", "How do I contact you?"],
    },
    "support": {
        "name": "Customer support",
        "description": "Grounded support with a human handoff when needed.",
        "welcome_message": "How can we help? Ask a question or request human support.",
        "suggested_questions": ["What are your support policies?", "How can I reach a person?"],
    },
    "appointments": {
        "name": "Appointment assistant",
        "description": "Find real availability and review details before confirming. Configure staff and services in Calendars.",
        "welcome_message": "Ask about our services or book an appointment. Booking requires verified identity.",
        "suggested_questions": ["Book an appointment", "What services are available?"],
    },
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IntegrationInput(Input):
    revision: int = Field(ge=0)
    enabled: bool
    lead_capture: bool = False
    support_enabled: bool = False
    bookings_enabled: bool = False
    daily_limit: int = Field(default=100, ge=1, le=10000)


def published(db, assistant_id):
    settings = db.get(AssistantSettings, assistant_id)
    version = (
        db.scalar(
            select(AssistantVersion).where(
                AssistantVersion.assistant_id == assistant_id,
                AssistantVersion.number == settings.published_version,
            )
        )
        if settings and settings.published_version
        else None
    )
    return json.loads(version.configuration)["configuration"] if version else None


def integration_record(db, assistant_id):
    row = db.get(AssistantIntegration, assistant_id)
    return {
        "revision": row.revision if row else 0,
        "enabled": bool(row and row.enabled),
        "lead_capture": bool(row and row.lead_capture),
        "support_enabled": bool(row and row.support_enabled),
        "bookings_enabled": bool(row and row.bookings_enabled),
        "daily_limit": row.daily_limit if row else 100,
        "has_identity_secret": bool(row and row.identity_secret),
        "published": published(db, assistant_id) is not None,
    }


def consume(db, assistant_id, kind, limit, bucket):
    key = f"{assistant_id}:{kind}:{bucket}"
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    count = db.execute(
        insert(IntegrationCounter)
        .values(key=key, total=1)
        .on_conflict_do_update(
            index_elements=[IntegrationCounter.key], set_={"total": IntegrationCounter.total + 1}
        )
        .returning(IntegrationCounter.total)
    ).scalar_one()
    if count > limit:
        db.commit()
        window = 86400 if kind in {"messages", "session-days"} else 60
        raise HTTPException(
            429,
            "PUBLIC_USAGE_LIMIT_REACHED",
            headers={"Retry-After": str(max(1, window - int(time.time()) % window))},
        )


@router.get("/assistant-templates")
def templates(session=Depends(identity)):
    return {"items": [{"id": key, **value} for key, value in TEMPLATES.items()]}


class TemplateInput(Input):
    template: str
    revision: int = Field(ge=0)


@router.post("/assistants/{assistant_id}/template")
def apply_template(
    body: TemplateInput,
    scope=Depends(assistant_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_writer(scope)
    if body.template not in TEMPLATES:
        raise HTTPException(422, "UNKNOWN_TEMPLATE")
    current = settings_record(db, scope[0])["configuration"]
    config = Configuration.model_validate({**current, **TEMPLATES[body.template]})
    return save_configuration(
        SaveConfiguration(revision=body.revision, configuration=config), scope, session, db
    )


@router.get("/assistants/{assistant_id}/integration")
def integration(scope=Depends(assistant_scope), db=Depends(database)):
    require_writer(scope)
    return integration_record(db, scope[0].id)


@router.put("/assistants/{assistant_id}/integration")
def configure(
    body: IntegrationInput,
    scope=Depends(assistant_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_writer(scope)
    row = db.get(AssistantIntegration, scope[0].id)
    if body.revision != (row.revision if row else 0):
        raise HTTPException(409, "INTEGRATION_CHANGED_REFRESH")
    if body.enabled and not published(db, scope[0].id):
        raise HTTPException(409, "PUBLISH_BEFORE_ENABLING_PUBLIC_CHAT")
    values = body.model_dump(exclude={"revision"})
    try:
        if row:
            changed = db.execute(
                update(AssistantIntegration)
                .where(
                    AssistantIntegration.assistant_id == scope[0].id,
                    AssistantIntegration.revision == body.revision,
                )
                .values(**values, revision=body.revision + 1)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "INTEGRATION_CHANGED_REFRESH")
        else:
            db.add(AssistantIntegration(assistant_id=scope[0].id, **values))
        audit(db, scope[0].project_id, session.user_id, "integration_configured", scope[0].id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "INTEGRATION_CHANGED_REFRESH") from None
    db.expire_all()
    return integration_record(db, scope[0].id)


@router.post("/assistants/{assistant_id}/identity-secret")
def rotate_identity(
    scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)
):
    if scope[1].role not in {"owner", "administrator"}:
        raise HTTPException(403, "IDENTITY_ADMIN_REQUIRED")
    row = db.get(AssistantIntegration, scope[0].id)
    if not row:
        raise HTTPException(409, "SAVE_INTEGRATION_FIRST")
    secret = secrets.token_urlsafe(32)
    try:
        row.identity_secret = seal(scope[0].id, secret)
    except ProviderUnavailable as exc:
        raise HTTPException(503, exc.code) from None
    row.revision += 1
    audit(db, scope[0].project_id, session.user_id, "identity_secret_rotated", scope[0].id)
    db.commit()
    return {"secret": secret, "revision": row.revision}


def verify_identity(db, row, token):
    try:
        payload, signature = token.split(".")
        secret_data = json.loads(cipher().decrypt(row.identity_secret.encode()))
        if secret_data["assistant_id"] != row.assistant_id:
            raise ValueError()
        expected = (
            base64.urlsafe_b64encode(
                hmac.digest(secret_data["key"].encode(), payload.encode(), "sha256")
            )
            .decode()
            .rstrip("=")
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if (
            claims["assistant_id"] != row.assistant_id
            or not isinstance(claims["sub"], str)
            or not 1 <= len(claims["sub"]) <= 200
            or type(claims["exp"]) is not int
            or not time.time() < claims["exp"] <= time.time() + 300
            or not isinstance(claims["nonce"], str)
            or not 16 <= len(claims["nonce"]) <= 100
        ):
            raise ValueError()
        db.add(IdentityNonce(digest=digest(token), expires_at=claims["exp"]))
        db.flush()
        return digest(claims["sub"])
    except (InvalidToken, ValueError, KeyError, TypeError, IntegrityError, ProviderUnavailable):
        db.rollback()
        raise HTTPException(401, "HOST_IDENTITY_INVALID_OR_REPLAYED") from None


class GuestInput(Input):
    identity_token: str = Field(default="", max_length=2000)


@router.post("/public/assistants/{assistant_id}/sessions", status_code=201)
def guest(assistant_id: str, body: GuestInput, db=Depends(database)):
    assistant = db.get(Assistant, assistant_id)
    row = db.get(AssistantIntegration, assistant_id)
    config = published(db, assistant_id)
    if not assistant or not row or not row.enabled or not config:
        raise HTTPException(404, "PUBLIC_ASSISTANT_UNAVAILABLE")
    consume(db, assistant_id, "sessions", 60, int(time.time()) // 60)
    consume(
        db, assistant_id, "session-days", max(100, row.daily_limit * 2), int(time.time()) // 86400
    )
    db.commit()
    subject = (
        verify_identity(db, row, body.identity_token)
        if body.identity_token and row.identity_secret
        else None
    )
    if body.identity_token and not subject:
        raise HTTPException(401, "HOST_IDENTITY_NOT_CONFIGURED")
    visitor = db.get(VisitorIdentity, (assistant_id, subject)) if subject else None
    if visitor:
        user_id = visitor.user_id
    else:
        from .app import passwords

        user = User(
            email=secrets.token_hex(24) + "@visitor.invalid",
            password_hash=passwords.hash(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.flush()
        project = db.get(Project, assistant.project_id)
        db.add(
            Membership(user_id=user.id, organization_id=project.organization_id, role="end_user")
        )
        if subject:
            db.add(
                VisitorIdentity(assistant_id=assistant_id, subject_digest=subject, user_id=user.id)
            )
        user_id = user.id
    token = secrets.token_urlsafe(32)
    session = Session(digest=digest(token), user_id=user_id)
    db.add(session)
    db.flush()
    db.add(
        WidgetSession(
            digest=session.digest,
            assistant_id=assistant_id,
            revision=row.revision,
            verified=bool(subject),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "IDENTITY_SESSION_RETRY_WITH_NEW_ASSERTION") from None
    return {
        "access_token": token,
        "project_id": assistant.project_id,
        "configuration": config,
        "lead_capture": row.lead_capture,
        "support_enabled": row.support_enabled,
        "bookings_enabled": row.bookings_enabled,
        "verified": bool(subject),
        "expires_at": session.expires_at,
    }


@router.get("/assistants/{assistant_id}/widget-info")
def widget_info(scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)):
    widget = db.get(WidgetSession, session.digest)
    preview_mode = bool(widget and widget.preview)
    config = db.get(AssistantIntegration, scope[0].id)
    return {
        "configuration": settings_record(db, scope[0])["configuration"]
        if preview_mode
        else published(db, scope[0].id),
        "preview": preview_mode,
        "project_id": scope[0].project_id,
        "verified": bool(widget and widget.verified),
        "lead_capture": bool(not preview_mode and config and config.lead_capture),
        "support_enabled": bool(not preview_mode and config and config.support_enabled),
        "bookings_enabled": bool(not preview_mode and config and config.bookings_enabled),
    }


@router.post("/assistants/{assistant_id}/preview")
def preview(scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)):
    require_writer(scope)
    token = secrets.token_urlsafe(32)
    from .app import passwords

    user = User(
        email=secrets.token_hex(24) + "@preview.invalid",
        password_hash=passwords.hash(secrets.token_urlsafe(32)),
    )
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=scope[1].organization_id, role="end_user"))
    record = Session(digest=digest(token), user_id=user.id, expires_at=int(time.time()) + 600)
    db.add(record)
    db.flush()
    db.add(WidgetSession(digest=record.digest, assistant_id=scope[0].id, revision=0, preview=True))
    db.commit()
    return {
        "access_token": token,
        "configuration": settings_record(db, scope[0])["configuration"],
        "project_id": scope[0].project_id,
    }


class URLInput(Input):
    url: str = Field(min_length=8, max_length=1000)


@router.post("/assistants/{assistant_id}/website-review", status_code=201)
def review(
    body: URLInput, scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)
):
    require_writer(scope)
    consume(db, scope[0].id, "imports", 10, int(time.time()) // 60)
    db.commit()
    try:
        page = read_page(body.url)
    except (RemoteError, ValueError):
        db.commit()
        raise HTTPException(422, "WEBSITE_FETCH_FAILED_USE_PUBLIC_HTTPS_HTML") from None
    row = WebsiteReview(
        assistant_id=scope[0].id,
        actor_id=session.user_id,
        url=page["url"],
        title=page["title"],
        text=page["text"],
        color=page["color"],
        font_family=page["font_family"],
        expires_at=int(time.time()) + 900,
    )
    db.add(row)
    db.commit()
    return {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "text": row.text,
        "color": row.color,
        "font_family": row.font_family,
    }


class AcceptInput(Input):
    review_id: str
    accepted: bool


@router.post("/assistants/{assistant_id}/website-import", status_code=202)
def accept(
    body: AcceptInput,
    scope=Depends(assistant_scope),
    session=Depends(identity),
    db=Depends(database),
):
    require_writer(scope)
    row = db.get(WebsiteReview, body.review_id)
    if (
        not body.accepted
        or not row
        or row.assistant_id != scope[0].id
        or row.actor_id != session.user_id
        or row.expires_at <= time.time()
    ):
        raise HTTPException(409, "REVIEW_REQUIRED_OR_EXPIRED")
    data = (row.text + "\n\nSource URL: " + row.url).encode()
    content_hash = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(Document).where(
            Document.assistant_id == scope[0].id, Document.content_hash == content_hash
        )
    )
    if existing:
        return {"id": existing.id, "status": existing.status}
    document = Document(
        assistant_id=scope[0].id,
        title=row.title,
        content=data,
        content_hash=content_hash,
        kind="txt",
    )
    db.add(document)
    db.flush()
    db.add(Job(document_id=document.id))
    db.delete(row)
    audit(db, scope[0].project_id, session.user_id, "website_import_approved", document.id)
    db.commit()
    return {"id": document.id, "status": document.status}


class CheckInput(URLInput):
    app_origin: str = Field(max_length=500)


@router.post("/assistants/{assistant_id}/installation-check")
def installation(body: CheckInput, scope=Depends(assistant_scope), db=Depends(database)):
    require_writer(scope)
    try:
        page = read_page(body.url)
    except (RemoteError, ValueError):
        raise HTTPException(422, "INSTALLATION_PAGE_NOT_READABLE") from None
    origin = body.app_origin.rstrip("/")
    detected = any(
        urlsplit(urljoin(page["url"], script.get("src", "")))
        ._replace(query="", fragment="")
        .geturl()
        == origin + "/widget-loader.js"
        and script.get("data-assistant") == scope[0].id
        and script.get("data-public") == "1"
        for script in page["scripts"]
    )
    config = published(db, scope[0].id) or {}
    host = urlsplit(body.url).netloc
    allowed = host in config.get("allowed_domains", [])
    record = integration_record(db, scope[0].id)
    return {
        "script_detected": detected,
        "domain_allowed": allowed,
        "public_enabled": record["enabled"],
        "published": record["published"],
        "ready": detected and allowed and record["enabled"] and record["published"],
        "note": "Static HTML check. Open the host page and test chat to verify runtime CSP, JavaScript and dynamic installation.",
    }


class LeadInput(Input):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    message: str = Field(min_length=1, max_length=2000)
    consent: bool


@router.post("/assistants/{assistant_id}/leads", status_code=201)
def create_lead(
    body: LeadInput, scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)
):
    config = db.get(AssistantIntegration, scope[0].id)
    if not body.consent or not config or not config.enabled or not config.lead_capture:
        raise HTTPException(422, "LEAD_CAPTURE_UNAVAILABLE_OR_CONSENT_REQUIRED")
    consume(db, scope[0].id, "leads", 20, int(time.time()) // 60)
    row = Lead(
        assistant_id=scope[0].id,
        user_id=session.user_id,
        name=body.name,
        email=body.email,
        message=body.message,
    )
    db.add(row)
    db.flush()
    from .webhooks import enqueue

    enqueue(
        db, scope[0].project_id, "lead.created", {"lead_id": row.id, "assistant_id": scope[0].id}
    )
    db.commit()
    return {"id": row.id, "status": "received"}


@router.get("/assistants/{assistant_id}/leads")
def leads(scope=Depends(assistant_scope), db=Depends(database)):
    require_writer(scope)
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "email": row.email,
                "message": row.message,
                "created_at": row.created_at,
            }
            for row in db.scalars(
                select(Lead)
                .where(Lead.assistant_id == scope[0].id)
                .order_by(Lead.created_at.desc())
                .limit(100)
            )
        ]
    }


@router.get("/assistants/{assistant_id}/diagnostics")
async def diagnostics(request: Request, scope=Depends(assistant_scope), db=Depends(database)):
    require_writer(scope)
    documents = list(db.scalars(select(Document).where(Document.assistant_id == scope[0].id)))
    try:
        provider = await resolve_provider(request, db, scope[0].id).check()
    except ProviderUnavailable:
        provider = {
            "status": "unavailable",
            "reason": "Check provider settings and server encryption key",
        }
    config = integration_record(db, scope[0].id)
    return {
        "provider": provider,
        "documents": {
            state: sum(row.status == state for row in documents)
            for state in {"ready", "queued", "failed"}
        },
        "issues": [
            {
                "title": row.title,
                "fix": row.error
                or "Keep the worker running; delete and re-upload failed documents.",
            }
            for row in documents
            if row.status != "ready" or row.error
        ],
        "integration": config,
        "cloud_test_note": "Configured cloud credentials are not live-verified. Use Test saved provider; charges may apply.",
        "next_steps": [
            "Add approved information",
            "Wait for ready documents",
            "Save and publish content",
            "Enable public chat and set a daily limit",
            "Allow your website domain in Settings and publish again",
            "Copy embed code and run installation check",
        ],
    }


@router.get("/downloads/wordpress")
def wordpress_download():
    import io
    import os
    import zipfile
    from pathlib import Path

    from fastapi.responses import Response

    root = (
        Path(
            os.getenv(
                "INTEGRATION_PACKAGES_DIR", str(Path(__file__).resolve().parents[3] / "packages")
            )
        )
        / "wordpress"
        / "universal-chatbot"
    )
    if not root.is_dir():
        raise HTTPException(404, "PLUGIN_PACKAGE_NOT_INSTALLED")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.glob("*")):
            if path.is_file():
                archive.write(path, "universal-chatbot/" + path.name)
    return Response(
        output.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="universal-chatbot-wordpress.zip"'},
    )


@router.delete("/assistants/{assistant_id}/leads/{lead_id}", status_code=204)
def delete_lead(
    lead_id: str, scope=Depends(assistant_scope), session=Depends(identity), db=Depends(database)
):
    require_writer(scope)
    row = db.get(Lead, lead_id)
    if not row or row.assistant_id != scope[0].id:
        raise HTTPException(404, "LEAD_NOT_FOUND")
    db.delete(row)
    audit(db, scope[0].project_id, session.user_id, "lead_deleted", lead_id)
    db.commit()
