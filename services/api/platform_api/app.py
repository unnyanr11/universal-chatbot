"""Phase 0 API: opaque revocable sessions and membership-derived authorization."""

import hashlib
import os
import secrets
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import Assistant, LoginWindow, Membership, Project, Session, User, connect
from .inference import OllamaProvider, ProviderUnavailable

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
WRITERS = {"owner", "administrator", "developer"}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class NewAssistant(Input):
    name: str = Field(min_length=1, max_length=100)
    welcome_message: str = Field(default="How can I help?", max_length=1000)


class Prompt(Input):
    text: str = Field(min_length=1, max_length=4000)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_app(database_url=None, provider=None):
    app = FastAPI(title="Universal Assistant — Foundation", version="0.1.0")
    engine, sessions = connect(
        database_url or os.getenv("DATABASE_URL", "sqlite:///./assistant.db")
    )
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.provider = provider or OllamaProvider(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), os.getenv("OLLAMA_MODEL", "")
    )

    @app.middleware("http")
    async def metadata(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def api_error(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": str(exc.detail), "request_id": request.state.request_id}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Do not echo submitted passwords or other raw inputs in validation errors.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_INPUT",
                    "request_id": request.state.request_id,
                    "fields": [".".join(map(str, error["loc"])) for error in exc.errors()],
                }
            },
        )

    def database():
        with sessions() as db:
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
        membership = (
            db.get(Membership, (session.user_id, project.organization_id)) if project else None
        )
        if not membership:
            raise HTTPException(404, "PROJECT_NOT_FOUND")
        return project, membership

    @app.get("/health")
    def health():
        return {"status": "alive", "milestone": "phase-0-partial"}

    @app.post("/v1/sessions", status_code=201)
    def login(body: Login, db=Depends(database)):
        # Global DB-backed minute budget also bounds arbitrary-identity guessing.
        key = f"login:{int(time.time()) // 60}"
        insert = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
        attempt = insert(LoginWindow).values(key=key, attempts=1)
        count = db.execute(
            attempt.on_conflict_do_update(
                index_elements=[LoginWindow.key], set_={"attempts": LoginWindow.attempts + 1}
            ).returning(LoginWindow.attempts)
        ).scalar_one()
        db.execute(
            delete(LoginWindow).where(LoginWindow.key < f"login:{int(time.time()) // 60 - 2}")
        )
        db.commit()
        if count > 20:
            raise HTTPException(429, "LOGIN_RATE_LIMITED", headers={"Retry-After": "60"})
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        valid = passwords.verify(body.password, user.password_hash if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, "INVALID_CREDENTIALS")
        token = secrets.token_urlsafe(32)
        session = Session(digest=digest(token), user_id=user.id)
        db.add(session)
        db.commit()
        return {"access_token": token, "token_type": "bearer", "expires_at": session.expires_at}

    @app.delete("/v1/sessions/current", status_code=204)
    def logout(session=Depends(identity), db=Depends(database)):
        db.delete(session)
        db.commit()

    @app.get("/v1/projects")
    def projects(session=Depends(identity), db=Depends(database)):
        rows = db.scalars(
            select(Project)
            .join(Membership, Membership.organization_id == Project.organization_id)
            .where(Membership.user_id == session.user_id)
            .order_by(Project.id)
            .limit(100)
        )
        return {"items": [{"id": p.id, "name": p.name, "environment": p.environment} for p in rows]}

    @app.get("/v1/projects/{project_id}/assistants")
    def assistants(scope=Depends(project_scope), db=Depends(database)):
        rows = db.scalars(
            select(Assistant)
            .where(Assistant.project_id == scope[0].id)
            .order_by(Assistant.id)
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": a.id,
                    "name": a.name,
                    "status": a.status,
                    "welcome_message": a.welcome_message,
                    "version": a.version,
                }
                for a in rows
            ]
        }

    @app.post("/v1/projects/{project_id}/assistants", status_code=201)
    def create_assistant(body: NewAssistant, scope=Depends(project_scope), db=Depends(database)):
        if scope[1].role not in WRITERS:
            raise HTTPException(403, "ROLE_FORBIDDEN")
        assistant = Assistant(project_id=scope[0].id, **body.model_dump())
        db.add(assistant)
        db.commit()
        return {"id": assistant.id, "name": assistant.name, "status": assistant.status}

    @app.get("/v1/provider")
    async def provider_status(session=Depends(identity)):
        return await app.state.provider.check()

    @app.post("/v1/projects/{project_id}/inference-check")
    async def inference_check(body: Prompt, scope=Depends(project_scope)):
        if scope[1].role not in WRITERS:
            raise HTTPException(403, "ROLE_FORBIDDEN")
        try:
            answer = await app.state.provider.complete(body.text)
            return {"text": answer, "mode": "ungrounded-model-diagnostic"}
        except ProviderUnavailable:
            raise HTTPException(503, "LOCAL_INFERENCE_UNAVAILABLE") from None

    return app
