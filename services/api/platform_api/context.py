"""Shared authentication and tenant checks used by every feature router."""

import hashlib
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import Assistant, Membership, Project, Session

bearer = HTTPBearer(auto_error=False)
WRITERS = {"owner", "administrator", "developer"}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def database(request: Request):
    with request.app.state.sessions() as db:
        yield db


def identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(database)
):
    if not credentials:
        raise HTTPException(401, "AUTHENTICATION_REQUIRED")
    session = db.get(Session, digest(credentials.credentials))
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, "SESSION_INVALID")
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
