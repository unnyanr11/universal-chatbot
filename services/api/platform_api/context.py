"""Shared authentication and tenant checks used by every feature router."""

import hashlib
import re
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import Assistant, AssistantIntegration, Membership, Project, Session, WidgetSession

bearer = HTTPBearer(auto_error=False)
WRITERS = {"owner", "administrator", "developer"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def database(request: Request):
    with request.app.state.sessions() as db:
        yield db


def identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(database),
):
    if not credentials:
        raise HTTPException(401, "AUTHENTICATION_REQUIRED")
    session = db.get(Session, digest(credentials.credentials))
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, "SESSION_INVALID")
    widget = db.get(WidgetSession, session.digest)
    if widget:
        assistant = db.get(Assistant, widget.assistant_id)
        config = db.get(AssistantIntegration, widget.assistant_id)
        if not assistant or (
            not widget.preview
            and (not config or not config.enabled or config.revision != widget.revision)
        ):
            raise HTTPException(401, "WIDGET_SESSION_REVOKED")
        suffix = request.url.path.removeprefix(f"/v1/assistants/{assistant.id}")
        allowed = request.url.path.startswith(f"/v1/assistants/{assistant.id}/") and (
            suffix in {"/chat", "/widget-info", "/provider/status"}
            or re.fullmatch(r"/conversations(?:/[^/]+)?", suffix)
            or (suffix == "/leads" and request.method == "POST" and not widget.preview)
        )
        project_prefix = f"/v1/projects/{assistant.project_id}"
        project_suffix = request.url.path.removeprefix(project_prefix)
        if not widget.preview and request.url.path.startswith(project_prefix + "/"):
            allowed = allowed or (
                request.method == "GET"
                and bool(re.fullmatch(r"/services(?:/[^/]+/slots)?", project_suffix))
            )
            allowed = allowed or (
                widget.verified
                and config.bookings_enabled
                and bool(
                    re.fullmatch(
                        r"/(?:operations(?:/[^/]+(?:/confirm)?)?|bookings|chat-actions/[^/]+(?:/propose)?)",
                        project_suffix,
                    )
                )
            )
        if (
            not widget.preview
            and config.support_enabled
            and request.url.path.startswith(project_prefix + "/")
        ):
            allowed = allowed or bool(re.fullmatch(r"/tickets(?:/[^/]+)?", project_suffix))
        if not allowed:
            raise HTTPException(403, "WIDGET_SCOPE_ONLY")
        if suffix == "/chat" and request.method == "POST" and not widget.preview:
            from .integrations import consume

            consume(db, assistant.id, "messages", config.daily_limit, int(time.time()) // 86400)
            db.commit()
    return session


def project_scope(project_id: str, session=Depends(identity), db=Depends(database)):
    project = db.get(Project, project_id)
    member = db.get(Membership, (session.user_id, project.organization_id)) if project else None
    if not member:
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    return project, member


def assistant_scope(assistant_id: str, session=Depends(identity), db=Depends(database)):
    assistant = db.get(Assistant, assistant_id)
    project = db.get(Project, assistant.project_id) if assistant else None
    member = db.get(Membership, (session.user_id, project.organization_id)) if project else None
    if not member:
        raise HTTPException(404, "ASSISTANT_NOT_FOUND")
    return assistant, member


def require_writer(scope):
    if scope[1].role not in WRITERS:
        raise HTTPException(403, "ROLE_FORBIDDEN")


def widget_active(db, session_digest, assistant_id):
    widget = db.get(WidgetSession, session_digest)
    if not widget:
        return True
    if widget.assistant_id != assistant_id:
        return False
    if widget.preview:
        return True
    config = db.get(AssistantIntegration, assistant_id)
    return bool(config and config.enabled and config.revision == widget.revision)
